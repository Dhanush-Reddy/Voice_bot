"""
CallLogService — business logic for persisting and querying call records.

Sprint 1: In-memory store.
Sprint 4: Enhanced with outcome/status filtering, agent_name enrichment,
          and a dedicated method for processing LiveKit webhook payloads.
Sprint 5: Will be replaced with a Supabase repository.
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone

from models.call_log import CallLog, CallLogCreateRequest, LiveKitWebhookPayload

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
            status=request.status,
            outcome=request.outcome,
            duration_seconds=request.duration_seconds,
            participant_count=request.participant_count,
            transcript=request.transcript,
            recording_url=request.recording_url,
            metadata=request.metadata,
            created_at=datetime.now(timezone.utc),
        )
        _call_store[call.id] = call
        logger.info("📞 Call log saved: %s (room=%s, status=%s)", call.id, call.room_name, call.status)
        return call

    async def process_livekit_webhook(self, payload: LiveKitWebhookPayload) -> Optional[CallLog]:
        """
        Process a LiveKit webhook event and create a call log.

        Currently handles:
          - room_finished: creates a CallLog from room metadata
        """
        if payload.event != "room_finished":
            logger.info("⏭️  Ignoring LiveKit event: %s", payload.event)
            return None

        room = payload.room or {}
        room_name = room.get("name", "unknown")
        duration = int(room.get("active_recording_duration", 0) or room.get("num_seconds", 0))
        num_participants = int(room.get("num_participants", 1))

        # Extract agent_id from room metadata (set by pool.py when spawning)
        metadata: dict = {}
        if room.get("metadata"):
            import json
            try:
                metadata = json.loads(room["metadata"])
            except Exception:
                metadata = {}

        agent_id = metadata.get("agent_id", "unknown")

        request = CallLogCreateRequest(
            room_name=room_name,
            agent_id=agent_id,
            duration_seconds=duration,
            status="completed",
            participant_count=num_participants,
            metadata={"livekit_room": room},
        )
        call = await self.create_call_log(request)
        logger.info("🔔 LiveKit webhook processed: room=%s → call_id=%s", room_name, call.id)
        return call

    async def list_calls(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
    ) -> List[CallLog]:
        """Return call logs with optional filters."""
        calls = list(_call_store.values())
        if agent_id:
            calls = [c for c in calls if c.agent_id == agent_id]
        if status:
            calls = [c for c in calls if c.status == status]
        if outcome:
            calls = [c for c in calls if c.outcome == outcome]
        # Sort newest first
        calls.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
        return calls[:limit]

    async def get_call(self, call_id: str) -> Optional[CallLog]:
        """Fetch a single call record by ID (includes transcript)."""
        return _call_store.get(call_id)

    async def delete_call(self, call_id: str) -> bool:
        """Delete a call log. Returns True if deleted."""
        if call_id in _call_store:
            del _call_store[call_id]
            logger.info("🗑️  Call log deleted: %s", call_id)
            return True
        return False

    @property
    def stats(self) -> dict:
        """Quick stats for the health endpoint."""
        calls = list(_call_store.values())
        return {
            "total": len(calls),
            "completed": sum(1 for c in calls if c.status == "completed"),
            "failed": sum(1 for c in calls if c.status == "failed"),
        }


# Module-level singleton
call_log_service = CallLogService()
