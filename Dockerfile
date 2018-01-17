# FROM python:3.5-alpine
FROM python:2.7-alpine

RUN apk add --update py-psutil linux-headers python-dev py-pip build-base gcc && rm -rf /var/cache/apk/*

ADD requirements.txt /
RUN pip install -r requirements.txt

ADD main.py /
ADD runbook.json /

ENV SLACK_TOKEN="supersecretslackbotapitokenthing"
ENV SLACK_CHANNEL="lost+found"
ENV SLACK_AS_USER="doubledragon"

EXPOSE 5000

CMD [ "python", "./main.py" ]
