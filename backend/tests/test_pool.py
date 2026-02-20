"""
Comprehensive tests for backend/bot/pool.py

Tests AgentPool functionality:
- Pool initialization and startup
- Agent spawning with retry logic
- Pop operation with health checks
- Health monitoring and auto-recovery
- Token generation for users
- Pool shutdown
- Status reporting
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from dataclasses import dataclass

from bot.pool import (
    AgentPool,
    PooledAgent,
    POOL_SIZE,
    AGENT_STARTUP_TIME,
    MAX_AGENT_AGE,
)


class TestPooledAgent:
    """Test suite for PooledAgent dataclass."""

    def test_pooled_agent_creation_minimal(self):
        """Should create pooled agent with minimal fields."""
        agent = PooledAgent(room_name="test-room")

        assert agent.room_name == "test-room"
        assert agent.process is None
        assert agent.ready is False
        assert agent.health_check_passed is False
        assert agent.created_at > 0
        assert agent.last_health_check > 0

    def test_pooled_agent_creation_full(self):
        """Should create pooled agent with all fields."""
        mock_process = MagicMock()
        agent = PooledAgent(
            room_name="test-room",
            process=mock_process,
            ready=True,
            health_check_passed=True,
        )

        assert agent.room_name == "test-room"
        assert agent.process == mock_process
        assert agent.ready is True
        assert agent.health_check_passed is True

    def test_pooled_agent_timestamps(self):
        """Should set timestamps on creation."""
        import time
        before = time.time()
        agent = PooledAgent(room_name="test-room")
        after = time.time()

        assert before <= agent.created_at <= after
        assert before <= agent.last_health_check <= after


class TestAgentPoolInitialization:
    """Test suite for AgentPool initialization."""

    def test_agent_pool_creation(self):
        """Should create agent pool with default size."""
        pool = AgentPool()

        assert pool.pool_size == POOL_SIZE
        assert pool._running is False
        assert pool._ready_agents.empty()
        assert len(pool._all_agents) == 0

    def test_agent_pool_custom_size(self):
        """Should create agent pool with custom size."""
        pool = AgentPool(pool_size=5)

        assert pool.pool_size == 5

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_start_pool_success(self, mock_spawn):
        """Should start pool and spawn all agents."""
        pool = AgentPool(pool_size=2)

        # Mock successful agent spawning
        agent1 = PooledAgent(room_name="room-1", ready=True)
        agent2 = PooledAgent(room_name="room-2", ready=True)
        mock_spawn.side_effect = [agent1, agent2]

        await pool.start()

        assert pool._running is True
        assert mock_spawn.call_count == 2
        assert pool._ready_agents.qsize() == 2
        assert len(pool._all_agents) == 2

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_start_pool_partial_failure(self, mock_spawn):
        """Should handle partial spawn failures gracefully."""
        pool = AgentPool(pool_size=3)

        # Mock mixed success/failure
        agent1 = PooledAgent(room_name="room-1", ready=True)
        mock_spawn.side_effect = [
            agent1,
            Exception("Spawn failed"),
            PooledAgent(room_name="room-3", ready=True),
        ]

        await pool.start()

        assert pool._running is True
        assert pool._ready_agents.qsize() == 2
        assert len(pool._all_agents) == 2

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    @patch.object(AgentPool, "_health_monitor")
    async def test_start_pool_starts_health_monitor(self, mock_health_monitor, mock_spawn):
        """Should start health monitoring task."""
        pool = AgentPool(pool_size=1)
        mock_spawn.return_value = PooledAgent(room_name="room-1")
        mock_health_monitor.return_value = asyncio.Future()

        await pool.start()

        assert pool._health_check_task is not None


class TestAgentSpawning:
    """Test suite for agent spawning."""

    @pytest.mark.asyncio
    @patch("bot.pool.asyncio.create_subprocess_exec")
    @patch("bot.pool.asyncio.sleep", new_callable=AsyncMock)
    async def test_spawn_agent_success(self, mock_sleep, mock_subprocess):
        """Should spawn agent successfully."""
        pool = AgentPool()

        # Mock successful process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_subprocess.return_value = mock_process

        agent = await pool._spawn_agent()

        assert agent.room_name is not None
        assert agent.process == mock_process
        assert agent.ready is True
        assert agent.health_check_passed is True
        assert mock_subprocess.call_count == 1

    @pytest.mark.asyncio
    @patch("bot.pool.asyncio.create_subprocess_exec")
    @patch("bot.pool.asyncio.sleep", new_callable=AsyncMock)
    async def test_spawn_agent_retry_logic(self, mock_sleep, mock_subprocess):
        """Should retry spawning if process dies immediately."""
        pool = AgentPool()

        # First attempt fails, second succeeds
        mock_dead_process = AsyncMock()
        mock_dead_process.returncode = 1
        mock_dead_process.stdout = AsyncMock()
        mock_dead_process.stderr = AsyncMock()

        mock_alive_process = AsyncMock()
        mock_alive_process.returncode = None
        mock_alive_process.pid = 12345
        mock_alive_process.stdout = AsyncMock()
        mock_alive_process.stderr = AsyncMock()

        mock_subprocess.side_effect = [mock_dead_process, mock_alive_process]

        agent = await pool._spawn_agent()

        assert agent.ready is True
        assert mock_subprocess.call_count == 2
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    @patch("bot.pool.asyncio.create_subprocess_exec")
    @patch("bot.pool.asyncio.sleep", new_callable=AsyncMock)
    async def test_spawn_agent_max_retries(self, mock_sleep, mock_subprocess):
        """Should raise exception after max retries."""
        pool = AgentPool()

        # All attempts fail
        mock_subprocess.side_effect = Exception("Spawn error")

        with pytest.raises(Exception, match="Spawn error"):
            await pool._spawn_agent()

        assert mock_subprocess.call_count == 3  # Max attempts


class TestPopOperation:
    """Test suite for pop operation."""

    @pytest.mark.asyncio
    async def test_pop_returns_healthy_agent(self):
        """Should return healthy agent from queue."""
        pool = AgentPool()
        pool._running = True

        # Add healthy agent to queue
        mock_process = MagicMock()
        mock_process.returncode = None
        agent = PooledAgent(room_name="room-1", process=mock_process, ready=True)
        await pool._ready_agents.put(agent)
        pool._all_agents.append(agent)

        with patch.object(pool, "_replenish", new_callable=AsyncMock):
            popped = await pool.pop()

        assert popped == agent
        assert pool._ready_agents.qsize() == 0
        assert agent not in pool._all_agents

    @pytest.mark.asyncio
    async def test_pop_skips_dead_agents(self):
        """Should skip dead agents and return healthy one."""
        pool = AgentPool()
        pool._running = True

        # Add dead agent
        dead_process = MagicMock()
        dead_process.returncode = 1
        dead_agent = PooledAgent(room_name="room-dead", process=dead_process, ready=True)
        await pool._ready_agents.put(dead_agent)
        pool._all_agents.append(dead_agent)

        # Add healthy agent
        healthy_process = MagicMock()
        healthy_process.returncode = None
        healthy_agent = PooledAgent(room_name="room-healthy", process=healthy_process, ready=True)
        await pool._ready_agents.put(healthy_agent)
        pool._all_agents.append(healthy_agent)

        with patch.object(pool, "_remove_agent", new_callable=AsyncMock) as mock_remove:
            with patch.object(pool, "_replenish", new_callable=AsyncMock):
                popped = await pool.pop()

        assert popped == healthy_agent
        mock_remove.assert_called_once_with(dead_agent)

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_pop_spawns_on_demand_when_empty(self, mock_spawn):
        """Should spawn agent on-demand if pool is empty."""
        pool = AgentPool()
        pool._running = True

        # Mock spawning
        mock_process = MagicMock()
        mock_process.returncode = None
        new_agent = PooledAgent(room_name="on-demand", process=mock_process, ready=True)
        mock_spawn.return_value = new_agent

        popped = await pool.pop()

        assert popped == new_agent
        mock_spawn.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_pop_returns_none_if_spawn_fails(self, mock_spawn):
        """Should return None if on-demand spawn fails."""
        pool = AgentPool()
        pool._running = True

        mock_spawn.side_effect = Exception("Spawn failed")

        popped = await pool.pop()

        assert popped is None


class TestHealthMonitoring:
    """Test suite for health monitoring."""

    @pytest.mark.asyncio
    @patch("bot.pool.asyncio.sleep", new_callable=AsyncMock)
    async def test_health_monitor_detects_dead_agents(self, mock_sleep):
        """Should detect and remove dead agents."""
        pool = AgentPool()
        pool._running = True

        # Add agent with dead process
        mock_process = MagicMock()
        mock_process.returncode = 1  # Dead
        agent = PooledAgent(room_name="room-1", process=mock_process, ready=True)
        pool._all_agents.append(agent)

        # Run one health check cycle
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        with patch.object(pool, "_remove_agent", new_callable=AsyncMock) as mock_remove:
            with patch.object(pool, "_replenish", new_callable=AsyncMock):
                try:
                    await pool._health_monitor()
                except asyncio.CancelledError:
                    pass

        mock_remove.assert_called_once_with(agent)

    @pytest.mark.asyncio
    @patch("bot.pool.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot.pool.time.time")
    async def test_health_monitor_recycles_old_agents(self, mock_time, mock_sleep):
        """Should recycle agents that exceed max age."""
        pool = AgentPool()
        pool._running = True

        # Create agent with old timestamp
        mock_process = MagicMock()
        mock_process.returncode = None
        agent = PooledAgent(room_name="room-1", process=mock_process, ready=True)
        agent.created_at = 0  # Very old
        pool._all_agents.append(agent)

        # Current time is way in the future
        mock_time.return_value = MAX_AGENT_AGE + 100

        # Run one health check cycle
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        with patch.object(pool, "_remove_agent", new_callable=AsyncMock) as mock_remove:
            with patch.object(pool, "_replenish", new_callable=AsyncMock):
                try:
                    await pool._health_monitor()
                except asyncio.CancelledError:
                    pass

        mock_remove.assert_called_once_with(agent)

    @pytest.mark.asyncio
    async def test_remove_agent_terminates_process(self):
        """Should terminate agent process on removal."""
        pool = AgentPool()

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.wait = AsyncMock()
        agent = PooledAgent(room_name="room-1", process=mock_process, ready=True)
        pool._all_agents.append(agent)

        await pool._remove_agent(agent)

        mock_process.terminate.assert_called_once()
        assert agent not in pool._all_agents


class TestReplenishment:
    """Test suite for pool replenishment."""

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_replenish_adds_agent(self, mock_spawn):
        """Should spawn and add agent to pool."""
        pool = AgentPool(pool_size=3)
        pool._running = True

        # Pool has 2 agents, needs 1 more
        pool._all_agents = [
            PooledAgent(room_name="room-1"),
            PooledAgent(room_name="room-2"),
        ]

        new_agent = PooledAgent(room_name="room-3", ready=True)
        mock_spawn.return_value = new_agent

        await pool._replenish()

        assert new_agent in pool._all_agents
        assert pool._ready_agents.qsize() == 1

    @pytest.mark.asyncio
    @patch.object(AgentPool, "_spawn_agent")
    async def test_replenish_respects_pool_size(self, mock_spawn):
        """Should not spawn if pool is full."""
        pool = AgentPool(pool_size=2)
        pool._running = True

        # Pool is already full
        pool._all_agents = [
            PooledAgent(room_name="room-1"),
            PooledAgent(room_name="room-2"),
        ]

        await pool._replenish()

        mock_spawn.assert_not_called()


class TestTokenGeneration:
    """Test suite for user token generation."""

    @patch("bot.pool.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pool.LIVEKIT_API_SECRET", "test-secret")
    def test_generate_user_token(self):
        """Should generate token for user to join room."""
        pool = AgentPool()

        token = pool.generate_user_token("test-room", "John Doe")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("bot.pool.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pool.LIVEKIT_API_SECRET", "test-secret")
    @patch("bot.pool.AccessToken")
    def test_generate_user_token_configuration(self, mock_access_token_class):
        """Should configure token with correct grants."""
        pool = AgentPool()

        mock_token = MagicMock()
        mock_token.with_identity.return_value = mock_token
        mock_token.with_name.return_value = mock_token
        mock_token.with_grants.return_value = mock_token
        mock_token.to_jwt.return_value = "user-jwt"
        mock_access_token_class.return_value = mock_token

        token = pool.generate_user_token("test-room", "John")

        mock_token.with_identity.assert_called_once_with("John")
        mock_token.with_name.assert_called_once_with("John")
        assert token == "user-jwt"


class TestShutdown:
    """Test suite for pool shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_running(self):
        """Should set running flag to False."""
        pool = AgentPool()
        pool._running = True

        await pool.shutdown()

        assert pool._running is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_health_check(self):
        """Should cancel health check task."""
        pool = AgentPool()
        pool._running = True

        # Create mock health check task
        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()
        pool._health_check_task = mock_task

        await pool.shutdown()

        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_terminates_all_agents(self):
        """Should terminate all agent processes."""
        pool = AgentPool()

        # Add agents with mock processes
        mock_process1 = AsyncMock()
        mock_process1.returncode = None
        mock_process1.wait = AsyncMock()

        mock_process2 = AsyncMock()
        mock_process2.returncode = None
        mock_process2.wait = AsyncMock()

        pool._all_agents = [
            PooledAgent(room_name="room-1", process=mock_process1),
            PooledAgent(room_name="room-2", process=mock_process2),
        ]

        await pool.shutdown()

        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()
        assert len(pool._all_agents) == 0


