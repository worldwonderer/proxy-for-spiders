import time
import asyncio
from collections import defaultdict

import aioredis

from models.proxy import Proxy


class Saver(object):

    RESULT_SAVE_NUM = 100
    pattern_lock_map = defaultdict(asyncio.Lock)
    success_count = 0
    total_count = 0

    def __init__(self, redis_addr='redis://localhost', password=None):
        self._redis_addr = redis_addr
        self._password = password

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr,
                                                      password=self._password, encoding='utf8')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis is not None:
            self.redis.close()
            await self.redis.wait_closed()

    async def _save(self, key, response):
        key += '_result'
        if hasattr(response, 'info_json'):
            info = await response.info_json()
            await asyncio.gather(*[self.redis.lpush(key, info),
                                 self.redis.ltrim(key, 0, self.RESULT_SAVE_NUM-1)])

    async def _score_counter(self, pattern_str, proxy_str, valid):
        async with self.pattern_lock_map[pattern_str]:
            proxy = await Proxy.discard(pattern_str, proxy_str, self.redis)
            if proxy is None:
                return

            self.total_count += 1
            if valid:
                if proxy.score < 0:
                    proxy.score = 0
                elif 0 <= proxy.score < 5:
                    proxy.score += 1
                self.success_count += 1
            else:
                proxy.score -= 1
                remain_time = proxy.insert_time + proxy.valid_time - int(time.time())
                if proxy.score <= -3 or (remain_time < 0 < proxy.valid_time):
                    await self._del_proxy_in_pattern(pattern_str, proxy)
                    return

            proxy.used = True
            await proxy.store(pattern_str, self.redis)

    async def save_result(self, pattern_str, proxy_str, response):
        tasks = [
            self._score_counter(pattern_str, proxy_str, response.valid),
            self._save(proxy_str, response),
            self._save(pattern_str, response)
        ]
        await asyncio.gather(*tasks)

    async def _del_proxy_in_pattern(self, pattern_str, proxy):
        fail_key = pattern_str + '_fail'
        await self.redis.hdel(pattern_str, str(proxy))
        proxy.delete_time = int(time.time())
        await proxy.store(fail_key, self.redis)
