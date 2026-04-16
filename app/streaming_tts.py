import os
import httpx
from typing import AsyncGenerator

class StreamingDeepgramTTS:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.base_url = "https://api.deepgram.com/v1/speak"
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        params = {
            "model": "aura-asteria-en",
            "encoding": "mp3",
        }
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

    async def synthesize(self, text: str) -> bytes:
        chunks = []
        async for chunk in self.stream_synthesize(text):
            chunks.append(chunk)
        return b"".join(chunks)
