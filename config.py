class Config(object):
    global_blacklist = [
        'antispider',
        'forbidden'
    ]
    redis_addr = 'redis://redis:6379'


conf = Config()

