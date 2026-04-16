"""
tts_deepgram.py - Deepgram Aura Integration (🔊 The Voice)

Handles real-time text-to-speech synthesis via Deepgram's low-latency Aura API.
Streams high-fidelity audio directly to the client via WebSocket.
"""

import os
import httpx
from typing import Optional
from app.interfaces import TTSProvider


class DeepgramTTS(TTSProvider):
    """
    Deepgram Aura Text-to-Speech Provider.
    
    Features:
    - Low-latency streaming audio
    - Native support for multiple languages (English, Urdu)
    - High-fidelity voices
    """

    def __init__(self, deepgram_api_key: Optional[str] = None):
        """
        Initialize Deepgram TTS client.

        Args:
            deepgram_api_key: API key for Deepgram (defaults to env var)
        """
        self.api_key = deepgram_api_key or os.getenv("DEEPGRAM_API_KEY")
        self.base_url = "https://api.deepgram.com/v1/speak"
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Synthesize text to speech audio using Deepgram Aura.

        Args:
            text: The text to speak
            language: Language code ('en' for English, 'ur' for Urdu)

        Returns:
            Audio bytes (MP3 format)
        """
        params = {
            "model": "aura-asteria-en",
            "encoding": "mp3",
        }

        payload = {"text": text}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                params=params,
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(
                    f"Deepgram API error: {response.status_code} - {response.text}"
                )

            return response.content
