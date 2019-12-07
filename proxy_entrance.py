import asyncio
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from aiohttp import web

from core import proxy_server
from config import conf


def run_server(port=None):
    app = proxy_server.ProxyServer(conf)
    web.run_app(app, port=port)


if __name__ == '__main__':
    run_server(8893)
