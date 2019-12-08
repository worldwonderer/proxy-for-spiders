import time
import asyncio

import aioredis

from models.proxy import Proxy


class Saver(object):

    pattern_lock_map = dict()
    RESULT_SAVE_NUM = 100

    def __init__(self, redis_addr='redis://localhost'):
        self._redis_addr = redis_addr

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr, encoding='utf8')
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
        if pattern_str not in self.pattern_lock_map:
            self.pattern_lock_map[pattern_str] = asyncio.Lock()
        async with self.pattern_lock_map[pattern_str]:
            proxy_json = await self.redis.hget(pattern_str, proxy_str)
            if proxy_json is None:
                return
            proxy = Proxy.loads(proxy_json)
            if valid:
                if proxy.score < 0:
                    proxy.score = 0
                elif 0 <= proxy.score < 5:
                    proxy.score += 1

            else:
                existed_time = int(time.time()) - proxy.insert_time
                if proxy.valid_time and existed_time > proxy.valid_time > 0:
                    await self._del_proxy_in_pattern(pattern_str, proxy)
                else:
                    proxy.score -= 1

            proxy.used = True
            await self.redis.hset(pattern_str, proxy_str, proxy.dumps())

    async def save_result(self, pattern_str, proxy_str, response):
        tasks = [
            self._score_counter(pattern_str, proxy_str, response.valid),
            self._save(proxy_str, response),
            self._save(pattern_str, response)
        ]
        await asyncio.gather(*tasks)

    async def _del_proxy_in_pattern(self, pattern_str, proxy):
        fail_key = pattern_str + '_fail'
        remain_time = proxy.insert_time + proxy.valid_time - int(time.time())
        if proxy.score <= -10 or (remain_time < 0 < proxy.valid_time and not proxy.used):
            await self.redis.hdel(pattern_str, str(proxy))
            if proxy.used:
                proxy.delete_time = int(time.time())
                await self.redis.hset(fail_key, proxy, proxy.dumps())
