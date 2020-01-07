import concurrent.futures

import requests
from lxml import etree


start_url = 'http://movie.douban.com/top250'
pattern_api = 'http://127.0.0.1:8893/dev-api/pattern'
pattern_data = {"pattern": "movie.douban.com/top250", "rule": "whitelist", "value": "rating_num"}
proxies = {
    'http': 'http://127.0.0.1:8893',
    'https': 'http://127.0.0.1:8893'
}


def set_pattern():
    requests.post(pattern_api, json=pattern_data)


def get_top250(start=0):
    payload = {'start': start, 'filter': ''}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/77.0.3809.132 Safari/537.36',
    }

    res = requests.get(start_url, headers=headers, params=payload, proxies=proxies)
    et = etree.HTML(res.text)
    li = et.xpath('//ol[@class="grid_view"]/li')
    return len(li)


def one_round():
    success_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        result = executor.map(get_top250, range(0, 250, 25))
        for count in result:
            if count != 0:
                success_count += 1
    return success_count / 10


def bench_proxy():
    set_pattern()
    i = 0
    while True:
        rate = one_round()
        i += 1
        print("finish one round. success rate: {}, current round: {}".format(rate, i))


if __name__ == '__main__':
    bench_proxy()
