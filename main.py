from multiprocessing import Process, Queue
from queue import Empty
import os
import pyaudio
import wave
import pyglet
import json
import requests
from vad import VoiceActivityDetector

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 1

from aip import AipSpeech
APP_ID = '10696597'
API_KEY = 'ogFTc19BzwkdOihXwsGMsj70'
SECRET_KEY = '0a517f5897a7901082d1623eec940722'

def listen_proc(q):
	print('Hello, I am listen process' + str(os.getpid()))
	p = pyaudio.PyAudio()
	stream = p.open(format=FORMAT,
					channels=CHANNELS,
					rate=RATE,
					input=True,
					frames_per_buffer=CHUNK)

	while True:
		frames = []
		for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
			data = stream.read(CHUNK)
			frames.append(data)
		q.put(frames)

def exit_callback(dt):
    pyglet.app.exit()

def analyze_proc(voice):
	#print('Hello, I am analyze process' + str(os.getpid()))
	aipSpeech = AipSpeech(APP_ID, API_KEY, SECRET_KEY)
	info = aipSpeech.asr(b''.join(voice), 'pcm', RATE)
	if info['err_no'] == 0:
		print('question: ' + info['result'][0])

		data = {'key':'50d6624f41424826807103b1a76a8f6e',
				'info' : info['result'][0],
				'userid' : '123456'}
		r = requests.post('http://www.tuling123.com/openapi/api', data=data)
		sentence = r.json()['text']
		print('answer: ' + sentence)
		aipSpeech = AipSpeech(APP_ID, API_KEY, SECRET_KEY)
		result  = aipSpeech.synthesis(sentence, 'zh', 1)
		if not isinstance(result, dict):
			with open('auido.mp3', 'wb') as f:
				f.write(result)
			music = pyglet.resource.media('auido.mp3', streaming=False)
			music.play()
			pyglet.clock.schedule_once(exit_callback , music.duration)
			pyglet.app.run()


def gui_proc():
	print('Hello, I am gui process' + str(os.getpid()))

if __name__=='__main__':
	print('Hello, I am main process' + str(os.getpid()))

	voice_q = Queue()
    
	listen = Process(target=listen_proc, args=(voice_q,))
    
	listen.start()

	p = pyaudio.PyAudio()
	voice = []


	count = 0

	while True:
		frames = voice_q.get(True)

		voice += frames

		voice = voice[-int(RATE / CHUNK * RECORD_SECONDS) * 10:]

		wf = wave.open('2seconds.wav', 'wb')
		wf.setnchannels(CHANNELS)
		wf.setsampwidth(p.get_sample_size(FORMAT))
		wf.setframerate(RATE)
		wf.writeframes(b''.join(frames))
		wf.close()

		v = VoiceActivityDetector('2seconds.wav')
		print(sum([_[1] for _ in v.detect_speech()]))
		if sum([_[1] for _ in v.detect_speech()]) < 3:
			count += 1
			if count > 1:
				analyze = Process(target=analyze_proc, args=(voice, ))
				analyze.start()
				voice = []
		else:
			count = 0