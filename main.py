import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.engine import CoreEngine
from app.streaming_stt import StreamingSTT
from app.streaming_tts import StreamingDeepgramTTS
from app.db_supabase import SupabaseDB
from dotenv import load_dotenv

load_dotenv()

stt = StreamingSTT()
tts = StreamingDeepgramTTS()
db = SupabaseDB()
engine = CoreEngine(tts_provider=tts, db_provider=db)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.websocket("/ws/browser")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # CRITICAL: Reset engine state for new call (prevents old history from bleeding in)
    engine.conversation_history = []
    engine.extracted_data = {
        "name": None,
        "phone": None,
        "property_type": None,
        "city": None,
        "area_society": None,
        "size_requirement": None,
        "budget_range": None,
        "timeline": None,
        "purpose": None,
        "additional_requirements": None,
    }
    engine.lead_profile = {
        "budget": None,
        "property_type": None,
        "timeline": None,
        "location": None,
        "score": "UNKNOWN",
        "sentiment": "neutral",
        "score_confidence": 0.0
    }
    engine.call_start_time = datetime.now()
    
    # Create a new lead at the start of the call
    lead_data = {
        "status": "in_call",
        "created_at": datetime.now().isoformat(),
        "initial_message": "Call started"
    }
    engine.current_lead_id = await engine.db.create_lead(lead_data)
    print(f"✅ Created lead: {engine.current_lead_id}")
    
    # ==========================================
    # 🌟 1. THE GREETING LOGIC
    # ==========================================
    try:
        greeting_text = "Hello! I am VoiceLead AI. Are you looking to buy or rent a property today?"
        
        # Send text to frontend UI
        await websocket.send_text(json.dumps({"ai_text": greeting_text}))
        
        # Buffer audio chunks before sending (fixes glitching)
        audio_buffer = bytearray()
        chunk_size = 4096  # 4KB chunks to balance between buffering and latency
        
        async for audio_chunk in tts.stream_synthesize(greeting_text):
            audio_buffer.extend(audio_chunk)
            
            # Send buffered data when we have enough
            if len(audio_buffer) >= chunk_size:
                await websocket.send_bytes(bytes(audio_buffer))
                audio_buffer = bytearray()
        
        # Send remaining audio
        if audio_buffer:
            await websocket.send_bytes(bytes(audio_buffer))
            
        # Add to AI memory
        engine.conversation_history.append({
            "role": "assistant",
            "content": greeting_text,
            "timestamp": None
        })
    except Exception as e:
        print(f"Greeting error: {e}")
    # ==========================================

    # 2. START FULL-DUPLEX LOOP
    audio_queue = asyncio.Queue()
    stop_audio_event = asyncio.Event()  # Signal to stop current audio
    
    async def receive_audio():
        try:
            while True:
                data = await websocket.receive_bytes()
                await audio_queue.put(data)
        except WebSocketDisconnect:
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
                    # User spoke - clear any current audio (handle interrupt)
                    stop_audio_event.set()
                    
                    print(f"🎤 User: {transcript}")
                    
                    # Send user's text to the UI so it shows in the chat box
                    await websocket.send_text(json.dumps({"user_text": transcript}))
    
                    # Generate AI response
                    full_response = await engine._generate_response(transcript)
                    
                    # Extract data and calculate score (happens inside _generate_response)
                    # Now update database with extracted fields
                    call_duration = int((datetime.now() - engine.call_start_time).total_seconds())
                    summary = engine._generate_summary()
                    
                    # Update database with ALL extracted fields + analytics
                    await engine.db.update_lead(
                        engine.current_lead_id,
                        {
                            "name": engine.extracted_data.get("name"),
                            "phone": engine.extracted_data.get("phone"),
                            "property_type": engine.extracted_data.get("property_type"),
                            "city": engine.extracted_data.get("city"),
                            "area_society": engine.extracted_data.get("area_society"),
                            "size_requirement": engine.extracted_data.get("size_requirement"),
                            "budget_range": engine.extracted_data.get("budget_range"),
                            "timeline": engine.extracted_data.get("timeline"),
                            "purpose": engine.extracted_data.get("purpose"),
                            "additional_requirements": engine.extracted_data.get("additional_requirements"),
                            "lead_score": engine.lead_profile.get("score"),
                            "score_confidence": engine.lead_profile.get("score_confidence"),
                            "sentiment": engine.lead_profile.get("sentiment"),
                            "summary": summary,
                            "transcript": engine.conversation_history,
                            "call_duration_seconds": call_duration
                        }
                    )
                    
                    # Check if AI wants to end call
                    call_should_end = engine.should_end_call(full_response)
                    full_response = engine.get_clean_response(full_response)
                    
                    print(f"🤖 AI: {full_response}")
                    
                    # Send AI's text to the UI
                    await websocket.send_text(json.dumps({"ai_text": full_response}))
                    
                    # Reset the stop signal for new audio
                    stop_audio_event.clear()
                    
                    # Stream the audio back with buffering (fixes glitching)
                    audio_buffer = bytearray()
                    chunk_size = 4096
                    
                    async for audio_chunk in tts.stream_synthesize(full_response):
                        # Check if we should stop playback (user interrupted)
                        if stop_audio_event.is_set():
                            print("⏹️ Audio playback stopped (user interrupted)")
                            break
                        
                        audio_buffer.extend(audio_chunk)
                        
                        # Send buffered data when we have enough
                        if len(audio_buffer) >= chunk_size:
                            try:
                                await websocket.send_bytes(bytes(audio_buffer))
                                audio_buffer = bytearray()
                            except:
                                break
                    
                    # Send remaining audio
                    if audio_buffer and not stop_audio_event.is_set():
                        try:
                            await websocket.send_bytes(bytes(audio_buffer))
                        except:
                            pass
                    
                    # Update History & Database
                    engine.conversation_history.append({
                        "role": "user",
                        "content": transcript,
                        "timestamp": None
                    })
                    engine.conversation_history.append({
                        "role": "assistant",
                        "content": full_response,
                        "timestamp": None
                    })
                    
                    # Save to Supabase if a lead ID exists
                    if engine.current_lead_id:
                        await engine.db.save_transcript(engine.current_lead_id, "user", transcript)
                        await engine.db.save_transcript(engine.current_lead_id, "agent", full_response)
                    
                    # If AI ended the call, close gracefully
                    if call_should_end:
                        print("📞 Call terminated by AI")
                        await websocket.send_text(json.dumps({"call_ended": True, "message": "Call ended"}))
                        break
                        
        except Exception as e:
            print(f"Process Stream Error: {e}")
            import traceback
            traceback.print_exc()
    
    receive_task = asyncio.create_task(receive_audio())
    process_task = asyncio.create_task(process_stream())
    
    done, pending = await asyncio.wait(
        [receive_task, process_task],
        return_when=asyncio.FIRST_EXCEPTION
    )
    
    for task in pending:
        task.cancel()
    
    try:
        await websocket.close()
    except RuntimeError:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)