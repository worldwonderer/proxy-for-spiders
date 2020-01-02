# proxy_tower

代理负载均衡模块，更高效率的使用代理池

可解决：
1. 免费代理可用率低
2. 付费代理过期时间不稳定，难以充分利用
3. 一直使用无效代理

注：proxy_tower本身不抓取、嗅探代理

## 特性
* 多倍转发
    * 支持将收到的代理请求转发给多个proxy
    * 返回最快并且有效的response
 
多倍转发可有效解决免费/不稳定代理可用率低的问题

* response校验
    * pattern是目标站点的某个复用页面，通常有同样的URL前缀，类似的HTML结构，如豆瓣电影`movie.douban.com/subject/`
    * 通过前缀树存储pattern和对应的xpath或keyword校验规则，高效、简便的解决了多站点校验的问题
    * 不同的pattern有其各自的代理池  

## 依赖环境
* Python3.6 及以上
* Redis

## 使用方法
1. 安装依赖 `pip install -r requirements.txt`
2. 启动 `python proxy_entrance.py`
3. 测试 `curl -x "http://0.0.0.0:8893" "http://www.httpbin.org/ip"`

## 配置 config.py
```shell
global_blacklist = [
    'antispider',
    'forbidden'
]  # 全局黑名单关键词列表，如果response中包含列表中的关键词，判定response无效

# 本项目重度依赖redis，用于存储校验规则和代理
redis_host = getenv('redis_host', 'redis')
redis_port = getenv('redis_port', 6379)
redis_db = getenv('redis_db', 0)
redis_password = getenv('redis_password', '')
redis_addr = 'redis://{}:{}/{}'.format(redis_host, redis_port, redis_db)
```

## Docker
```shell
docker pull worldwonderer/proxy_tower

# 已有redis服务
docker run redis_host=<redis-ip> --env redis_port=<6379> --env redis_password=<foobared> -p 8893:8893 worldwonderer/proxy_tower

# 无redis服务，启用redis container
cd proxy_tower/
docker-compose up
```

## 校验规则配置
目前支持两种校验规则的配置
1. `whitelist`，即如果response中包含了这些关键词，判定response有效
2. `xpath`，即如果response中能用该xpath解析到对应的内容，判定response有效

```shell
import json
import redis

r = redis.StrictRedis()
# whitelist校验
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'pattern': 'movie.douban.com/subject/', 'rule': 'whitelist', 'value':'ratingValue'}))

# xpath校验
r.hset("response_check_pattern", "movie.douban.com/subject/", json.dumps({'pattern': 'movie.douban.com/subject/', 'rule': '//*[@id="recommendations"]/h2/i', 'value':'喜欢这部电影的人也喜欢'}))
```

配置校验规则后，代理`https://movie.douban.com/subject/27119724/`类似的页面，proxy_tower会对页面内容做校验，优先返回符合规则的response，并对proxy计分

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
                yield Proxy.parse(proxy, tag=self.tag, support_https=True, paid=False)


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
            yield Proxy.parse(proxy, tag=self.tag, valid_time=self.valid_time, paid=False)
```

由于每个proxy源获取到的proxy特性不同，可以使用tag给proxy做标记，并初始化属性
* valid_time：proxy有效时长
* support_https：proxy是否支持https
* paid: proxy是否为付费代理

## HTTPS

对于必须使用https的站点，可以在请求的headers中添加`'Need-Https': 'yes'`，proxy_tower会选取带有support_https标记的proxy

注：URL不要带上https，例如使用`http://www.bilibili.com`，而不是`https://www.bilibili.com`

## Dashboard

[proxy_tower_dashboard](https://github.com/worldwonderer/proxy_tower_dashboard)

* 查看proxy
* 查看、修改、添加pattern
* 各pattern成功率的折线表

## Todo

* Test
* 校验规则使用条件表达式
