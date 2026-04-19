import os
import json
import asyncio
from datetime import datetime
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.engine import CoreEngine
from app.services import StreamingSTT, StreamingDeepgramTTS, SupabaseDB
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

stt = StreamingSTT()
tts = StreamingDeepgramTTS()
db = SupabaseDB()
engine = CoreEngine(tts_provider=tts, db_provider=db)

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("static/dashboard.html")

@app.get("/api/leads")
async def get_dashboard_leads():
    try:
        leads = await engine.db.get_all_leads()
        return leads
    except Exception as e:
        print(f"Error fetching leads: {e}")
        return []

@app.get("/api/leads/{lead_id}/transcript")
async def get_lead_transcript(lead_id: str):
    try:
        lead = await engine.db.get_lead(lead_id)
        if lead and lead.get("transcript"):
            return lead["transcript"]
        return []
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return []
    
@app.websocket("/ws/browser")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Reset engine for new call
    engine.conversation_history = []
    engine.call_start_time = datetime.now()
    
    engine.current_lead_id = await engine.db.create_lead({
        "pipeline_status": "in_call",
        "phone": "pending_web_call"
    })
    
    # --- Greeting ---
    try:
        greeting_text = "Hello! I am VoiceLead AI. Are you looking to buy or rent a property today?"
        await websocket.send_text(json.dumps({"ai_text": greeting_text}))
        
        audio_buffer = bytearray()
        is_first_chunk = True
        
        async for audio_chunk in tts.stream_synthesize(greeting_text):
            audio_buffer.extend(audio_chunk)
            
            target_size = 16384 if is_first_chunk else 8192
            if len(audio_buffer) >= target_size:
                await websocket.send_bytes(bytes(audio_buffer))
                audio_buffer.clear()
                is_first_chunk = False
        if audio_buffer:
            await websocket.send_bytes(bytes(audio_buffer))
            
        engine.conversation_history.append({"role": "assistant", "content": greeting_text})
    except Exception as e:
        print(f"Greeting error: {e}")

    # --- Full Duplex Loop ---
    audio_queue = asyncio.Queue()
    stop_audio_event = asyncio.Event()
    
    
    async def receive_audio():
        try:
            while True:
                data = await websocket.receive_bytes()
                await audio_queue.put(data)
        except WebSocketDisconnect:
            await audio_queue.put(None)
        except Exception as e:
            print(f"WebSocket Receive Error: {e}")
            await audio_queue.put(None)

            
    async def audio_generator():
        while True:
            data = await audio_queue.get()
            if data is None:
                break
            yield data
    
    async def process_stream():
        try:
            async for transcript in stt.stream_transcribe(audio_generator()):
                if transcript:
                    stop_audio_event.set() # Interrupt AI if it's speaking
                    print(f"🎤 User: {transcript}")
                    await websocket.send_text(json.dumps({"user_text": transcript}))
    
                    # ⚡ Fast Brain: Just generate the conversational response
                    raw_response = await engine._generate_response(transcript)
                    
                    call_should_end = engine.should_end_call(raw_response)
                    clean_response = engine.get_clean_response(raw_response)
                    
                    print(f"🤖 AI: {clean_response}")
                    await websocket.send_text(json.dumps({"ai_text": clean_response}))
                    
                    # Log History
                    engine.conversation_history.append({"role": "user", "content": transcript})
                    engine.conversation_history.append({"role": "assistant", "content": clean_response})
                    
                    # Stream audio back
                    stop_audio_event.clear()
                    audio_buffer = bytearray()
                    is_first_chunk = True
                    
                    async for audio_chunk in tts.stream_synthesize(clean_response):
                        if stop_audio_event.is_set():
                            print("⏹️ Audio stopped (user interrupted)")
                            break
                        
                        audio_buffer.extend(audio_chunk)
                        
                        target_size = 16384 if is_first_chunk else 8192
                        if len(audio_buffer) >= target_size:
                            try:
                                await websocket.send_bytes(bytes(audio_buffer))
                                audio_buffer.clear()
                                is_first_chunk = False
                            except:
                                break
                    
                    if audio_buffer and not stop_audio_event.is_set():
                        try:
                            await websocket.send_bytes(bytes(audio_buffer))
                        except:
                            pass
                    
                    # If AI ended the call, close gracefully
                    if call_should_end:
                        print("📞 Call terminated by AI")
                        try:
                            await websocket.send_text(json.dumps({"call_ended": True}))
                        except Exception:
                            pass
                        return
                        
        except Exception as e:
            print(f"Stream error: {e}")
            import traceback
            traceback.print_exc()
    
    
    # Run tasks
    receive_task = asyncio.create_task(receive_audio())
    process_task = asyncio.create_task(process_stream())
    
    done, pending = await asyncio.wait([receive_task, process_task], return_when=asyncio.FIRST_EXCEPTION)
    for task in pending: task.cancel()
    
    # --- Disconnect & Post-Call Trigger ---
    try:
        await websocket.close()
    except Exception:
        pass

    if engine.current_lead_id:
        print("🔌 Connection closed. Launching Deep Analyst...")
        asyncio.create_task(engine.analyze_completed_call(engine.current_lead_id))


