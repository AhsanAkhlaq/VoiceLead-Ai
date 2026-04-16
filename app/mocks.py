"""
mocks.py - The "Stunt Doubles" (Fake Implementations)

Mock implementations of TTS and Database providers for testing.
These are invisible objects that claim to be real providers but don't actually
call external APIs. They have built-in memory so we can interrogate them later.
"""

from typing import Dict, Any, List, Optional
from app.interfaces import TTSProvider, DatabaseProvider


class MockTTS(TTSProvider):
    """
    The TTS Stunt Double.
    
    When handed text, it doesn't go to the internet. Instead:
    - It instantly returns fake audio bytes
    - It records every call for later interrogation
    """

    def __init__(self):
        """Initialize the mock with call tracking."""
        self.call_history = []
        self.call_count = 0

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Fake TTS synthesis that doesn't call Deepgram.

        Args:
            text: The text to "synthesize"
            language: Language code (ignored in mock)

        Returns:
            Fake audio bytes (just a marker)
        """
        # Track this call
        self.call_history.append({
            "text": text,
            "language": language,
            "call_number": self.call_count
        })
        self.call_count += 1

        # Return fake audio bytes (in real implementation, would be MP3/WAV)
        # This is just a marker: b"FAKE_AUDIO_DATA"
        return f"FAKE_AUDIO_{self.call_count}".encode()

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Return the complete call history for interrogation."""
        return self.call_history

    def was_called_with(self, text: str, language: str = "en") -> bool:
        """
        Detective question: "Were you ever called with this exact text?"

        Args:
            text: The expected text
            language: The expected language

        Returns:
            True if found in call history
        """
        return any(
            call["text"] == text and call["language"] == language
            for call in self.call_history
        )


class MockDB(DatabaseProvider):
    """
    The Database Stunt Double.
    
    When handed data, it doesn't connect to Supabase. Instead:
    - It instantly returns success (True)
    - It records every interaction in memory
    - It stores fake lead data locally
    """

    def __init__(self):
        """Initialize the mock with data storage and call tracking."""
        self.leads = {}  # Fake in-memory lead storage
        self.transcripts = {}  # Fake transcript storage
        self.call_history = {
            "create_lead": [],
            "update_lead": [],
            "get_lead": [],
            "get_all_leads": [],
            "save_transcript": []
        }
        self.next_lead_id = 1

    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """
        Create a fake lead without touching Supabase.

        Args:
            lead_data: Lead information

        Returns:
            Fake lead ID
        """
        lead_id = f"MOCK_LEAD_{self.next_lead_id}"
        self.next_lead_id += 1

        self.call_history["create_lead"].append({
            "lead_data": lead_data,
            "returned_id": lead_id
        })

        self.leads[lead_id] = lead_data
        self.transcripts[lead_id] = []

        return lead_id

    async def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """
        Fake lead update without touching Supabase.

        Args:
            lead_id: Lead ID
            updates: Fields to update

        Returns:
            Always True (success)
        """
        self.call_history["update_lead"].append({
            "lead_id": lead_id,
            "updates": updates
        })

        if lead_id in self.leads:
            self.leads[lead_id].update(updates)

        return True

    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Fake lead retrieval from in-memory storage.

        Args:
            lead_id: Lead ID

        Returns:
            Lead data or None
        """
        self.call_history["get_lead"].append({
            "lead_id": lead_id
        })

        return self.leads.get(lead_id)

    async def get_all_leads(self) -> List[Dict[str, Any]]:
        """
        Fake retrieval of all leads.

        Returns:
            List of all fake leads
        """
        self.call_history["get_all_leads"].append({
            "timestamp": "mock_call"
        })

        return list(self.leads.values())

    async def save_transcript(self, lead_id: str, role: str, message: str) -> bool:
        """
        Fake transcript saving to in-memory storage.

        Args:
            lead_id: Lead ID
            role: 'user' or 'agent'
            message: Message text

        Returns:
            Always True (success)
        """
        self.call_history["save_transcript"].append({
            "lead_id": lead_id,
            "role": role,
            "message": message
        })

        if lead_id in self.transcripts:
            self.transcripts[lead_id].append({
                "role": role,
                "message": message
            })

        return True

    async def get_transcript(self, lead_id: str) -> List[Dict[str, Any]]:
        """
        Fake transcript retrieval.

        Args:
            lead_id: Lead ID

        Returns:
            List of transcript messages
        """
        return self.transcripts.get(lead_id, [])

    # ========================================================================
    # INTERROGATION METHODS (For Detective/Test Questions)
    # ========================================================================

    def was_called(self, method: str) -> bool:
        """
        Detective question: "Were you called at all?"

        Args:
            method: Method name like 'save_transcript', 'update_lead'

        Returns:
            True if method was called at least once
        """
        if method not in self.call_history:
            return False
        return len(self.call_history[method]) > 0

    def call_count(self, method: str) -> int:
        """
        Detective question: "How many times were you called?"

        Args:
            method: Method name

        Returns:
            Number of times called
        """
        if method not in self.call_history:
            return 0
        return len(self.call_history[method])

    def get_calls(self, method: str) -> List[Dict[str, Any]]:
        """
        Detective question: "What exactly were you called with?"

        Args:
            method: Method name

        Returns:
            List of call arguments
        """
        return self.call_history.get(method, [])

    def was_called_with_transcript(self, lead_id: str, role: str, message: str) -> bool:
        """
        Detective question: "Were you saved with this exact transcript?"

        Args:
            lead_id: Lead ID
            role: 'user' or 'agent'
            message: Message text

        Returns:
            True if found
        """
        return any(
            call["lead_id"] == lead_id
            and call["role"] == role
            and call["message"] == message
            for call in self.call_history["save_transcript"]
        )

    def get_stored_data(self, lead_id: str) -> Dict[str, Any]:
        """
        Detective question: "What data is stored about this lead?"

        Args:
            lead_id: Lead ID

        Returns:
            Dictionary of lead data
        """
        return {
            "lead_info": self.leads.get(lead_id, {}),
            "transcript": self.transcripts.get(lead_id, [])
        }
