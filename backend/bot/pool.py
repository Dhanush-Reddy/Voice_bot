"""
Pre-warmed Agent Pool — eliminates cold-start delay by keeping bot workers
already connected to LiveKit rooms, ready for users to join instantly.
"""

import asyncio
import logging
import os
import uuid
import time
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

load_dotenv()

logger = logging.getLogger(__name__)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
POOL_SIZE = int(os.getenv("AGENT_POOL_SIZE", "3"))


@dataclass
class PooledAgent:
    """A pre-warmed agent sitting in a LiveKit room, waiting for a user."""
    room_name: str
    process: Optional[asyncio.subprocess.Process] = None
    created_at: float = field(default_factory=time.time)
    ready: bool = False


class AgentPool:
    """
    Manages a pool of pre-spawned bot workers.

    On startup, spawns POOL_SIZE bots in separate LiveKit rooms.
    When a user requests a session, we pop a ready agent (instant)
    and replenish the pool in the background.
    """

    def __init__(self, pool_size: int = POOL_SIZE):
        self.pool_size = pool_size
        self._ready_agents: asyncio.Queue[PooledAgent] = asyncio.Queue()
        self._all_agents: list[PooledAgent] = []
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        """Initialize the pool — spawn all agents concurrently."""
        self._running = True
        logger.info("🚀 Starting agent pool with %d slots…", self.pool_size)

        # Spawn all agents concurrently for fast startup
        tasks = [self._spawn_agent() for _ in range(self.pool_size)]
        agents = await asyncio.gather(*tasks, return_exceptions=True)

        for agent in agents:
            if isinstance(agent, PooledAgent):
                await self._ready_agents.put(agent)
                self._all_agents.append(agent)
                logger.info("✅ Agent ready in room: %s", agent.room_name)
            else:
                logger.error("❌ Failed to spawn agent: %s", agent)

        logger.info(
            "🏊 Agent pool initialized: %d/%d ready",
            self._ready_agents.qsize(),
            self.pool_size,
        )

    async def pop(self) -> Optional[PooledAgent]:
        """
        Pop a ready agent from the pool (instant).
        Triggers background replenishment.
        """
        try:
            agent = self._ready_agents.get_nowait()
            logger.info(
                "⚡ Popped agent from pool (room=%s), %d remaining",
                agent.room_name,
                self._ready_agents.qsize(),
            )
            # Replenish in the background
            asyncio.create_task(self._replenish())
            return agent
        except asyncio.QueueEmpty:
            # Pool exhausted — spawn one on-demand (slower fallback)
            logger.warning("⚠️ Agent pool exhausted! Spawning on-demand…")
            agent = await self._spawn_agent()
            if isinstance(agent, PooledAgent):
                return agent
            return None

    async def _replenish(self) -> None:
        """Spawn a new agent to refill the pool."""
        async with self._lock:
            agent = await self._spawn_agent()
            if isinstance(agent, PooledAgent):
                await self._ready_agents.put(agent)
                self._all_agents.append(agent)
                logger.info(
                    "🔄 Pool replenished (room=%s), %d ready",
                    agent.room_name,
                    self._ready_agents.qsize(),
                )

    async def _spawn_agent(self) -> PooledAgent:
        """Spawn a bot worker subprocess in a new LiveKit room."""
        room_name = f"voice-room-{uuid.uuid4().hex[:8]}"
        agent = PooledAgent(room_name=room_name)

        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "bot.runner",
                "--room",
                room_name,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            agent.process = proc
            agent.ready = True

            # Give the bot a moment to connect to LiveKit
            await asyncio.sleep(1.5)

            logger.info("🤖 Spawned agent in room %s (pid=%d)", room_name, proc.pid)
            return agent
        except Exception as e:
            logger.error("Failed to spawn agent for room %s: %s", room_name, e)
            raise

    def generate_user_token(self, room_name: str, participant_name: str) -> str:
        """Generate a LiveKit token for a user to join a pre-warmed room."""
        token = (
            AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(participant_name)
            .with_name(participant_name)
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                )
            )
        )
        return token.to_jwt()

    async def shutdown(self) -> None:
        """Cleanup — terminate all bot workers."""
        self._running = False
        logger.info("Shutting down agent pool…")
        for agent in self._all_agents:
            if agent.process and agent.process.returncode is None:
                agent.process.terminate()
                try:
                    await asyncio.wait_for(agent.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    agent.process.kill()
        self._all_agents.clear()
        logger.info("Agent pool shut down.")

    @property
    def status(self) -> dict:
        """Return pool health info."""
        return {
            "pool_size": self.pool_size,
            "ready": self._ready_agents.qsize(),
            "total_spawned": len(self._all_agents),
            "running": self._running,
        }


# Singleton instance
agent_pool = AgentPool()
