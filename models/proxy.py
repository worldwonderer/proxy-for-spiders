import re
import json
import time
import heapq
import random
import warnings

import aioredis

from core.crawler import crawl


class Proxy(object):

    INIT_SCORE = 10

    def __init__(self, ip, port, **kwargs):
        self.ip = ip
        self.port = int(port)
        self.valid_time = kwargs.get('valid_time')
        self.insert_time = kwargs.get('insert_time') or int(time.time())
        self.tag = kwargs.get('tag')
        self._score = self.INIT_SCORE
        self.used = False

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, value):
        if value < -10:
            warnings.warn("proxy's score is lower than -10, consider abandon it")
        if value >= 10:
            return
        self._score = value

    def dumps(self):
        return json.dumps({
            "score": self.score,
            "ip": self.ip,
            "port": self.port,
            "used": self.used,
            "valid_time": self.valid_time,
            "insert_time": self.insert_time,
            "tag": self.tag,
        })

    def __str__(self):
        return 'http://{0}:{1}'.format(self.ip, self.port)

    @classmethod
    def loads(cls, j):
        d = json.loads(j)
        proxy = Proxy(d['ip'], d['port'], valid_time=d.get('valid_time'),
                      insert_time=d.get('insert_time'), tag=d.get('tag'))
        proxy.score = d['score']
        proxy.used = d['used']
        return proxy

    @classmethod
    def parse(cls, proxy_str, **kwargs):
        if proxy_str.startswith('http'):
            proxy_str = re.sub(r'https?://', '', proxy_str, 1)
        ip, port = proxy_str.split(':')
        return Proxy(ip, port, **kwargs)


class ProxyManager(object):

    REQUEST_CONCURRENT = 3
    SCORE_RANDOM_SCOPE = 10
    INIT_SCORE = 10
    RENEW_TIME = 8 * 60 * 60
    PROXY_NUM_SHRESHOLD = 100
    ADD_NUM = 30
    _concurrent_semaphore = dict()

    def __init__(self, redis_addr='redis://localhost', tags_source_map=None):
        self._redis_addr = redis_addr
        self.tags_source_map = tags_source_map or dict()

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr, encoding='utf8')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis is not None:
            self.redis.close()
            await self.redis.wait_closed()

    async def proxies(self, pattern_str='public_proxies'):
        d = await self.redis.hgetall(pattern_str)
        return [Proxy.loads(v) for _, v in d.items()]

    async def select_proxies(self, pattern_str, prefer_used=True, style='score'):
        proxies = await self.proxies(pattern_str)
        concurrent_num = min(len(proxies), self.REQUEST_CONCURRENT)
        if style == 'shuffle':
            selected_proxies = random.sample(proxies, concurrent_num)
        else:
            scope = self.SCORE_RANDOM_SCOPE
            n = min(scope, len(proxies))

            def selector(proxy):
                score, used = proxy.score, proxy.used
                if used and prefer_used:
                    score *= 1.5
                return score
            selected_proxies = random.sample(heapq.nlargest(n, proxies, key=lambda a: selector(a)), concurrent_num)
        return selected_proxies

    async def sync_public(self, pattern_str):
        added_num = 0
        proxies = await self.proxies(pattern_str='public_proxies')
        for proxy in proxies:
            if await self._add_proxy(proxy, pattern_str):
                added_num += 1
        return added_num

    async def add_proxies(self, num, pattern_str='public_proxies'):
        added_num = 0
        for source in proxy_sources:
            async for proxy in source.fetch_proxies():
                if await self._add_proxy(proxy, pattern_str):
                    added_num += 1
                    if added_num >= num:
                        break
        return added_num

    async def _add_proxy(self, proxy, pattern_str='public_proxies'):
        for p in {pattern_str, 'public_proxies'}:
            del_info_json = await self.redis.hget(p + '_fail', str(proxy))
            if del_info_json is not None:
                del_info = json.load(del_info_json)
                del_time = del_info['delete_time']
                if int(time.time()) - del_time < self.RENEW_TIME:
                    return False
                else:
                    await self.redis.hdel(p + '_fail', str(proxy))
            if await self.redis.hexists(pattern_str, str(proxy)):
                return False
            await self.redis.hset(p, str(proxy), proxy.dumps())
        return True

    async def add_proxies_for_pattern(self, pattern_str):
        proxy_num = await self.redis.hlen(pattern_str)
        if proxy_num < self.PROXY_NUM_SHRESHOLD:
            await self.sync_public(pattern_str)
            await self.add_proxies(self.ADD_NUM, pattern_str)


class ProxySource(object):

    proxy_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}"

    async def fetch_proxies(self):
        pass


class ProxyFile(ProxySource):

    def __init__(self, tag, file_path):
        self.file_path = file_path
        self.tag = tag

    async def fetch_proxies(self):
        with open(self.file_path, 'r') as f:
            proxy_candidates = re.findall(self.proxy_pattern, f.read())
            for proxy in proxy_candidates:
                yield Proxy.parse(proxy, tag=self.tag)


class ProxyApi(ProxySource):

    def __init__(self, tag, api):
        self.api = api
        self.tag = tag

    async def fetch_proxies(self):
        r = await crawl("GET", self.api)
        text = await r.text()
        proxy_candidates = re.findall(self.proxy_pattern, text)
        for proxy in proxy_candidates:
            yield Proxy.parse(proxy, tag=self.tag)


proxy_sources = {
    ProxyFile('file', './conf/proxy.txt'),
    ProxyApi('free_api', 'http://118.24.52.95/get_all/')
}
