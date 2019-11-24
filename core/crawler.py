import sys
import asyncio
import traceback

import aiohttp

from utils import log_utils
from models.response import Response, FailedResponse


logger = log_utils.LogHandler(__name__, file=True)


async def async_crawl(method, url, session, **kwargs):
    proxy = kwargs.get('proxy')
    kwargs.update({'ssl': False, 'timeout': 10})
    try:
        async with session.request(method, url, **kwargs) as r:
            r.proxy = proxy
            await r.read()
            r.__class__ = Response
    except Exception as e:
        r = FailedResponse()
        r.traceback = traceback.format_exception(*sys.exc_info())
        logger.warning(e, exc_info=True)
    return r


async def async_crawl_and_check(method, url, session, pattern, **kwargs):
    r = await async_crawl(method, url, session, **kwargs)
    r.traceback = await pattern.check(r)
    r.valid = True if r.traceback is None else False
    await pattern.score_and_save(kwargs['proxy'], r)
    return r


async def crawl(method, url, proxies=None, **kwargs):
    if proxies is None:
        proxies = list()
    if len(proxies) == 0:
        proxies.append(None)

    pattern = kwargs.pop('pattern', None)
    session = kwargs.get('session')

    need_close_session = False
    if session is None:
        need_close_session = True
        session = aiohttp.ClientSession()

    r = None
    need_check = all((any(proxies), pattern))
    try:
        if need_check:
            tasks = [asyncio.ensure_future(async_crawl_and_check(method, url, session, pattern,
                                                                 proxy=proxy, **kwargs)) for proxy in proxies]
        else:
            tasks = [asyncio.ensure_future(async_crawl(method, url, session, proxy=proxy, **kwargs))
                     for proxy in proxies]
        for task in asyncio.as_completed(tasks):
            try:
                r = await task
            except asyncio.CancelledError:
                continue
            if (need_check and r.valid) or not need_check:
                for t in tasks:
                    if not t.done():
                        t.cancel()
        return r
    finally:
        if need_close_session:
            await session.close()
