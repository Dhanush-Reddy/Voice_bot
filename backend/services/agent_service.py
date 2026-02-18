"""
AgentService — business logic for managing agent configurations.

This service is the single source of truth for agent data. It currently
uses an in-memory store (for Sprint 1) and will be swapped for a Supabase
repository in Sprint 3 without changing any callers.
"""

import uuid
import logging
from typing import Optional, List

from models.agent import AgentConfig, AgentCreateRequest, AgentUpdateRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default agent — used when no agent_id is specified (backward compatible)
# ---------------------------------------------------------------------------
_DEFAULT_SYSTEM_PROMPT = """
You are a helpful, friendly, and professional AI voice assistant.
Keep your responses concise and conversational — this is a voice call.
Do not use markdown, bullet points, or special characters in your responses.
"""

_DEFAULT_AGENT = AgentConfig(
    id="default",
    name="Default Assistant",
    system_prompt=_DEFAULT_SYSTEM_PROMPT,
    voice_id="Aoede",
    model="gemini-2.0-flash-live-001",
    language="en-US",
    vad_min_volume=0.15,
    is_active=True,
)

# In-memory store: { agent_id -> AgentConfig }
# Sprint 3 will replace this with a Supabase-backed repository.
_agent_store: dict[str, AgentConfig] = {
    _DEFAULT_AGENT.id: _DEFAULT_AGENT,
}


class AgentService:
    """
    Handles all CRUD operations for agent configurations.

    Design principle: All methods are async so the implementation can be
    swapped for async DB calls (Supabase) in Sprint 3 without changing callers.
    """

    async def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Fetch a single agent by ID. Returns None if not found."""
        agent = _agent_store.get(agent_id)
        if not agent:
            logger.warning("Agent not found: %s", agent_id)
        return agent

    async def get_default_agent(self) -> AgentConfig:
        """Return the default agent config (backward-compatible fallback)."""
        return _DEFAULT_AGENT

    async def list_agents(self) -> List[AgentConfig]:
        """Return all agents in the store."""
        return list(_agent_store.values())

    async def create_agent(self, request: AgentCreateRequest) -> AgentConfig:
        """Create a new agent and persist it."""
        agent = AgentConfig(
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
        _agent_store[agent.id] = agent
        logger.info("✅ Created agent: %s (%s)", agent.name, agent.id)
        return agent

    async def update_agent(
        self, agent_id: str, request: AgentUpdateRequest
    ) -> Optional[AgentConfig]:
        """Update an existing agent's configuration."""
        agent = _agent_store.get(agent_id)
        if not agent:
            return None

        # Apply only the fields that were provided (partial update)
        updated_data = agent.model_dump()
        for field, value in request.model_dump(exclude_none=True).items():
            updated_data[field] = value

        updated_agent = AgentConfig(**updated_data)
        _agent_store[agent_id] = updated_agent
        logger.info("✏️ Updated agent: %s", agent_id)
        return updated_agent

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent. Returns True if deleted, False if not found."""
        if agent_id not in _agent_store:
            return False
        del _agent_store[agent_id]
        logger.info("🗑️ Deleted agent: %s", agent_id)
        return True


# Module-level singleton — import this in routes and other services
agent_service = AgentService()
