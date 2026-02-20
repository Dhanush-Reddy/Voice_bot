"""
Pydantic models for Agent configuration.
These are the canonical data shapes used across the entire application.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Represents a fully-configured voice agent."""

    id: str = Field(..., description="Unique agent UUID")
    name: str = Field(..., description="Human-readable agent name")
    system_prompt: str = Field(..., description="The LLM system instruction")
    voice_id: str = Field(default="Aoede", description="Gemini voice name")
    model: str = Field(default="gemini-2.0-flash-live-001", description="LLM model ID")
    language: str = Field(default="en-US", description="Primary language code")
    vad_min_volume: float = Field(default=0.15, description="VAD sensitivity threshold")
    is_active: bool = Field(default=True, description="Whether the agent is active")
    # Sprint 2 additions
    temperature: float = Field(
        default=0.7, ge=0.0, le=1.0, description="LLM temperature"
    )
    success_outcomes: List[str] = Field(
        default_factory=lambda: ["Appointment Booked"],
        description="Tags for successful calls",
    )
    handoff_number: Optional[str] = Field(
        default=None, description="PSTN number to transfer to a human"
    )
    first_message: Optional[str] = Field(
        default=None, description="Agent's opening line when a call connects"
    )


class AgentCreateRequest(BaseModel):
    """Request body for creating a new agent."""

    name: str
    system_prompt: str
    voice_id: Optional[str] = "Aoede"
    model: Optional[str] = "gemini-2.0-flash-live-001"
    language: Optional[str] = "en-US"
    temperature: Optional[float] = 0.7
    success_outcomes: Optional[List[str]] = None
    handoff_number: Optional[str] = None
    first_message: Optional[str] = None


class AgentUpdateRequest(BaseModel):
    """Request body for updating an existing agent."""

    name: Optional[str] = None
    system_prompt: Optional[str] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    temperature: Optional[float] = None
    success_outcomes: Optional[List[str]] = None
    handoff_number: Optional[str] = None
    first_message: Optional[str] = None


class TokenRequest(BaseModel):
    """Parameters for generating a LiveKit token."""

    participant_name: str
    agent_id: Optional[str] = None  # If None, uses the default agent config


class TokenResponse(BaseModel):
    """Response containing the LiveKit connection credentials."""

    token: str
    url: str
    room_name: str
    agent_id: Optional[str] = None
