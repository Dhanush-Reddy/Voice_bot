"""
FastAPI routes — token generation, agent CRUD, and health checks.

Architecture:
- Routes are thin: they validate input and delegate to services.
- Business logic lives in services/, not here.
- Pydantic models in models/ define all request/response shapes.
"""

import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from bot.pool import agent_pool, LIVEKIT_URL
from models.agent import (
    AgentConfig,
    AgentCreateRequest,
    AgentUpdateRequest,
    TokenResponse,
)
from models.call_log import CallLog, LiveKitWebhookPayload
from models.knowledge import KnowledgeDocument, KnowledgeSearchResult
from services.agent_service import agent_service
from services.call_log_service import call_log_service
from services.config_service import config_service
from services.knowledge_service import knowledge_service
from models.options import ConfigOptionsResponse
from core.options import VOICE_OPTIONS, MODEL_OPTIONS, LANGUAGE_OPTIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifespan — start/stop the agent pool
# ---------------------------------------------------------------------------
from core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start agent pool and database on boot, shut down on exit."""
    logger.info("🗄️  [BOOT] Initializing database...")
    try:
        await init_db()
        logger.info("✅ [BOOT] Database initialized successfully")
    except Exception as e:
        logger.error("❌ [BOOT] Database initialization failed: %s", e, exc_info=True)
        # We continue anyway to let the health check pass; pool might fail later
    
    logger.info("🌱 [BOOT] Seeding default agent...")
    try:
        await agent_service.seed_default_agent()
    except Exception as e:
        logger.error("❌ [BOOT] Seeding failed: %s", e)

    # CRITICAL: Start pool in background so we don't block Uvicorn from binding to the port.
    # Cloud Run health checks fail if we don't listen within a timeout.
    logger.info("🏊 [BOOT] Starting agent pool in background…")
    asyncio.create_task(agent_pool.start())
    
    yield
    
    logger.info("🛑 [SHUTDOWN] Shutting down agent pool…")
    await agent_pool.shutdown()


app = FastAPI(
    title="Voice AI Agency Platform",
    description="Multi-tenant voice agent backend",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow specific origins for secure credential handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://voicebt.netlify.app",
        "https://voice-frontend-mcdqao6eba-uc.a.run.app",
        "https://voice-frontend-820513756722.us-central1.run.app",
    ],
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
    agent_id: Optional[str] = Query(
        None, description="Agent UUID (uses default if omitted)"
    ),
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
                raise HTTPException(
                    status_code=404, detail=f"Agent '{agent_id}' not found."
                )
            if not agent.is_active:
                raise HTTPException(
                    status_code=400, detail=f"Agent '{agent_id}' is not active."
                )
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
# Call log endpoints
# ---------------------------------------------------------------------------
@app.get("/api/calls", response_model=List[CallLog])
async def list_calls(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    status: Optional[str] = Query(
        None, description="Filter by status: completed, failed, no_answer"
    ),
    outcome: Optional[str] = Query(
        None, description="Filter by outcome: success, not_interested, etc."
    ),
    limit: int = Query(100, le=500),
):
    """Return call history with optional filters."""
    return await call_log_service.list_calls(
        agent_id=agent_id, status=status, outcome=outcome, limit=limit
    )


@app.get("/api/calls/{call_id}", response_model=CallLog)
async def get_call(call_id: str):
    """Return a single call record with its full transcript."""
    call = await call_log_service.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found.")
    return call


@app.delete("/api/calls/{call_id}", status_code=204)
async def delete_call(call_id: str):
    """Delete a call log record."""
    deleted = await call_log_service.delete_call(call_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Call not found.")


# ---------------------------------------------------------------------------
# Sprint 4: LiveKit Webhook
# ---------------------------------------------------------------------------
@app.post("/api/webhooks/livekit", status_code=200)
async def livekit_webhook(payload: LiveKitWebhookPayload):
    """
    Receive LiveKit server-side webhook events.

    Configure this URL in your LiveKit project settings:
      POST https://<your-backend>/api/webhooks/livekit

    Handled events:
      - room_finished: Creates a CallLog with duration and participant count.

    All other events are acknowledged and ignored.
    """
    logger.info("🔔 LiveKit webhook received: event=%s", payload.event)
    call = await call_log_service.process_livekit_webhook(payload)
    if call:
        return {"status": "ok", "call_id": call.id, "room": call.room_name}
    return {"status": "ignored", "event": payload.event}


# ---------------------------------------------------------------------------
# Sprint 5: Knowledge Base & RAG
# ---------------------------------------------------------------------------
@app.post(
    "/api/agents/{agent_id}/knowledge",
    response_model=KnowledgeDocument,
    status_code=201,
)
async def upload_document(
    agent_id: str,
    file: UploadFile = File(...),
):
    """
    Upload a document (PDF or TXT) to an agent's knowledge base.

    The document is chunked, embedded via Gemini text-embedding-004,
    and stored in the in-memory vector store for RAG retrieval.
    """
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    # Read file content
    raw = await file.read()
    content_type = file.content_type or "text/plain"

    # Extract text
    if content_type == "application/pdf" or (file.filename or "").endswith(".pdf"):
        try:
            import io
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise HTTPException(
                status_code=422,
                detail="PDF support requires 'pypdf'. Install it with: pip install pypdf",
            )
    else:
        text = raw.decode("utf-8", errors="replace")

    if not text.strip():
        raise HTTPException(
            status_code=422, detail="Could not extract text from the uploaded file."
        )

    doc = await knowledge_service.ingest(
        agent_id=agent_id,
        filename=file.filename or "document.txt",
        text_content=text,
        content_type=content_type,
    )
    logger.info("📚 Knowledge doc uploaded: agent=%s file=%s", agent_id, file.filename)
    return doc


@app.get("/api/agents/{agent_id}/knowledge", response_model=List[KnowledgeDocument])
async def list_documents(agent_id: str):
    """List all knowledge base documents for an agent."""
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return await knowledge_service.list_documents(agent_id)


@app.delete("/api/knowledge/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """Delete a knowledge base document and all its chunks."""
    deleted = await knowledge_service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")


@app.get(
    "/api/agents/{agent_id}/knowledge/search",
    response_model=List[KnowledgeSearchResult],
)
async def search_knowledge(
    agent_id: str,
    q: str = Query(..., description="Search query"),
    top_k: int = Query(3, le=10),
):
    """Semantic search over an agent's knowledge base."""
    return await knowledge_service.search(agent_id=agent_id, query=q, top_k=top_k)


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
    return {
        "message": f"Config cache cleared for agent '{agent.name}'. Next call will use updated config.",
        "agent_id": agent_id,
    }


