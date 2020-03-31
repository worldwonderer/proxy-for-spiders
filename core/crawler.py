import asyncio
import sys
import traceback

import aiohttp

import log_utils
from config import conf
from models.response import FailedResponse, Response

logger = log_utils.LogHandler(__name__, file=True)


async def _crawl(method, url, session, **kwargs):
    proxy = kwargs.get('proxy')
    if proxy is not None:
        kwargs['proxy'] = str(proxy)
    kwargs.update({'ssl': False, 'timeout': kwargs.get('timeout') or conf.timeout})
    try:
        async with session.request(method, url, **kwargs) as r:
            r.__class__ = Response
            await r.read()
    except asyncio.CancelledError:
        r = FailedResponse()
        r.cancelled = True
    except Exception as e:
        r = FailedResponse()
        r.traceback = str(proxy) + '\n' + ''.join(traceback.format_exception(*sys.exc_info())) + '\n'
        # logger.debug(e, exc_info=True)
    r.proxy = proxy
    return r


async def _crawl_with_check(method, url, session, pattern, **kwargs):
    r = await _crawl(method, url, session, **kwargs)
    if hasattr(r, 'cancelled') and r.cancelled:
        return r
    await pattern.check(r)
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

    result = FailedResponse()
    need_check = pattern is not None
    try:
        if need_check:
            tasks = [asyncio.ensure_future(_crawl_with_check(method, url, session, pattern,
                                                             proxy=proxy, **kwargs)) for proxy in proxies]
        else:
            tasks = [asyncio.ensure_future(_crawl(method, url, session, proxy=proxy, **kwargs))
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
            else:
                if result.traceback is None:
                    result.traceback = ''
                result.traceback += r.traceback
                logger.debug("response from {} for {} is invalid, trying other proxies".format(r.proxy, url))
        return result
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        if need_close_session:
            await session.close()
