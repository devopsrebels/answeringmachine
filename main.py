from __future__ import print_function  # In python 2.7

import json
import io
import os
import sys
import time
import urllib
from time import gmtime, strftime

from celery import Celery
from flask import Flask, request
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from slacker import Slacker
from twilio.twiml.voice_response import VoiceResponse

slack_token = os.environ['SLACK_TOKEN']
slack_channel = os.environ['SLACK_CHANNEL']
slack_as_user = os.environ['SLACK_AS_USER']

redis_url = os.environ['REDIS_URL']

slack = Slacker(slack_token)
app = Flask(__name__)

app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

voicemail_dir = os.environ['VOICEMAIL_DIR']

runbook = os.environ['RUNBOOK']
text = json.load(open(runbook))


@celery.task(bind=True)
def getVoicemail(self, language, voicemailUrl, caller):
    with app.app_context():
        print("In app.app_context of getVoicemail")
        attempts = 0
        current_time = strftime("%Y-%m-%d_%H-%M-%S", gmtime())
        assert isinstance(current_time, object)
        voicemail_file = "{0}".format(str(caller + '-' + current_time))

        if not os.path.exists(voicemail_dir):
            os.makedirs(voicemail_dir)

        while attempts < 3:
            try:
                print("Trying to download voicemail...")
                time.sleep(3)
                urllib.urlretrieve(url=voicemailUrl, filename="{0}{1}.wav".format(voicemail_dir, voicemail_file))
                break
            except Exception, e:
                print("An error occured trying to download the voicemail, we will try again...")
                print(e)
                attempts += 1
                print("Retrieving voicemail failed for %s times: %s", attempts, e.message)
        print("Transcribing voicemail with transcribeVoicemail.apply_assync")
        transcribeVoicemail.apply_async(args=[language, voicemail_dir + voicemail_file + '.wav'])


@celery.task(bind=True)
def transcribeVoicemail(self, language, audiofile):
    global languageCode
    if language == "Dutch":
        languageCode = 'nl-NL'
    elif language == "English":
        languageCode = 'en-US'

    print('Inside transcribeVoicemail')
    with app.app_context():
        print('Inside app.app_context')

        try:
            text = transcribe(language=languageCode, audiofile=audiofile)
            print("Trying to send to slack")
            slack.files.upload(file_=audiofile,
                               filetype='mp3',
                               filename=audiofile,
                               channels=slack_channel,
                               initial_comment=str(text))
            return text
        except Exception, e:
            print('Transcription went wrong: %s', e)
            print("Will send to slack.")
            slack.files.upload(file_=audiofile,
                               filetype='wav',
                               filename=audiofile,
                               channels=slack_channel,
                               initial_comment=str('A voicemail has been left behind'))
            return


# Transcribe function
def transcribe(language, audiofile):
    # Instantiates a client
    print('inside transcribe function ' + language + ' ' + audiofile)
    gclient = speech.SpeechClient()

    # Loads the audio into memory
    with io.open(audiofile, 'rb') as audio_file:
        print('inside io.open')
        content = audio_file.read()
        audio = types.RecognitionAudio(content=content)

        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            language_code=language)

        # Detects speech in the audio file
        response = gclient.recognize(config, audio)
        print('just after response')

        for result in response.results:
            transcribedText = 'Transcript: {}'.format(result.alternatives[0].transcript)
            print('Transcript: {}'.format(result.alternatives[0].transcript))
            return str(transcribedText)


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
    slack.chat.post_message('#phonecalls', '{0} is calling us.', number)
    with resp.gather(num_digits=1, action='/start-recording', method='POST', timeout=15) as g:
        g.say(text['introduction'])

    return str(resp)


@app.route("/start-recording", methods=["GET", "POST"])
def startRecording():
    resp = VoiceResponse()

    if 'Digits' in request.values and request.values['Digits'] == '1':
        slack.chat.post_message('#phonecalls', '{0} has chosen to leave a dutch message.', request.values.get('From', None))
        resp.record(max_length=120, play_beep=True, action="/end-call-dutch")
    elif 'Digits' in request.values and request.values['Digits'] == '2':
        slack.chat.post_message('#phonecalls', '{0} has chosen to leave an English message.', request.values.get('From', None))
        resp.record(max_length=120, play_beep=True, action="/end-call-english")
    else:
        slack.chat.post_message('#phonecalls', '{0} is detonating an A-Bomb!', request.values.get('From', None))
        resp.say(text['recording'])
        resp.gather(num_digits=1, action='/start-recording', timeout=15)

    return str(resp)


@app.route("/end-call-dutch", methods=["GET", "POST"])
def endCalldutch():
    voicemailUrl = request.values.get("RecordingUrl", None)
    caller = request.values.get("From", None)
    getVoicemail.apply_async(args=['Dutch', voicemailUrl, caller])
    resp = VoiceResponse()
    resp.say(text['dutchending'])
    resp.hangup()

    return str(resp)


@app.route("/end-call-english", methods=["GET", "POST"])
def endCallenglish():
    voicemailUrl = request.values.get("RecordingUrl", None)
    caller = request.values.get("From", None)
    getVoicemail.apply_async(args=['English', voicemailUrl, caller])
    resp = VoiceResponse()
    resp.say(text['englishending'])
    resp.hangup()

    return str(resp)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
