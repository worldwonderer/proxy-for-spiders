import json

from core.crawler import crawl


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
    return await crawl(method, url, proxies, session=session, pattern=pattern, data=content, headers=headers)


async def cookies_handler(headers, pam, pattern_str):
    if 'Need-Cookies' in headers:
        j = await pam.get_cookies(pattern_str)
        if j is None:
            return
        headers.update(json.loads(j))
