import json

from aiohttp import web
from multidict import CIMultiDict

import log_utils
from core.crawler import crawl

logger = log_utils.LogHandler('server', file=True)


def _gen_headers(r):
    res_headers = CIMultiDict()
    if 'Set-Cookie' in r.headers:
        for cookie in r.headers.getall('Set-Cookie'):
            res_headers.add('Set-Cookie', cookie)
    res_headers['Via-Proxy'] = str(r.proxy)
    return res_headers


async def forward(method, url, pam, pom, **kwargs):
    session = kwargs.get('session')
    headers = kwargs.get('headers')
    content = kwargs.get('content')
    mode = kwargs.get('mode', 'score')

    need_https = 'Need-Https' in headers
    if need_https:
        url = url.replace('http://', 'https://', 1)

    pattern_str, check_rule_json = pam.t.closest_pattern(url)
    await cookies_handler(headers, pam, pattern_str)
    await pom.add_proxies_for_pattern(pattern_str)
    proxies = await pom.select_proxies(pattern_str, need_https=need_https,
                                       prefer_used=True, mode=mode)
    pattern = pam.get_pattern(pattern_str)
    r = await crawl(method, url, proxies, session=session, pattern=pattern, data=content, headers=headers)
    if r is None or r.traceback or r.cancelled:
        await pattern.counter(False)
        text = 'unable to get any response' if r is None else r.traceback
        logger.warning("unable to get any valid response for {}".format(url))
        return web.Response(status=417, text=text)
    else:
        await pattern.counter(True)
        text = await r.text()
        logger.info("get valid response for {} via proxy {}".format(url, r.proxy))
        return web.Response(status=r.status, text=text, headers=_gen_headers(r))


async def cookies_handler(headers, pam, pattern_str):
    if 'Need-Cookies' in headers:
        j = await pam.get_cookies(pattern_str)
        if j is None:
            return
        headers.update(json.loads(j))
