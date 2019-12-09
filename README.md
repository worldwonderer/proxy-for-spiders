# proxy_tower

爬虫代理模块，可以更高效率的使用代理池

可解决：
1. 开源代理池项目低可用率的痛点
2. 付费代理过期时间不稳定，无法充分利用

## 特性
* 增倍转发，将收到的请求转发给多个proxy，返回最快并且符合校验规则的response
* response校验：可配置关键词或xpath，校验response
* 分站点计分

注：proxy_tower本身不生产代理

## 依赖环境
* Python3.6 及以上
* 测试地址：

## 使用方法
1. 下载源码
2. 安装依赖 `pip install -r requirements.txt`
3. 启动 `python proxy_entrance.py`
4. 测试 `curl -x "http://0.0.0.0:8893" "http://www.httpbin.org/ip"`

## 配置 config.py
```shell
redis_addr = 'redis://localhost'  # 本项目重度依赖redis，用于存储校验规则和代理
global_blacklist = [
    'antispider',
    'forbidden'
]  # 全局黑名单关键词列表，如果response中包含列表中的关键词，判定response无效
```

## 校验规则配置
校验规则基于pattern，pattern是目标站点的某个复用页面，通常有同样的URL前缀，有类似的HTML元素，例如豆瓣电影movie.douban.com/subject/

目前支持两种校验规则的配置，
1. whitelist，即如果response中包含了这些关键词，判定response有效
2. xpath，即如果response中能用该xpath解析到对应的内容，判定response有效

```shell
import json
import redis

r = redis.StrictRedis()
# whitelist校验
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'rule': 'whitelist', 'value':'ratingValue'}))

# xpath校验
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'rule': '//*[@id="recommendations"]/h2/i', 'value':'喜欢这部电影的人也喜欢'}))
```

配置校验规则后，抓取https://movie.douban.com/subject/27119724/ 类似的页面，proxy_tower会对页面内容做校验，优先返回符合规则的response，并对proxy计分

## 代理接入

可以在models/proxy.py中拓展proxy源，目前支持文件和API两种方式
```shell
# 文件
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

由于每个proxy源获取到的proxy特性不同，可以使用tag给proxy做标记，并初始化属性
* valid_time：proxy有效时长
* support_https：proxy是否支持https
