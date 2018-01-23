from __future__ import print_function  # In python 2.7

import json
import os
import sys

from celery import Celery
from flask import Flask, request
from slackclient import SlackClient
from twilio.twiml.voice_response import VoiceResponse

import transcribefunction

slack_token = os.environ['SLACK_TOKEN']
slack_channel = os.environ['SLACK_CHANNEL']
slack_as_user = os.environ['SLACK_AS_USER']

redis_url = os.environ['REDIS_URL']

sc = SlackClient(slack_token)
app = Flask(__name__)

app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

voicemail_dir = os.environ['VOICEMAIL_DIR']

runbook = os.environ['RUNBOOK']
text = json.load(open(runbook))


def getVoicemail(language, audiofile, caller):
    print('hoi wereld')
    answer = transcribefunction
    answer.createvoicemailmessage.apply_async(args=[language, audiofile, caller])
    return

@app.route("/health", methods=["GET"])
def health():
    return str("Healty")

@app.route("/", methods=["GET", 'POST'])
def intro():
    resp = VoiceResponse()
    number = request.values.get('From', None)
    status = request.values.get('CallStatus', None)
    print(number, file=sys.stderr)
    print(status, file=sys.stderr)
    slacktext = 'Hi I am calling you!'
    sc.api_call('chat.postMessage', channel=slack_channel, text=slacktext, username=number, icon_emoji=':phone:')
    with resp.gather(num_digits=1, action='/start-recording', method='POST', timeout=15) as g:
        g.say(text['introduction'])

    return str(resp)


@app.route("/start-recording", methods=["GET", "POST"])
def startRecording():
    resp = VoiceResponse()

    if 'Digits' in request.values and request.values['Digits'] == '1':
        caller = request.values.get("From", None)
        slacktext = '{} pressed 1 and should speak in Dutch.'.format(caller)
        sc.api_call('chat.postMessage', channel=slack_channel, text=slacktext, username=caller, icon_emoji=':phone:')
        resp.record(max_length=120, play_beep=True, action="/end-call-dutch")
    elif 'Digits' in request.values and request.values['Digits'] == '2':
        caller = request.values.get("From", None)
        slacktext = '{} pressed 2 and should speak in English.'.format(caller)
        sc.api_call('chat.postMessage', channel=slack_channel, text=slacktext, username=caller, icon_emoji=':phone:')
        resp.record(max_length=120, play_beep=True, action="/end-call-english")
    else:
        caller = request.values.get("From", None)
        slacktext = '{} punched his phone and should learn to listen.'.format(caller)
        sc.api_call('chat.postMessage', channel=slack_channel, text=slacktext, username=caller, icon_emoji=':phone:')
        resp.say(text['recording'])
        resp.gather(num_digits=1, action='/start-recording', timeout=15)

    return str(resp)


@app.route("/end-call-dutch", methods=["GET", "POST"])
def endCalldutch():
    voicemailUrl = request.values.get("RecordingUrl", None)
    caller = request.values.get("From", None)
    getVoicemail(language='nl-NL', audiofile=voicemailUrl, caller=caller)
    resp = VoiceResponse()
    resp.say(text['dutchending'])
    resp.hangup()

    return str(resp)


@app.route("/end-call-english", methods=["GET", "POST"])
def endCallenglish():
    voicemailUrl = request.values.get("RecordingUrl", None)
    caller = request.values.get("From", None)
    getVoicemail(language='en-GB', audiofile=voicemailUrl, caller=caller)
    resp = VoiceResponse()
    resp.say(text['englishending'])
    resp.hangup()

    return str(resp)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
