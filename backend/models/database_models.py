import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Float, Boolean, JSON, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

# --- NextAuth Prisma Models Equivalent ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    emailVerified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    agents: Mapped[List["Agent"]] = relationship("Agent", back_populates="user", cascade="all, delete-orphan")

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    providerAccountId: Mapped[str] = mapped_column(String(255))
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    id_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="accounts")

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sessionToken: Mapped[str] = mapped_column(String(255), unique=True)
    userId: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped["User"] = relationship("User", back_populates="sessions")

class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    identifier: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(255), primary_key=True)
    expires: Mapped[datetime] = mapped_column(DateTime)

# --- Application Models ---

class Agent(Base):
    """SQLAlchemy model for Agent configuration."""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
    user: Mapped[Optional["User"]] = relationship("User", back_populates="agents")
    calls: Mapped[List["CallLog"]] = relationship("CallLog", back_populates="agent", cascade="all, delete-orphan")

class CallLog(Base):
    """SQLAlchemy model for call analytics and logs."""
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
