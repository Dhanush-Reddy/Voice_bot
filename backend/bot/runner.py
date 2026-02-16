"""
Worker process spawner — runs the Pipecat pipeline for a single LiveKit room.
Invoked as:  python -m bot.runner --room <room_name>
"""

import argparse
import asyncio
import logging
import time

from pipecat.pipeline.runner import PipelineRunner

from bot.pipeline import create_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main(room_name: str) -> None:
    start = time.time()
    logger.info("🚀 Starting bot worker for room: %s", room_name)

    task, transport = await create_pipeline(room_name)
    setup_ms = (time.time() - start) * 1000
    logger.info("⚡ Pipeline ready in %.0fms for room %s", setup_ms, room_name)

    runner = PipelineRunner()

    @transport.event_handler("on_connected")
    async def on_connected(transport, *args):
        connect_ms = (time.time() - start) * 1000
        logger.info(
            "✅ Bot connected to room %s (total boot: %.0fms) | args: %s",
            room_name,
            connect_ms,
            args
        )

    @transport.event_handler("on_disconnected")
    async def on_disconnected(transport, *args):
        logger.info("👋 Bot disconnected from room %s | args: %s", room_name, args)
        await runner.cancel()

    await runner.run(task)
    logger.info("🏁 Bot worker finished for room: %s", room_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipecat bot worker")
    parser.add_argument("--room", required=True, help="LiveKit room name to join")
    args = parser.parse_args()

    asyncio.run(main(args.room))