@app.post("/api/config/flush", status_code=200)
async def flush_config_cache():
    """Flush the entire config cache (use after bulk agent updates)."""
    config_service.invalidate_all()
    return {"message": "Entire config cache flushed."}


@app.get("/api/config/cache")
async def config_cache_stats():
    """Return ConfigService cache statistics for debugging and monitoring."""
    return config_service.cache_stats


@app.get("/api/config/options", response_model=ConfigOptionsResponse)
async def get_config_options():
    """Return available voice, model, and language options."""
    return ConfigOptionsResponse(
        voices=VOICE_OPTIONS,
        models=MODEL_OPTIONS,
        languages=LANGUAGE_OPTIONS,
    )


@app.get("/api/health")
async def health():
    """Comprehensive health check for monitoring."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "config_ok": settings.livekit_configured and settings.gemini_configured,
        "uptime_seconds": settings.uptime_seconds,
        "pool": agent_pool.status,
        "config_cache": config_service.cache_stats,
        "calls": await call_log_service.get_stats(),
        "env_check": {
            "has_lk_url": bool(settings.livekit_url),
            "has_lk_key": bool(settings.livekit_api_key),
            "has_lk_secret": bool(settings.livekit_api_secret),
            "has_gcp_project": bool(settings.google_cloud_project),
            "has_gcp_creds": settings.gemini_configured,
        },
    }
