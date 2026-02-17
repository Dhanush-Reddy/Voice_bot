"""
BULLETPROOF Agent Pool — ensures 100% reliability with health checks and auto-recovery.
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

# Health check constants
AGENT_STARTUP_TIME = 3.0  # seconds to wait for agent to start
AGENT_HEALTH_CHECK_INTERVAL = 10.0  # seconds between health checks
MAX_AGENT_AGE = 600  # 10 minutes max age before recycling


@dataclass
class PooledAgent:
    """A pre-warmed agent sitting in a LiveKit room, waiting for a user."""
    room_name: str
    process: Optional[asyncio.subprocess.Process] = None
    created_at: float = field(default_factory=time.time)
    ready: bool = False
    last_health_check: float = field(default_factory=time.time)
    health_check_passed: bool = False


class AgentPool:
    """
    BULLETPROOF agent pool with health monitoring and auto-recovery.
    """

    def __init__(self, pool_size: int = POOL_SIZE):
        self.pool_size = pool_size
        self._ready_agents: asyncio.Queue[PooledAgent] = asyncio.Queue()
        self._all_agents: list[PooledAgent] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Initialize the pool with health monitoring."""
        self._running = True
        logger.info(f"🚀 [BULLETPROOF] Starting agent pool with {self.pool_size} slots…")

        # Spawn all agents concurrently
        tasks = [self._spawn_agent() for _ in range(self.pool_size)]
        agents = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = 0
        for agent in agents:
            if isinstance(agent, PooledAgent):
                await self._ready_agents.put(agent)
                self._all_agents.append(agent)
                success_count += 1
                logger.info(f"✅ Agent ready in room: {agent.room_name}")
            else:
                logger.error(f"❌ Failed to spawn agent: {agent}")

        logger.info(
            f"🏊 Agent pool initialized: {success_count}/{self.pool_size} ready"
        )

        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())

    async def _health_monitor(self) -> None:
        """Continuously monitor agent health and restart dead agents."""
        while self._running:
            try:
                await asyncio.sleep(AGENT_HEALTH_CHECK_INTERVAL)
                
                if not self._running:
                    break

                # Check all agents
                dead_agents = []
                for agent in self._all_agents:
                    # Check if process is still alive
                    if agent.process and agent.process.returncode is not None:
                        logger.warning(f"⚠️ Agent in room {agent.room_name} died (code: {agent.process.returncode})")
                        dead_agents.append(agent)
                    
                    # Check agent age
                    age = time.time() - agent.created_at
                    if age > MAX_AGENT_AGE:
                        logger.info(f"⏰ Agent in room {agent.room_name} reached max age ({age:.0f}s), recycling...")
                        dead_agents.append(agent)

                # Remove dead agents and replenish
                for agent in dead_agents:
                    await self._remove_agent(agent)
                    
                # Replenish pool if needed
                current_size = self._ready_agents.qsize()
                if current_size < self.pool_size:
                    needed = self.pool_size - current_size
                    logger.info(f"🔄 Replenishing pool: {needed} agents needed")
                    for _ in range(needed):
                        asyncio.create_task(self._replenish())
                        
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")

    async def _remove_agent(self, agent: PooledAgent) -> None:
        """Remove a dead agent from the pool."""
        try:
            if agent in self._all_agents:
                self._all_agents.remove(agent)
            
            if agent.process and agent.process.returncode is None:
                agent.process.terminate()
                try:
                    await asyncio.wait_for(agent.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    agent.process.kill()
                    
            logger.info(f"🗑️ Removed dead agent from room {agent.room_name}")
        except Exception as e:
            logger.error(f"❌ Error removing agent: {e}")

    async def pop(self) -> Optional[PooledAgent]:
        """
        Pop a ready agent from the pool (instant).
        Triggers background replenishment.
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Try to get from pool
                agent = self._ready_agents.get_nowait()
                
                # Verify agent is still healthy
                if agent.process and agent.process.returncode is None:
                    logger.info(
                        f"⚡ Popped agent from pool (room={agent.room_name}), {self._ready_agents.qsize()} remaining"
                    )
                    # Replenish in background
                    asyncio.create_task(self._replenish())
                    return agent
                else:
                    # Agent died, remove it and try again
                    logger.warning(f"⚠️ Popped dead agent, removing and retrying...")
                    await self._remove_agent(agent)
                    
            except asyncio.QueueEmpty:
                # Pool exhausted — spawn one on-demand
                logger.warning(f"⚠️ Agent pool exhausted! Spawning on-demand (attempt {attempt + 1})...")
                agent = await self._spawn_agent()
                if isinstance(agent, PooledAgent):
                    return agent
                
                # Wait before retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    
        logger.error("❌ Failed to get agent after all retries")
        return None

    async def _replenish(self) -> None:
        """Spawn a new agent to refill the pool."""
        async with self._lock:
            # Double-check pool size
            if self._ready_agents.qsize() >= self.pool_size:
                return
                
            agent = await self._spawn_agent()
            if isinstance(agent, PooledAgent):
                await self._ready_agents.put(agent)
                self._all_agents.append(agent)
                logger.info(
                    f"🔄 Pool replenished (room={agent.room_name}), {self._ready_agents.qsize()} ready"
                )

    async def _stream_logs(self, stream, label, room_name):
        """Streams subprocess pipe to the main logger."""
        logger.info(f"📡 Started log streaming for {room_name} ({label})")
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                # Print to stdout so Cloud Run captures it
                print(f"[{room_name}] [{label}] {line.decode().strip()}", flush=True)
        except Exception as e:
            logger.error(f"❌ Log streaming error for {room_name}: {e}")

    async def _spawn_agent(self) -> PooledAgent:
        """Spawn a bot worker subprocess with retry logic."""
        room_name = f"voice-room-{uuid.uuid4().hex[:8]}"
        agent = PooledAgent(room_name=room_name)
        
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🤖 Spawning agent for room {room_name} (attempt {attempt})...")
                
                import sys
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "bot.runner",
                    "--room",
                    room_name,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    env=os.environ.copy(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                agent.process = proc
                
                # Start background log streaming tasks
                asyncio.create_task(self._stream_logs(proc.stdout, "STDOUT", room_name))
                asyncio.create_task(self._stream_logs(proc.stderr, "STDERR", room_name))
                
                # Wait for agent to initialize
                await asyncio.sleep(AGENT_STARTUP_TIME)
                
                # Check if process is still alive
                if proc.returncode is not None:
                    logger.error(f"❌ Agent process died immediately (code: {proc.returncode})")
                    if attempt < max_attempts:
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise Exception(f"Agent failed to start after {max_attempts} attempts")
                
                agent.ready = True
                agent.health_check_passed = True
                agent.last_health_check = time.time()
                
                logger.info(f"✅ Agent spawned in room {room_name} (pid={proc.pid})")
                return agent
                
            except Exception as e:
                logger.error(f"❌ Attempt {attempt} failed to spawn agent: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(1)
                else:
                    raise
        
        raise Exception(f"Failed to spawn agent after {max_attempts} attempts")

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
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
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
            "all_agents": len(self._all_agents),
            "total_spawned": len(self._all_agents),
            "running": self._running,
            "livekit_config": {
                "has_url": bool(LIVEKIT_URL),
                "has_key": bool(LIVEKIT_API_KEY),
                "has_secret": bool(LIVEKIT_API_SECRET)
            }
        }


# Singleton instance
agent_pool = AgentPool()
