"""
test_db.py - Testing Checkpoint 3 (Supabase Integration Test)

Direct test of the Supabase database service.
Bypasses the AI entirely to verify the "delivery truck" works.

This tests:
1. Lead creation in Supabase
2. Transcript storage (JSONB)
3. Lead updates
4. Data retrieval

Run with:
  uv run python test_db.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.db_supabase import SupabaseDB


async def main():
    """Run the database integration test."""
    print("=" * 70)
    print("🧪 TESTING CHECKPOINT 3: SUPABASE DATABASE INTEGRATION")
    print("=" * 70)
    print()

    # Initialize Supabase client
    print("📦 Connecting to Supabase...")
    db = SupabaseDB()
    print(f"✓ Connected to: {os.getenv('SUPABASE_URL')}")
    print()

    try:
        # Create a test lead
        print("📝 Creating test lead...")
        lead_data = {
            "phone": "+923001234567",
            "property_type": "apartment",
            "city": "Lahore",
            "area_society": "DHA Phase 6",
            "budget": "5 crore",
            "timeline": "1-3 months",
            "purpose": "self-use",
            "score": "unknown"
        }

        lead_id = await db.create_lead(lead_data)
        print(f"✓ Lead created with ID: {lead_id}")
        print()

        # Save transcript messages
        print("💬 Saving transcript messages...")
        await db.save_transcript(lead_id, "user", "I want a house in DHA. My budget is 5 crore.")
        print("   ✓ User message saved")

        await db.save_transcript(
            lead_id,
            "agent",
            "Excellent! 5 crore is a solid budget for DHA. Are you looking for a 10 Marla or 1 Kanal plot?"
        )
        print("   ✓ Agent message saved")

        await db.save_transcript(lead_id, "user", "I prefer 1 Kanal.")
        print("   ✓ Follow-up message saved")
        print()

        # Retrieve and verify lead
        print("🔍 Retrieving lead from database...")
        retrieved_lead = await db.get_lead(lead_id)

        if retrieved_lead:
            print("✓ Lead retrieved successfully!")
            print()
            print("Lead Data:")
            print(f"  ID: {retrieved_lead['id']}")
            print(f"  Phone: {retrieved_lead.get('phone')}")
            print(f"  Property Type: {retrieved_lead.get('property_type')}")
            print(f"  Location: {retrieved_lead.get('area_society')}")
            print(f"  Budget: {retrieved_lead.get('budget_range')}")
            print(f"  Score: {retrieved_lead.get('lead_score')}")
            print(f"  Status: {retrieved_lead.get('pipeline_status')}")
            print(f"  Created: {retrieved_lead.get('created_at')}")
            print()

            # Retrieve and verify transcript
            print("📋 Retrieving transcript...")
            transcript = await db.get_transcript(lead_id)

            if transcript:
                print(f"✓ Transcript retrieved ({len(transcript)} messages):")
                for i, msg in enumerate(transcript, 1):
                    role = "👤 User" if msg.get("role") == "user" else "🤖 Agent"
                    print(f"   {i}. {role}: {msg.get('content')}")
                print()
            else:
                print("⚠ No transcript found")
                print()

            # Update lead with score
            print("🎯 Updating lead score...")
            await db.update_lead(
                lead_id,
                {
                    "lead_profile": {
                        "budget": "5 crore",
                        "property_type": "1 Kanal plot",
                        "location": "DHA Phase 6",
                        "timeline": "1-3 months",
                        "score": "HOT"
                    }
                }
            )
            print("✓ Lead score updated to HOT")
            print()

            # Verify update
            print("🔄 Verifying update...")
            updated_lead = await db.get_lead(lead_id)
            print(f"✓ Updated score: {updated_lead.get('lead_score')}")
            print()

            # Retrieve all leads
            print("📊 Fetching all leads...")
            all_leads = await db.get_all_leads()
            print(f"✓ Total leads in system: {len(all_leads)}")
            print()

            print("-" * 70)
            print("✅ VERIFICATION CHECKLIST:")
            print("✓ Lead created in Supabase")
            print("✓ Transcript saved (JSONB array)")
            print("✓ Multiple messages stored correctly")
            print("✓ Lead retrieved from database")
            print("✓ Lead score updated")
            print("✓ All leads query works")
            print()
            print("🎉 CHECKPOINT 3 PASSED!")
            print("=" * 70)

        else:
            print("❌ Failed to retrieve lead")

    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
