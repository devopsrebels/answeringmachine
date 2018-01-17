# Super awesome twilio based Answering Machine

## Tha fuq is dis?!
Well it's a super awesome answering machine relying on Twilio, Google and Slack of course!
Someone calls you, [Twilio](https://www.twilio.com) asks what to do, the super awesome answering machine replies with a [TwiML](https://www.twilio.com/docs/api/twiml) and your callers can start talking.
The super awesome answering machine will then download the voicemail, stick it into some [google speech API hole](https://cloud.google.com/speech/) and gets some jibberish back, which the super awesome answering machine
will then shout to a [Slack](https://slack.com) channel of your liking!

## Requirements

### API's
* Twilio account + phone number (and credits)
* Google Speech API account (active the API in your google cloud account)
* Slack + Legacy API token.

### Tools
* Python 2.7 (twilio API doesn't work nice with 3.X)
* Redis KV store (used for async tasks, think pub/sub)
* Docker is recommended
* gunicorn (not needed but recommended, any other WSGI should work too)
* [google-cloud-sdk](https://cloud.google.com/sdk/downloads) library and account configuration

### Libraries
* Flask
* slacker
* twilio
* celery
* google.cloud
* redis

Check requirements.txt for python libs

#### Configuration options (environment variables)
* ```SLACK_TOKEN=xoxp-blablabla```
* ```SLACK_AS_USER=answerbot``` (doesn't work anymore since legacy tokens)
* ```SLACK_CHANNEL=voicemails```
* ```REDIS_URL=redis://localhost:6379/0```
* ```VOICEMAIL_DIR=/voicemails/```
* ```RUNBOOK=runbook.json```

Above are of course just examples fill in with your own settings.

## Run
### Commandline (no docker)

#### Description
The super awesome answering machine executes with two commands, one for the actually (flask-based) webservice and one
for the celery based tasks. This is because the actual download and transcribtion of the voicemail
is a blocking request causing long waits for your callers. Celery is used to create async calls
to download the voicemail file, transcribe it via google and upload it to slack.

It also assumes you installed the google-cloud-sdk (see Requirements from this README).

#### Execution
* Rename runbook.sample.json to runbook.json: ```mv runbook.sample.json runbook.json```
* Install libraries that are needed, there is no strict versioning in the requirements.txt so latest and greatest: ```pip install -r requirements.txt```
* To start the webservice: ```gunicorn -b 0.0.0.0:5000 wsgi```
* To start the celery worker: ```celery -A main.celery worker```

The above is indeed a bit dirty, when I feel to it, I'll change this into seperate code.

This will run on any IP on your machine on port 5000 so a ```curl -Li http://localhost:5000``` should give you a [TwiML](https://www.twilio.com/docs/api/twiml) response.

### Docker
#### Description
A Dockerfile is included so you can create your own docker image like: ```docker build -t awesomeness/answermachine .```
This creates a single image that, depending on the command you give it will run either the webservice or a worker instance, when no command (CMD) )is given the default will be used
as defined in the Dockerfile.

#### Execution
* Rename runbook.sample.json to runbook.json: ```mv runbook.sample.json runbook.json```
* Build the docker image if not already done so: ```docker build -t awesomeness/answermachine .```
* To start Redis: ```docker run --rm -d -p 6379:6379 --name redis redis```
* To start the webservice: ```docker run --name answermachine --mount source=voicemails,target=/voicemails --link redis:redis -e SLACK_TOKEN=xoxp-blabla -e SLACK_AS_USER=blaat -e SLACK_CHANNEL=voicemails -e REDIS_URL=redis://redis:6379/0 -e VOICEMAIL_DIR=/voicemails/ -p 5000:5000 awesomeness/answermachine```
* To start the Celery worker node: ```docker run --mount source=voicemails,target=/voicemails --link redis:redis -e SLACK_TOKEN=xoxp-blabla -e SLACK_AS_USER=blaat -e SLACK_CHANNEL=voicemails -e REDIS_URL=redis://redis:6379/0 -e VOICEMAIL_DIR=/voicemails/ awesomeness/answermachine celery -A main.celery worker```

This should start the whole system, if you run it on your laptop make sure to add some NAT (port forwarding) on your home/SOHO router and use your IP address as address in Twilio.



