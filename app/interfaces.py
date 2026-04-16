"""
interfaces.py - The Blueprints

Abstract base classes and interfaces for the VoiceLead AI system.
Defines the contracts for TTS, Database, and other pluggable providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Convert text to speech audio bytes.

        Args:
            text: The text to synthesize
            language: Language code (e.g., 'en' for English, 'ur' for Urdu)

        Returns:
            Audio bytes ready to stream
        """
        pass


class DatabaseProvider(ABC):
    """Abstract base class for database providers."""

    @abstractmethod
    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """Create a new lead and return the lead ID."""
        pass

    @abstractmethod
    async def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing lead."""
        pass

    @abstractmethod
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lead details by ID."""
        pass

    @abstractmethod
    async def get_all_leads(self) -> list:
        """Retrieve all leads."""
        pass

    @abstractmethod
    async def save_transcript(self, lead_id: str, role: str, message: str) -> bool:
        """Save conversation transcript."""
        pass
