import uuid
import logging
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import AgentConfig, AgentCreateRequest, AgentUpdateRequest
from models.database_models import Agent as AgentModel
from core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default agent — used when no agent_id is specified (backward compatible)
# ---------------------------------------------------------------------------
_DEFAULT_SYSTEM_PROMPT = """
You are a helpful, friendly, and professional AI voice assistant.
Keep your responses concise and conversational — this is a voice call.
Do not use markdown, bullet points, or special characters in your responses.
"""

class AgentService:
    """
    Handles all CRUD operations for agent configurations via SQLAlchemy.
    """

    def _to_pydantic(self, model: AgentModel) -> AgentConfig:
        """Helper to convert SQLAlchemy model to Pydantic AgentConfig."""
        return AgentConfig(
            id=model.id,
            name=model.name,
            system_prompt=model.system_prompt,
            voice_id=model.voice_id,
            model=model.model,
            language=model.language,
            vad_min_volume=model.vad_min_volume,
            is_active=model.is_active,
            temperature=model.temperature,
            success_outcomes=model.success_outcomes,
            handoff_number=model.handoff_number,
            first_message=model.first_message,
        )

    async def get_agent(self, agent_id: str, db: Optional[AsyncSession] = None) -> Optional[AgentConfig]:
        """Fetch a single agent by ID. Returns None if not found."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.get_agent(agent_id, session)

        result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()
        return self._to_pydantic(model) if model else None

    async def get_default_agent(self, db: Optional[AsyncSession] = None) -> AgentConfig:
        """Return the default agent config. Seeds it if missing."""
        agent = await self.get_agent("default", db)
        if not agent:
            # Seed default agent if not exists
            agent = await self.seed_default_agent(db)
        return agent

    async def seed_default_agent(self, db: Optional[AsyncSession] = None) -> AgentConfig:
        """Ensure a default agent exists in the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.seed_default_agent(session)

        # Check if "default" exists
        existing = await self.get_agent("default", db)
        if existing:
            return existing

        logger.info("🌱 Seeding default agent into database...")
        default_model = AgentModel(
            id="default",
            name="Default Assistant",
            system_prompt=_DEFAULT_SYSTEM_PROMPT,
            voice_id="Aoede",
            model="gemini-2.0-flash-live-001",
            language="en-US",
            vad_min_volume=0.15,
            is_active=True,
            temperature=0.7,
            success_outcomes=["Appointment Booked"]
        )
        db.add(default_model)
        await db.commit()
        await db.refresh(default_model)
        return self._to_pydantic(default_model)

    async def list_agents(self, db: Optional[AsyncSession] = None) -> List[AgentConfig]:
        """Return all agents in the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.list_agents(session)

        result = await db.execute(select(AgentModel).order_by(AgentModel.created_at.desc()))
        models = result.scalars().all()
        return [self._to_pydantic(m) for m in models]

    async def create_agent(self, request: AgentCreateRequest, db: Optional[AsyncSession] = None) -> AgentConfig:
        """Create a new agent and persist it to the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.create_agent(request, session)

        model = AgentModel(
            id=str(uuid.uuid4()),
            name=request.name,
            system_prompt=request.system_prompt,
            voice_id=request.voice_id or "Aoede",
            model=request.model or "gemini-2.0-flash-live-001",
            language=request.language or "en-US",
            temperature=request.temperature or 0.7,
            success_outcomes=request.success_outcomes or ["Appointment Booked"],
            handoff_number=request.handoff_number,
            first_message=request.first_message,
        )
        db.add(model)
        await db.commit()
        await db.refresh(model)
        logger.info("✅ Created agent in DB: %s (%s)", model.name, model.id)
        return self._to_pydantic(model)

    async def update_agent(
        self, agent_id: str, request: AgentUpdateRequest, db: Optional[AsyncSession] = None
    ) -> Optional[AgentConfig]:
        """Update an existing agent's configuration in the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.update_agent(agent_id, request, session)

        result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()
        if not model:
            return None

        # Apply only provided fields
        data = request.model_dump(exclude_none=True)
        for key, value in data.items():
            setattr(model, key, value)

        await db.commit()
        await db.refresh(model)
        logger.info("✏️ Updated agent in DB: %s", agent_id)
        return self._to_pydantic(model)

    async def delete_agent(self, agent_id: str, db: Optional[AsyncSession] = None) -> bool:
        """Delete an agent from the database."""
        if db is None:
            async with AsyncSessionLocal() as session:
                return await self.delete_agent(agent_id, session)

        result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()
        if not model:
            return False

        await db.delete(model)
        await db.commit()
        logger.info("🗑️ Deleted agent from DB: %s", agent_id)
        return True

# Module-level singleton
agent_service = AgentService()
