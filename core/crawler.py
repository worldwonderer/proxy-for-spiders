import sys
import asyncio
import traceback

import aiohttp

import log_utils
from models.response import Response, FailedResponse


logger = log_utils.LogHandler(__name__, file=True)


async def async_crawl(method, url, session, **kwargs):
    proxy = kwargs.get('proxy')
    if proxy is not None and not isinstance(proxy, str):
        kwargs['proxy'] = str(proxy)
    kwargs.update({'ssl': False, 'timeout': 10})
    try:
        async with session.request(method, url, **kwargs) as r:
            r.proxy = proxy
            await r.read()
            r.__class__ = Response
    except asyncio.CancelledError:
        r = FailedResponse()
        r.traceback = 'cancelled'
    except Exception as e:
        r = FailedResponse()
        r.traceback = [str(proxy)+'\n'] + traceback.format_exception(*sys.exc_info())
        logger.warning(e, exc_info=True)
    return r


async def async_crawl_and_check(method, url, session, pattern, **kwargs):
    r = await async_crawl(method, url, session, **kwargs)
    if r.traceback is None:
        r.traceback = await pattern.check(r)
    r.valid = not r.traceback
    if r.traceback != 'cancelled':
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

    result = None
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
                result = r
                break
        if r is not None and result is None:
            result = r
        return result
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        if need_close_session:
            await session.close()
