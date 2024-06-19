FROM python:3.12-alpine

WORKDIR /usr/src/app

SHELL [ "/bin/ash", "-eo", "pipefail", "-c" ]

# hadolint ignore=DL3018
RUN apk add --no-cache gcc libc-dev libffi-dev

COPY requirements.txt ./
RUN pip install --no-cache-dir -r ./requirements.txt
# Wavelink is dependant on discord.py, so we need to uninstall it and install py-cord
RUN pip uninstall discord.py py-cord -y && pip install --no-cache-dir "py-cord[voice]==$(grep 'py-cord\[voice\]' requirements.txt | awk -F'==' '{print $2}')"

COPY . .

CMD [ "python", "-Bu", "./main.py"]
