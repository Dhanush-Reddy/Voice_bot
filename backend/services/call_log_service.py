"""
CallLogService — business logic for persisting and querying call records.

Sprint 1: In-memory store.
Sprint 4: Will be replaced with a Supabase repository.
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone

from models.call_log import CallLog, CallLogCreateRequest

logger = logging.getLogger(__name__)

# In-memory store: { call_id -> CallLog }
_call_store: dict[str, CallLog] = {}


class CallLogService:
    """Handles persistence and retrieval of call records."""

    async def create_call_log(self, request: CallLogCreateRequest) -> CallLog:
        """Persist a new call record after a call ends."""
        call = CallLog(
            id=str(uuid.uuid4()),
            agent_id=request.agent_id,
            room_name=request.room_name,
            status="completed",
            duration_seconds=request.duration_seconds,
            transcript=request.transcript,
            recording_url=request.recording_url,
            created_at=datetime.now(timezone.utc),
        )
        _call_store[call.id] = call
        logger.info("📞 Call log saved: %s (room=%s)", call.id, call.room_name)
        return call

    async def list_calls(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[CallLog]:
        """Return call logs, optionally filtered by agent."""
        calls = list(_call_store.values())
        if agent_id:
            calls = [c for c in calls if c.agent_id == agent_id]
        # Sort newest first
        calls.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
        return calls[:limit]

    async def get_call(self, call_id: str) -> Optional[CallLog]:
        """Fetch a single call record by ID."""
        return _call_store.get(call_id)


# Module-level singleton
call_log_service = CallLogService()
