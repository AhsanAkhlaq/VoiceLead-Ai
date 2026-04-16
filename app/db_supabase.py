"""
db_supabase.py - Supabase PostgreSQL Integration (💾 The Memory)

Handles lead storage, retrieval, and transcript history via Supabase (PostgreSQL).
Manages real-time lead updates for the agent monitoring dashboard.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client
from app.interfaces import DatabaseProvider


class SupabaseDB(DatabaseProvider):
    """
    Supabase (PostgreSQL) Database Provider.
    
    Manages:
    - Lead profiles and qualification data
    - Conversation transcripts
    - Lead scoring history
    - Real-time updates for dashboard
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """
        Initialize Supabase client.

        Args:
            supabase_url: Supabase project URL (defaults to env var)
            supabase_key: Supabase API key (defaults to env var)
        """
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_KEY")
        
        self.client = create_client(url, key)

    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """
        Create a new lead record in the database.

        Args:
            lead_data: Dictionary with lead information

        Returns:
            Lead ID (UUID)
        """
        payload = {
            "phone": lead_data.get("phone"),
            "property_type": lead_data.get("property_type"),
            "city": lead_data.get("city"),
            "area_society": lead_data.get("area_society"),
            "budget_range": lead_data.get("budget"),
            "timeline": lead_data.get("timeline"),
            "purpose": lead_data.get("purpose", "self-use"),
            "lead_score": lead_data.get("score", "unknown"),
            "transcript": [],
            "pipeline_status": "new"
        }

        response = self.client.table("leads").insert(payload).execute()
        
        if response.data:
            return response.data[0]["id"]
        raise Exception("Failed to create lead")

    async def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing lead's information.

        Args:
            lead_id: Lead ID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        payload = {}

        # Map engine fields to database fields
        if "lead_profile" in updates:
            profile = updates["lead_profile"]
            payload["budget_range"] = profile.get("budget")
            payload["property_type"] = profile.get("property_type")
            payload["area_society"] = profile.get("location")
            payload["timeline"] = profile.get("timeline")
            payload["lead_score"] = profile.get("score", "unknown").lower()

        if "lead_score" in updates:
            payload["lead_score"] = updates["lead_score"].lower()

        if "summary" in updates:
            payload["summary"] = updates["summary"]

        if payload:
            self.client.table("leads").update(payload).eq("id", lead_id).execute()

        return True

    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single lead by ID.

        Args:
            lead_id: Lead ID

        Returns:
            Lead data dictionary or None
        """
        response = self.client.table("leads").select("*").eq("id", lead_id).execute()

        if response.data:
            return response.data[0]
        return None

    async def get_all_leads(self) -> List[Dict[str, Any]]:
        """
        Retrieve all leads (for dashboard display).

        Returns:
            List of all lead records
        """
        response = self.client.table("leads").select("*").order("created_at", desc=True).execute()
        return response.data or []

    async def save_transcript(self, lead_id: str, role: str, message: str) -> bool:
        """
        Save a conversation message to the transcript.

        Args:
            lead_id: Lead ID
            role: 'user' or 'agent'
            message: Message text

        Returns:
            True if successful
        """
        # Get current transcript
        lead = await self.get_lead(lead_id)
        if not lead:
            return False

        transcript = lead.get("transcript", []) or []

        # Append new message
        transcript.append({
            "role": role,
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # Update lead with new transcript
        self.client.table("leads").update({
            "transcript": transcript
        }).eq("id", lead_id).execute()

        return True

    async def get_transcript(self, lead_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve full conversation transcript for a lead.

        Args:
            lead_id: Lead ID

        Returns:
            List of transcript messages in chronological order
        """
        lead = await self.get_lead(lead_id)
        if not lead:
            return []

        return lead.get("transcript", []) or []
