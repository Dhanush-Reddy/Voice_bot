"""
Comprehensive tests for backend/models/call_log.py

Tests Pydantic models:
- TranscriptMessage validation
- CallLog validation and field defaults
- CallLogCreateRequest validation
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from models.call_log import TranscriptMessage, CallLog, CallLogCreateRequest


class TestTranscriptMessage:
    """Test suite for TranscriptMessage model."""

    def test_valid_transcript_message(self):
        """Should create valid transcript message."""
        message = TranscriptMessage(
            role="agent",
            content="Hello, how can I help you?",
            timestamp="2024-01-15T10:30:00Z",
        )

        assert message.role == "agent"
        assert message.content == "Hello, how can I help you?"
        assert message.timestamp == "2024-01-15T10:30:00Z"

    def test_transcript_message_without_timestamp(self):
        """Should allow optional timestamp."""
        message = TranscriptMessage(
            role="user",
            content="I need help",
        )

        assert message.role == "user"
        assert message.content == "I need help"
        assert message.timestamp is None

    def test_transcript_message_missing_required_fields(self):
        """Should raise ValidationError if required fields missing."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptMessage(role="agent")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)

    def test_transcript_message_role_variations(self):
        """Should accept different role values."""
        roles = ["agent", "user", "system", "assistant"]
        for role in roles:
            message = TranscriptMessage(role=role, content="Test")
            assert message.role == role

    def test_transcript_message_empty_content(self):
        """Should allow empty string content."""
        message = TranscriptMessage(role="agent", content="")
        assert message.content == ""


class TestCallLog:
    """Test suite for CallLog model."""

    def test_valid_call_log_minimal(self):
        """Should create call log with minimal required fields."""
        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
        )

        assert call.id == "call-123"
        assert call.agent_id == "agent-456"
        assert call.room_name == "room-789"
        assert call.status == "completed"
        assert call.duration_seconds == 0  # Default value
        assert call.outcome is None
        assert call.transcript is None
        assert call.recording_url is None
        assert call.created_at is None

    def test_valid_call_log_full(self):
        """Should create call log with all fields."""
        transcript = [
            TranscriptMessage(role="agent", content="Hello"),
            TranscriptMessage(role="user", content="Hi"),
        ]
        created = datetime.now(timezone.utc)

        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
            outcome="success",
            duration_seconds=180,
            transcript=transcript,
            recording_url="https://example.com/recording.mp3",
            created_at=created,
        )

        assert call.id == "call-123"
        assert call.agent_id == "agent-456"
        assert call.room_name == "room-789"
        assert call.status == "completed"
        assert call.outcome == "success"
        assert call.duration_seconds == 180
        assert len(call.transcript) == 2
        assert call.recording_url == "https://example.com/recording.mp3"
        assert call.created_at == created

    def test_call_log_status_values(self):
        """Should accept various status values."""
        statuses = ["completed", "failed", "no_answer", "in_progress"]
        for status in statuses:
            call = CallLog(
                id=f"call-{status}",
                agent_id="agent-1",
                room_name="room-1",
                status=status,
            )
            assert call.status == status

    def test_call_log_outcome_values(self):
        """Should accept various outcome values."""
        outcomes = ["success", "not_interested", "callback_requested", "voicemail"]
        for outcome in outcomes:
            call = CallLog(
                id=f"call-{outcome}",
                agent_id="agent-1",
                room_name="room-1",
                status="completed",
                outcome=outcome,
            )
            assert call.outcome == outcome

    def test_call_log_missing_required_fields(self):
        """Should raise ValidationError if required fields missing."""
        with pytest.raises(ValidationError) as exc_info:
            CallLog(
                id="call-123",
                agent_id="agent-456",
                # Missing room_name and status
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("room_name",) for e in errors)
        assert any(e["loc"] == ("status",) for e in errors)

    def test_call_log_negative_duration(self):
        """Should allow negative duration (though not semantically valid)."""
        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="failed",
            duration_seconds=-1,
        )
        # Pydantic doesn't enforce positive integers unless specified
        assert call.duration_seconds == -1

    def test_call_log_with_empty_transcript(self):
        """Should accept empty transcript list."""
        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
            transcript=[],
        )
        assert call.transcript == []

    def test_call_log_serialization(self):
        """Should serialize to dict correctly."""
        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
            duration_seconds=120,
        )

        data = call.model_dump()
        assert data["id"] == "call-123"
        assert data["duration_seconds"] == 120

    def test_call_log_with_transcript_messages(self):
        """Should handle transcript with multiple messages."""
        transcript = [
            TranscriptMessage(role="agent", content="Hello"),
            TranscriptMessage(role="user", content="Hi there"),
            TranscriptMessage(role="agent", content="How can I help?"),
        ]

        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
            transcript=transcript,
        )

        assert len(call.transcript) == 3
        assert call.transcript[0].role == "agent"
        assert call.transcript[1].role == "user"


