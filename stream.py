import asyncio
import websockets
import json
import subprocess
import os
import signal
import requests
import json


#--------Variables that will eventually be env vars
#SERVER_URL = "ws://15.156.160.96:8080/api/cameras/connect"
# BASE_URL = "http://127.0.0.1:8000"
BASE_URL = "http://15.156.160.96:8000"
WS_URL = "ws://15.156.160.96:8000/api/devices/connect"
# WS_URL = "ws://127.0.0.1:8000/api/devices/connect"
DEVICE_ID = "pi_0001"
DESCRIPTION = "Mounted to utility mole pointing north"
STREAM_URL = f"rtmp://15.156.160.96/live/{DEVICE_ID}"
API_KEY = "dbe4248ce6a720c6db4302d5dc4319c5d768ca0f10f3241ec9e1628eebfa0d165a758b62d48e317c25a019da0dfdbe0e8a48166aa6ad270b2d13e51c06a8d93b"
CAMERA_COMMAND = f"rpicam-vid -n -o - -t 0 --vflip | ffmpeg -re -f h264 -i - -vcodec copy -f flv {STREAM_URL}?api-key={API_KEY}"


streaming_process = None

# def authenticate() -> str:
#     """Authenticate the pi to the server. Returns a token used for API access"""
    
#     form_data = {
#         "username": "ericmuzzo",
#         "password": "dirtbIke1*"
#     }
    
#     headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
#     try:
#         response = requests.post(f"{BASE_URL}/auth/login", data=form_data, headers=headers)
        
#         if response.status_code == 401:
#             print("Authentication failed")
#             return None
        
#         response.raise_for_status()
#         token = json.loads(response.content.decode())["access_token"]
#         return token
        
#     except Exception as e:
#         print(f"Authentication error: {e}")
#         return None
    


async def connect_to_server():
    """Establish connection to the server and manage reconnection."""
    
    # headers = {
    #     "Accept": "application/json",
    #     "Authorization": f"Bearer {token}"
    # }
    headers = {
        "x-key": API_KEY
    }

    try:
        print("Attempting to connect to the server...")
        
        websocket = await websockets.connect(WS_URL, additional_headers=headers)
        print("Connected to the server.")
        
        # Identify itself to the server
        identifier = {
            "id": DEVICE_ID,
            "name": DESCRIPTION,
            "connected": True,
            "streaming": False,
            "liveStreamURL": f"http://queueview.ca/play/{DEVICE_ID}"
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
            
            
async def handle_server_messages(websocket: websockets.ClientConnection):
    """Handle incoming messages from the server."""
    global streaming_process
    
    headers = {
        "x-key": API_KEY
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
                    requests.put(f"{BASE_URL}/api/cameras/{DEVICE_ID}", json={"streaming": True}, headers=headers)
                else:
                    print("Streaming is already active.")
            elif action == "stop":
                if streaming_process is not None:
                    print("Stopping video stream...")
                    os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
                    streaming_process = None
                    print(f"Streaming process: {streaming_process}")
                    requests.put(f"{BASE_URL}/api/cameras/{DEVICE_ID}", json={"streaming": False}, headers=headers)
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
        # token = authenticate()
        # if not token:
        #     print("Failed to obtain a token. Retrying in 10 seconds...")
        #     await asyncio.sleep(5)
        #     continue
        
        # websocket = await connect_to_server(token)
        websocket = await connect_to_server()

        if not websocket:
            await asyncio.sleep(5)
            continue
        
        try:
            await handle_server_messages(websocket)
        
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