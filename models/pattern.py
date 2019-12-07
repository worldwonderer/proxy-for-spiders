import re
import sys
import json
import traceback

import aioredis
from lxml import etree
from pygtrie import CharTrie


class Checker(object):

    def __init__(self, global_blacklist=None):
        self.global_blacklist = global_blacklist or list()

    @staticmethod
    def _status_code_checker(status_code):
        return status_code is not None and (status_code == 404 or status_code < 400)

    @staticmethod
    def _xpath_checker(html, xpath, value):
        try:
            et = etree.HTML(html)
            assert et.xpath(xpath)[0] == value
        except IndexError:
            return 'xpath check failed, {} not found'
        except AssertionError:
            return 'xpath check failed, value not equal'
        except Exception:
            return traceback.format_exception(*sys.exc_info())

    def check(self, status_code, text, rule, value):
        if not self._status_code_checker(status_code):
            return 'status_code check failed, get {}'.format(status_code)
        for word in self.global_blacklist:
            if word in text:
                return 'global blacklist check failed, get {}'.format(word)
        if rule == 'whitelist':
            if value not in text:
                return 'whitelist check failed, {} not found'.format(value)
        elif len(rule.strip()) != 0 and len(value.strip()) != 0:
            tb = self._xpath_checker(text, rule, value)
            if tb is not None:
                return tb


class Pattern(object):

    def __init__(self, pattern_str, checker, check_rule, saver=None):
        self._pattern_str = pattern_str
        self.checker = checker
        self.saver = saver
        self.check_rule = check_rule

    def __str__(self):
        return self._pattern_str

    async def check(self, response):
        if response is None:
            return False
        rule, value = self.check_rule['rule'], self.check_rule['value']
        text = await response.text()
        tb = self.checker.check(response.status, text, rule, value)
        return tb

    async def score_and_save(self, proxy, response):
        if self.saver is None:
            return
        await self.saver.save_result(str(self), str(proxy), response)


class PatternManager(object):

    def __init__(self, redis_addr='redis://localhost'):
        self._redis_addr = redis_addr
        self.key = 'response_check_pattern'

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self._redis_addr, encoding='utf8')
        self.t = await self._init_trie()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis is not None:
            self.redis.close()
            await self.redis.wait_closed()

    async def patterns(self):
        d = await self.redis.hgetall(self.key)
        return [{'pattern': p, 'rule': json.loads(v)['rule'], 'value': json.loads(v)['value']} for p, v in d.items()]

    async def _init_trie(self):
        d = await self.redis.hgetall(self.key)
        return CheckPatternTrie(d)

    async def restore_trie(self, t):
        await self.redis.hmset(self.key, t)

    async def add(self, pattern, check_rule):
        self.t[str(pattern)] = json.dumps(check_rule)
        await self.redis.hset(self.key, str(pattern), json.dumps(check_rule))

    async def delete(self, pattern):
        del self.t[str(pattern)]
        await self.redis.hdel(self.key, str(pattern))

    async def update(self, pattern, check_rule):
        await self.add(pattern, check_rule)

    async def get_cookies(self, pattern_str):
        return await self.redis.srandmember(pattern_str + '_cookies')


class CheckPatternTrie(CharTrie):

    def __init__(self, *args, **kwargs):
        super(CheckPatternTrie, self).__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super(CheckPatternTrie, self).__setitem__(self._remove_http_prefix(key), value)

    def closest_pattern(self, url):
        url = self._remove_http_prefix(url)
        step = self.longest_prefix(url)
        pattern_str, check_rule_json = step.key, step.value
        if pattern_str is None:
            pattern_str, check_rule_json = 'public_proxies', json.dumps({'rule': '', 'value': ''})
        return pattern_str, check_rule_json

    @staticmethod
    def _remove_http_prefix(url):
        if url.startswith('http'):
            url = re.sub(r'https?://', '', url, 1)
        return url
