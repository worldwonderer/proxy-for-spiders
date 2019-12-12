from os import getenv


class Config(object):
    global_blacklist = [
        'antispider',
        'forbidden'
    ]

    redis_host = getenv('redis_host', 'redis')
    redis_port = getenv('redis_port', 6379)
    redis_db = getenv('redis_db', 0)
    redis_password = getenv('redis_password', None)
    redis_addr = 'redis://{}:{}/{}'.format(redis_host, redis_port, redis_db)


conf = Config()
