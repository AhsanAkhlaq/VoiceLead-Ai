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
import json
import re
from dotenv import load_dotenv
from groq import AsyncGroq
from app.interfaces import TTSProvider, DatabaseProvider

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
        self.conversation_history = []
        self.current_lead_id: Optional[str] = None
        self.call_start_time = datetime.now()
        self.extracted_data = {
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
        self.lead_profile = {
            "budget": None,
            "property_type": None,
            "timeline": None,
            "location": None,
            "score": "UNKNOWN",
            "sentiment": "neutral",
            "score_confidence": 0.0
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
        # (this is now called inside _generate_response and stream_response)

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
        call_duration = int((datetime.now() - self.call_start_time).total_seconds())
        summary = self._generate_summary()
        
        await self.db.update_lead(
            self.current_lead_id,
            {
                "name": self.extracted_data.get("name"),
                "phone": self.extracted_data.get("phone"),
                "property_type": self.extracted_data.get("property_type"),
                "city": self.extracted_data.get("city"),
                "area_society": self.extracted_data.get("area_society"),
                "size_requirement": self.extracted_data.get("size_requirement"),
                "budget_range": self.extracted_data.get("budget_range"),
                "timeline": self.extracted_data.get("timeline"),
                "purpose": self.extracted_data.get("purpose"),
                "additional_requirements": self.extracted_data.get("additional_requirements"),
                "lead_score": self.lead_profile.get("score"),
                "score_confidence": self.lead_profile.get("score_confidence"),
                "sentiment": self.lead_profile.get("sentiment"),
                "summary": summary,
                "transcript": self.conversation_history,
                "call_duration_seconds": call_duration,
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
        system_prompt = """You are  Lisa, a friendly Pakistani real estate agent for luxury properties. You work professionally and help people find their dream homes.

EXTRACTION GOALS (INTERNAL ONLY):
Get: name, property_type, city, budget, timeline, area/society, size, purpose, 

TONE:
- Friendly and professional, ENGLISH-first
- Brief (1-2 sentences max)
- Natural, conversational
- NO robotic phrases like "Got it", "Understood", "Noted"

SMART CONVERSATION FLOW:
Turn 1: "What's your name?" (extract name)
Turn 2: "What property are you looking for?" Combined answer might have: property type + location + budget + timeline
   - If user says: "house in DHA, 5 crore, 2 months" → Extract ALL of that, don't ask again
   - If user says: "three point five marla house" → Extract size + type, ask location next

Turn 3+: Ask ONLY what wasn't mentioned yet
   - Never ask twice for same info
   - If user said "cheap budget", accept it (don't need exact number)
   - Ask remaining items naturally

CLOSING:
- Only after user says "that's it", "no more", "we're done", "that's all"
- Close with: "Thanks for chatting! A specialist will contact you with options. Goodbye! [CALL_END]"

CRITICAL DO NOTS:
- Never Ask for info already given: "So you want a house in Lahore? What property are you looking for?"
- NeverRepeat confirmation: "5 crore? OK. 2 months? OK."
- Never Be judgmental about budget
- Never Close without user saying they're done
- Never Switch to Urdu/Hindi
- Never say "Got it", "Understood", "Noted" - sounds robotic
- Never repeat details back: "So house in DHA? OK. 5 crore? OK." - annoying
- Never be judgmental: "5 crore is a bit low" - use neutral: "5 crore is good for Lahore"
- Never switch to pure Urdu/Hindi - stay in English mostly
- Never close without having 6+ fields
- Never close without user confirming they're done"
"""

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        for entry in self.conversation_history:
            messages.append({
                "role": entry["role"],
                "content": entry["content"]
            })

        messages.append({
            "role": "user",
            "content": user_text
        })

        response = await self.groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        ai_response = response.choices[0].message.content
        
        self._extract_lead_data(user_text, ai_response)
        self._calculate_lead_score()
        
        return ai_response

    def _extract_lead_data(self, user_text: str, ai_response: str) -> Dict[str, Any]:
        combined_text = (user_text + " " + ai_response).lower()
        
        # Extract name from user_text (not AI response) - look for capitalized words
        if not self.extracted_data.get("name"):
            # Simple heuristic: if AI just asked for name, user's response is probably their name
            if "name" in ai_response.lower() or "your name" in ai_response.lower():
                # Take first 1-3 words from user as name (assuming they give it)
                words = user_text.strip().split()
                if len(words) > 0:
                    # Get first 1-2 words that look like names (start with capital or are short)
                    name_parts = []
                    for word in words[:3]:  # Check first 3 words
                        if word.isalpha() and len(word) > 1:  # Valid word
                            name_parts.append(word)
                        if len(name_parts) >= 2:  # Usually name is 1-2 words
                            break
                    if name_parts:
                        self.extracted_data["name"] = " ".join(name_parts)
        
        keywords = {
            "property_type": {
                "house": ["house", "ghar"],
                "apartment": ["apartment", "flat", "apt"],
                "plot": ["plot", "land", "zameen"],
                "commercial": ["commercial", "shop", "office"]
            },
            "city": {
                "Lahore": ["lahore"],
                "Karachi": ["karachi"],
                "Islamabad": ["islamabad"],
                "Faisalabad": ["faisalabad"],
                "Multan": ["multan"]
            },
            "timeline": {
                "Immediate": ["immediately", "asap", "now", "urgent"],
                "1-3 months": ["1.*month", "2.*month", "3.*month", "few months"],
                "3-6 months": ["3.*month", "4.*month", "5.*month", "6.*month"],
                "6+ months": ["6.*month", "year", "anytime"]
            },
            "purpose": {
                "self-use": ["live", "stay", "reside", "myself"],
                "investment": ["invest", "investment", "rental", "income"]
            }
        }
        
        for field, options in keywords.items():
            for value, patterns in options.items():
                for pattern in patterns:
                    if re.search(pattern, combined_text):
                        self.extracted_data[field] = value
                        break
        
        budget_match = re.search(r'(\d+(?:\s*(?:lakh|crore|lac|cr|k)))', combined_text)
        if budget_match:
            self.extracted_data["budget_range"] = budget_match.group(1).strip()
        
        area_match = re.search(r'(dha.*?(?:\d|phase)?\s*\d*|bahria.*?town|wapda.*?city)', combined_text)
        if area_match:
            self.extracted_data["area_society"] = area_match.group(1).strip()
        
        size_match = re.search(r'(\d+\s*(?:marla|kanal|sq.*?yd|sqyd))', combined_text)
        if size_match:
            self.extracted_data["size_requirement"] = size_match.group(1).strip()

    def _calculate_lead_score(self):
        fields_filled = sum(1 for v in self.extracted_data.values() if v is not None)
        
        if fields_filled >= 6:
            self.lead_profile["score"] = "HOT"
            self.lead_profile["score_confidence"] = 0.9
        elif fields_filled >= 4:
            self.lead_profile["score"] = "WARM"
            self.lead_profile["score_confidence"] = 0.7
        else:
            self.lead_profile["score"] = "COLD"
            self.lead_profile["score_confidence"] = 0.4
        
        self._analyze_sentiment()

    def _analyze_sentiment(self):
        positive_words = ["great", "perfect", "excellent", "yes", "definitely", "interested", "looking"]
        negative_words = ["no", "dont", "not interested", "maybe", "hesitant", "unsure"]
        
        history_text = " ".join([e["content"].lower() for e in self.conversation_history])
        
        pos_count = sum(history_text.count(word) for word in positive_words)
        neg_count = sum(history_text.count(word) for word in negative_words)
        
        if pos_count > neg_count:
            self.lead_profile["sentiment"] = "positive"
        elif neg_count > pos_count:
            self.lead_profile["sentiment"] = "hesitant"
        else:
            self.lead_profile["sentiment"] = "neutral"

    def _score_lead(self) -> str:
        """Calculate lead score based on extracted data."""
        return "UNKNOWN"

    def _generate_summary(self) -> str:
        """Generate AI 2-3 sentence summary of the lead."""
        data = self.extracted_data
        parts = []
        
        if data.get("property_type"):
            parts.append(f"Looking for {data['property_type']}")
        if data.get("area_society") or data.get("city"):
            location = data.get("area_society") or data.get("city") or ""
            parts.append(f"in {location}")
        if data.get("budget_range"):
            parts.append(f"with budget of {data['budget_range']}")
        
        summary = " ".join(parts)
        
        if data.get("timeline"):
            summary += f". Timeline: {data['timeline']}."
        if data.get("purpose"):
            summary += f" Purpose: {data['purpose']}."
        
        return summary if summary else "Lead information collected during call."

    def get_conversation_history(self) -> list:
        """Return the complete conversation history."""
        return self.conversation_history

    def get_lead_profile(self) -> Dict[str, Any]:
        """Return the current lead profile."""
        return self.lead_profile

    def get_current_lead_id(self) -> Optional[str]:
        """Return the current lead ID."""
        return self.current_lead_id

    def should_end_call(self, ai_response: str) -> bool:
        """Check if AI marked the call for termination."""
        return "[CALL_END]" in ai_response
    
    def get_clean_response(self, ai_response: str) -> str:
        """Remove [CALL_END] marker from response before returning."""
        return ai_response.replace("[CALL_END]", "").strip()
