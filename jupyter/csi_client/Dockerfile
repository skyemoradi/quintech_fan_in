FROM ubuntu:22.04 AS builder

# update os and install packages
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -y \
  && apt-get -y upgrade \
  && apt-get install -y redis-tools software-properties-common curl

# add MITRE certs
RUN curl http://pki.mitre.org/MITRE%20BA%20Root.crt >> /etc/ssl/certs/ca-certificates.crt \
  && curl  http://pki.mitre.org/MITRE%20BA%20NPE%20CA-1.crt >> /etc/ssl/certs/ca-certificates.crt \
  && curl "http://pki.mitre.org/MITRE%20BA%20NPE%20CA-3(1).crt" >> /etc/ssl/certs/ca-certificates.crt \
  && curl  http://pki.mitre.org/ZScaler_Root.crt >> /etc/ssl/certs/ca-certificates.crt

# add deadsnakes repo, python 3.10 and cleanup
RUN add-apt-repository ppa:deadsnakes/ppa -y \
  && apt-get update -y \
  && apt-get install -y python3.10 python3-venv git \
  && apt-get autoremove -y \
  && apt-get clean

# poetry uses VIRTUAL_ENV if defined
ENV VIRTUAL_ENV=/opt/venv

# update path to use python from the virtual environment.
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# add poetry to path
ENV PATH="/opt/poetry/bin:$PATH"

# set working directory
WORKDIR /usr/local/src

# create python virtual environment
# install poetry
# disable git user/owner warning
RUN python3.10 -m venv /opt/venv \
  && curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - \
  && poetry completions bash >> ~/.bash_completion \
  && git config --global --add safe.directory '*'