class TestStatus:
    """Test suite for pool status reporting."""

    def test_status_property(self):
        """Should return pool status information."""
        pool = AgentPool(pool_size=5)
        pool._running = True

        # Add some agents
        pool._all_agents = [
            PooledAgent(room_name="room-1", ready=True),
            PooledAgent(room_name="room-2", ready=True),
            PooledAgent(room_name="room-3", ready=False),
        ]

        status = pool.status

        assert status["pool_size"] == 5
        assert status["running"] is True
        assert status["total_tracked"] == 3
        assert "ready_rooms" in status
        assert "livekit_config" in status

    @patch("bot.pool.LIVEKIT_URL", "wss://test.livekit.cloud")
    @patch("bot.pool.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pool.LIVEKIT_API_SECRET", "test-secret")
    def test_status_livekit_config(self):
        """Should report LiveKit configuration status."""
        pool = AgentPool()

        status = pool.status

        assert status["livekit_config"]["has_url"] is True
        assert status["livekit_config"]["has_key"] is True
        assert status["livekit_config"]["has_secret"] is True


class TestModuleSingleton:
    """Test suite for module-level singleton."""

    def test_agent_pool_singleton_exists(self):
        """Should have module-level singleton instance."""
        from bot.pool import agent_pool

        assert agent_pool is not None
        assert isinstance(agent_pool, AgentPool)


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.mark.asyncio
    async def test_pop_with_queue_desync(self):
        """Should handle queue desynchronization."""
        pool = AgentPool(pool_size=2)
        pool._running = True

        # Manually create desync: queue has many items but they're all invalid
        for _ in range(10):
            dead_process = MagicMock()
            dead_process.returncode = 1
            dead_agent = PooledAgent(room_name="dead", process=dead_process)
            await pool._ready_agents.put(dead_agent)

        with patch.object(pool, "_spawn_agent") as mock_spawn:
            mock_process = MagicMock()
            mock_process.returncode = None
            mock_spawn.return_value = PooledAgent(room_name="new", process=mock_process, ready=True)
            with patch.object(pool, "_remove_agent", new_callable=AsyncMock):
                popped = await pool.pop()

        # Should drain invalid agents and spawn new one
        assert popped is not None

    @pytest.mark.asyncio
    async def test_replenish_spawn_failure(self):
        """Should handle spawn failure during replenishment."""
        pool = AgentPool(pool_size=2)
        pool._running = True

        with patch.object(pool, "_spawn_agent", side_effect=Exception("Spawn error")):
            # Should not raise, just return
            await pool._replenish()

        assert len(pool._all_agents) == 0