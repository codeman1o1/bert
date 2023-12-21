# https://github.com/aio-libs/aiohttp/issues/7675#issuecomment-1812900722
FROM python:3.12-alpine

WORKDIR /usr/src/app

COPY . .

RUN apk add --no-cache gcc libc-dev libffi-dev

RUN pip install --no-cache-dir -r ./requirements.txt

# Wavelink being wavelink
RUN pip uninstall py-cord -y && pip install --no-cache-dir -r ./requirements.txt

CMD [ "python", "./main.py"]
