import os
import json
from typing import Optional, Dict, Any
from datetime import datetime
from groq import AsyncGroq
from app.services import StreamingDeepgramTTS, SupabaseDB

class CoreEngine:
    def __init__(self, tts_provider: StreamingDeepgramTTS, db_provider: SupabaseDB):
        self.tts = tts_provider
        self.db = db_provider
        self.groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        
        self.conversation_history = []
        self.current_lead_id: Optional[str] = None
        self.call_start_time = datetime.now()

    # ==========================================
    # ⚡ BRAIN 1: THE FAST CONVERSATIONALIST
    # ==========================================
    async def _generate_response(self, user_text: str) -> str:
        system_prompt = """You are Lisa, a friendly Pakistani real estate agent.
        YOUR GOAL: Extract the user's name, property type, location, budget, and timeline.

        STRICT RULES:
        1. NEVER mention scores, points, HOT/WARM/COLD to the user.
        2. Ask only ONE question at a time.
        3. Keep your answers short (1-2 sentences).
        4. Never repeat details back like a robot.

        HOW TO END THE CALL:
        When you have collected the Budget, Property Type, Location, and Timeline, YOU MUST END THE CALL.
        Say: "Thank you, I have all the details we need. A senior agent will contact you shortly. Goodbye! [CALL_END]"
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend([{"role": e["role"], "content": e["content"]} for e in self.conversation_history])
        messages.append({"role": "user", "content": user_text})

        response = await self.groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=250
        )

        return response.choices[0].message.content

    # ==========================================
    # 🔬 BRAIN 2: THE DEEP ANALYST
    # ==========================================
    async def analyze_completed_call(self, lead_id: str) -> bool:
        if not self.conversation_history:
            return False

        print(f"🔬 [ANALYST] Starting post-call analysis for lead: {lead_id}")
        transcript_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.conversation_history])
        
        system_prompt = """Extract lead data from the transcript. 
        Return a valid JSON object using exactly these keys (use null if missing):
        - "name" (string)
        - "property_type" (string: plot, apartment, house, commercial)
        - "city" (string)
        - "area_society" (string)
        - "size_requirement" (string)
        - "budget_range" (string)
        - "timeline" (string: immediate, 1-3 months, 3-6 months)
        - "purpose" (string: investment, self-use, rental)
        - "additional_requirements" (string)
        - "score_confidence" (float: 0.0 to 100.0 based on buyer readiness)
        - "sentiment" (string: positive, neutral, hesitant, frustrated)
        - "summary" (string: 2-3 sentence professional summary)
        """

        try:
            response = await self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript_text}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content.strip()
            
            # Clean markdown code blocks if the LLM outputted them despite JSON mode
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            
            extracted_data = json.loads(raw_content.strip())
            
            payload = {**extracted_data}
            payload["call_duration_seconds"] = int((datetime.now() - self.call_start_time).total_seconds())
            payload["pipeline_status"] = "contacted"
            payload["transcript"] = self.conversation_history
            
            # Clean nulls to respect DB defaults
            clean_payload = {k: v for k, v in payload.items() if v is not None}

            await self.db.update_lead(lead_id, clean_payload)
            print("✅ [ANALYST] Database updated successfully!")
            return True

        except Exception as e:
            print(f"❌ [ANALYST] Error analyzing call: {e}")
            return False

    def should_end_call(self, ai_response: str) -> bool:
        return "[CALL_END]" in ai_response
    
    def get_clean_response(self, ai_response: str) -> str:
        return ai_response.replace("[CALL_END]", "").strip()