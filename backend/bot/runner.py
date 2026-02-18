"""
Worker process spawner — BULLETPROOF Pipecat pipeline runner.

Sprint 3 upgrade: accepts --agent-id argument so the pool can spawn
per-agent workers that fetch their configuration from ConfigService.
"""

import argparse
import asyncio
import logging
import time
import sys
from typing import Optional

from pipecat.pipeline.runner import PipelineRunner

from bot.pipeline import create_pipeline
from services.config_service import config_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
HEALTH_CHECK_INTERVAL = 5.0   # seconds
MAX_RUNTIME = 3600             # 1 hour max runtime per worker
CONNECTION_TIMEOUT = 30.0     # seconds


async def main(room_name: str, agent_id: Optional[str] = None) -> None:
    """
    Main worker function with bulletproof error handling.

    Args:
        room_name: LiveKit room to join.
        agent_id:  Agent UUID to fetch config for. Uses default if None.
    """
    start = time.time()
    logger.info("🚀 [BULLETPROOF] Starting bot worker for room: %s (agent_id=%s)", room_name, agent_id)

    task = None
    transport = None
    runner = None
    connected = False
    last_activity = time.time()

    try:
        # ── Fetch agent config via ConfigService (with TTL cache) ──────────
        logger.info("⚙️  Fetching agent config (agent_id=%s)…", agent_id)
        agent_config = await config_service.get(agent_id)
        if agent_config:
            logger.info(
                "✅ Config loaded: name=%s, voice=%s, model=%s",
                agent_config.name, agent_config.voice_id, agent_config.model,
            )
        else:
            logger.warning("⚠️  No config found for agent_id=%s — using defaults", agent_id)

        # ── Create pipeline ────────────────────────────────────────────────
        logger.info("🔧 Creating pipeline…")
        try:
            task, transport = await asyncio.wait_for(
                create_pipeline(room_name, agent_config=agent_config),
                timeout=60.0,
            )
            setup_ms = (time.time() - start) * 1000
            logger.info("⚡ Pipeline ready in %.0fms for room %s", setup_ms, room_name)
        except asyncio.TimeoutError:
            logger.error("❌ Pipeline creation timed out after 60s")
            raise
        except Exception as exc:
            logger.error("❌ Failed to create pipeline: %s", exc)
            raise

        runner = PipelineRunner()

        # ── Event handlers ─────────────────────────────────────────────────
        @transport.event_handler("on_connected")
        async def on_connected(transport: object, *args: object) -> None:
            nonlocal connected, last_activity
            connected = True
            last_activity = time.time()
            connect_ms = (time.time() - start) * 1000
            logger.info("✅ Bot CONNECTED to room %s (boot: %.0fms)", room_name, connect_ms)

        @transport.event_handler("on_disconnected")
        async def on_disconnected(transport: object, *args: object) -> None:
            nonlocal connected
            connected = False
            logger.info("👋 Bot DISCONNECTED from room %s", room_name)
            if runner:
                await runner.cancel()

        @transport.event_handler("on_audio_frame")
        async def on_audio_frame(transport: object, frame: object) -> None:
            nonlocal last_activity
            last_activity = time.time()

        @transport.event_handler("on_bot_started_speaking")
        async def on_bot_started_speaking(transport: object) -> None:
            nonlocal last_activity
            last_activity = time.time()
            logger.info("🗣️ Bot started speaking")

        @transport.event_handler("on_bot_stopped_speaking")
        async def on_bot_stopped_speaking(transport: object) -> None:
            nonlocal last_activity
            last_activity = time.time()
            logger.info("🤐 Bot stopped speaking")

        # ── Run pipeline with health monitoring ────────────────────────────
        logger.info("🏃 Starting pipeline runner for room %s…", room_name)
        try:
            pipeline_task = asyncio.create_task(runner.run(task))

            while not pipeline_task.done():
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

                runtime = time.time() - start
                if runtime > MAX_RUNTIME:
                    logger.warning("⏰ Max runtime (%ds) reached, restarting worker", MAX_RUNTIME)
                    await runner.cancel()
                    break

                if connected and (time.time() - last_activity) > 60:
                    logger.warning("⚠️ No activity for 60s, connection may be stale")

                logger.debug("💓 Health check: runtime=%.0fs, connected=%s", runtime, connected)

            await pipeline_task

        except asyncio.CancelledError:
            logger.info("🛑 Pipeline runner cancelled")
            raise
        except Exception as exc:
            logger.error("❌ Pipeline runner error: %s", exc)
            raise

    except Exception as exc:
        logger.error("❌ Worker error for room %s: %s", room_name, exc)
        raise
    finally:
        logger.info("🧹 Cleaning up worker for room %s", room_name)
        if runner:
            try:
                await runner.cancel()
            except Exception:
                pass

        runtime = time.time() - start
        logger.info("🏁 Worker finished for room %s (runtime: %.0fs)", room_name, runtime)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulletproof Pipecat bot worker")
    parser.add_argument("--room", required=True, help="LiveKit room name to join")
    parser.add_argument("--agent-id", default=None, help="Agent UUID for dynamic config")
    args = parser.parse_args()

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            asyncio.run(main(args.room, agent_id=args.agent_id))
            logger.info("✅ Worker completed successfully")
            sys.exit(0)
        except Exception as exc:
            logger.error("❌ Worker crashed (attempt %d/%d): %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                logger.info("⏳ Restarting in 2s…")
                time.sleep(2)
            else:
                logger.error("❌ All restart attempts failed")
                sys.exit(1)
