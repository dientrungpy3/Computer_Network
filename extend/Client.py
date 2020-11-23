from tkinter import *
from tkinter import messagebox 
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os
from time import time, sleep
from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	SETUP = 0
	PLAY = 1
	PAUSE = 2
	STOP = 3
	DESCRIBE = 4

	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.stopAcked = 0
		# self.connectToServer()
		self.frameNbr = 0
	
		self.lenghtDataVideo=0
		self.sumTime=0
		self.dataRate=0
		self.startTime=0
		self.countLost=0

		self.isFirst=True

	def init_state(self):
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.stopAcked = 0
		self.connectToServer()
		self.frameNbr = 0
	
		self.lenghtDataVideo=0
		self.sumTime=0
		self.dataRate=0
		self.startTime=0
		self.countLost=0


	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		# self.setup = Button(self.master, width=20, padx=3, pady=3)
		# self.setup["text"] = "Setup"
		# self.setup["command"] = self.setupMovie
		# self.setup.grid(row=1, column=0, padx=2, pady=2)

		# Create Play button
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=0, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=1, padx=2, pady=2)

		# Create Stop button
		self.stop = Button(self.master, width=20, padx=3, pady=3)
		self.stop["text"] = "Stop"
		self.stop["command"] = self.stopMovie
		self.stop.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Describe button
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe["text"] = "Describe"
		self.describe["command"] = self.requestDescriptionFile
		self.describe.grid(row=1, column=3, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4,
		                sticky=W+E+N+S, padx=5, pady=5)

		# Create a Text to display statistics information
		self.txtForm = Text(self.master, height=8, wrap=WORD)
		self.txtForm.grid(row=2, column=0, columnspan=4,
		                sticky=W+E+N+S, padx=5, pady=5)
		
		
		
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)

	def stopMovie(self):
		"""Stop button handler."""
		self.sendRtspRequest(self.STOP)
		# Delete the cache image from video 
		try:
			os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
		except:
			return

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.isFirst: # ==>If it is the first time pressing play, send the SETUP request
			self.init_state()
			self.setupMovie()
			self.isFirst = False
			sleep(0.1)
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			self.startTime=int(time()*1000) # ==> Get the current time
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
        
	def requestDescriptionFile(self):
		"""Describe button handler."""
		if self.state != self.INIT:
			self.sendRtspRequest(self.DESCRIBE)
		
	def listenRtp(self):
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					# Calculate the total transmission time
					currentTime=int(time()*1000)
					self.sumTime += currentTime - self.startTime
					self.startTime = currentTime

					currFrameNbr = rtpPacket.seqNum()
					# calculate the number of packages lost
					if self.frameNbr + 1 != currFrameNbr: self.countLost += currFrameNbr - self.frameNbr
						
					if currFrameNbr > self.frameNbr:  # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
					
					# Calculates the total number of bytes received
					self.lenghtDataVideo += len(rtpPacket.getPayload())

					# Calculates data rate 
					self.dataRate = self.lenghtDataVideo / (self.sumTime/1000.0) if (self.sumTime != 0) else 0 

					# Calculates packets lost rate
					lostRate = float(self.countLost) / self.frameNbr

					# print information
					print('\n'+'-'*50)
					print("Current Seq Num: " + str(currFrameNbr))
					print("Data length :",len(rtpPacket.getPayload())," bytes")
					print('-'*50)

					#  Export statistics information
					self.txtForm.delete(0.0,'end')
					var= "STATISTICS INFORMATION : " \
						"\n\nTotal bytes received : " + str(self.lenghtDataVideo) + " bytes" \
						+"\nPackets number lost : " + str(self.countLost) \
						+"\nPackets lost rate : " + str(lostRate) + " %" \
						+"\nTotal transmission time : " + str(self.sumTime) + " ms" \
						+"\nData rate : " + str(int(self.dataRate)) + " bytes/s"
					self.txtForm.insert(0.0,var)
					
			except:
				# Stop listening upon requesting PAUSE or STOP
				if self.playEvent.isSet():
					break

				# Upon receiving ACK for STOP request,
				# close the RTP socket
				if self.stopAcked == 1:
					print('stop acked')
					# self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()

		return cachename

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image=photo, height=288)
		self.label.image = photo

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			messagebox.showwarning(
			    'Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr) 

	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		# -------------
		# TO COMPLETE
		# -------------

		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
		
			# Write the RTSP request to be sent.
			# request = ...

			request = "SETUP %s RTSP/1.0\nCSeq: %d\nTransport: RTP/UDP;client_port = %d" % (self.fileName, self.rtspSeq, self.rtpPort)
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP

		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = "PLAY %s RTSP/1.0\nCSeq: %d\nSession: %d" % ( self.fileName, self.rtspSeq, self.sessionId)
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY

		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = "PAUSE %s RTSP/1.0\nCSeq: %d\nSession: %d" % (self.fileName, self.rtspSeq, self.sessionId)
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
			
		# Stop request
		elif requestCode == self.STOP and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = "STOP %s RTSP/1.0\nCSeq: %d\nSession: %d" % ( self.fileName, self.rtspSeq, self.sessionId)
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.STOP
        
		# Stop request
		elif requestCode == self.DESCRIBE:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = "DESCRIBE %s RTSP/1.0\nCSeq: %d\nSession: %d\nAccept: application/sdp" % ( self.fileName, self.rtspSeq, self.sessionId)
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.DESCRIBE
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		# ...
		self.rtspSocket.send(request.encode())
		print('\nData sent:\n' + request)
		
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Stop
			if self.requestSent == self.STOP:
				self.isFirst = True
				self.state = self.INIT
				# self.rtspSocket.close()
				self.sessionId = 0
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		
		if seqNum == self.rtspSeq:
			temp = lines[2].split(' ')[0]
			if temp == "Session:":
				session = int(lines[2].split(' ')[1])
				# New RTSP session ID
				if self.sessionId == 0:
					self.sessionId = session
				
				# Process only if the session ID is the same
				if self.sessionId == session:
					if int(lines[0].split(' ')[1]) == 200: 
						if self.requestSent == self.SETUP:
							# -------------
							# TO COMPLETE
							# -------------
							# Update RTSP state.
							# self.state = ...
							self.state = self.READY
							# Open RTP port.
							self.openRtpPort()
						elif self.requestSent == self.PLAY:
							# self.state = ...
							self.state = self.PLAYING
						elif self.requestSent == self.PAUSE:
							# self.state = ...
							self.state = self.READY
							# The play thread exits. A new thread is created on resume.
							self.playEvent.set()
						elif self.requestSent == self.STOP:
							# self.state = ...
							self.state = self.INIT
							# Flag the stopAcked to close the socket.
							self.stopAcked = 1
			elif temp == "Content-Base:": 
				if int(lines[0].split(' ')[1]) == 200: 
					self.state = self.READY
					print('\nData received:')
					for i in range(2, len(lines)):
						print(lines[i])
				
					
						
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# -------------
		# TO COMPLETE
		# -------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtpSocket.settimeout(0.5)
		try:
			# Bind the socket to the address using the RTP port given by the client user
			# ...
			self.state = self.READY
			self.rtpSocket.bind(('', self.rtpPort))
		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort) #note

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):  # note
			self.stopMovie()
			self.master.destroy()  # Close the gui window
		else: # When the user presses cancel, resume playing.
			self.playMovie()
