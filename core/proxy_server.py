from socket import AddressFamily

import psutil
from aiohttp import web
from multidict import CIMultiDict

import log_utils
from core.forwarder import forward
from core.saver import Saver
from models.pattern import Checker, PatternManager
from models.proxy import ProxyManager


logger = log_utils.LogHandler('server', file=True)


class ProxyServer(web.Application):

    dashboard_data_template = {
        'code': 20000,
        'data': {
            'items': [],
            'total': 0
        }
    }

    def __init__(self, config):
        super(ProxyServer, self).__init__()
        self.ips = self._get_self_ips()
        self.cleanup_ctx.append(self.core_session)
        self.add_routes([web.get('/{path:.*}', self.receive_request)])
        self.add_routes([web.post('/{path:.*}', self.receive_request)])
        self._config = config

    async def core_session(self, app):
        checker = Checker(global_blacklist=self._config.global_blacklist)
        saver = Saver(redis_addr=self._config.redis_addr)
        proxy_manager = ProxyManager(redis_addr=self._config.redis_addr)
        pattern_manager = PatternManager(redis_addr=self._config.redis_addr)
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
            return await self.dashboard(request)
        else:
            return await self.forward_request(request)

    async def forward_request(self, request):
        pam = request.app['pam']
        pom = request.app['pom']
        ck = request.app['ck']
        sv = request.app['sv']

        body = await request.content.read()
        logger.info('received request {} from {}'.format(request.url, request.remote))

        r = await forward(request.method, str(request.url), pam, pom, ck, sv, headers=request.headers, body=body)

        if r is None:
            return web.Response(status=417, text='unable to get any response')
        elif r.traceback:
            tb = ''.join(r.traceback)
            return web.Response(status=417, text=tb)
        else:
            text = await r.text()
            return web.Response(status=r.status, text=text, headers=self._gen_headers(r))

    async def patterns(self, request):
        r = self.dashboard_data_template.copy()
        items = await request.app['pam'].patterns()
        r['data']['items'] = items
        r['data']['total'] = len(items)
        return web.json_response(data=r)

    async def proxies(self, request):
        r = self.dashboard_data_template.copy()
        items = await request.app['pom'].proxies(format_type='dict')
        r['data']['items'] = items
        r['data']['total'] = len(items)
        return web.json_response(data=r)

    async def login(self, request):
        return web.json_response(data={'code': 20000, 'data': 'admin'})

    async def user_info(self, request):
        data = {
            'roles': ['admin'],
            'introduction': 'I am a super administrator',
            'avatar': 'https://wpimg.wallstcn.com/f778738c-e4f8-4870-b634-56703b4acafe.gif',
            'name': 'Super Admin'
        }
        return web.json_response(data={'code': 20000, 'data': data})

    async def dashboard(self, request):
        path = request.path
        if path == '/dev-api/patterns':
            return await self.patterns(request)
        elif path == '/dev-api/proxies':
            return await self.proxies(request)
        elif path == '/dev-api/user/login':
            return await self.login(request)
        elif path == '/dev-api/user/info':
            return await self.user_info(request)
        return web.Response(status=200, text="hello world")
