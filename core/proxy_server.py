from socket import AddressFamily

import psutil
import aioredis
from aiohttp import web
import aiohttp_cors

import log_utils
from core.dashboard import dashboard
from core.forwarder import forward
from core.saver import Saver
from core.crawler import crawl, init_session
from models.pattern import Checker, PatternManager
from models.proxy import ProxyManager

logger = log_utils.LogHandler('server', file=True)


async def _get_self_ips():
    ips = ['localhost']
    addresses = psutil.net_if_addrs()
    for _, i in addresses.items():
        for f in i:
            if f.family == AddressFamily.AF_INET:
                ips.append(f.address)
    res = await crawl('GET', 'http://httpbin.org/ip')
    d = await res.json()
    ips.append(d['origin'])
    return ips


class ProxyServer(web.Application):

    def __init__(self, config):
        super(ProxyServer, self).__init__()
        self.cleanup_ctx.append(self.core_session)
        self._config = config
        cors = aiohttp_cors.setup(self, defaults={
            config.dashboard_addr: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",)
        })
        resource = cors.add(self.router.add_resource('/{path:.*}'))
        cors.add(resource.add_route("GET", self.receive_request))
        cors.add(resource.add_route("POST", self.receive_request))
        cors.add(resource.add_route("DELETE", self.receive_request))

    async def core_session(self, app):
        app['ips'] = await _get_self_ips()
        app['config'] = self._config
        app['redis'] = await aioredis.create_redis_pool(app['config'].redis_addr,
                                                        password=app['config'].redis_password,
                                                        encoding='utf8')
        checker = Checker(global_blacklist=app['config'].global_blacklist)
        saver = Saver(app['redis'])
        proxy_manager = ProxyManager(
            config=app['config'],
            redis=app['redis']
        )
        pattern_manager = PatternManager(checker, saver, app['redis'])

        await pattern_manager.__aenter__()
        await proxy_manager.__aenter__()
        app['pom'] = proxy_manager
        app['pam'] = pattern_manager
        app['ck'] = checker
        app['sv'] = saver
        app['client_session'] = init_session()
        yield
        await app['pam'].__aexit__(None, None, None)
        await app['pom'].__aexit__(None, None, None)
        await app['client_session'].close()
        await app['redis'].close()

    async def receive_request(self, request):
        if request.url.host in request.app['ips']:
            return await dashboard(request)
        else:
            return await self.forward_request(request)

    async def forward_request(self, request):
        logger.info('received request {} from {}'.format(request.url, request.remote))
        body = await request.content.read()
        return await forward(request.method, str(request.url), request.app['pam'], request.app['pom'],
                             headers=request.headers, body=body, mode=request.app['config'].mode,
                             session=request.app['client_session'])
