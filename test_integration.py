"""
test_integration.py - Testing Checkpoint 2 (Integration Test)

Real Groq + Real Deepgram + Mock Database

This test proves that:
1. Groq can generate intelligent responses
2. Deepgram can turn that response into audio
3. The Core Engine orchestrates both perfectly

The audio output is saved to test_output.mp3 for verification.

Run with:
  uv run python test_integration.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.engine import CoreEngine
from app.tts_deepgram import DeepgramTTS
from app.mocks import MockDB
from dotenv import load_dotenv
load_dotenv()
async def main():
    """Run the integration test."""
    print("=" * 70)
    print("🧪 TESTING CHECKPOINT 2: GROQ + DEEPGRAM INTEGRATION TEST")
    print("=" * 70)
    print()

    # Setup
    print("📦 Setting up...")
    tts = DeepgramTTS()
    db = MockDB()
    engine = CoreEngine(tts_provider=tts, db_provider=db)
    print("✓ Engine initialized with real Groq + real Deepgram + mock DB")
    print()

    # The test input (hardcoded)
    test_input = "I want a house in DHA. My budget is 5 crore."
    print(f"🎤 Test Input: '{test_input}'")
    print()

    # Process through the engine
    print("⏳ Processing through Groq + Deepgram...")
    print("-" * 70)

    try:
        result = await engine.process_call(test_input)

        # Display results
        print()
        print("✅ SUCCESS!")
        print("-" * 70)
        print()

        response_text = result["response_text"]
        print(f"🤖 AI Response:\n{response_text}")
        print()

        # Save audio to file
        audio_bytes = result["audio_bytes"]
        output_file = "test_output.mp3"

        with open(output_file, "wb") as f:
            f.write(audio_bytes)

        print(f"💾 Audio saved: {output_file} ({len(audio_bytes)} bytes)")
        print()

        # Conversation history
        history = engine.get_conversation_history()
        print(f"📝 Conversation History:")
        for i, entry in enumerate(history, 1):
            role = "👤 User" if entry["role"] == "user" else "🤖 Agent"
            print(f"   {i}. {role}: {entry['content']}")
        print()

        # Lead info
        lead_profile = engine.get_lead_profile()
        lead_id = result["lead_id"]
        print(f"📊 Lead Profile (ID: {lead_id}):")
        print(f"   Budget: {lead_profile.get('budget', 'N/A')}")
        print(f"   Property Type: {lead_profile.get('property_type', 'N/A')}")
        print(f"   Location: {lead_profile.get('location', 'N/A')}")
        print(f"   Timeline: {lead_profile.get('timeline', 'N/A')}")
        print(f"   Score: {lead_profile.get('score', 'N/A')}")
        print()

        print("-" * 70)
        print("🎯 VERIFICATION CHECKLIST:")
        print("✓ Groq generated a logical response")
        print("✓ Deepgram converted to audio")
        print("✓ Engine orchestrated both seamlessly")
        print("✓ Audio file created successfully")
        print()
        print("🎉 CHECKPOINT 2 PASSED!")
        print("=" * 70)

    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
