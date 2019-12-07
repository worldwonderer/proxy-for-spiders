import json

from models.pattern import Pattern
from core.crawler import crawl


async def forward(method, url, pam, pom, checker, saver, **kwargs):
    headers = kwargs.get('headers')
    content = kwargs.get('content')
    style = kwargs.get('style', 'score')

    pattern_str, check_rule_json = pam.t.closest_pattern(url)
    await cookies_handler(headers, pam, pattern_str)
    await pom.add_proxies_for_pattern(pattern_str)
    proxies = await pom.select_proxies(pattern_str, need_https='Need-Https' in headers, prefer_used=True, style=style)
    pattern = Pattern(pattern_str, checker, json.loads(check_rule_json), saver)
    return await crawl(method, url, proxies, pattern=pattern, data=content, headers=headers)


async def cookies_handler(headers, pam, pattern_str):
    if 'Need-Cookies' in headers:
        j = await pam.get_cookies(pattern_str)
        if j is None:
            return
        headers.update(json.loads(j))
