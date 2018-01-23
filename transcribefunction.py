from __future__ import print_function  # In python 2.7

import os
import time
import urllib
from time import gmtime, strftime

from flask import Flask, request
from celery import Celery
from google.cloud import speech
from google.cloud import storage
from google.cloud.speech import enums
from google.cloud.speech import types
from slackclient import SlackClient

bucket_name = os.environ['BUCKET_NAME']
bucket_folder = os.environ['BUCKET_FOLDER']
redis = os.environ['REDIS_URL']
voicemail_dir = os.environ['VOICEMAIL_DIR']
create_voicemail_message = Celery('createvoicemailmessage', broker=redis)

app = Flask(__name__)


class Transcribevoicemail(object):
    def __init__(self):
        self.alert_system = str(os.environ['ALERT_SYSTEM']).lower()
        self.slack_token = str(os.environ['SLACK_TOKEN'])
        self.slack_channel = str(os.environ['SLACK_CHANNEL'])

        self.client = speech.SpeechClient()
        self.storageclient = storage.Client()

    def download(self, audiofile, callerID):
        attempts = 0
        current_time = strftime("%Y-%m-%d_%H-%M-%S", gmtime())
        voicemail_file = '{0}'.format(str(callerID + '-' + current_time))

        if not os.path.exists(voicemail_dir):
            os.makedirs(voicemail_dir)

        while attempts < 3:
            try:
                time.sleep(5)
                urllib.urlretrieve(url=audiofile, filename='{}{}.wav'.format(voicemail_dir, voicemail_file))
                break
            except Exception, e:
                print('An error occured downloading the file: {} with reason: {}'.format(audiofile, e))
                attempts += 1
        local_audiofile = '{}{}'.format(voicemail_file, '.wav')
        return local_audiofile

    def upload(self, bucket_name, audiofile):
        bucket = self.storageclient.get_bucket(bucket_name=bucket_name)
        blob = bucket.blob(blob_name='{}/{}'.format(bucket_folder, audiofile))

        try:
            blob.upload_from_filename('{}{}'.format(voicemail_dir, audiofile))
            print('{} has been uploaded to: {}/{}'.format(audiofile, bucket_name, bucket_folder))
            print('{}{}/{}'.format('gs://', bucket_name, audiofile))
            print('Public URL is: %s' % str(blob.public_url))
            return str('{}{}/{}/{}'.format('gs://', bucket_name, bucket_folder, audiofile)), blob.public_url
        except Exception as e:
            print('Uploading {} to {} had an error: {}'.format(audiofile, bucket_name, e))

    def transcribe(self, language, gcs_uri):
        global response
        audio = types.RecognitionAudio(uri=gcs_uri)
        config = types.RecognitionConfig(encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
                                         sample_rate_hertz=8000,
                                         language_code=language)

        print('Start longrunning recognize job...{}'.format(audio))
        try:
            assert isinstance(audio, object)
            operation = self.client.long_running_recognize(config, audio)
            response = operation.result(timeout=300)
            for result in response.results:
                transcribedText = 'Transcript: {}'.format(result.alternatives[0].transcript)
                return str(transcribedText).encode('utf-8')
        except Exception as e:
            print(e)
            return str('Voicemail could not be transcribed, reason: {}'.format(e))

    def sendSlack(self, text, audiofile, callerID):
        sc = SlackClient(self.slack_token)
        print(audiofile)
        try:
            sc.api_call('files.upload', channels=self.slack_channel, filename=audiofile, file=open(audiofile, 'rb'),
                    filetype='wav', initial_comment=str(text).encode('utf-8'),
                    title='A voicemail has been left by {}'.format(
                        callerID))
        except Exception, e:
            print('Could not send to Slack due to the following error: {}'.format(e))
            pass

        print('%s %s' % (text, callerID))

    def sendVoicemail(self, text, audiofile, callerID):
        print(self.alert_system, text, callerID)

        if self.alert_system == 'slack':
            self.sendSlack(text=text, audiofile=audiofile, callerID=callerID)
        elif self.alert_system == 'telegram':
            print('Telegram has been chosen.')
        elif self.alert_system == 'email':
            print('Email has been chosen.')
        else:
            print('No alert system has been chosen!')
        return


@create_voicemail_message.task
def createvoicemailmessage(language, audiofile, callerID):
    voicemail = Transcribevoicemail()
    local_audiofile = voicemail.download(audiofile=audiofile, callerID=callerID)
    gcs_uri = (voicemail.upload(bucket_name=bucket_name, audiofile=local_audiofile))
    transcribed_text = voicemail.transcribe(language=language, gcs_uri=str(gcs_uri[0]))
    voicemail.sendVoicemail(text=transcribed_text, audiofile='{}{}'.format(voicemail_dir, local_audiofile), callerID=callerID)
