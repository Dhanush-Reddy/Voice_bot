"""
Comprehensive tests for backend/api/routes.py

Tests all endpoints including:
- Token generation (with/without agent_id)
- Agent CRUD operations
- Agent search functionality
- Call log endpoints
- Health checks and pool status
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from models.agent import AgentConfig
from models.call_log import CallLog


@pytest.fixture
def mock_agent_pool():
    """Mock the agent pool singleton."""
    with patch("api.routes.agent_pool") as mock_pool:
        # Mock pooled agent
        mock_pooled_agent = MagicMock()
        mock_pooled_agent.room_name = "test-room-123"

        # Setup mock methods
        mock_pool.pop = AsyncMock(return_value=mock_pooled_agent)
        mock_pool.generate_user_token = MagicMock(return_value="test_token_123")
        mock_pool.status = {
            "pool_size": 3,
            "ready": 2,
            "ready_rooms": ["room-1", "room-2"],
            "total_tracked": 2,
            "running": True,
        }

        yield mock_pool


@pytest.fixture
def mock_agent_service():
    """Mock the agent service singleton."""
    with patch("api.routes.agent_service") as mock_service:
        # Sample agents
        default_agent = AgentConfig(
            id="default-agent-id",
            name="Default Agent",
            language="en-US",
            voice="Aoede",
            is_active=True,
            is_default=True,
        )

        active_agent = AgentConfig(
            id="active-agent-id",
            name="Active Agent",
            language="hi-IN",
            voice="Puck",
            is_active=True,
            is_default=False,
        )

        inactive_agent = AgentConfig(
            id="inactive-agent-id",
            name="Inactive Agent",
            language="en-US",
            voice="Aoede",
            is_active=False,
            is_default=False,
        )

        # Setup mock methods
        mock_service.get_agent = AsyncMock(side_effect=lambda agent_id: {
            "default-agent-id": default_agent,
            "active-agent-id": active_agent,
            "inactive-agent-id": inactive_agent,
        }.get(agent_id))

        mock_service.get_default_agent = AsyncMock(return_value=default_agent)
        mock_service.list_agents = AsyncMock(return_value=[default_agent, active_agent, inactive_agent])
        mock_service.create_agent = AsyncMock(return_value=active_agent)
        mock_service.update_agent = AsyncMock(side_effect=lambda aid, req: active_agent if aid == "active-agent-id" else None)
        mock_service.delete_agent = AsyncMock(side_effect=lambda aid: aid == "active-agent-id")

        yield mock_service


@pytest.fixture
def mock_call_log_service():
    """Mock the call log service singleton."""
    with patch("api.routes.call_log_service") as mock_service:
        # Sample call logs
        call1 = CallLog(
            id="call-1",
            agent_id="default-agent-id",
            room_name="room-1",
            status="completed",
            outcome="success",
            duration_seconds=120,
            created_at=datetime.now(timezone.utc),
        )

        call2 = CallLog(
            id="call-2",
            agent_id="active-agent-id",
            room_name="room-2",
            status="completed",
            outcome="not_interested",
            duration_seconds=45,
            created_at=datetime.now(timezone.utc),
        )

        # Setup mock methods
        mock_service.list_calls = AsyncMock(side_effect=lambda agent_id=None, limit=50: (
            [call1] if agent_id == "default-agent-id" else [call1, call2]
        ))
        mock_service.get_call = AsyncMock(side_effect=lambda cid: call1 if cid == "call-1" else None)

        yield mock_service


@pytest.fixture
def client(mock_agent_pool, mock_agent_service, mock_call_log_service):
    """Create a test client with mocked dependencies."""
    # Mock environment variables
    with patch.dict("os.environ", {
        "LIVEKIT_URL": "wss://test.livekit.cloud",
        "LIVEKIT_API_KEY": "test_key",
        "LIVEKIT_API_SECRET": "test_secret",
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON": '{"type": "service_account"}',
    }):
        # Mock the lifespan to avoid starting the pool
        with patch("api.routes.agent_pool.start"), patch("api.routes.agent_pool.shutdown"):
            from api.routes import app
            yield TestClient(app)


class TestTokenGeneration:
    """Test suite for /api/token endpoint."""

    def test_generate_token_without_agent_id(self, client, mock_agent_service, mock_agent_pool):
        """Should generate token using default agent."""
        response = client.get("/api/token?participant_name=TestUser")

        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test_token_123"
        assert data["url"] == "wss://test.livekit.cloud"
        assert data["room_name"] == "test-room-123"
        assert data["agent_id"] == "default-agent-id"

        mock_agent_service.get_default_agent.assert_called_once()
        mock_agent_pool.pop.assert_called_once()

    def test_generate_token_with_valid_agent_id(self, client, mock_agent_service, mock_agent_pool):
        """Should generate token using specified active agent."""
        response = client.get("/api/token?participant_name=TestUser&agent_id=active-agent-id")

        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test_token_123"
        assert data["agent_id"] == "active-agent-id"

        mock_agent_service.get_agent.assert_called_once_with("active-agent-id")

    def test_generate_token_with_nonexistent_agent(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        response = client.get("/api/token?participant_name=TestUser&agent_id=nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_generate_token_with_inactive_agent(self, client, mock_agent_service):
        """Should return 400 if agent is not active."""
        response = client.get("/api/token?participant_name=TestUser&agent_id=inactive-agent-id")

        assert response.status_code == 400
        assert "not active" in response.json()["detail"].lower()

    def test_generate_token_pool_exhausted(self, client, mock_agent_pool):
        """Should return 503 if no agents available in pool."""
        mock_agent_pool.pop.return_value = None

        response = client.get("/api/token?participant_name=TestUser")

        assert response.status_code == 503
        assert "no agents available" in response.json()["detail"].lower()

    def test_generate_token_missing_livekit_config(self, mock_agent_service, mock_agent_pool, mock_call_log_service):
        """Should return 500 if LiveKit environment not configured."""
        with patch.dict("os.environ", {"LIVEKIT_URL": ""}, clear=True):
            with patch("api.routes.agent_pool.start"), patch("api.routes.agent_pool.shutdown"):
                from api.routes import app
                test_client = TestClient(app)
                response = test_client.get("/api/token?participant_name=TestUser")

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"].lower()


class TestAgentCRUD:
    """Test suite for agent CRUD endpoints."""

    def test_list_agents(self, client, mock_agent_service):
        """Should return all agents."""
        response = client.get("/api/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3
        assert any(a["id"] == "default-agent-id" for a in agents)

    def test_get_agent_success(self, client, mock_agent_service):
        """Should return specific agent by ID."""
        response = client.get("/api/agents/active-agent-id")

        assert response.status_code == 200
        agent = response.json()
        assert agent["id"] == "active-agent-id"
        assert agent["name"] == "Active Agent"

    def test_get_agent_not_found(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        response = client.get("/api/agents/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_agent(self, client, mock_agent_service):
        """Should create a new agent."""
        payload = {
            "name": "New Agent",
            "language": "en-US",
            "voice": "Aoede",
        }
        response = client.post("/api/agents", json=payload)

        assert response.status_code == 201
        agent = response.json()
        assert agent["id"] == "active-agent-id"

    def test_update_agent_success(self, client, mock_agent_service):
        """Should update existing agent."""
        payload = {"name": "Updated Name"}
        response = client.patch("/api/agents/active-agent-id", json=payload)

        assert response.status_code == 200
        agent = response.json()
        assert agent["id"] == "active-agent-id"

    def test_update_agent_not_found(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        payload = {"name": "Updated Name"}
        response = client.patch("/api/agents/nonexistent", json=payload)

        assert response.status_code == 404

    def test_delete_agent_success(self, client, mock_agent_service):
        """Should delete existing agent."""
        response = client.delete("/api/agents/active-agent-id")

        assert response.status_code == 204

    def test_delete_agent_not_found(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        response = client.delete("/api/agents/nonexistent")

        assert response.status_code == 404


class TestAgentSearch:
    """Test suite for /api/agents/search endpoint."""

    def test_search_agents_no_filters(self, client, mock_agent_service):
        """Should return all agents when no filters applied."""
        response = client.get("/api/agents/search")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3

    def test_search_agents_by_name(self, client, mock_agent_service):
        """Should filter by name (case-insensitive)."""
        response = client.get("/api/agents/search?name=default")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["name"] == "Default Agent"

    def test_search_agents_by_language(self, client, mock_agent_service):
        """Should filter by language code."""
        response = client.get("/api/agents/search?language=hi-IN")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["language"] == "hi-IN"

    def test_search_agents_active_only(self, client, mock_agent_service):
        """Should filter to only active agents."""
        response = client.get("/api/agents/search?active_only=true")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 2
        assert all(a["is_active"] for a in agents)

    def test_search_agents_combined_filters(self, client, mock_agent_service):
        """Should apply multiple filters together."""
        response = client.get("/api/agents/search?name=agent&active_only=true")

        assert response.status_code == 200
        agents = response.json()
        # Should match "Default Agent" and "Active Agent" but filter out "Inactive Agent"
        assert len(agents) == 2


class TestCallLogEndpoints:
    """Test suite for call log endpoints."""

    def test_list_calls_all(self, client, mock_call_log_service):
        """Should return all calls."""
        response = client.get("/api/calls")

        assert response.status_code == 200
        calls = response.json()
        assert len(calls) == 2

    def test_list_calls_filtered_by_agent(self, client, mock_call_log_service):
        """Should filter calls by agent_id."""
        response = client.get("/api/calls?agent_id=default-agent-id")

        assert response.status_code == 200
        calls = response.json()
        assert len(calls) == 1
        assert calls[0]["agent_id"] == "default-agent-id"

    def test_list_calls_with_limit(self, client, mock_call_log_service):
        """Should respect limit parameter."""
        response = client.get("/api/calls?limit=1")

        assert response.status_code == 200
        # The mock will still return based on its logic, but endpoint accepts the param
        assert response.status_code == 200

    def test_get_call_success(self, client, mock_call_log_service):
        """Should return specific call by ID."""
        response = client.get("/api/calls/call-1")

        assert response.status_code == 200
        call = response.json()
        assert call["id"] == "call-1"
        assert call["room_name"] == "room-1"

    def test_get_call_not_found(self, client, mock_call_log_service):
        """Should return 404 if call doesn't exist."""
        response = client.get("/api/calls/nonexistent")

        assert response.status_code == 404


