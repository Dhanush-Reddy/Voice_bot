"""
Pydantic models for Call Log data.
"""

from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Outcome constants
# ---------------------------------------------------------------------------
class Outcome:
    SUCCESS = "success"
    NOT_INTERESTED = "not_interested"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    COMPLETED = "completed"


class TranscriptMessage(BaseModel):
    """A single message in a call transcript."""

    role: str = Field(..., description="'agent' or 'user'")
    content: str = Field(..., description="The spoken text")
    timestamp: Optional[str] = None


class CallLog(BaseModel):
    """Represents a completed call record."""

    id: str
    agent_id: str
    agent_name: Optional[str] = None
    room_name: str
    status: str = Field(..., description="'completed', 'failed', 'no_answer'")
    outcome: Optional[str] = Field(None, description="'success', 'not_interested', etc.")
    duration_seconds: int = Field(default=0)
    participant_count: int = Field(default=1, description="Number of participants in the room")
    transcript: Optional[List[TranscriptMessage]] = None
    recording_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra data from LiveKit webhook")
    created_at: Optional[datetime] = None


class CallLogCreateRequest(BaseModel):
    """Payload to create a call log — accepts LiveKit webhook data."""

    room_name: str
    agent_id: str
    duration_seconds: int
    status: str = "completed"
    outcome: Optional[str] = None
    participant_count: int = 1
    transcript: Optional[List[Any]] = None
    recording_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LiveKitWebhookPayload(BaseModel):
    """
    Subset of the LiveKit room_finished webhook payload.
    See: https://docs.livekit.io/home/server/webhooks/
    """

    event: str = Field(..., description="e.g. 'room_finished'")
    room: Optional[Dict[str, Any]] = None
    participant: Optional[Dict[str, Any]] = None
