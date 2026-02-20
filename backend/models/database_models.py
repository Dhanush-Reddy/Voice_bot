import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Float, Boolean, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

class Agent(Base):
    """SQLAlchemy model for Agent configuration."""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(String(4000), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(50), default="Aoede")
    model: Mapped[str] = mapped_column(String(100), default="gemini-2.0-flash-live-001")
    language: Mapped[str] = mapped_column(String(10), default="en-US")
    vad_min_volume: Mapped[float] = mapped_column(Float, default=0.15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    success_outcomes: Mapped[List[str]] = mapped_column(JSON, default=list)
    handoff_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    first_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    calls: Mapped[List["CallLog"]] = relationship("CallLog", back_populates="agent", cascade="all, delete-orphan")

class CallLog(Base):
    """SQLAlchemy model for call analytics and logs."""
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    participant_name: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="connected")  # connected, completed, failed
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(default=0)
    participant_count: Mapped[int] = mapped_column(default=1)
    transcript: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True) 
    summary: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    recording_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    outcome_tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    call_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="calls")
