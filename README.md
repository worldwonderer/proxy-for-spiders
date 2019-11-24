# proxy-for-spiders

目前开源代理池项目有低可用率的痛点。该代理服务器基于 Asyncio 编写，拥有增倍转发、返回结果校验、分站点计分等特性。

## 依赖环境
* Python3.6 以上
* redis

## 使用方法
1. Clone the repository
2. Run `pip install -r requirements.txt`
3. Run `python proxy_entrance.py

测试: curl -x "http://0.0.0.0:8893" "http://www.httpbin.org/ip"