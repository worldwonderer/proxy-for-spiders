import copy

from aiohttp import web

dashboard_data_template = {
    'code': 20000,
    'data': {
        'items': [],
        'total': 0
    }
}


async def dashboard(request):
    dashboard_router = {
        '/dev-api/patterns': patterns,
        '/dev-api/pattern': pattern,
        '/dev-api/proxies': proxies,
        '/dev-api/user/login': login,
        '/dev-api/user/logout': logout,
        '/dev-api/user/info': user_info,
        '/dev-api/status': status,
        '/dev-api/index': index,
        '/dev-api/config': config,
    }
    path = request.path
    if path in dashboard_router:
        return await dashboard_router[path](request)
    return web.Response(status=200, text="hello world")


async def patterns(request):
    r = copy.deepcopy(dashboard_data_template)
    items = await request.app['pam'].patterns(format_type='dict')
    r['data']['items'] = items
    r['data']['total'] = len(items)
    return web.json_response(data=r)


async def proxies(request):
    if request.method == 'GET':
        r = copy.deepcopy(dashboard_data_template)
        pattern_str = request.query.get('pattern', 'public_proxies')
        items = await request.app['pom'].proxies(pattern_str=pattern_str, format_type='dict')
        r['data']['items'] = items
        r['data']['total'] = len(items)
        return web.json_response(data=r)
    elif request.method == 'DELETE':
        pattern_str = request.query.get('pattern', 'public_proxies')
        await request.app['pom'].clean_proxies(pattern_str=pattern_str)
        return web.json_response(data={'code': 20000, 'message': 'success'})


async def login(request):
    info = await request.json()
    username, password = info['username'], info['password']
    if username == 'admin' and password == request.app['config'].secret:
        return web.json_response(data={'code': 20000, 'data': {'token': 'admin'}})
    else:
        return web.json_response(data={'code': 60204, 'message': 'Account and password are incorrect.'})


async def logout(request):
    return web.json_response(data={'code': 20000, 'message': 'success'})


async def status(request):
    r = copy.deepcopy(dashboard_data_template)
    x, items = request.app['pam'].status()
    r['data']['items'] = items
    r['data']['x'] = x
    r['data']['total'] = len(r['data']['items'])
    return web.json_response(data=r)


async def index(request):
    data = {
        'proxy_count': await request.app['pom'].proxy_count('public_proxies'),
        'pattern_count': await request.app['pam'].pattern_count(),
        'success_requests': request.app['sv'].success_count,
        'total_requests': request.app['sv'].total_count
    }
    return web.json_response(data={'code': 20000, 'data': data})


async def user_info(request):
    return web.json_response(data={'code': 20000, 'data': request.app['config'].admin_token})


async def pattern(request):
    d = await request.json()
    if request.method == 'POST':
        await request.app['pam'].add(d['pattern'], d['rule'], d['value'])
    elif request.method == 'DELETE':
        await request.app['pam'].delete(d['pattern'])
    return web.json_response(data={'code': 20000, 'message': 'success'})


async def config(request):
    fields = ['mode', 'pool_size', 'concurrent', 'timeout']
    if request.method == 'GET':
        data = dict()
        for k in fields:
            if hasattr(request.app['config'], k):
                data[k] = getattr(request.app['config'], k)
        return web.json_response(data={'code': 20000, 'data': data})
    else:
        data = await request.json()
        for k in data:
            if k in fields:
                setattr(request.app['config'], k, data[k])
        return web.json_response(data={'code': 20000, 'message': 'success'})
