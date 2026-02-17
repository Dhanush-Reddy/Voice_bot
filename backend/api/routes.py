"""
FastAPI routes — token generation via agent pool and bot worker dispatch.
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from bot.pool import agent_pool, LIVEKIT_URL

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


app = FastAPI(title="Voice AI Backend", lifespan=lifespan)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/token")
async def generate_token(
    participant_name: str = Query(..., description="Display name of the participant"),
):
    """
    Pop a pre-warmed agent from the pool and return a token for the user
    to join its room. The bot is already connected — zero delay.
    """
    try:
        if not LIVEKIT_URL:
            raise HTTPException(
                status_code=500,
                detail="LiveKit environment variables are not configured.",
            )

        # Pop a ready agent (instant if pool has capacity)
        agent = await agent_pool.pop()
        if agent is None:
            raise HTTPException(
                status_code=503,
                detail="No agents available. Please try again in a moment.",
            )

        # Generate a token for the user to join the agent's pre-warmed room
        token = agent_pool.generate_user_token(agent.room_name, participant_name)

        logger.info(
            "🎫 Token issued for room: %s (participant=%s)",
            agent.room_name,
            participant_name,
        )

        return {
            "token": token,
            "url": LIVEKIT_URL,
            "room_name": agent.room_name,
        }
    except Exception as e:
        logger.error(f"❌ Error generating token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pool/status")
async def pool_status():
    """Check the health of the agent pool."""
    return agent_pool.status


@app.get("/api/health")
async def health():
    config_ok = all([
        os.getenv("LIVEKIT_URL"),
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
        os.getenv("GOOGLE_CLOUD_PROJECT"),
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    ])
    return {
        "status": "ok",
        "deploy_time": "2026-02-17T04:45:00Z (v1.1.16-SANITY)",
        "config_ok": config_ok,
        "pool": agent_pool.status,
        "env_check": {
            "has_lk_url": bool(os.getenv("LIVEKIT_URL")),
            "has_lk_key": bool(os.getenv("LIVEKIT_API_KEY")),
            "has_lk_secret": bool(os.getenv("LIVEKIT_API_SECRET")),
            "has_gcp_project": bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
            "has_gcp_creds": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        }
    }
