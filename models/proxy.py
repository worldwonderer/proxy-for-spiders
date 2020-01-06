import re
import json
import time
import heapq
import random
from collections import defaultdict

import aioredis

import log_utils
from core.crawler import crawl
from models.response import FailedResponse


logger = log_utils.LogHandler(__name__, file=True)


class Proxy(object):

    _score = 0

    def __init__(self, ip, port, **kwargs):
        self.ip = ip
        self.port = int(port)
        self.valid_time = kwargs.get('valid_time', -1)
        self.insert_time = kwargs.get('insert_time') or int(time.time())
        self.support_https = kwargs.get('support_https', None)
        self.paid = kwargs.get('paid')
        self.tag = kwargs.get('tag')
        self.used = False

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, value):
        if value > 5:
            return
        self._score = value

    def dumps(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        d = {
            "score": self.score,
            "ip": self.ip,
            "port": self.port,
            "used": self.used,
            "valid_time": self.valid_time,
            "insert_time": self.insert_time,
            "tag": self.tag,
            "paid": self.paid,
            "support_https": self.support_https
        }
        if hasattr(self, 'delete_time'):
            d['delete_time'] = self.delete_time
        return d

    def __str__(self):
        return 'http://{0}:{1}'.format(self.ip, self.port)

    async def store(self, pattern_str, redis):
        await redis.hset(str(pattern_str), str(self), self.dumps())

    @classmethod
    async def discard(cls, pattern_str, proxy_str, redis):
        j = await redis.hget(str(pattern_str), str(proxy_str))
        if j is None:
            return None
        return cls.loads(j)

    @classmethod
    def loads(cls, j):
        d = json.loads(j)
        proxy = Proxy(d['ip'], d['port'], valid_time=d.get('valid_time'),
                      insert_time=d['insert_time'], tag=d.get('tag'),
                      support_https=d.get('support_https', False), paid=d.get('paid'))
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

    SCORE_RANDOM_SCOPE = 10
    RENEW_TIME = 8 * 60 * 60
    _last_add_time = defaultdict(int)

    def __init__(self, concurrent, pool_size, redis_addr='redis://localhost', password=None, tags_source_map=None):
        self._redis_addr = redis_addr
        self._password = password
        self.tags_source_map = tags_source_map or dict()
        self.concurrent = concurrent
        self.pool_size = pool_size

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr,
                                                      password=self._password, encoding='utf8')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis is not None:
            self.redis.close()
            await self.redis.wait_closed()

    async def proxies(self, need_https=False, pattern_str='public_proxies', format_type='raw'):
        d = await self.redis.hgetall(pattern_str)
        proxies = [Proxy.loads(v) for _, v in d.items()]
        if need_https:
            proxies = [p for p in proxies if p.support_https]
        if format_type == 'dict':
            proxies = [p.to_dict() for p in proxies]
        return proxies

    async def select_proxies(self, pattern_str, need_https=False, prefer_used=True, economic=True, style='score'):
        proxies = await self.proxies(need_https, pattern_str)
        if style == 'shuffle':
            concurrent_num = min(len(proxies), self.concurrent)
            selected_proxies = random.sample(proxies, concurrent_num)
        else:
            scope = self.SCORE_RANDOM_SCOPE
            n = min(scope, len(proxies))
            concurrent_num = min(n, self.concurrent)

            def selector(proxy):
                score, used = proxy.score, proxy.used
                if used and prefer_used:
                    score *= 1.5
                return score
            selected_proxies = random.sample(
                heapq.nlargest(
                    n, proxies, key=lambda a: selector(a)
                ), concurrent_num
            )
        if economic:
            # put only one paid proxy in selected_proxies to avoid wasting
            already_put_one = False
            temp = list()
            for p in selected_proxies:
                if p.paid and already_put_one:
                    continue
                if p.paid and not already_put_one:
                    already_put_one = True
                temp.append(p)
            selected_proxies = temp
        return selected_proxies

    async def sync_public(self, pattern_str):
        added_num = 0
        proxies = await self.proxies(pattern_str='public_proxies')
        for proxy in proxies:
            if await self._add_proxy(proxy, pattern_str):
                added_num += 1
        return added_num

    async def add_proxies(self, pattern_str, num=30):
        added_num = 0
        for source in proxy_sources:
            logger.debug("start fetching proxy from source {}".format(source.tag))
            try:
                async for proxy in source.fetch_proxies():
                    if await self._add_proxy(proxy, pattern_str):
                        added_num += 1
                        if added_num >= num:
                            break
            except Exception as e:
                logger.warning("unable to fetch proxy from {}, {}".format(source.tag, e), exc_info=True)
        return added_num

    async def _add_proxy(self, proxy, pattern_str):
        for p in {pattern_str, 'public_proxies'}:
            del_info_json = await self.redis.hget(p+'_fail', str(proxy))
            if del_info_json is not None:
                del_info = json.loads(del_info_json)
                del_time = del_info['delete_time']
                if int(time.time()) - del_time < self.RENEW_TIME:
                    return False
                else:
                    await self.redis.hdel(p + '_fail', str(proxy))
            if await self.redis.hexists(pattern_str, str(proxy)):
                return False
            await proxy.store(p, self.redis)
        return True

    async def proxy_count(self, pattern_str):
        return await self.redis.hlen(pattern_str)

    async def add_proxies_for_pattern(self, pattern_str):
        added_num = 0
        proxy_count = await self.proxy_count(pattern_str)
        if proxy_count < self.pool_size:
            now = int(time.time())
            if now - self._last_add_time[pattern_str] < 5:
                return added_num
            else:
                self._last_add_time[pattern_str] = now

            logger.info("proxy not enough for {}, now has {}, start adding".format(pattern_str, proxy_count))
            if pattern_str != 'public_proxies':
                added_num += await self.sync_public(pattern_str)
            added_num += await self.add_proxies(pattern_str, self.pool_size-proxy_count)
            logger.info("{} proxies added for {}".format(added_num, pattern_str))
            if added_num == 0:
                logger.warning("no proxy fetched, consider adding more sources")
        return added_num


class ProxySource(object):

    proxy_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}"

    async def fetch_proxies(self):
        pass


class ProxyFile(ProxySource):

    def __init__(self, tag, file_path):
        self.file_path = file_path
        self.tag = tag
        self.paid = False

    async def fetch_proxies(self):
        with open(self.file_path, 'r') as f:
            proxy_candidates = re.findall(self.proxy_pattern, f.read())
            for proxy in proxy_candidates:
                yield Proxy.parse(proxy, tag=self.tag, support_https=True, paid=False)


class ProxyApi(ProxySource):

    def __init__(self, tag, api, valid_time):
        self.api = api
        self.tag = tag
        self.valid_time = valid_time

    async def fetch_proxies(self):
        r = await crawl("GET", self.api, timeout=3)
        if isinstance(r, FailedResponse):
            raise ConnectionError("unable to fetch api {}".format(self.api))
        text = await r.text()
        proxy_candidates = re.findall(self.proxy_pattern, text)
        for proxy in proxy_candidates:
            yield Proxy.parse(proxy, tag=self.tag, valid_time=self.valid_time, paid=False)


proxy_sources = {
    ProxyFile('file', './conf/proxy.txt'),
    ProxyApi('free_api', 'http://122.51.7.207:5010/get_all/', 300)
    # you can add your own proxy pool api here
}
