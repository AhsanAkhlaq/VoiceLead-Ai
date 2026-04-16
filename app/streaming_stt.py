import os
import json
import asyncio
import websockets
from typing import AsyncGenerator

class StreamingSTT:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        # Notice the wss:// protocol and endpointing=500 (detects 500ms of silence)
        self.url = "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=linear16&sample_rate=16000&endpointing=700"

    async def stream_transcribe(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        headers = {"Authorization": f"Token {self.api_key}"}
        
        # Open the live WebSocket to Deepgram
        async with websockets.connect(self.url, additional_headers=headers) as ws:
            
            # TASK 1: Send microphone chunks to Deepgram
            async def sender():
                try:
                    async for chunk in audio_stream:
                        await ws.send(chunk)
                    await ws.send(json.dumps({"type": "CloseStream"}))
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"STT Sender Error: {e}")

            send_task = asyncio.create_task(sender())
            
            # TASK 2: Listen for transcripts from Deepgram
            try:
                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") == "Results":
                        # Check if Deepgram detected the end of your sentence
                        speech_final = data.get("speech_final", False) 
                        transcript = data.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
                        
                        # Only yield the text if it's a complete thought
                        if transcript and speech_final:
                            yield transcript
            finally:
                send_task.cancel() # Clean up when done