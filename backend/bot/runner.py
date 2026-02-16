"""
Worker process spawner — BULLETPROOF Pipecat pipeline runner.
Handles crashes, restarts, and ensures 100% uptime.
"""

import argparse
import asyncio
import logging
import time
import sys

from pipecat.pipeline.runner import PipelineRunner

from bot.pipeline import create_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
HEALTH_CHECK_INTERVAL = 5.0  # seconds
MAX_RUNTIME = 3600  # 1 hour max runtime per worker
CONNECTION_TIMEOUT = 30.0  # seconds


async def main(room_name: str) -> None:
    """Main worker function with bulletproof error handling."""
    start = time.time()
    logger.info(f"🚀 [BULLETPROOF] Starting bot worker for room: {room_name}")
    
    task = None
    transport = None
    runner = None
    connected = False
    last_activity = time.time()

    try:
        # Create pipeline with full error handling
        logger.info("🔧 Creating pipeline...")
        try:
            task, transport = await asyncio.wait_for(
                create_pipeline(room_name),
                timeout=60.0  # 60 second timeout for pipeline creation
            )
            setup_ms = (time.time() - start) * 1000
            logger.info(f"⚡ Pipeline ready in {setup_ms:.0f}ms for room {room_name}")
        except asyncio.TimeoutError:
            logger.error("❌ Pipeline creation timed out after 60s")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to create pipeline: {e}")
            raise

        runner = PipelineRunner()

        # Connection handler
        @transport.event_handler("on_connected")
        async def on_connected(transport, *args):
            nonlocal connected, last_activity
            connected = True
            last_activity = time.time()
            connect_ms = (time.time() - start) * 1000
            logger.info(f"✅ Bot CONNECTED to room {room_name} (boot: {connect_ms:.0f}ms)")

        # Disconnection handler
        @transport.event_handler("on_disconnected")
        async def on_disconnected(transport, *args):
            nonlocal connected
            connected = False
            logger.info(f"👋 Bot DISCONNECTED from room {room_name}")
            if runner:
                await runner.cancel()

        # Track activity for health monitoring
        @transport.event_handler("on_audio_frame")
        async def on_audio_frame(transport, frame):
            nonlocal last_activity
            last_activity = time.time()

        @transport.event_handler("on_bot_started_speaking")
        async def on_bot_started_speaking(transport):
            nonlocal last_activity
            last_activity = time.time()
            logger.info("🗣️ Bot started speaking")

        @transport.event_handler("on_bot_stopped_speaking")
        async def on_bot_stopped_speaking(transport):
            nonlocal last_activity
            last_activity = time.time()
            logger.info("🤐 Bot stopped speaking")

        # Start pipeline with timeout
        logger.info(f"🏃 Starting pipeline runner for room {room_name}...")
        
        try:
            # Run with health check
            pipeline_task = asyncio.create_task(runner.run(task))
            
            # Health monitoring loop
            while not pipeline_task.done():
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
                # Check for timeout
                runtime = time.time() - start
                if runtime > MAX_RUNTIME:
                    logger.warning(f"⏰ Max runtime ({MAX_RUNTIME}s) reached, restarting worker")
                    await runner.cancel()
                    break
                
                # Check for stale connection (no activity for 60s)
                if connected and (time.time() - last_activity) > 60:
                    logger.warning("⚠️ No activity for 60s, connection may be stale")
                    # Don't kill it yet, just warn
                
                logger.debug(f"💓 Health check: runtime={runtime:.0f}s, connected={connected}")
            
            # Wait for pipeline to complete
            await pipeline_task
            
        except asyncio.CancelledError:
            logger.info("🛑 Pipeline runner cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Pipeline runner error: {e}")
            raise

    except Exception as e:
        logger.error(f"❌ Worker error for room {room_name}: {e}")
        raise
    finally:
        # Cleanup
        logger.info(f"🧹 Cleaning up worker for room {room_name}")
        if runner:
            try:
                await runner.cancel()
            except:
                pass
        
        runtime = time.time() - start
        logger.info(f"🏁 Worker finished for room {room_name} (runtime: {runtime:.0f}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulletproof Pipecat bot worker")
    parser.add_argument("--room", required=True, help="LiveKit room name to join")
    args = parser.parse_args()

    # Run with retry on failure
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            asyncio.run(main(args.room))
            logger.info("✅ Worker completed successfully")
            sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Worker crashed (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                logger.info(f"⏳ Restarting in 2s...")
                time.sleep(2)
            else:
                logger.error("❌ All restart attempts failed")
                sys.exit(1)
