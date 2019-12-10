FROM python:3.6


MAINTAINER worldwonderer <xtchen.pitt@gmail.com>


ENV TZ Asia/Shanghai


WORKDIR /usr/src/app


COPY ./requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/


RUN mkdir log/


COPY . .


EXPOSE 8893


WORKDIR /usr/src/app


ENTRYPOINT [ "python", "proxy_entrance.py" ]

