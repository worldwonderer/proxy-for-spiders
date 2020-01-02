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
    r = copy.deepcopy(dashboard_data_template)
    items = await request.app['pom'].proxies(format_type='dict')
    r['data']['items'] = items
    r['data']['total'] = len(items)
    return web.json_response(data=r)


async def login(request):
    # to be implemented
    return web.json_response(data={'code': 20000, 'data': 'admin'})


async def logout(request):
    # to be implemented
    return web.json_response(data={'code': 20000, 'data': 'success'})


async def status(request):
    r = copy.deepcopy(dashboard_data_template)
    x, items = request.app['pam'].status()
    r['data']['items'] = items
    r['data']['x'] = x
    r['data']['total'] = len(r['data']['items'])
    return web.json_response(data=r)


async def user_info(request):
    # to be implemented
    data = {
        'roles': ['admin'],
        'introduction': 'I am a super administrator',
        'avatar': 'https://wpimg.wallstcn.com/f778738c-e4f8-4870-b634-56703b4acafe.gif',
        'name': 'Super Admin'
    }
    return web.json_response(data={'code': 20000, 'data': data})


async def pattern(request):
    d = await request.json()
    if request.method == 'POST':
        await request.app['pam'].add(d['pattern'], d['rule'], d['value'])
    elif request.method == 'DELETE':
        await request.app['pam'].delete(d['pattern'])
    return web.json_response(data={'code': 20000, 'data': 'success'})