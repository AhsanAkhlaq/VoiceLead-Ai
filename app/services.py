import os
import json
import asyncio
import httpx
import websockets
from typing import AsyncGenerator, Dict, Any, Optional
from supabase import create_client

class StreamingSTT:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")

    async def stream_transcribe(self, audio_stream: AsyncGenerator[bytes, None], encoding: str = "linear16", sample_rate: int = 16000) -> AsyncGenerator[str, None]:
        url = f"wss://api.deepgram.com/v1/listen?model=nova-2&encoding={encoding}&sample_rate={sample_rate}&endpointing=700"
        headers = {"Authorization": f"Token {self.api_key}"}
        
        async with websockets.connect(url, additional_headers=headers) as ws:
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
            
            try:
                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") == "Results":
                        speech_final = data.get("speech_final", False) 
                        transcript = data.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
                        
                        if transcript and speech_final:
                            yield transcript
            finally:
                send_task.cancel()


class StreamingDeepgramTTS:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.base_url = "https://api.deepgram.com/v1/speak"
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    async def stream_synthesize(self, text: str, encoding: str = "mp3", sample_rate: int | None = None) -> AsyncGenerator[bytes, None]:
        params = {
            "model": "aura-asteria-en",
            "encoding": encoding,
        }
        if sample_rate:
            params["sample_rate"] = sample_rate
            
        payload = {"text": text}

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers=self.headers,
                json=payload,
                params=params,
                timeout=30.0,
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise Exception(f"Deepgram error: {response.status_code} - {response.text}")
                
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk

    async def synthesize(self, text: str, encoding: str = "mp3", sample_rate: int | None = None) -> bytes:
        chunks = []
        async for chunk in self.stream_synthesize(text, encoding=encoding, sample_rate=sample_rate):
            chunks.append(chunk)
        return b"".join(chunks)


class SupabaseDB:
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_KEY")
        self.client = create_client(url, key)

    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        response = self.client.table("leads").insert(lead_data).execute()
        if response.data:
            return response.data[0]["id"]
        raise Exception("Failed to create lead")

    async def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
        self.client.table("leads").update(updates).eq("id", lead_id).execute()
        return True

    async def get_all_leads(self) -> list[Dict[str, Any]]:
        response = self.client.table("leads").select("*").order("score_confidence", desc=True).order("created_at", desc=True).execute()
        return response.data if response.data else []

    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        response = self.client.table("leads").select("*").eq("id", lead_id).execute()
        return response.data[0] if response.data else None
