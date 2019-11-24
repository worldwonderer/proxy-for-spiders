# proxy-for-spiders

由于开源代理池项目有低可用率的痛点，基于 Asyncio 编写异步的正向代理服务器，拥有增倍转发、返回结果
校验、分站点计分等特性

## 依赖环境
python3.7
redis

## 使用方法
1. Clone the repository
2. Run `pip install -r requirements.txt`
3. Run `python proxy_entrance.py

测试: curl -x "http://0.0.0.0:8893" "http://www.httpbin.org/ip"