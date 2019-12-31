from os import getenv


class Config(object):
    global_blacklist = [
        'antispider',
        'forbidden'
    ]

    redis_host = getenv('redis_host', '127.0.0.1')
    redis_port = getenv('redis_port', 6379)
    redis_db = getenv('redis_db', 0)
    redis_password = getenv('redis_password')
    redis_addr = 'redis://{}:{}/{}'.format(redis_host, redis_port, redis_db)

    timeout = 30
    request_concurrent = 10


conf = Config()
