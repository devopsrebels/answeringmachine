# FROM python:3.5-alpine
FROM python:2.7-alpine

RUN apk add --update py-psutil linux-headers python-dev py-pip build-base gcc && rm -rf /var/cache/apk/*

ADD requirements.txt /
RUN pip install -r requirements.txt

ADD main.py /
ADD runbook.json /
ADD transcribefunction.py /

ENV SLACK_TOKEN="supersecretslackbotapitokenthing"
ENV SLACK_CHANNEL="phonecalls"
ENV SLACK_AS_USER="doubledragon"
ENV REDIS_URL="redis://redis:6379/0"
ENV ALERT_SYSTEM="slack"
ENV VOICEMAIL_DIR="voicemails/"
ENV BUCKET_NAME="my-awesome-voicemails"
ENV BUCKET_FOLDER='voicemails'
ENV RUNBOOK="runbook.sample.json"

EXPOSE 5000

CMD [ "python", "./main.py" ]
