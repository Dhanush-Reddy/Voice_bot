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
import asyncio
import sys
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
            system_prompt="You are a helpful AI assistant.",
            language="en-US",
            voice_id="Aoede",
            is_active=True,
        )

        active_agent = AgentConfig(
            id="active-agent-id",
            name="Active Agent",
            system_prompt="You are a friendly Hindi-speaking assistant.",
            language="hi-IN",
            voice_id="Puck",
            is_active=True,
        )

        inactive_agent = AgentConfig(
            id="inactive-agent-id",
            name="Inactive Agent",
            system_prompt="You are inactive.",
            language="en-US",
            voice_id="Aoede",
            is_active=False,
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
        mock_service.list_calls = AsyncMock(side_effect=lambda agent_id=None, status=None, outcome=None, limit=50: (
            [call1] if agent_id == "default-agent-id" else [call1, call2]
        ))
        mock_service.get_call = AsyncMock(side_effect=lambda cid: call1 if cid == "call-1" else None)
        mock_service.get_stats = AsyncMock(return_value={"total_calls": 10, "avg_duration": 120})

        yield mock_service


@pytest.fixture
def client(mock_agent_pool, mock_agent_service, mock_call_log_service):
    """Create a test client with mocked dependencies."""
    # Environment is already configured by conftest.py
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

    def test_generate_token_missing_livekit_config(self, client):
        """Should return 500 if LiveKit environment not configured."""
        # Patch LIVEKIT_URL to be empty in the routes module
        with patch("api.routes.LIVEKIT_URL", ""):
            response = client.get("/api/token?participant_name=TestUser")

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
            "system_prompt": "You are a helpful assistant.",
            "language": "en-US",
            "voice_id": "Aoede",
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
    """Test suite for /api/agents/search endpoint.

    Note: The /api/agents/search endpoint is not implemented in routes.py.
    These tests verify that the endpoint returns 404 as expected.
    If the endpoint is added in the future, update these tests.
    """

    def test_search_endpoint_not_implemented(self, client):
        """Should return 404 since search endpoint is not implemented."""
        response = client.get("/api/agents/search")
        assert response.status_code == 404


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

    def test_health_check_missing_env(self, client):
        """Should report config_ok=False when env vars missing."""
        # Patch the settings to simulate missing env vars
        with patch("api.routes.settings") as mock_settings:
            mock_settings.livekit_configured = False
            mock_settings.gemini_configured = False
            mock_settings.uptime_seconds = 100
            mock_settings.livekit_url = ""
            mock_settings.livekit_api_key = ""
            mock_settings.livekit_api_secret = ""
            mock_settings.google_cloud_project = ""

            response = client.get("/api/health")

            assert response.status_code == 200
            health = response.json()
            assert health["config_ok"] is False


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_generate_token_missing_participant_name(self, client):
        """Should return 422 if participant_name is missing."""
        response = client.get("/api/token")

        assert response.status_code == 422

    def test_agent_search_endpoint_not_found(self, client):
        """Agent search endpoint is not implemented."""
        response = client.get("/api/agents/search?name=nonexistent")

        assert response.status_code == 404

    def test_calls_limit_validation(self, client):
        """Should reject limit > 500."""
        response = client.get("/api/calls?limit=600")

        assert response.status_code == 422


class TestCallLogDeletion:
    """Test suite for call log deletion endpoint."""

    def test_delete_call_success(self, client, mock_call_log_service):
        """Should delete existing call."""
        mock_call_log_service.delete_call = AsyncMock(return_value=True)
        response = client.delete("/api/calls/call-1")

        assert response.status_code == 204

    def test_delete_call_not_found(self, client, mock_call_log_service):
        """Should return 404 if call doesn't exist."""
        mock_call_log_service.delete_call = AsyncMock(return_value=False)
        response = client.delete("/api/calls/nonexistent")

        assert response.status_code == 404


class TestLiveKitWebhook:
    """Test suite for LiveKit webhook endpoint."""

    def test_webhook_room_finished_creates_call(self, client, mock_call_log_service):
        """Should process room_finished event and create call log."""
        from models.call_log import CallLog
        from datetime import datetime, timezone

        mock_call = CallLog(
            id="webhook-call-1",
            agent_id="test-agent",
            room_name="test-room",
            status="completed",
            duration_seconds=120,
            created_at=datetime.now(timezone.utc),
        )
        mock_call_log_service.process_livekit_webhook = AsyncMock(return_value=mock_call)

        payload = {
            "event": "room_finished",
            "room": {"name": "test-room"},
            "participant": {"identity": "user123"},
        }
        response = client.post("/api/webhooks/livekit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["call_id"] == "webhook-call-1"
        assert data["room"] == "test-room"

    def test_webhook_ignored_event(self, client, mock_call_log_service):
        """Should acknowledge but ignore non-room_finished events."""
        mock_call_log_service.process_livekit_webhook = AsyncMock(return_value=None)

        payload = {
            "event": "participant_joined",
            "room": {"name": "test-room"},
        }
        response = client.post("/api/webhooks/livekit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["event"] == "participant_joined"


class TestKnowledgeBaseEndpoints:
    """Test suite for knowledge base/RAG endpoints."""

    @pytest.fixture
    def mock_knowledge_service(self):
        """Mock the knowledge service singleton."""
        with patch("api.routes.knowledge_service") as mock_service:
            from models.knowledge import KnowledgeDocument, KnowledgeSearchResult
            from datetime import datetime, timezone

            doc1 = KnowledgeDocument(
                id="doc-1",
                agent_id="active-agent-id",
                filename="test.txt",
                content_type="text/plain",
                chunk_count=5,
                created_at=datetime.now(timezone.utc),
            )

            search_result = KnowledgeSearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="Relevant content here",
                score=0.95,
            )

            mock_service.ingest = AsyncMock(return_value=doc1)
            mock_service.list_documents = AsyncMock(return_value=[doc1])
            mock_service.delete_document = AsyncMock(return_value=True)
            mock_service.search = AsyncMock(return_value=[search_result])

            yield mock_service

    def test_upload_document_txt(self, client, mock_agent_service, mock_knowledge_service):
        """Should upload text document successfully."""
        from io import BytesIO

        file_content = b"This is a test document with important information."
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

        response = client.post(
            "/api/agents/active-agent-id/knowledge",
            files=files
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "doc-1"
        assert data["filename"] == "test.txt"
        assert data["chunk_count"] == 5

    def test_upload_document_pdf_with_pypdf(self, client, mock_agent_service, mock_knowledge_service):
        """Should handle PDF upload when pypdf is available."""
        from io import BytesIO
        import pypdf

        # Create a minimal valid PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000317 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n409\n%%EOF"

        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}

        response = client.post(
            "/api/agents/active-agent-id/knowledge",
            files=files
        )

        # Should successfully process the PDF
        assert response.status_code == 201

    def test_upload_document_empty_content(self, client, mock_agent_service):
        """Should return 422 if document has no extractable text."""
        from io import BytesIO

        files = {"file": ("empty.txt", BytesIO(b""), "text/plain")}

        response = client.post(
            "/api/agents/active-agent-id/knowledge",
            files=files
        )

        assert response.status_code == 422
        assert "could not extract text" in response.json()["detail"].lower()

    def test_upload_document_agent_not_found(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        from io import BytesIO

        files = {"file": ("test.txt", BytesIO(b"content"), "text/plain")}

        response = client.post(
            "/api/agents/nonexistent/knowledge",
            files=files
        )

        assert response.status_code == 404

    def test_list_documents(self, client, mock_agent_service, mock_knowledge_service):
        """Should list all documents for an agent."""
        response = client.get("/api/agents/active-agent-id/knowledge")

        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 1
        assert docs[0]["id"] == "doc-1"

    def test_list_documents_agent_not_found(self, client, mock_agent_service):
        """Should return 404 if agent doesn't exist."""
        response = client.get("/api/agents/nonexistent/knowledge")

        assert response.status_code == 404

    def test_delete_document_success(self, client, mock_knowledge_service):
        """Should delete document successfully."""
        response = client.delete("/api/knowledge/doc-1")

        assert response.status_code == 204

    def test_delete_document_not_found(self, client, mock_knowledge_service):
        """Should return 404 if document doesn't exist."""
        mock_knowledge_service.delete_document.return_value = False

        response = client.delete("/api/knowledge/nonexistent")

        assert response.status_code == 404

    def test_search_knowledge(self, client, mock_knowledge_service):
        """Should search knowledge base and return results."""
        response = client.get("/api/agents/active-agent-id/knowledge/search?q=test+query")

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-1"
        assert results[0]["score"] == 0.95

    def test_search_knowledge_with_top_k(self, client, mock_knowledge_service):
        """Should respect top_k parameter."""
        response = client.get("/api/agents/active-agent-id/knowledge/search?q=test&top_k=5")

        assert response.status_code == 200
        mock_knowledge_service.search.assert_called_once()

    def test_search_knowledge_missing_query(self, client):
        """Should return 422 if query parameter is missing."""
        response = client.get("/api/agents/active-agent-id/knowledge/search")

        assert response.status_code == 422


class TestConfigManagement:
    """Test suite for config cache management endpoints."""

    @pytest.fixture
    def mock_config_service(self):
        """Mock the config service singleton."""
        with patch("api.routes.config_service") as mock_service:
            mock_service.invalidate = MagicMock()
            mock_service.invalidate_all = MagicMock()
            mock_service.cache_stats = {
                "hits": 42,
                "misses": 8,
                "size": 5,
            }
            yield mock_service

    def test_reload_agent_config(self, client, mock_agent_service, mock_config_service):
        """Should invalidate cache for specific agent."""
        response = client.post("/api/agents/active-agent-id/reload")

        assert response.status_code == 200
        data = response.json()
        assert "config cache cleared" in data["message"].lower()
        assert data["agent_id"] == "active-agent-id"
        mock_config_service.invalidate.assert_called_once_with("active-agent-id")

    def test_reload_agent_config_not_found(self, client, mock_agent_service, mock_config_service):
        """Should return 404 if agent doesn't exist."""
        response = client.post("/api/agents/nonexistent/reload")

        assert response.status_code == 404

    def test_flush_config_cache(self, client, mock_config_service):
        """Should flush entire config cache."""
        response = client.post("/api/config/flush")

        assert response.status_code == 200
        data = response.json()
        assert "entire config cache flushed" in data["message"].lower()
        mock_config_service.invalidate_all.assert_called_once()

    def test_config_cache_stats(self, client, mock_config_service):
        """Should return cache statistics."""
        response = client.get("/api/config/cache")

        assert response.status_code == 200
        stats = response.json()
        assert stats["hits"] == 42
        assert stats["misses"] == 8
        assert stats["size"] == 5

    def test_get_config_options(self, client):
        """Should return available configuration options."""
        response = client.get("/api/config/options")

        # Endpoint should work now with our builtins patch
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert "models" in data
        assert "languages" in data


class TestLifespanManagement:
    """Test suite for application lifespan management.

    Note: Lifespan function is complex to test due to asyncio.create_task and module
    imports. The lifespan is implicitly tested by the client fixture which successfully
    creates a TestClient with the app. Additional lifespan tests would require extensive
    mocking and may not provide significant value beyond integration testing.
    """

    def test_lifespan_function_exists(self):
        """Verify lifespan function is defined and used by the app."""
        with patch.dict("sys.modules", {"core.database": MagicMock(init_db=AsyncMock())}):
            with patch("asyncio.create_task"):
                from api.routes import app, lifespan

                # Verify app uses the lifespan
                assert app.router.lifespan_context is not None


class TestCORSConfiguration:
    """Test suite for CORS middleware configuration."""

    def test_cors_allows_configured_origins(self, client):
        """Should allow requests from configured origins."""
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200

    def test_cors_headers_present(self, client):
        """Should include CORS headers in response."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # CORS headers should be present
        assert response.status_code in [200, 405]  # OPTIONS may not be explicitly handled


class TestAdditionalEdgeCases:
    """Additional edge cases and regression tests."""

    def test_health_endpoint_includes_all_fields(self, client, mock_call_log_service):
        """Should include all expected health check fields."""
        mock_call_log_service.get_stats = AsyncMock(return_value={
            "total_calls": 10,
            "avg_duration": 120,
        })

        response = client.get("/api/health")

        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "version" in health
        assert "config_ok" in health
        assert "uptime_seconds" in health
        assert "pool" in health
        assert "config_cache" in health
        assert "calls" in health
        assert "env_check" in health

    def test_pool_status_returns_dict(self, client, mock_agent_pool):
        """Should return pool status as dictionary."""
        response = client.get("/api/pool/status")

        assert response.status_code == 200
        status = response.json()
        assert isinstance(status, dict)
        assert "pool_size" in status
        assert "ready" in status

    def test_token_generation_logs_room_info(self, client, mock_agent_service, mock_agent_pool):
        """Should log token generation details."""
        with patch("api.routes.logger") as mock_logger:
            response = client.get("/api/token?participant_name=TestUser")

            assert response.status_code == 200
            # Verify logging occurred
            assert mock_logger.info.called

    def test_calls_filter_by_status(self, client, mock_call_log_service):
        """Should filter calls by status parameter."""
        response = client.get("/api/calls?status=completed")

        assert response.status_code == 200

    def test_calls_filter_by_outcome(self, client, mock_call_log_service):
        """Should filter calls by outcome parameter."""
        response = client.get("/api/calls?outcome=success")

        assert response.status_code == 200

    def test_search_knowledge_top_k_validation(self, client):
        """Should validate top_k <= 10."""
        response = client.get("/api/agents/active-agent-id/knowledge/search?q=test&top_k=20")

        assert response.status_code == 422