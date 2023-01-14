FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt-get -y install software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get -y install \
      inotify-tools \
      nodejs \
      npm \
      python3.11 \
      python3-pip

WORKDIR /captain

COPY requirements.txt .
COPY dev.requirements.txt .
RUN python3 -m pip install -r dev.requirements.txt

WORKDIR /captain/web

COPY web/package*.json .
RUN npm install

RUN mkdir -p ~/.captain/downloads

