import asyncio
import websockets
import json
import subprocess
import os
import signal
import time

SERVER_URL = "ws://192.168.50.6:8080"
AUTH_TOKEN = "secret"
STREAM_URL = "rtmp://15.156.160.96/live/eric"
CAMERA_COMMAND = f"rpicam-vid -n -o - -t 0 --vflip | ffmpeg -re -f h264 -i - -vcodec copy -f flv {STREAM_URL}"

streaming_process = None

async def authenticate(websocket):
    """Send an authentication message to the server."""
    message = {
        "action": "authenticate",
        "payload": {"id": "RPi-1", "key": AUTH_TOKEN}
    }
    await websocket.send(json.dumps(message))
    print("Authentication message sent.")
    
async def handle_server_messages(websocket):
    """Handle incoming messages from the server."""
    global streaming_process

    async for message in websocket:
        try:
            data = json.loads(message)
            action = data.get("action")
            payload = data.get("payload")

            if action == "stream" and payload:
                if streaming_process is None:
                    print("Starting video stream...")
                    streaming_process = subprocess.Popen(
                        CAMERA_COMMAND, shell=True, stdin=subprocess.PIPE, start_new_session=True
                    )
                else:
                    print("Streaming is already active.")
            elif action == "stop":
                if streaming_process is not None:
                    print("Stopping video stream...")
                    os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
                    streaming_process = None
                else:
                    print("No active streaming process to stop.")
            else:
                print(f"Unknown action: {action}")
        except json.JSONDecodeError:
            print("Failed to decode server message.")
        except Exception as e:
            print(f"Error handling server message: {e}")


async def connect_to_server():
    """Establish connection to the server and manage reconnection."""
    global streaming_process
    
    headers = {
        "Authorization": AUTH_TOKEN
    }

    while True:
        try:
            print("Attempting to connect to the server...")
            async with websockets.connect(SERVER_URL, additional_headers=headers) as websocket:
                print("Connected to the server.")
                await authenticate(websocket)
                await handle_server_messages(websocket)
        except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            if streaming_process is not None:
                print("Stopping streaming process due to connection loss...")
                os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
                streaming_process = None
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(connect_to_server())
    except KeyboardInterrupt:
        print("Script interrupted. Cleaning up...")
        if streaming_process is not None:
            os.killpg(os.getpgid(streaming_process.pid), signal.SIGTERM)
        print("Cleanup complete. Exiting.")
