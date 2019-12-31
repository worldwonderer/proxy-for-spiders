import json

from aiohttp import ClientResponse


class FailedResponse(object):

    def __init__(self):
        self.traceback = list()


class Response(ClientResponse):

    proxy = None
    valid = None
    traceback = list()

    def get_encoding(self):
        encoding = super(Response, self).get_encoding()
        if encoding == 'gb2312':
            encoding = 'gbk'
        return encoding

    async def info_json(self):
        text = await self.text()
        return json.dumps({
            'url': str(self.url),
            'status_code': self.status,
            'valid': self.valid,
            'text': text,
            'proxy': str(self.proxy),
            'traceback': ''.join(self.traceback)
        })
