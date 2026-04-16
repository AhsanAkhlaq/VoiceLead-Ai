
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.voice_agent import VoiceLeadAgent
import json

app = FastAPI(title="VoiceLead AI - Browser Demo")

app.mount("/static", StaticFiles(directory="static"), name="static")

agent = VoiceLeadAgent()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    print("✅ Browser voice session started")
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "audio":
                # Process the recorded audio
                result = await agent.process_audio(data["audio_base64"])
                await websocket.send_json(result)
                
    except WebSocketDisconnect:
        print("❌ Browser session closed")
    except Exception as e:
        print("Error in websocket:", e)
        await websocket.send_json({"type": "error", "message": str(e)})