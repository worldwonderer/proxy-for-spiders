from socket import AddressFamily

import psutil
from aiohttp import web
from multidict import CIMultiDict

import log_utils
from core.forwarder import forward
from core.saver import Saver
from core.dashboard import dashboard
from models.pattern import Checker, PatternManager
from models.proxy import ProxyManager


logger = log_utils.LogHandler('server', file=True)


class ProxyServer(web.Application):

    def __init__(self, config):
        super(ProxyServer, self).__init__()
        self.ips = self._get_self_ips()
        self.cleanup_ctx.append(self.core_session)
        self.add_routes([web.get('/{path:.*}', self.receive_request)])
        self.add_routes([web.post('/{path:.*}', self.receive_request)])
        self.add_routes([web.delete('/{path:.*}', self.receive_request)])
        self._config = config

    async def core_session(self, app):
        checker = Checker(global_blacklist=self._config.global_blacklist)
        saver = Saver(redis_addr=self._config.redis_addr,
                      password=self._config.redis_password)
        proxy_manager = ProxyManager(
            request_concurrent=self._config.request_concurrent,
            redis_addr=self._config.redis_addr,
            password=self._config.redis_password
        )
        pattern_manager = PatternManager(checker, saver, redis_addr=self._config.redis_addr,
                                         password=self._config.redis_password)
        await saver.__aenter__()
        await proxy_manager.__aenter__()
        await pattern_manager.__aenter__()
        await proxy_manager.add_proxies_for_pattern('public_proxies')
        app['pom'] = proxy_manager
        app['pam'] = pattern_manager
        app['ck'] = checker
        app['sv'] = saver
        yield
        await app['pam'].__aexit__(None, None, None)
        await app['pom'].__aexit__(None, None, None)
        await app['sv'].__aexit__(None, None, None)

    @staticmethod
    def _gen_headers(r):
        res_headers = CIMultiDict()
        if 'Set-Cookie' in r.headers:
            for cookie in r.headers.getall('Set-Cookie'):
                res_headers.add('Set-Cookie', cookie)
        res_headers['Via-Proxy'] = str(r.proxy)
        return res_headers

    @staticmethod
    def _get_self_ips():
        ips = ['localhost']
        addresses = psutil.net_if_addrs()
        for _, i in addresses.items():
            for f in i:
                if f.family == AddressFamily.AF_INET:
                    ips.append(f.address)
        return ips

    async def receive_request(self, request):
        if request.url.host in self.ips:
            return await dashboard(request)
        else:
            return await self.forward_request(request)

    async def forward_request(self, request):
        pam = request.app['pam']
        pom = request.app['pom']

        body = await request.content.read()
        logger.info('received request {} from {}'.format(request.url, request.remote))

        r = await forward(request.method, str(request.url), pam, pom, headers=request.headers, body=body,
                          style=self._config.style)

        if r is None:
            logger.warning("unable to get any valid response for {}".format(request.url))
            return web.Response(status=417, text='unable to get any response')
        elif r.traceback:
            tb = ''.join(r.traceback)
            logger.warning("unable to get any valid response for {}".format(request.url))
            return web.Response(status=417, text=tb)
        else:
            text = await r.text()
            logger.info("get valid response for {} via proxy {}".format(request.url, r.proxy))
            return web.Response(status=r.status, text=text, headers=self._gen_headers(r))
