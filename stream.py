from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory
import json
import subprocess
import os
import signal

server = "15.156.160.96"
port = 8080

streamingProcess = None


class App:
    
    def __init__(self):
        print("App is initialized.")
        
    def showCamera(self, is_bool):
        
        global streamingProcess
        # print("Show the camera to the server? {0}".format(is_bool))
        
        if is_bool:
        
            if streamingProcess is None:
                #ffmpeg_cmd = f'ffmpeg -re -i video.mov -c:v libx264 -preset veryfast -maxrate 3000k -bufsize 6000k -pix_fmt yuv420p -g 50 -c:a aac -b:a 160k -ac 2 -ar 44100 -f flv rtmp://{server}/live/eric'
     
                
                ffmpeg_cmd = f'rpicam-vid -n -o - -t 0 --vflip | ffmpeg -re -f h264 -i - -vcodec copy -f flv rtmp://15.156.160.96/live/eric'
                streamingProcess = subprocess.Popen(ffmpeg_cmd, shell=True, stdin=subprocess.PIPE, start_new_session=True)
                
                # streamingProcess.communicate()
            else:
                print("Camera is already streaming")
            
        else:
            self.stopCamera()
        
    def stopCamera(self):
        
        global streamingProcess
        print(f'stopCamera() was called. Current PID of streamingProcess is {streamingProcess.pid}')
        if streamingProcess is not None:
            print("Stopping the camera")
            os.killpg(os.getpgid(streamingProcess.pid), signal.SIGTERM)
            streamingProcess = None
        else:
            print("No streaming process is active")
        
    def decode_message(self, payload):
        print("Got a message, must decode {0}".format(payload))
        json_message = json.loads(payload)
        action = json_message.get('action')
        payloadValue = json_message.get('payload')
        
        if action == 'stream':
            self.showCamera(payloadValue)

class AppProtocol(WebSocketClientProtocol):

    def onConnect(self, response):
        print("Connected to the server")
        self.factory.resetDelay()

    def onOpen(self):
        print("Connection is open.")

        # when connection is open we send a test message the the server.

        def hello_server():
            
            message = {
                "action": "pi_online",
                "payload": {
                    "id": "RPi-1",
                    "key": "secret"
                }
            }
            
            self.sendMessage(json.dumps(message).encode('UTF-8'))
            
            # self.sendMessage(u"Hello server i'm Raspberry PI".encode('utf8'))
            # self.factory.reactor.callLater(1, hello_server)
        hello_server()

    def onMessage(self, payload, isBinary):
        if (isBinary):
            print("Got Binary message {0} bytes".format(len(payload)))
        else:
            print("Got Text message from the server {0}".format(payload.decode('utf8')))
            
            #Decode the message
            app = App()
            app.decode_message(payload)

    def onClose(self, wasClean, code, reason):
        print("Connect closed {0}".format(reason))


class AppFactory(WebSocketClientFactory, ReconnectingClientFactory):
    protocol = AppProtocol

    def clientConnectionFailed(self, connector, reason):
        print("Unable connect to the server {0}".format(reason))
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        print("Lost connection and retrying... {0}".format(reason))
        self.retry(connector)


if __name__ == '__main__':
    import sys
    from twisted.python import log
    from twisted.internet import reactor


    log.startLogging(sys.stdout)
    factory = AppFactory(u"ws://15.156.160.96:8080")
    reactor.connectTCP(server, port, factory)
    reactor.run()