@app.api_route("/api/twilio/twiml", methods=["GET", "POST"])
async def twilio_twiml(request: Request):
    ngrok_url = os.getenv("NGROK_URL", "").rstrip('/')
    if not ngrok_url:
        print("Warning: NGROK_URL not set in environment.")
    
    if ngrok_url.startswith("http"):
        wss_url = ngrok_url.replace("https://", "wss://").replace("http://", "ws://")
    elif ngrok_url.startswith("wss://") or ngrok_url.startswith("ws://"):
        wss_url = ngrok_url
    else:
        wss_url = f"wss://{ngrok_url}"
    print("got it", wss_url)
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting to Voice Lead A I.</Say>
    <Connect>
        <Stream url="{wss_url}/ws/twilio" />
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="text/xml")

@app.websocket("/ws/twilio")
async def twilio_websocket_endpoint(websocket: WebSocket):
    print("📞 Incoming Twilio WebSocket connection...")
    await websocket.accept()
    stream_sid = None
    print("📞 Twilio WebSocket accepted. Waiting for 'connected' event...")
    # Reset engine state for new call
    engine.conversation_history = []
    engine.call_start_time = datetime.now()
    try:
        engine.current_lead_id = await engine.db.create_lead({
            "pipeline_status": "in_call",
            "phone": "twilio_phone_call"
        })
    except Exception as e:
        print(f"Failed to create lead for Twilio call: {e}")
        engine.current_lead_id = None

    audio_queue = asyncio.Queue()
    stop_audio_event = asyncio.Event()
    active_synthesis_task = None

    async def stream_tts_to_twilio(text: str):
        try:
            async for audio_chunk in tts.stream_synthesize(text, encoding="mulaw", sample_rate=8000):
                if stop_audio_event.is_set():
                    break
                payload = base64.b64encode(audio_chunk).decode("utf-8")
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": payload
                    }
                }
                try:
                    await websocket.send_text(json.dumps(media_msg))
                except Exception:
                    break
        except Exception as e:
            print(f"Twilio TTS stream error: {e}")

    async def receive_from_twilio():
        nonlocal stream_sid, active_synthesis_task
        try:
            while True:
                message = await websocket.receive_text()
                packet = json.loads(message)
                event = packet.get("event")

                if event == "connected":
                    print("🌐 Twilio Stream 'connected' event received.")

                elif event == "start":
                    stream_sid = packet["start"]["streamSid"]
                    print(f"📞 Twilio stream started. Stream SID: {stream_sid}")
                    
                    greeting_text = "Hello! I am VoiceLead AI. Are you looking to buy or rent a property today?"
                    engine.conversation_history.append({"role": "assistant", "content": greeting_text})
                    
                    active_synthesis_task = asyncio.create_task(stream_tts_to_twilio(greeting_text))

                elif event == "media":
                    payload = packet["media"]["payload"]
                    chunk = base64.b64decode(payload)
                    await audio_queue.put(chunk)

                elif event == "stop":
                    print("📞 Twilio stream stopped.")
                    await audio_queue.put(None)
                    break
        except WebSocketDisconnect:
            print("📞 Twilio WebSocket disconnected.")
            await audio_queue.put(None)
        except Exception as e:
            print(f"Twilio Receive Error: {e}")
            await audio_queue.put(None)

    async def audio_generator():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def process_stream():
        nonlocal active_synthesis_task
        try:
            async for transcript in stt.stream_transcribe(audio_generator(), encoding="mulaw", sample_rate=8000):
                if transcript:
                    stop_audio_event.set()
                    if active_synthesis_task and not active_synthesis_task.done():
                        # Let the current TTS finish properly so it doesn't break Deepgram connection loop
                        await active_synthesis_task
                    
                    stop_audio_event.clear()
                    
                    # Optionally clear twilio side
                    try:
                        await websocket.send_text(json.dumps({
                            "event": "clear",
                            "streamSid": stream_sid
                        }))
                    except Exception:
                        pass
                    
                    print(f"🎤 Twilio User: {transcript}")
                    
                    raw_response = await engine._generate_response(transcript)
                    call_should_end = engine.should_end_call(raw_response)
                    clean_response = engine.get_clean_response(raw_response)

                    print(f"🤖 AI: {clean_response}")
                    
                    engine.conversation_history.append({"role": "user", "content": transcript})
                    engine.conversation_history.append({"role": "assistant", "content": clean_response})
                    
                    active_synthesis_task = asyncio.create_task(stream_tts_to_twilio(clean_response))
                    
                    if call_should_end:
                        await active_synthesis_task
                        print("📞 Call terminated by AI")
                        return

        except Exception as e:
            print(f"Twilio STT Stream error: {e}")

    receive_task = asyncio.create_task(receive_from_twilio())
    process_task = asyncio.create_task(process_stream())

    done, pending = await asyncio.wait([receive_task, process_task], return_when=asyncio.FIRST_EXCEPTION)
    for task in pending: task.cancel()

    try:
        await websocket.close()
    except:
        pass

    if engine.current_lead_id:
        print("🔌 Twilio Connection closed. Launching Deep Analyst...")
        asyncio.create_task(engine.analyze_completed_call(engine.current_lead_id))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)