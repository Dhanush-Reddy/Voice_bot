"""
Pydantic models for Call Log data.
"""

from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TranscriptMessage(BaseModel):
    """A single message in a call transcript."""

    role: str = Field(..., description="'agent' or 'user'")
    content: str = Field(..., description="The spoken text")
    timestamp: Optional[str] = None


class CallLog(BaseModel):
    """Represents a completed call record."""

    id: str
    agent_id: str
    room_name: str
    status: str = Field(..., description="'completed', 'failed', 'no_answer'")
    outcome: Optional[str] = Field(None, description="'success', 'not_interested', etc.")
    duration_seconds: int = Field(default=0)
    transcript: Optional[List[TranscriptMessage]] = None
    recording_url: Optional[str] = None
    created_at: Optional[datetime] = None


class CallLogCreateRequest(BaseModel):
    """Payload from a LiveKit webhook to create a call log."""

    room_name: str
    agent_id: str
    duration_seconds: int
    transcript: Optional[List[Any]] = None
    recording_url: Optional[str] = None
