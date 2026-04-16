"""
engine.py - The Core Engine (🤖 The Assembly Line)

The heart of VoiceLead AI. Orchestrates the complete flow:
Step A (Listen): Receive user text
Step B (Remember): Add to conversation history
Step C (Think): Generate AI response via Groq LLM
Step D (Speak): Convert to audio via TTS (Deepgram)
Step E (Archive): Save to database
Step F (Deliver): Return audio + text to caller

Design Pattern: The Engine doesn't care if TTS is Deepgram or a Mock;
it doesn't care if DB is Supabase or a Mock. It just knows the interfaces.
This is dependency injection at its finest.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import os
from dotenv import load_dotenv
from groq import AsyncGroq
from app.interfaces import TTSProvider, DatabaseProvider

# Load environment variables
load_dotenv()


class CoreEngine:
    """
    The Core Engine - The Assembly Line of VoiceLead AI.
    
    The Engine is dependency-injected with:
    - A TTS provider (could be real Deepgram or Mock)
    - A Database provider (could be real Supabase or Mock)
    
    During testing, we pass Mocks. During production, we pass real APIs.
    The Engine doesn't care. It just orchestrates the flow.
    """

    def __init__(
        self,
        tts_provider: TTSProvider,
        db_provider: DatabaseProvider,
        groq_api_key: Optional[str] = None
    ):
        """
        Initialize the Core Engine with its tooling.

        Args:
            tts_provider: The TTS implementation (Deepgram or Mock)
            db_provider: The Database implementation (Supabase or Mock)
            groq_api_key: API key for Groq (defaults to env var)
        """
        self.tts = tts_provider
        self.db = db_provider
        
        # Initialize Groq client
        groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.groq = AsyncGroq(api_key=groq_key)

        # State Management
        self.conversation_history = []  # The memory log
        self.current_lead_id: Optional[str] = None
        self.lead_profile = {
            "budget": None,
            "property_type": None,
            "timeline": None,
            "location": None,
            "score": "UNKNOWN"
        }

    async def process_call(self, user_text: str) -> Dict[str, Any]:
        """
        The Main Assembly Line: Process a user's input through the complete pipeline.

        This is the heart of the engine. Six steps:

        Args:
            user_text: The transcribed user speech

        Returns:
            Dictionary with:
            - 'audio_bytes': The response audio to play
            - 'response_text': The text response
            - 'lead_update': Updated lead profile
            - 'lead_id': The lead's ID
        """
        # ====================================================================
        # STEP A: LISTEN (Receive the input)
        # ====================================================================
        print(f"🎤 [STEP A] Listening to user: {user_text}")

        # ====================================================================
        # STEP B: REMEMBER (Add to conversation history)
        # ====================================================================
        print("[STEP B] Remembering user input...")
        self.conversation_history.append({
            "role": "user",
            "content": user_text,
            "timestamp": datetime.now().isoformat()
        })

        # Save to database
        if not self.current_lead_id:
            # Create a new lead if this is the first message
            lead_data = {
                "status": "in_call",
                "created_at": datetime.now().isoformat(),
                "initial_message": user_text
            }
            self.current_lead_id = await self.db.create_lead(lead_data)
            print(f"✅ Created new lead: {self.current_lead_id}")

        # Save transcript
        await self.db.save_transcript(
            self.current_lead_id,
            "user",
            user_text
        )

        # ====================================================================
        # STEP C: THINK (Generate AI response)
        # ====================================================================
        print("[STEP C] Thinking...")
        ai_response = await self._generate_response(user_text)
        print(f"💭 AI Response: {ai_response}")

        # Add AI response to conversation history
        self.conversation_history.append({
            "role": "agent",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })

        # Save AI response to database
        await self.db.save_transcript(
            self.current_lead_id,
            "agent",
            ai_response
        )

        # Extract lead data from the interaction
        lead_update = self._extract_lead_data(user_text, ai_response)
        self.lead_profile.update(lead_update)

        # ====================================================================
        # STEP D: SPEAK (Generate audio via TTS)
        # ====================================================================
        print("[STEP D] Speaking (generating audio)...")
        audio_bytes = await self.tts.synthesize(ai_response, language="en")
        print(f"✅ Generated audio ({len(audio_bytes)} bytes)")

        # ====================================================================
        # STEP E: ARCHIVE (Save to database)
        # ====================================================================
        print("[STEP E] Archiving...")
        await self.db.update_lead(
            self.current_lead_id,
            {
                "lead_profile": self.lead_profile,
                "last_updated": datetime.now().isoformat(),
                "message_count": len(self.conversation_history)
            }
        )
        print(f"✅ Archived to database")

        # ====================================================================
        # STEP F: DELIVER (Return results to caller)
        # ====================================================================
        print("[STEP F] Delivering response...")
        result = {
            "audio_bytes": audio_bytes,
            "response_text": ai_response,
            "lead_update": self.lead_profile,
            "lead_id": self.current_lead_id,
            "conversation_history": self.conversation_history
        }
        print("✅ Response delivered")

        return result

    async def _generate_response(self, user_text: str) -> str:
        """
        Generate an AI response using Groq's Llama 3.3 70B model.

        Args:
            user_text: The user's transcribed speech

        Returns:
            AI response text from Llama 3
        """
        # Build the messages array with system prompt and history
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a top-tier Pakistani real estate agent specializing in luxury properties. "
                    "Your goal is to qualify the lead by extracting: budget, property type (apartment/villa/plot/house), "
                    "timeline, and preferred location. Be conversational, professional, and concise. "
                    "Ask one clarifying question at a time. When you have enough info, provide a HOT/WARM/COLD score."
                )
            }
        ]

        # Add conversation history
        for entry in self.conversation_history:
            messages.append({
                "role": entry["role"],
                "content": entry["content"]
            })

        # Add current user input
        messages.append({
            "role": "user",
            "content": user_text
        })

        # Call Groq API
        response = await self.groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        return response.choices[0].message.content

    def _extract_lead_data(self, user_text: str, ai_response: str) -> Dict[str, Any]:
        """
        Extract structured lead data from the interaction.

        For the skeleton phase, this returns empty updates.
        In the next checkpoint, this will parse the real Groq response for lead data.

        Args:
            user_text: The user's text
            ai_response: The AI's response

        Returns:
            Dictionary with updated lead profile fields
        """
        # TODO: Implement real extraction logic via Groq API response parsing

        # Skeleton phase: Return empty updates
        return {}

    def _score_lead(self) -> str:
        """
        Calculate the lead score (HOT/WARM/COLD).

        For the skeleton phase, we always return UNKNOWN.
        In the next checkpoint, this will implement real scoring logic.

        Returns:
            Score string
        """
        # TODO: Implement real scoring logic

        return "UNKNOWN"

    def get_conversation_history(self) -> list:
        """Return the complete conversation history."""
        return self.conversation_history

    def get_lead_profile(self) -> Dict[str, Any]:
        """Return the current lead profile."""
        return self.lead_profile

    def get_current_lead_id(self) -> Optional[str]:
        """Return the current lead ID."""
        return self.current_lead_id
