import time
import json
import asyncio

import aioredis

from models.proxy import Proxy


class Maintainer(object):

    SHRESHOLD = 300
    ADD_NUM = 30

    def __init__(self, pom, redis_addr='redis://localhost'):
        self._redis_addr = redis_addr
        self.pom = pom

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr, encoding='utf8')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis is not None:
            self.redis.close()
            await self.redis.wait_closed()

    async def maintain_proxies(self):
        patterns = await self.redis.hkeys('response_check_pattern')
        await asyncio.gather(*[self._maintain_proxies_for_pattern(pattern_str) for pattern_str in patterns])

    async def _maintain_proxies_for_pattern(self, pattern_str):
        proxies = await self.redis.hgetall(pattern_str)
        if len(proxies) < self.SHRESHOLD:
            await self.pom.add_proxies(self.ADD_NUM, pattern_str=pattern_str)
        await asyncio.gather(*[asyncio.create_task(self._del_proxy_in_pattern(pattern_str, proxy_str, proxy_json))
                               for proxy_str, proxy_json in proxies.items()])

    async def _del_proxy_in_pattern(self, pattern_str, proxy_str, proxy_json):
        fail_key = pattern_str + '_fail'
        proxy = Proxy.loads(proxy_json)
        remain_time = proxy.insert_time + proxy.valid_time - int(time.time())
        if proxy.score <= -10 or (remain_time < 0 < proxy.valid_time and not proxy.used):
            await self.redis.hdel(pattern_str, proxy_str)
            if proxy.used:
                del_info = json.loads(proxy_json)
                del_info['delete_time'] = int(time.time())
                await self.redis.hset(fail_key, proxy, json.dumps(del_info))
