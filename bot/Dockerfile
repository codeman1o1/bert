FROM python:3.11-alpine

WORKDIR /usr/src/app

# hadolint ignore=DL3018
RUN apk add --no-cache gcc libc-dev libffi-dev

COPY requirements.txt ./

RUN pip install --no-cache-dir -r ./requirements.txt

# Wavelink being wavelink
RUN pip uninstall py-cord -y && pip install --no-cache-dir -r ./requirements.txt

COPY . .

CMD [ "python", "-Bu", "./main.py"]
