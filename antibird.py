'''
Script to schedule playback from volumio: https://volumio.com
volumio API: https://volumio.github.io/docs/API/REST_API.html
Tested on Raspberry Pi 3B with volumio image: https://volumio.com/en/get-started/
'''
import datetime
import json
import os
import requests
import socket
import time

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

### Set on/off times in pairs of (hour, minute) in 24-hr format
### Set shotdown to True to shutdown machine after play has finished

### Scare away birds around sunrise and sunset
ANTIBIRD_SCHEDULE = [
    # on time  off time  shutdown?
    [(5, 40),  (8, 0),   True],
    [(16, 30), (18, 15), True],
]

POLL_TIME_SEC = 15
MIN_VOLUME = 10
MAX_VOLUME = 50

#//////////////////////////////////////////////////////////////////////////////
#////////////////// VOLUMIO DEFINITIONS ///////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

CLEAR_QUEUE = 'clearQueue'
GET_STATE = 'getState'
GET_SYSINFO = 'getSystemInfo'
PLAY_SONG = 'replaceAndPlay'
STOP_PLAY = 'commands/?cmd=stop'
START_PLAY = 'commands/?cmd=play'
SET_VOLUME = 'commands/?cmd=volume&volume={volume}'
PING = 'ping'

### change 'volumio' if you changed the host name
if socket.gethostname() == 'volumio':
    HOSTPORT = 'localhost:3000'
else:
    HOSTPORT = 'volumio.local'

VOLUMIO_URL_BASE = 'http://{hostport}/api/v1/'.format(hostport=HOSTPORT)
VOLUMIO_URL = VOLUMIO_URL_BASE + '{cmd}'

### Post data used to start playing media
'''
To get the data you need for your application:
1. Play your media manually (e.g., via web interface or Andoid app)
2. Call the function get_cmd(GET_STATE) to get the fields you need
'''

ANTIBIRD_DATA = {
    ### https://www.youtube.com/watch?v=6IyZLTIcy5U
    "uri": "mnt/INTERNAL/antibird_3hrs.mp3",
    "service": "mpd",
    "title": "antibird_3hrs",
    "artist": "Milleaccendini",
    "album": "Birds Away",
    "type": "song",
    "tracknumber": 0,
    "duration": 0,
    "trackType": "mp3",
}

RP_DATA = {
    ### Example of how to play webstream
    "albumart" : "https://radio-directory.firebaseapp.com/volumio/src/images/radio-thumbnails/Radio Paradise.jpg",
    "artist" : "Radio Paradise (192k Ogg/Vorbis) - playlist: radioparadise.com",
    "service" : "webradio",
    "status" : "play",
    "stream" : "True",
    "trackType" : "webradio",
    "updatedb" : "False",
    "uri" : "http://stream-dc1.radioparadise.com/rp_192m.ogg",
}

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def _print_dict(d):
    for k in sorted(d.keys()):
        print('{} : {}'.format(k, d[k]))

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def _response_to_result(response):
    result = {'status':'fail', 'error':'unknown'}
    # print('response.status_code: {}'.format(response.status_code))
    if response.status_code == 200 or response.status_code == 201:
        if 'Content-Type' in response.headers and response.headers['Content-Type'][:16] == 'application/json':
            result = json.loads(response.text)
        else:
            result = {'status':'ok', 'data':response.text}
    elif response.reason is not None:
        result['error'] = response.reason
    return result

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def start_play(media_data):
    response = requests.request("GET", VOLUMIO_URL.format(cmd=STOP_PLAY))
    print('STOP_PLAY: {}'.format(_response_to_result(response)))

    headers = {'Content-type': 'application/json'}
    response = requests.request("POST", VOLUMIO_URL.format(cmd=PLAY_SONG), headers=headers, data=json.dumps(media_data))
    print('PLAY_SONG: {}'.format(_response_to_result(response)))

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def get_volume():
    response = requests.request("GET", VOLUMIO_URL.format(cmd=GET_STATE))
    try:
        result = _response_to_result(response)
        return result['volume']
    except Exception as ex:
        print('get_volume: {}'.format(str(ex)))
    return -1

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def set_volume(level):
    url = VOLUMIO_URL.format(cmd=SET_VOLUME.format(volume=level))
    response = requests.request("GET", url)
    print('SET_VOLUME: {}'.format(_response_to_result(response)))

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def get_cmd(what):
    response = requests.request("GET", VOLUMIO_URL.format(cmd=what))
    print('{}: {}'.format(what, _response_to_result(response)))

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def get_time_now():
    now = datetime.datetime.now()
    return now.hour * 60 + now.minute

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def ramp_volume(start_level, end_level, step_level, step_secs):

    direction = 'UP' if end_level > start_level else 'DOWN'

    def is_finished(level):
        if level >= 0:
            if direction == 'UP':
                return level >= end_level
            else:
                return level <= end_level
        return False

    if start_level >= 0:
        set_volume(start_level)
    level_now = get_volume()
    while(not is_finished(level_now)):
        time.sleep(step_secs)
        if level_now >= 0:
            set_volume(level_now + step_level)
        level_now = get_volume()

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

def run_schedule(schedule, media_data):
    print('Starting at {}'.format(get_time_now()))

    playing_now = False
    shutdown_after_stop = False
    while(True):
        play_should_stop = True
        minutes = get_time_now()
        for ontime_pair, offtime_pair, shutdown_after in schedule:
            ### convert on/off times to minutes
            ontime  = ontime_pair[0]*60 + ontime_pair[1]
            offtime = offtime_pair[0]*60 + offtime_pair[1]
            if minutes >= ontime and minutes < offtime:
                play_should_stop = False
                if not playing_now:
                    try:
                        set_volume(1)
                        start_play(media_data)
                        ramp_volume(MIN_VOLUME, MAX_VOLUME, 1, 5)
                        playing_now = True
                        shutdown_after_stop = shutdown_after
                    except Exception as ex:
                        print('Command failed: {}'.format(str(ex)))

        if playing_now and play_should_stop:
            try:
                ramp_volume(-1, MIN_VOLUME, -1, 5)
                get_cmd(STOP_PLAY)
                playing_now = False
                if shutdown_after_stop:
                    ### Only shutdown if running on the volumio host
                    if 'localhost' in HOSTPORT:
                        print('Shutting down in one minute..')
                        os.system('sudo /sbin/shutdown +1')
                    else:
                        print('Skipping shutdown for host {}'.format(HOSTPORT))
            except Exception as ex:
                print('Command failed: {}'.format(str(ex)))
        time.sleep(POLL_TIME_SEC)

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////

if __name__ == "__main__":
    ### Go away birds
    run_schedule(ANTIBIRD_SCHEDULE, ANTIBIRD_DATA)

#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
#//////////////////////////////////////////////////////////////////////////////
