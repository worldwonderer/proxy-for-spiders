import json

from aiohttp import ClientResponse


class FailedResponse(object):
    cancelled = False
    proxy = None
    valid = False
    traceback = None


class Response(ClientResponse):
    proxy = None
    valid = None
    traceback = None
    cancelled = False

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
            'traceback': self.traceback
        })