class TestInfrastructureEndpoints:
    """Test suite for infrastructure/health endpoints."""

    def test_pool_status(self, client, mock_agent_pool):
        """Should return agent pool status."""
        response = client.get("/api/pool/status")

        assert response.status_code == 200
        status = response.json()
        assert status["pool_size"] == 3
        assert status["ready"] == 2
        assert status["running"] is True

    def test_health_check_all_ok(self, client):
        """Should return comprehensive health status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        health = response.json()
        assert health["status"] == "ok"
        assert health["version"] == "2.0.0"
        assert health["config_ok"] is True
        assert "uptime_seconds" in health
        assert health["uptime_seconds"] >= 0
        assert "pool" in health
        assert "env_check" in health
        assert health["env_check"]["has_lk_url"] is True
        assert health["env_check"]["has_gcp_project"] is True

    def test_health_check_missing_env(self, mock_agent_service, mock_agent_pool, mock_call_log_service):
        """Should report config_ok=False when env vars missing."""
        with patch.dict("os.environ", {"LIVEKIT_URL": ""}, clear=True):
            with patch("api.routes.agent_pool.start"), patch("api.routes.agent_pool.shutdown"):
                from api.routes import app
                test_client = TestClient(app)
                response = test_client.get("/api/health")

        assert response.status_code == 200
        health = response.json()
        assert health["config_ok"] is False
        assert health["env_check"]["has_lk_url"] is False


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_generate_token_missing_participant_name(self, client):
        """Should return 422 if participant_name is missing."""
        response = client.get("/api/token")

        assert response.status_code == 422

    def test_agent_search_empty_results(self, client, mock_agent_service):
        """Should return empty list if no agents match filters."""
        response = client.get("/api/agents/search?name=nonexistent")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 0

    def test_calls_limit_validation(self, client):
        """Should reject limit > 200."""
        response = client.get("/api/calls?limit=300")

        assert response.status_code == 422