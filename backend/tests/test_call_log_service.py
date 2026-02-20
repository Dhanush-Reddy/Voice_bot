"""
Comprehensive tests for backend/services/call_log_service.py

Tests CallLogService methods:
- create_call_log
- list_calls (with filtering and limits)
- get_call
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from services.call_log_service import CallLogService, _call_store
from models.call_log import CallLog, CallLogCreateRequest, TranscriptMessage


@pytest.fixture(autouse=True)
def clear_call_store():
    """Clear the in-memory store before each test."""
    _call_store.clear()
    yield
    _call_store.clear()


@pytest.fixture
def service():
    """Create a fresh CallLogService instance."""
    return CallLogService()


class TestCreateCallLog:
    """Test suite for create_call_log method."""

    @pytest.mark.asyncio
    async def test_create_call_log_minimal(self, service):
        """Should create call log with minimal required fields."""
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=120,
        )

        call = await service.create_call_log(request)

        assert call.id is not None
        assert call.agent_id == "test-agent"
        assert call.room_name == "test-room"
        assert call.status == "completed"
        assert call.duration_seconds == 120
        assert call.transcript is None
        assert call.recording_url is None
        assert call.created_at is not None
        assert isinstance(call.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_call_log_full(self, service):
        """Should create call log with all fields."""
        transcript = [
            {"role": "agent", "content": "Hello"},
            {"role": "user", "content": "Hi"},
        ]
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=180,
            transcript=transcript,
            recording_url="https://example.com/rec.mp3",
        )

        call = await service.create_call_log(request)

        assert call.id is not None
        assert call.agent_id == "test-agent"
        assert call.room_name == "test-room"
        assert call.status == "completed"
        assert call.duration_seconds == 180
        # Transcript is stored as list (Any type in model)
        assert call.transcript is not None
        assert len(call.transcript) == 2
        assert call.recording_url == "https://example.com/rec.mp3"
        assert call.created_at is not None

    @pytest.mark.asyncio
    async def test_create_call_log_persists_to_store(self, service):
        """Should persist call log to in-memory store."""
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=60,
        )

        call = await service.create_call_log(request)

        assert call.id in _call_store
        assert _call_store[call.id] == call

    @pytest.mark.asyncio
    async def test_create_call_log_generates_unique_ids(self, service):
        """Should generate unique IDs for each call."""
        request1 = CallLogCreateRequest(
            room_name="room-1",
            agent_id="agent-1",
            duration_seconds=60,
        )
        request2 = CallLogCreateRequest(
            room_name="room-2",
            agent_id="agent-2",
            duration_seconds=90,
        )

        call1 = await service.create_call_log(request1)
        call2 = await service.create_call_log(request2)

        assert call1.id != call2.id
        assert len(_call_store) == 2

    @pytest.mark.asyncio
    async def test_create_call_log_sets_utc_timestamp(self, service):
        """Should set created_at in UTC timezone."""
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=60,
        )

        call = await service.create_call_log(request)

        assert call.created_at.tzinfo is not None
        assert call.created_at.tzinfo == timezone.utc


class TestListCalls:
    """Test suite for list_calls method."""

    @pytest.mark.asyncio
    async def test_list_calls_empty(self, service):
        """Should return empty list when no calls exist."""
        calls = await service.list_calls()

        assert calls == []

    @pytest.mark.asyncio
    async def test_list_calls_all(self, service):
        """Should return all calls when no filter applied."""
        # Create test calls
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-1", agent_id="agent-1", duration_seconds=60
        ))
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-2", agent_id="agent-2", duration_seconds=90
        ))
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-3", agent_id="agent-1", duration_seconds=120
        ))

        calls = await service.list_calls()

        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_list_calls_filtered_by_agent(self, service):
        """Should filter calls by agent_id."""
        # Create test calls
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-1", agent_id="agent-1", duration_seconds=60
        ))
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-2", agent_id="agent-2", duration_seconds=90
        ))
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-3", agent_id="agent-1", duration_seconds=120
        ))

        calls = await service.list_calls(agent_id="agent-1")

        assert len(calls) == 2
        assert all(c.agent_id == "agent-1" for c in calls)

    @pytest.mark.asyncio
    async def test_list_calls_filtered_by_nonexistent_agent(self, service):
        """Should return empty list if agent has no calls."""
        await service.create_call_log(CallLogCreateRequest(
            room_name="room-1", agent_id="agent-1", duration_seconds=60
        ))

        calls = await service.list_calls(agent_id="nonexistent-agent")

        assert calls == []

    @pytest.mark.asyncio
    async def test_list_calls_sorted_newest_first(self, service):
        """Should return calls sorted by created_at, newest first."""
        import asyncio

        # Create calls with slight time delays
        call1 = await service.create_call_log(CallLogCreateRequest(
            room_name="room-1", agent_id="agent-1", duration_seconds=60
        ))
        await asyncio.sleep(0.01)  # Small delay
        call2 = await service.create_call_log(CallLogCreateRequest(
            room_name="room-2", agent_id="agent-1", duration_seconds=60
        ))
        await asyncio.sleep(0.01)
        call3 = await service.create_call_log(CallLogCreateRequest(
            room_name="room-3", agent_id="agent-1", duration_seconds=60
        ))

        calls = await service.list_calls()

        # Newest should be first
        assert calls[0].id == call3.id
        assert calls[1].id == call2.id
        assert calls[2].id == call1.id

    @pytest.mark.asyncio
    async def test_list_calls_with_limit(self, service):
        """Should respect limit parameter."""
        # Create 5 calls
        for i in range(5):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-{i}", agent_id="agent-1", duration_seconds=60
            ))

        calls = await service.list_calls(limit=3)

        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_list_calls_default_limit(self, service):
        """Should use default limit of 50."""
        # Create 60 calls
        for i in range(60):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-{i}", agent_id="agent-1", duration_seconds=60
            ))

        calls = await service.list_calls()

        assert len(calls) == 50  # Default limit

    @pytest.mark.asyncio
    async def test_list_calls_limit_larger_than_total(self, service):
        """Should return all calls if limit exceeds total count."""
        # Create 3 calls
        for i in range(3):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-{i}", agent_id="agent-1", duration_seconds=60
            ))

        calls = await service.list_calls(limit=100)

        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_list_calls_combined_filter_and_limit(self, service):
        """Should apply both agent filter and limit."""
        # Create calls for two agents
        for i in range(5):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-agent1-{i}", agent_id="agent-1", duration_seconds=60
            ))
        for i in range(3):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-agent2-{i}", agent_id="agent-2", duration_seconds=60
            ))

        calls = await service.list_calls(agent_id="agent-1", limit=3)

        assert len(calls) == 3
        assert all(c.agent_id == "agent-1" for c in calls)


class TestGetCall:
    """Test suite for get_call method."""

    @pytest.mark.asyncio
    async def test_get_call_success(self, service):
        """Should return call by ID."""
        created_call = await service.create_call_log(CallLogCreateRequest(
            room_name="test-room", agent_id="test-agent", duration_seconds=60
        ))

        retrieved_call = await service.get_call(created_call.id)

        assert retrieved_call is not None
        assert retrieved_call.id == created_call.id
        assert retrieved_call.room_name == "test-room"
        assert retrieved_call.agent_id == "test-agent"

    @pytest.mark.asyncio
    async def test_get_call_not_found(self, service):
        """Should return None if call doesn't exist."""
        call = await service.get_call("nonexistent-id")

        assert call is None

    @pytest.mark.asyncio
    async def test_get_call_with_transcript(self, service):
        """Should return call with full transcript."""
        transcript = [
            {"role": "agent", "content": "Hello"},
            {"role": "user", "content": "Hi there"},
        ]
        created_call = await service.create_call_log(CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=60,
            transcript=transcript,
        ))

        retrieved_call = await service.get_call(created_call.id)

        # Transcript is stored
        assert retrieved_call.transcript is not None
        assert len(retrieved_call.transcript) == 2

    @pytest.mark.asyncio
    async def test_get_call_returns_same_instance(self, service):
        """Should return the same instance from the store."""
        created_call = await service.create_call_log(CallLogCreateRequest(
            room_name="test-room", agent_id="test-agent", duration_seconds=60
        ))

        retrieved_call = await service.get_call(created_call.id)

        assert retrieved_call is created_call


