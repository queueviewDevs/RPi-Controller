import asyncio
import websockets
import json
import subprocess
import os
import signal
import requests
import json

#SERVER_URL = "ws://15.156.160.96:8080/api/cameras/connect"
# BASE_URL = "http://127.0.0.1:8000"
BASE_URL = "http://15.156.160.96:8000"
WS_URL = "ws://15.156.160.96:8000/connect"
#AUTH_TOKEN = "secret"
STREAM_URL = "rtmp://15.156.160.96/live/eric"
CAMERA_COMMAND = f"rpicam-vid -n -o - -t 0 --vflip | ffmpeg -re -f h264 -i - -vcodec copy -f flv {STREAM_URL}"

streaming_process = None

def authenticate() -> str:
    """Authenticate the pi to the server. Returns a token used for API access"""
    
    form_data = {
        "username": "ericmuzzo",
        "password": "dirtbIke1*"
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", data=form_data, headers=headers)
        
        if response.status_code == 401:
            print("Authentication failed")
            return None
        
        response.raise_for_status()
        token = json.loads(response.content.decode())["access_token"]
        return token
        
    except Exception as e:
        print(f"Authentication error: {e}")
        return None
    


async def connect_to_server(token):
    """Establish connection to the server and manage reconnection."""
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        print("Attempting to connect to the server...")
        
        websocket = await websockets.connect(WS_URL, additional_headers=headers)
        print("Connected to the server.")
        
        # Identify itself to the server
        identifier = {
            "id": 1,
            "name": "First cam",
            "connected": True,
            "streaming": False,
            "liveStreamURL": "http://url.com"
        }
        await websocket.send(json.dumps(identifier))
        print("Send ID to server")
        return websocket

    except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
        print(f"Connection error: {e}. Retrying in 5 seconds...")
        return None
    
    except Exception as e:
        print(f"Unexpected websocket error: {e}")
        return None
            
            
async def handle_server_messages(websocket: websockets.ClientConnection, token):
    """Handle incoming messages from the server."""
    global streaming_process
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    async for message in websocket:
        try:
            data = json.loads(message)
            action = data.get("action")
            #payload = data.get("payload")

            if action == "start":
                if streaming_process is None:
                    print("Starting video stream...")
                    streaming_process = subprocess.Popen(
                        CAMERA_COMMAND, shell=True, stdin=subprocess.PIPE, start_new_session=True
                    )
                    requests.put(f"{BASE_URL}/api/cameras/1", json={"streaming": True}, headers=headers)
                else:
                    print("Streaming is already active.")
            elif action == "stop":
                if streaming_process is not None:
                    print("Stopping video stream...")
                    os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
                    streaming_process = None
                    print(f"Streaming process: {streaming_process}")
                    requests.put(f"{BASE_URL}/api/cameras/1", json={"streaming": False}, headers=headers)
                else:
                    print("No active streaming process to stop.")
                    
            else:
                print(f"Unknown action: {action}")
        except json.JSONDecodeError:
            print("Failed to decode server message.")
        except Exception as e:
            print(f"Error handling server message: {e}")


async def main():
    
    global streaming_process
    
    while True:
        token = authenticate()
        if not token:
            print("Failed to obtain a token. Retrying in 10 seconds...")
            await asyncio.sleep(5)
            continue
        
        websocket = await connect_to_server(token)

        if not websocket:
            await asyncio.sleep(5)
            continue
        
        try:
            await handle_server_messages(websocket, token)
        
        except websockets.ConnectionClosed as cc:
            print(f"Websocket connection closed: {cc}")
        
        except ConnectionRefusedError as cr:
            print(f"Websocket connection refused error: {cr}")
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            
        if streaming_process:
            print("Stopping streaming process due to connection loss...")
            os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
            streaming_process = None
        
        await asyncio.sleep(5)
        
if __name__ == "__main__":
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt received, shutting down...")