class TestCallLogCreateRequest:
    """Test suite for CallLogCreateRequest model."""

    def test_valid_create_request_minimal(self):
        """Should create request with minimal required fields."""
        request = CallLogCreateRequest(
            room_name="room-123",
            agent_id="agent-456",
            duration_seconds=90,
        )

        assert request.room_name == "room-123"
        assert request.agent_id == "agent-456"
        assert request.duration_seconds == 90
        assert request.transcript is None
        assert request.recording_url is None

    def test_valid_create_request_full(self):
        """Should create request with all fields."""
        request = CallLogCreateRequest(
            room_name="room-123",
            agent_id="agent-456",
            duration_seconds=90,
            transcript=[{"role": "agent", "content": "Hello"}],
            recording_url="https://example.com/rec.mp3",
        )

        assert request.room_name == "room-123"
        assert request.agent_id == "agent-456"
        assert request.duration_seconds == 90
        assert request.transcript is not None
        assert len(request.transcript) == 1
        assert request.recording_url == "https://example.com/rec.mp3"

    def test_create_request_missing_required_fields(self):
        """Should raise ValidationError if required fields missing."""
        with pytest.raises(ValidationError) as exc_info:
            CallLogCreateRequest(
                room_name="room-123",
                # Missing agent_id and duration_seconds
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("agent_id",) for e in errors)
        assert any(e["loc"] == ("duration_seconds",) for e in errors)

    def test_create_request_transcript_as_list_of_dicts(self):
        """Should accept transcript as list of any objects."""
        request = CallLogCreateRequest(
            room_name="room-123",
            agent_id="agent-456",
            duration_seconds=60,
            transcript=[
                {"role": "agent", "content": "Hello"},
                {"role": "user", "content": "Hi"},
            ],
        )

        assert len(request.transcript) == 2
        assert request.transcript[0]["role"] == "agent"

    def test_create_request_zero_duration(self):
        """Should accept zero duration."""
        request = CallLogCreateRequest(
            room_name="room-123",
            agent_id="agent-456",
            duration_seconds=0,
        )
        assert request.duration_seconds == 0

    def test_create_request_empty_strings(self):
        """Should accept empty strings for required fields."""
        request = CallLogCreateRequest(
            room_name="",
            agent_id="",
            duration_seconds=0,
        )
        assert request.room_name == ""
        assert request.agent_id == ""


class TestModelInteroperability:
    """Test suite for model interactions and conversions."""

    def test_create_request_to_call_log_conversion(self):
        """Should demonstrate conversion from request to call log."""
        request = CallLogCreateRequest(
            room_name="room-123",
            agent_id="agent-456",
            duration_seconds=120,
            transcript=[{"role": "agent", "content": "Test"}],
        )

        # Simulating service layer conversion
        call = CallLog(
            id="generated-id",
            agent_id=request.agent_id,
            room_name=request.room_name,
            status="completed",
            duration_seconds=request.duration_seconds,
            transcript=request.transcript,
            recording_url=request.recording_url,
            created_at=datetime.now(timezone.utc),
        )

        assert call.agent_id == request.agent_id
        assert call.room_name == request.room_name
        assert call.duration_seconds == request.duration_seconds

    def test_transcript_message_in_call_log(self):
        """Should work with properly typed transcript messages."""
        messages = [
            TranscriptMessage(role="agent", content="Welcome", timestamp="2024-01-15T10:00:00Z"),
            TranscriptMessage(role="user", content="Thanks", timestamp="2024-01-15T10:00:05Z"),
        ]

        call = CallLog(
            id="call-123",
            agent_id="agent-456",
            room_name="room-789",
            status="completed",
            transcript=messages,
        )

        assert isinstance(call.transcript[0], TranscriptMessage)
        assert call.transcript[0].role == "agent"
        assert call.transcript[1].timestamp is not None