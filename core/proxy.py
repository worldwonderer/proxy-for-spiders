from aiohttp import web
from multidict import CIMultiDict

from utils import log_utils
from core.forwarder import forward
from models.pattern import Checker
from models.saver import Saver
from proxy_entrance import proxy_manager, pattern_manager


logger = log_utils.LogHandler('server', file=True)


class ProxyServer(web.Application):

    def __init__(self):
        super(ProxyServer, self).__init__()
        self.cleanup_ctx.append(self.core_session)
        self.add_routes([web.get('/{path:.*}', self.receive_request)])
        self.add_routes([web.post('/{path:.*}', self.receive_request)])

    @staticmethod
    async def core_session(app):
        checker = Checker()
        saver = Saver()
        await saver.__aenter__()
        await proxy_manager.__aenter__()
        await pattern_manager.__aenter__()
        app['pom'] = proxy_manager
        app['pam'] = pattern_manager
        app['ck'] = checker
        app['sv'] = saver
        yield
        await app['pam'].__aexit__()
        await app['pom'].__aexit__()
        await app['sv'].__aexit__()

    @staticmethod
    def _gen_headers(r):
        res_headers = CIMultiDict()
        if 'Set-Cookie' in r.headers:
            for cookie in r.headers.getall('Set-Cookie'):
                res_headers.add('Set-Cookie', cookie)
        res_headers['Via-Proxy'] = str(r.proxy)
        return res_headers

    async def receive_request(self, request):
        pam = request.app['pam']
        pom = request.app['pom']
        ck = request.app['ck']
        sv = request.app['sv']

        body = await request.content.read()
        logger.info('received request {} from {}'.format(request.url, request.remote))

        r = await forward(request.method, str(request.url), pam, pom, ck, sv, headers=request.headers, body=body)
        if r.traceback is not None:
            if isinstance(r.traceback, list):
                tb = ''.join(r.traceback)
            else:
                tb = r.traceback
            return web.Response(status=417, text=tb)
        else:
            text = await r.text()
            return web.Response(status=r.status, text=text, headers=self._gen_headers(r))
