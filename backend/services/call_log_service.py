import uuid
import logging
import json
import asyncio
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from models.call_log import CallLog, CallLogCreateRequest, LiveKitWebhookPayload, Outcome
from models.database_models import CallLog as CallLogModel, Agent as AgentModel
from core.database import AsyncSessionLocal
from core.config import settings

logger = logging.getLogger(__name__)

class CallLogService:
    """Handles persistence and retrieval of call records via SQLAlchemy with AI enrichment."""

    def __init__(self):
        # Configure modern Gemini client
        self.client = None
        try:
            # For summarization/analytics, a standard API Key is the most reliable & lightweight method.
            if settings.gemini_api_key:
                logger.info("🧠 [AI] Initializing Gemini Intelligence via API Key")
                self.client = genai.Client(api_key=settings.gemini_api_key)
            elif settings.google_credentials_json:
                logger.info("🧠 [AI] Initializing Gemini Intelligence via Vertex AI (GCP Service Account)")
                # Pass the project/location, the SDK handles the GOOGLE_APPLICATION_CREDENTIALS env var automatically
                self.client = genai.Client(
                    vertexai=True,
                    project=settings.google_cloud_project,
                    location=settings.google_cloud_location
                )
            else:
                logger.warning("⚠️ [AI] No GEMINI_API_KEY found. Summarization will be skipped.")
        except Exception as e:
            logger.error(f"❌ [AI] Failed to initialize Gemini client: {e}")

    def _to_pydantic(self, model: CallLogModel, agent_name: Optional[str] = None) -> CallLog:
        """Helper to convert SQLAlchemy model to Pydantic CallLog."""
        return CallLog(
            id=model.id,
            agent_id=model.agent_id,
            agent_name=agent_name,
            room_name=model.room_name,
            status=model.status,
            outcome=model.outcome,
            duration_seconds=model.duration_seconds,
            participant_count=model.participant_count,
            transcript=model.transcript,
            summary=model.summary,
            recording_url=model.recording_url,
            metadata=model.call_metadata,
            created_at=model.created_at,
        )

    async def _generate_ai_intelligence(self, transcript: List[dict]) -> tuple[Optional[str], Optional[str]]:
        """Uses Gemini to summarize the call and determine the outcome."""
        if not self.client or not transcript:
            return None, None

        try:
            # Format transcript for the LLM
            lines = []
            for entry in transcript:
                role = entry.get("role", "unknown")
                content = entry.get("content", "")
                lines.append(f"{role.upper()}: {content}")
            full_transcript = "\n".join(lines)

            # 1. Generate Summary
            summary_prompt = f"Summarize the following phone call transcript in 1-2 concise sentences. Focus on the user's intent and the final resolution.\n\nTranscript:\n{full_transcript}"
            
            # 2. Determine Outcome
            outcome_prompt = f"Analyze the following phone call transcript and determine the primary outcome. Choose ONLY one from: success, not_interested, no_answer, failed, completed. Respond with just the single word.\n\nTranscript:\n{full_transcript}\n\nOutcome:"

            # Run concurrently for speed
            responses = await asyncio.gather(
                asyncio.to_thread(self.client.models.generate_content, model='gemini-2.0-flash', contents=summary_prompt),
                asyncio.to_thread(self.client.models.generate_content, model='gemini-2.0-flash', contents=outcome_prompt)
            )

            summary = responses[0].text.strip()
            outcome = responses[1].text.strip().lower()

            # Validate outcome against constants
            valid_outcomes = [Outcome.SUCCESS, Outcome.NOT_INTERESTED, Outcome.NO_ANSWER, Outcome.FAILED, Outcome.COMPLETED]
            if outcome not in valid_outcomes:
                outcome = Outcome.COMPLETED

            return summary, outcome
        except Exception as e:
            logger.error(f"❌ AI Intelligence generation failed: {e}")
            return None, None

    async def create_call_log(self, request: CallLogCreateRequest, user_id: Optional[str] = None, db: Optional[AsyncSession] = None) -> CallLog:
        """Persist a new call record after a call ends, enriched with AI intelligence."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.create_call_log(request, user_id, session)

        # Generate AI summary and outcome if transcript is available
        ai_summary = None
        ai_outcome = request.outcome
        
        if request.transcript:
            ai_summary, detected_outcome = await self._generate_ai_intelligence(request.transcript)
            if detected_outcome:
                ai_outcome = detected_outcome

        # Use request.user_id if provided, otherwise fallback to user_id param
        final_user_id = request.user_id or user_id

        # Check if a CallLog already exists for this room (pre-created by /api/token)
        result = await db.execute(select(CallLogModel).where(CallLogModel.room_name == request.room_name).order_by(CallLogModel.created_at.desc()))
        existing = result.scalars().first()

        if existing:
            # Update existing record
            existing.status = request.status
            existing.outcome = ai_outcome
            existing.duration_seconds = request.duration_seconds
            existing.participant_count = request.participant_count
            existing.transcript = request.transcript
            existing.summary = ai_summary
            existing.recording_url = request.recording_url
            if hasattr(request, "agent_id") and request.agent_id:
                existing.agent_id = request.agent_id
            if request.metadata:
                existing.call_metadata = request.metadata
            if final_user_id and not existing.user_id:
                existing.user_id = final_user_id

            await db.commit()
            await db.refresh(existing)
            logger.info("📞 Call log updated in DB: %s (room=%s, outcome=%s)", existing.id, existing.room_name, ai_outcome)
            return self._to_pydantic(existing)

        model = CallLogModel(
            id=str(uuid.uuid4()),
            user_id=final_user_id,
            agent_id=request.agent_id,
            room_name=request.room_name,
            status=request.status,
            outcome=ai_outcome,
            duration_seconds=request.duration_seconds,
            participant_count=request.participant_count,
            transcript=request.transcript,
            summary=ai_summary,
            recording_url=request.recording_url,
            call_metadata=request.metadata,
            created_at=datetime.now(timezone.utc),
        )
        db.add(model)
        await db.commit()
        await db.refresh(model)
        
        logger.info("📞 Call log saved to DB: %s (room=%s, outcome=%s)", model.id, model.room_name, ai_outcome)
        return self._to_pydantic(model)

    async def process_livekit_webhook(
        self, payload: LiveKitWebhookPayload, db: Optional[AsyncSession] = None
    ) -> Optional[CallLog]:
        """Process a LiveKit webhook event and create a call log record."""
        if payload.event != "room_finished":
            return None

        room = payload.room or {}
        room_name = room.get("name", "unknown")
        duration = int(room.get("active_recording_duration", 0) or room.get("num_seconds", 0))
        num_participants = int(room.get("num_participants", 1))

        # Extract agent_id from room metadata
        metadata_dict = {}
        if room.get("metadata"):
            try:
                metadata_dict = json.loads(room["metadata"])
            except Exception:
                pass

        agent_id = metadata_dict.get("agent_id", "default")

        # NOTE: Webhooks don't have the transcript easily available here.
        # Transcript capture is primarily handled in runner.py.
        request = CallLogCreateRequest(
            room_name=room_name,
            agent_id=agent_id,
            duration_seconds=duration,
            status="completed",
            participant_count=num_participants,
            metadata={"livekit_room": room},
        )
        return await self.create_call_log(request, db)

    async def list_calls(
        self,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[CallLog]:
        """Return call logs with optional filters from the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.list_calls(agent_id, status, outcome, limit, user_id, session)

        # Join with Agent to get agent_name
        query = select(CallLogModel, AgentModel.name).join(AgentModel, CallLogModel.agent_id == AgentModel.id, isouter=True)
        
        if user_id:
            query = query.where(CallLogModel.user_id == user_id)
        if agent_id:
            query = query.where(CallLogModel.agent_id == agent_id)
        if status:
            query = query.where(CallLogModel.status == status)
        if outcome:
            query = query.where(CallLogModel.outcome == outcome)
            
        query = query.order_by(CallLogModel.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [self._to_pydantic(row.CallLog, row.name) for row in rows]

    async def get_call(self, call_id: str, user_id: Optional[str] = None, db: Optional[AsyncSession] = None) -> Optional[CallLog]:
        """Fetch a single call record by ID."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.get_call(call_id, user_id, session)

        query = select(CallLogModel, AgentModel.name).join(AgentModel, CallLogModel.agent_id == AgentModel.id, isouter=True).where(CallLogModel.id == call_id)
        if user_id:
            query = query.where(CallLogModel.user_id == user_id)

        result = await db.execute(query)
        row = result.first()
        
        return self._to_pydantic(row.CallLog, row.name) if row else None

    async def delete_call(self, call_id: str, user_id: Optional[str] = None, db: Optional[AsyncSession] = None) -> bool:
        """Delete a call log from the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.delete_call(call_id, user_id, session)

        query = select(CallLogModel).where(CallLogModel.id == call_id)
        if user_id:
            query = query.where(CallLogModel.user_id == user_id)

        result = await db.execute(query)
        model = result.scalar_one_or_none()
        if not model:
            return False

        await db.delete(model)
        await db.commit()
        logger.info("🗑️ Call log deleted from DB: %s", call_id)
        return True

    async def get_stats(self, db: Optional[AsyncSession] = None) -> dict:
        """Quick stats for the health endpoint."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.get_stats(session)

        total = await db.scalar(select(func.count(CallLogModel.id)))
        completed = await db.scalar(select(func.count(CallLogModel.id)).where(CallLogModel.status == "completed"))
        failed = await db.scalar(select(func.count(CallLogModel.id)).where(CallLogModel.status == "failed"))
        
        return {
            "total": total or 0,
            "completed": completed or 0,
            "failed": failed or 0,
        }

# Module-level singleton
call_log_service = CallLogService()
