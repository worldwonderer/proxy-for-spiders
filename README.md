# proxy_tower
A proxy load balance server allows web crawlers to use proxy pool more effectively

 [中文文档](https://raw.githubusercontent.com/worldwonderer/proxy_tower/master/README_ZH.md)

1. Free proxies usually have low success rate 
2. Payment proxies's expiration time is unstable and difficult to make full use of
3. Avoid using invalid proxies constantly 

## Features
* Multiple forwarding
    * Forward request to multiple proxies 
    * Return the fastest and valid response
    
Multiple forwarding can increase the success rate of using free or unstable proxies

* Response verification
    * Pattern is a reused page of the target site, the page has same URL prefix and similar HTML structure，such as 'movie.douban.com/subject/'
    * Patterns and verification rules are stored in a prefix tree which helps verify responses from different sites easily and effectively
    * Separated proxy pools for different patterns

Note: proxy_tower itself does not seek proxies

## Requirements
* Python >= 3.6
* A redis server

## Getting started
1. `pip install -r requirements.txt`
2. `python proxy_entrance.py`
3. For test: `curl -x "http://0.0.0.0:8893" "http://www.httpbin.org/ip"`

## config.py
```shell
global_blacklist = [
    'antispider',
    'forbidden'
]  # global keywords blacklist. if response contains any words in it, response is considered invalid

# proxy_tower relies heavily on redis which is used for storing proxies and validation rules
redis_host = getenv('redis_host', 'redis')
redis_port = getenv('redis_port', 6379)
redis_db = getenv('redis_db', 0)
redis_password = getenv('redis_password', '')
redis_addr = 'redis://{}:{}/{}'.format(redis_host, redis_port, redis_db)
```

## Docker
```shell
docker pull worldwonderer/proxy_tower

docker run redis_host=<redis-ip> --env redis_port=<6379> --env redis_password=<foobared> -p 8893:8893 worldwonderer/proxy_tower
```

## Response Verification
Currently support two kinds of verification rules
1. whitelist, if the response contains specified keywords, response is determined to be valid
2. xpath, if xpath can extract specified value from response, response is determined to be valid

```shell
import json
import redis

r = redis.StrictRedis()
# whitelist
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'rule': 'whitelist', 'value':'ratingValue'}))

# xpath
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'rule': '//*[@id="recommendations"]/h2/i', 'value':'喜欢这部电影的人也喜欢'}))
```

After configuring the validation rule for a pattern，when you crawl web pages like 'https://movie.douban.com/subject/27119724/' ，proxy_tower will verify the content of response and score the proxy

## Adding proxies

You can add proxy source in models/proxy.py through reading file or requesting API

```
# file
class ProxyFile(ProxySource):

    def __init__(self, tag, file_path):
        self.file_path = file_path
        self.tag = tag

    async def fetch_proxies(self):
        with open(self.file_path, 'r') as f:
            proxy_candidates = re.findall(self.proxy_pattern, f.read())
            for proxy in proxy_candidates:
                yield Proxy.parse(proxy, tag=self.tag, support_https=True)


# API
class ProxyApi(ProxySource):

    def __init__(self, tag, api, valid_time):
        self.api = api
        self.tag = tag
        self.valid_time = valid_time

    async def fetch_proxies(self):
        r = await crawl("GET", self.api)
        text = await r.text()
        proxy_candidates = re.findall(self.proxy_pattern, text)
        for proxy in proxy_candidates:
            yield Proxy.parse(proxy, tag=self.tag, valid_time=self.valid_time)
```

Proxies from different proxy source have their own properties, you can tag the proxy and initialize them at the very beginning
* valid_time
* support_https

## Dashboard

[proxy_tower_dashboard](https://github.com/worldwonderer/proxy_tower_dashboard)

* Display all proxies and their info
* View, modify, and add patterns
* A Line chart of each pattern's success rate

## Todo

* Test
* Support conditional expressions in verification rules
