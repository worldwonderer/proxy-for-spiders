import json

from aiohttp import ClientResponse


class FailedResponse(object):
    pass


class Response(ClientResponse):

    proxy = None
    valid = None
    traceback = None

    def get_encoding(self):
        encoding = super(Response, self).get_encoding()
        if encoding == 'gb2312':
            encoding = 'gbk'
        return encoding

    async def info(self):
        text = await self.text()
        return json.dumps({
            'url': str(self.url),
            'status_code': self.status,
            'valid': self.valid,
            'text': text,
            'proxy': str(self.proxy)
        })

