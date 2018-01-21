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

class Frame(object):
	"""Represents a "frame" of audio data."""
	def __init__(self, bytes, timestamp, duration):
		self.bytes = bytes
		self.timestamp = timestamp
		self.duration = duration

def frame_generator(frame_duration_ms, audio, sample_rate):
	"""Generates audio frames from PCM audio data.
	Takes the desired frame duration in milliseconds, the PCM data, and
	the sample rate.
	Yields Frames of the requested duration.
	"""
	n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
	offset = 0
	timestamp = 0.0
	duration = (float(n) / sample_rate) / 2.0
	while offset + n < len(audio):
		yield Frame(audio[offset:offset + n], timestamp, duration)
		timestamp += duration
		offset += n

def vad_collector(sample_rate, frame_duration_ms,
				  padding_duration_ms, vad, frames):
	"""Filters out non-voiced audio frames.
	Given a webrtcvad.Vad and a source of audio frames, yields only
	the voiced audio.
	Uses a padded, sliding window algorithm over the audio frames.
	When more than 90% of the frames in the window are voiced (as
	reported by the VAD), the collector triggers and begins yielding
	audio frames. Then the collector waits until 90% of the frames in
	the window are unvoiced to detrigger.
	The window is padded at the front and back to provide a small
	amount of silence or the beginnings/endings of speech around the
	voiced frames.
	Arguments:
	sample_rate - The audio sample rate, in Hz.
	frame_duration_ms - The frame duration in milliseconds.
	padding_duration_ms - The amount to pad the window, in milliseconds.
	vad - An instance of webrtcvad.Vad.
	frames - a source of audio frames (sequence or generator).
	Returns: A generator that yields PCM audio data.
	"""
	num_padding_frames = int(padding_duration_ms / frame_duration_ms)
	# We use a deque for our sliding window/ring buffer.
	ring_buffer = collections.deque(maxlen=num_padding_frames)
	# We have two states: TRIGGERED and NOTTRIGGERED. We start in the
	# NOTTRIGGERED state.
	triggered = False

	voiced_frames = []
	for frame in frames:
		if not triggered:
			ring_buffer.append(frame)
			num_voiced = len([f for f in ring_buffer
							  if vad.is_speech(f.bytes, sample_rate)])
			# If we're NOTTRIGGERED and more than 90% of the frames in
			# the ring buffer are voiced frames, then enter the
			# TRIGGERED state.
			if num_voiced > 0.9 * ring_buffer.maxlen:
				triggered = True
				# We want to yield all the audio we see from now until
				# we are NOTTRIGGERED, but we have to start with the
				# audio that's already in the ring buffer.
				voiced_frames.extend(ring_buffer)
				ring_buffer.clear()
		else:
			# We're in the TRIGGERED state, so collect the audio data
			# and add it to the ring buffer.
			voiced_frames.append(frame)
			ring_buffer.append(frame)
			num_unvoiced = len([f for f in ring_buffer
								if not vad.is_speech(f.bytes, sample_rate)])
			# If more than 90% of the frames in the ring buffer are
			# unvoiced, then enter NOTTRIGGERED and yield whatever
			# audio we've collected.
			if num_unvoiced > 0.9 * ring_buffer.maxlen:
				triggered = False
				yield b''.join([f.bytes for f in voiced_frames])
				ring_buffer.clear()
				voiced_frames = []
	# If we have any leftover voiced audio when we run out of input,
	# yield it.
	if voiced_frames:
		yield b''.join([f.bytes for f in voiced_frames])

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
			if count == 4:
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
						print('goodbye_flag')
						flag = False
				cap.release()
			f = 'goodbye.avi'
			cap = cv2.VideoCapture(f)
			while(cap.isOpened()):
				ret, frame = cap.read()
				if not(ret):
					break
				cv2.imshow("kizunaai", frame)
				if cv2.waitKey(33) == 27:
					flag = False	
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

		sample = frame_generator(30, b''.join(frames), RATE)
		sample = list(sample)

		segments = vad_collector(RATE, 30, 300, vad, sample)
		segments = list(segments)

		if len(segments) == 0:
			if flag:
				analyze = Process(target=analyze_proc, args=(voice, speak_q, PV, manager_q, status_on_q))
				analyze.start()
				flag = False
			voice = []
		else:
			flag = True