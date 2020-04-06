from os import getenv


class Config(object):
    # redis db
    redis_host = getenv('redis_host', '127.0.0.1')
    redis_port = getenv('redis_port', 6379)
    redis_db = getenv('redis_db', 0)
    redis_password = getenv('redis_password', None)
    redis_addr = 'redis://{}:{}/{}'.format(redis_host, redis_port, redis_db)

    # proxy
    port = 8893
    timeout = 10
    concurrent = 10
    pool_size = 50
    mode = 'combine'
    global_blacklist = [
        'antispider',
        'forbidden',
        'This is the default welcome page',
        'you\'ve successfully installed Tomcat'
    ]

    # dashboard
    dashboard_addr = 'http://127.0.0.1:8894'
    admin_token = {
        'roles': ['admin'],
        'avatar': 'https://wpimg.wallstcn.com/f778738c-e4f8-4870-b634-56703b4acafe.gif',
        'name': 'Proxy Tower'
    }


conf = Config()
