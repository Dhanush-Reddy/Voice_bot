"""
FastAPI routes — token generation, agent CRUD, and health checks.

Architecture:
- Routes are thin: they validate input and delegate to services.
- Business logic lives in services/, not here.
- Pydantic models in models/ define all request/response shapes.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from bot.pool import agent_pool, LIVEKIT_URL
from models.agent import (
    AgentConfig,
    AgentCreateRequest,
    AgentUpdateRequest,
    TokenResponse,
)
from models.call_log import CallLog, CallLogCreateRequest
from services.agent_service import agent_service
from services.call_log_service import call_log_service
from services.config_service import config_service

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifespan — start/stop the agent pool
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start agent pool on boot, shut down on exit."""
    logger.info("🏊 Initializing agent pool on server startup…")
    await agent_pool.start()
    yield
    logger.info("🛑 Shutting down agent pool…")
    await agent_pool.shutdown()


app = FastAPI(
    title="Voice AI Agency Platform",
    description="Multi-tenant voice agent backend",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend and dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Token endpoint — now supports optional agent_id for dynamic configuration
# ---------------------------------------------------------------------------
@app.get("/api/token", response_model=TokenResponse)
async def generate_token(
    participant_name: str = Query(..., description="Display name of the participant"),
    agent_id: Optional[str] = Query(None, description="Agent UUID (uses default if omitted)"),
):
    """
    Pop a pre-warmed agent from the pool and return a token for the user.
    Supports dynamic agent configuration via agent_id.
    """
    try:
        if not LIVEKIT_URL:
            raise HTTPException(
                status_code=500,
                detail="LiveKit environment variables are not configured.",
            )

        # Validate agent exists if specified
        if agent_id:
            agent = await agent_service.get_agent(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
            if not agent.is_active:
                raise HTTPException(status_code=400, detail=f"Agent '{agent_id}' is not active.")
        else:
            agent = await agent_service.get_default_agent()

        # Pop a ready agent from the pool, passing agent_id for on-demand spawning
        pool_agent = await agent_pool.pop(agent_id=agent_id)
        if pool_agent is None:
            raise HTTPException(
                status_code=503,
                detail="No agents available. Please try again in a moment.",
            )

        # Generate a token for the user to join the agent's pre-warmed room
        token = agent_pool.generate_user_token(pool_agent.room_name, participant_name)

        logger.info(
            "🎫 Token issued for room: %s (participant=%s, agent=%s)",
            pool_agent.room_name,
            participant_name,
            agent.id,
        )

        return TokenResponse(
            token=token,
            url=LIVEKIT_URL,
            room_name=pool_agent.room_name,
            agent_id=agent.id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error generating token: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Agent CRUD endpoints
# ---------------------------------------------------------------------------
@app.get("/api/agents", response_model=List[AgentConfig])
async def list_agents():
    """Return all configured agents."""
    return await agent_service.list_agents()


@app.get("/api/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str):
    """Return a single agent by ID."""
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


@app.post("/api/agents", response_model=AgentConfig, status_code=201)
async def create_agent(request: AgentCreateRequest):
    """Create a new agent configuration."""
    return await agent_service.create_agent(request)


@app.patch("/api/agents/{agent_id}", response_model=AgentConfig)
async def update_agent(agent_id: str, request: AgentUpdateRequest):
    """Update an existing agent's configuration (partial update)."""
    agent = await agent_service.update_agent(agent_id, request)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


@app.delete("/api/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str):
    """Delete an agent configuration."""
    deleted = await agent_service.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found.")


# ---------------------------------------------------------------------------
# Call log endpoints (Sprint 4 will add LiveKit webhook here)
# ---------------------------------------------------------------------------
@app.get("/api/calls", response_model=List[CallLog])
async def list_calls(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(50, le=200),
):
    """Return call history, optionally filtered by agent."""
    return await call_log_service.list_calls(agent_id=agent_id, limit=limit)


@app.get("/api/calls/{call_id}", response_model=CallLog)
async def get_call(call_id: str):
    """Return a single call record with its transcript."""
    call = await call_log_service.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found.")
    return call


# ---------------------------------------------------------------------------
# Infrastructure endpoints
# ---------------------------------------------------------------------------
@app.get("/api/pool/status")
async def pool_status():
    """Check the health of the agent pool."""
    return agent_pool.status


# ---------------------------------------------------------------------------
# Sprint 3: Hot-reload & cache management
# ---------------------------------------------------------------------------
@app.post("/api/agents/{agent_id}/reload", status_code=200)
async def reload_agent_config(agent_id: str):
    """
    Hot-reload an agent's config without restarting the server.

    Invalidates the ConfigService TTL cache for this agent so the next
    call to config_service.get(agent_id) fetches a fresh copy from the
    AgentService (and eventually Supabase in Sprint 4).
    """
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    config_service.invalidate(agent_id)
    logger.info("🔥 Hot-reload triggered for agent: %s (%s)", agent.name, agent_id)
    return {"message": f"Config cache cleared for agent '{agent.name}'. Next call will use updated config.", "agent_id": agent_id}


@app.post("/api/config/flush", status_code=200)
async def flush_config_cache():
    """Flush the entire config cache (use after bulk agent updates)."""
    config_service.invalidate_all()
    return {"message": "Entire config cache flushed."}


@app.get("/api/config/cache")
async def config_cache_stats():
    """Return ConfigService cache statistics for debugging and monitoring."""
    return config_service.cache_stats


@app.get("/api/health")
async def health():
    """Comprehensive health check for monitoring."""
    config_ok = all([
        os.getenv("LIVEKIT_URL"),
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
        os.getenv("GOOGLE_CLOUD_PROJECT"),
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    ])
    return {
        "status": "ok",
        "version": "2.0.0",
        "config_ok": config_ok,
        "pool": agent_pool.status,
        "config_cache": config_service.cache_stats,
        "env_check": {
            "has_lk_url": bool(os.getenv("LIVEKIT_URL")),
            "has_lk_key": bool(os.getenv("LIVEKIT_API_KEY")),
            "has_lk_secret": bool(os.getenv("LIVEKIT_API_SECRET")),
            "has_gcp_project": bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
            "has_gcp_creds": bool(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
                or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            ),
        },
    }
