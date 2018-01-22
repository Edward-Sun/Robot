from multiprocessing import Process, Queue
from queue import Empty
import os
import pyaudio
import wave
import json
import requests
import collections
import sys
import webrtcvad
import random
import numpy
import cv2
import vadhelper
vad = webrtcvad.Vad()
vad.set_mode(3)


CHUNK = 4000
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 0.5

def gui_listen_sample():
	r = random.random()
	if r < 0.91:
		return 'listen/00.avi'
	if r < 0.97:
		return 'listen/01.avi'
	if r <= 1.00:
		return 'listen/02.avi'

def gui_speak_sample():
	r = random.random()
	if r < 0.2:
		return 'speak/00.avi'
	if r < 0.4:
		return 'speak/01.avi'
	if r < 0.6:
		return 'speak/02.avi'
	if r < 0.8:
		return 'speak/03.avi'
	if r < 1.0:
		return 'speak/04.avi'

def manager_proc(manager_q, speak_q, PV, gui_q, status_on_q):
	speak = Process(target=speak_proc, args=(speak_q, PV, gui_q, status_on_q))
	speak.start()
	while manager_q.get(True) != 0:
		speak.terminate()
		while not PV.empty():
			PV.get(True)
		speak = Process(target=speak_proc, args=(speak_q, PV, gui_q, status_on_q))
		speak.start()

def listen_proc(voice_q):
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
		voice_q.put(frames)



def analyze_proc(voice, speak_q, PV, manager_q, status_on_q):
	print('Hello, I am analyze process' + str(os.getpid()))
	p = pyaudio.PyAudio()
	wf = wave.open('question.wav', 'wb')
	wf.setnchannels(CHANNELS)
	wf.setsampwidth(p.get_sample_size(FORMAT))
	wf.setframerate(RATE)
	wf.writeframes(b''.join(voice))
	wf.close()
	p.terminate()

	os.system('question.exe')
	fq = open('question.txt', 'r', encoding="utf-8")
	question = fq.readline().strip()
	fq.close()

	if question != '':
		flag = status_on_q.get(True)
		status_on_q.put(flag)
		if flag:
			print('question:' + question)
			if PV.empty():	
				speak_q.put(question)
			else:
				manager_q.put(1)
				print('Terminate')
				speak_q.put(question)
		else:
			if '开机' in question:
				status_on_q.get(True)
				status_on_q.put(True)
				speak_q.put('initialization')



def speak_proc(speak_q, PV, gui_q, status_on_q):
	while True:
		question = speak_q.get(True)
		PV.put('PV')
		if '关机' in question:
			answer = '再见'
		elif 'initialization' in question:
			answer = '主人你好，我是爱酱'
		else:
			data = {'key':'50d6624f41424826807103b1a76a8f6e',
					'info' : question,
					'userid' : '123456'}
			r = requests.post('http://www.tuling123.com/openapi/api', data=data)
			answer = r.json()['text']
		print('answer: ' + answer)

		fa = open('answer.txt', 'w')
		fa.write(answer)
		fa.close()
		os.system('answer.exe')
		

		p = pyaudio.PyAudio()
		wf = wave.open('answer.wav', 'rb')
		stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
				channels=wf.getnchannels(),
				rate=wf.getframerate(),
				output=True)
		data = wf.readframes(CHUNK)
		count = 4
		while data != b'':
			if count == 4 and not 'initialization' in question:
				gui_q.put(1)
			count = (count % 4) + 1
			stream.write(data)
			data = wf.readframes(CHUNK)
		stream.stop_stream()
		stream.close()
		p.terminate()
		if '关机' in question:
			status_on_q.get(True)
			status_on_q.put(False)
		PV.get(True)

def gui_proc(gui_q, status_on_q):
	print('Hello, I am gui process' + str(os.getpid()))
	while True:
		flag = status_on_q.get(True)
		status_on_q.put(flag)
		if flag:
			f = 'hello.avi'
			cap = cv2.VideoCapture(f)
			while(cap.isOpened()):
				ret, frame = cap.read()
				if not(ret):
					break
				cv2.imshow("kizunaai", frame)
				if cv2.waitKey(33) == 27:
					status_on_q.get(True)
					flag = False
					status_on_q.put(flag)	
			cap.release()
			while flag:
				try:
					r = gui_q.get(False)
				except Empty:
					r = 0
				flag = status_on_q.get(True)
				status_on_q.put(flag)
				f = ''
				if r == 0:
					f = gui_listen_sample()
				elif r == 2:
					f = 'goodbye.avi'
				else:
					f = gui_speak_sample()
				cap = cv2.VideoCapture(f)
				while(cap.isOpened()):
					ret, frame = cap.read()
					if not(ret):
						break
					cv2.imshow("kizunaai", frame)
					if cv2.waitKey(33) == 27:
						status_on_q.get(True)
						flag = False
						status_on_q.put(flag)
				cap.release()
			f = 'goodbye.avi'
			cap = cv2.VideoCapture(f)
			while(cap.isOpened()):
				ret, frame = cap.read()
				if not(ret):
					break
				cv2.imshow("kizunaai", frame)
				if cv2.waitKey(33) == 27:
					status_on_q.get(True)
					flag = False
					status_on_q.put(flag)
			cap.release()
			cv2.destroyAllWindows()

if __name__=='__main__':
	print('Hello, I am main process' + str(os.getpid()))

	voice_q = Queue()
	speak_q = Queue()

	manager_q = Queue()
	PV = Queue()
	gui_q = Queue()
	status_on_q = Queue()

	status_on_q.put(False)

	gui = Process(target=gui_proc, args=(gui_q, status_on_q))
	gui.start()

	listen = Process(target=listen_proc, args=(voice_q, ))
	listen.start()

	manager = Process(target=manager_proc, args=(manager_q, speak_q, PV, gui_q, status_on_q))
	manager.start()

	p = pyaudio.PyAudio()
	voice = []

	flag = False

	while True:
		frames = voice_q.get(True)

		voice += frames

		voice = voice[-int(RATE / CHUNK * RECORD_SECONDS) * 10:]

		sample = list(vadhelper.frame_generator(30, b''.join(frames), RATE))
		segments = list(vadhelper.vad_collector(RATE, 30, 300, vad, sample))

		if len(segments) == 0:
			if flag:
				analyze = Process(target=analyze_proc, args=(voice, speak_q, PV, manager_q, status_on_q))
				analyze.start()
				flag = False
			voice = []
		else:
			flag = True