FROM ubuntu:14.04

RUN apt-get update -qq && apt-get install -y \
	build-essential \
	libffi-dev \
	libssl-dev \
	python \
	python-pip \
	python-dev

ADD . /app

RUN pip install -r /app/requirements.txt
