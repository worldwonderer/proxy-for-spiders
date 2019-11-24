import asyncio
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from aiohttp import web

from core import proxy
from models.proxy import ProxyManager
from models.pattern import PatternManager
from models.saver import Saver
from models.pattern import Checker


proxy_manager = ProxyManager()
pattern_manager = PatternManager()
saver = Saver()
checker = Checker()


def run_server(port=None):
    app = proxy.ProxyServer()
    web.run_app(app, port=port)


if __name__ == '__main__':
    run_server(8893)