class TestServiceIntegration:
    """Test suite for service integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, service):
        """Should handle complete call log lifecycle."""
        # Create a call
        request = CallLogCreateRequest(
            room_name="integration-room",
            agent_id="integration-agent",
            duration_seconds=150,
            transcript=[{"role": "agent", "content": "Test"}],
            recording_url="https://example.com/rec.mp3",
        )
        created_call = await service.create_call_log(request)

        # Retrieve by ID
        retrieved = await service.get_call(created_call.id)
        assert retrieved is not None
        assert retrieved.id == created_call.id

        # List all calls
        all_calls = await service.list_calls()
        assert len(all_calls) == 1
        assert all_calls[0].id == created_call.id

    @pytest.mark.asyncio
    async def test_multiple_agents_multiple_calls(self, service):
        """Should handle multiple agents with multiple calls each."""
        # Create calls for agent-1
        for i in range(3):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-1-{i}", agent_id="agent-1", duration_seconds=60 + i
            ))

        # Create calls for agent-2
        for i in range(2):
            await service.create_call_log(CallLogCreateRequest(
                room_name=f"room-2-{i}", agent_id="agent-2", duration_seconds=90 + i
            ))

        # Verify total count
        all_calls = await service.list_calls()
        assert len(all_calls) == 5

        # Verify agent-1 calls
        agent1_calls = await service.list_calls(agent_id="agent-1")
        assert len(agent1_calls) == 3
        assert all(c.agent_id == "agent-1" for c in agent1_calls)

        # Verify agent-2 calls
        agent2_calls = await service.list_calls(agent_id="agent-2")
        assert len(agent2_calls) == 2
        assert all(c.agent_id == "agent-2" for c in agent2_calls)

    @pytest.mark.asyncio
    async def test_empty_transcript_handling(self, service):
        """Should handle calls with empty transcripts."""
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=60,
            transcript=[],
        )

        call = await service.create_call_log(request)
        assert call.transcript == []

        retrieved = await service.get_call(call.id)
        assert retrieved.transcript == []

    @pytest.mark.asyncio
    async def test_zero_duration_calls(self, service):
        """Should handle calls with zero duration."""
        request = CallLogCreateRequest(
            room_name="test-room",
            agent_id="test-agent",
            duration_seconds=0,
        )

        call = await service.create_call_log(request)
        assert call.duration_seconds == 0

        calls = await service.list_calls()
        assert calls[0].duration_seconds == 0


class TestModuleSingleton:
    """Test suite for module-level singleton."""

    def test_call_log_service_singleton_exists(self):
        """Should have module-level singleton instance."""
        from services.call_log_service import call_log_service

        assert call_log_service is not None
        assert isinstance(call_log_service, CallLogService)

    @pytest.mark.asyncio
    async def test_singleton_uses_same_store(self):
        """Should use the same in-memory store."""
        from services.call_log_service import call_log_service

        # Create call using singleton
        request = CallLogCreateRequest(
            room_name="singleton-room",
            agent_id="singleton-agent",
            duration_seconds=60,
        )
        call = await call_log_service.create_call_log(request)

        # Verify it's in the shared store
        assert call.id in _call_store

        # Create another instance and verify it sees the same data
        new_instance = CallLogService()
        retrieved = await new_instance.get_call(call.id)
        assert retrieved is not None
        assert retrieved.id == call.id