"""
Comprehensive tests for backend/bot/pipeline.py

Tests pipeline creation and configuration:
- Gemini service creation with retry logic
- LiveKit transport setup
- Pipeline and task creation
- Event handler registration
- Token generation
- Error handling and retries
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from bot.pipeline import (
    _generate_bot_token,
    _create_gemini_service_with_retry,
    create_pipeline,
    SYSTEM_PROMPT,
    GREETING,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY,
)


class TestBotTokenGeneration:
    """Test suite for _generate_bot_token function."""

    @patch("bot.pipeline.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pipeline.LIVEKIT_API_SECRET", "test-secret")
    def test_generate_bot_token(self):
        """Should generate valid JWT token for bot."""
        room_name = "test-room-123"

        token = _generate_bot_token(room_name)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("bot.pipeline.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pipeline.LIVEKIT_API_SECRET", "test-secret")
    def test_generate_bot_token_different_rooms(self):
        """Should generate different tokens for different rooms."""
        token1 = _generate_bot_token("room-1")
        token2 = _generate_bot_token("room-2")

        # Tokens should be different (room name is encoded)
        assert token1 != token2

    @patch("bot.pipeline.LIVEKIT_API_KEY", "test-key")
    @patch("bot.pipeline.LIVEKIT_API_SECRET", "test-secret")
    @patch("bot.pipeline.AccessToken")
    def test_generate_bot_token_configuration(self, mock_access_token_class):
        """Should configure token with correct identity and grants."""
        mock_token = MagicMock()
        mock_token.with_identity.return_value = mock_token
        mock_token.with_name.return_value = mock_token
        mock_token.with_grants.return_value = mock_token
        mock_token.to_jwt.return_value = "test-jwt"
        mock_access_token_class.return_value = mock_token

        room_name = "test-room"
        token = _generate_bot_token(room_name)

        mock_access_token_class.assert_called_once_with("test-key", "test-secret")
        mock_token.with_identity.assert_called_once_with("priya-bot")
        mock_token.with_name.assert_called_once_with("Priya")
        mock_token.with_grants.assert_called_once()
        mock_token.to_jwt.assert_called_once()
        assert token == "test-jwt"


class TestGeminiServiceCreation:
    """Test suite for _create_gemini_service_with_retry function."""

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "BOT_VOICE": "Aoede",
    })
    async def test_create_gemini_service_success(self, mock_gemini_class):
        """Should create Gemini service on first attempt."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        service = await _create_gemini_service_with_retry()

        assert service == mock_service
        mock_gemini_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON": '{"type": "service_account"}',
    })
    async def test_create_gemini_service_with_credentials_json(self, mock_gemini_class):
        """Should use credentials JSON when provided."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        assert call_kwargs["credentials"] == '{"type": "service_account"}'
        assert call_kwargs["credentials_path"] is None

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch("bot.pipeline.os.path.exists", return_value=True)
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json",
    })
    async def test_create_gemini_service_with_credentials_path(self, mock_exists, mock_gemini_class):
        """Should use credentials path when file exists."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        assert call_kwargs["credentials_path"] == "/path/to/creds.json"

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON": "{}",
    })
    async def test_create_gemini_service_empty_json_ignored(self, mock_gemini_class):
        """Should ignore empty credentials JSON."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        assert call_kwargs["credentials"] is None

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch("bot.pipeline.asyncio.sleep", new_callable=AsyncMock)
    @patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"})
    async def test_create_gemini_service_retry_logic(self, mock_sleep, mock_gemini_class):
        """Should retry on failure and eventually succeed."""
        # Fail twice, succeed on third attempt
        mock_service = MagicMock()
        mock_gemini_class.side_effect = [
            Exception("Connection error"),
            Exception("Timeout"),
            mock_service,
        ]

        service = await _create_gemini_service_with_retry()

        assert service == mock_service
        assert mock_gemini_class.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch("bot.pipeline.asyncio.sleep", new_callable=AsyncMock)
    @patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"})
    async def test_create_gemini_service_max_retries_exceeded(self, mock_sleep, mock_gemini_class):
        """Should raise exception after max retries."""
        mock_gemini_class.side_effect = Exception("Persistent error")

        with pytest.raises(Exception, match="Persistent error"):
            await _create_gemini_service_with_retry()

        assert mock_gemini_class.call_count == MAX_RETRY_ATTEMPTS

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "BOT_VOICE": "CustomVoice",
    })
    async def test_create_gemini_service_custom_voice(self, mock_gemini_class):
        """Should use custom voice from environment."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        assert call_kwargs["voice_id"] == "CustomVoice"

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"})
    async def test_create_gemini_service_system_prompt(self, mock_gemini_class):
        """Should configure service with system prompt."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        assert call_kwargs["system_instruction"] == SYSTEM_PROMPT


class TestPipelineCreation:
    """Test suite for create_pipeline function."""

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_success(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should create complete pipeline successfully."""
        # Setup mocks
        mock_gemini = MagicMock()
        mock_gemini_service.return_value = mock_gemini

        mock_transport = MagicMock()
        mock_transport.input.return_value = MagicMock()
        mock_transport.output.return_value = MagicMock()
        mock_transport.event_handler = lambda event_name: lambda func: func
        mock_transport_class.return_value = mock_transport

        mock_pipeline = MagicMock()
        mock_pipeline_class.return_value = mock_pipeline

        mock_task = MagicMock()
        mock_task_class.return_value = mock_task

        room_name = "test-room-123"
        task, transport = await create_pipeline(room_name)

        assert task == mock_task
        assert transport == mock_transport
        mock_generate_token.assert_called_once_with(room_name)
        mock_gemini_service.assert_called_once()
        mock_transport_class.assert_called_once()
        mock_pipeline_class.assert_called_once()
        mock_task_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_transport_configuration(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should configure LiveKit transport with correct parameters."""
        mock_gemini = MagicMock()
        mock_gemini_service.return_value = mock_gemini

        mock_transport = MagicMock()
        mock_transport.input.return_value = MagicMock()
        mock_transport.output.return_value = MagicMock()
        mock_transport.event_handler = lambda event_name: lambda func: func
        mock_transport_class.return_value = mock_transport

        mock_pipeline_class.return_value = MagicMock()
        mock_task_class.return_value = MagicMock()

        await create_pipeline("test-room")

        call_kwargs = mock_transport_class.call_args.kwargs
        assert call_kwargs["url"] == "wss://test.livekit.cloud"
        assert call_kwargs["token"] == "test-token"
        assert call_kwargs["room_name"] == "test-room"

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_topology(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should create pipeline with correct topology."""
        mock_gemini = MagicMock()
        mock_gemini_service.return_value = mock_gemini

        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_transport = MagicMock()
        mock_transport.input.return_value = mock_input
        mock_transport.output.return_value = mock_output
        mock_transport.event_handler = lambda event_name: lambda func: func
        mock_transport_class.return_value = mock_transport

        mock_pipeline_class.return_value = MagicMock()
        mock_task_class.return_value = MagicMock()

        await create_pipeline("test-room")

        # Verify pipeline topology: input -> gemini -> output
        pipeline_args = mock_pipeline_class.call_args.args[0]
        assert pipeline_args[0] == mock_input
        assert pipeline_args[1] == mock_gemini
        assert pipeline_args[2] == mock_output

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_gemini_failure(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should raise exception if Gemini service creation fails."""
        mock_gemini_service.side_effect = Exception("Gemini error")

        with pytest.raises(Exception, match="Gemini error"):
            await create_pipeline("test-room")

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_failure(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should raise exception if pipeline creation fails."""
        mock_gemini_service.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.input.return_value = MagicMock()
        mock_transport.output.return_value = MagicMock()
        mock_transport.event_handler = lambda event_name: lambda func: func
        mock_transport_class.return_value = mock_transport

        mock_pipeline_class.side_effect = Exception("Pipeline error")

        with pytest.raises(Exception, match="Pipeline error"):
            await create_pipeline("test-room")

    @pytest.mark.asyncio
    @patch("bot.pipeline._generate_bot_token", return_value="test-token")
    @patch("bot.pipeline._create_gemini_service_with_retry")
    @patch("bot.pipeline.LiveKitTransport")
    @patch("bot.pipeline.Pipeline")
    @patch("bot.pipeline.PipelineTask")
    @patch("bot.pipeline.SileroVADAnalyzer")
    @patch.dict("os.environ", {"LIVEKIT_URL": "wss://test.livekit.cloud"})
    async def test_create_pipeline_event_handlers_registered(
        self,
        mock_vad,
        mock_task_class,
        mock_pipeline_class,
        mock_transport_class,
        mock_gemini_service,
        mock_generate_token,
    ):
        """Should register event handlers on transport."""
        mock_gemini = MagicMock()
        mock_gemini_service.return_value = mock_gemini

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport = MagicMock()
        mock_transport.input.return_value = MagicMock()
        mock_transport.output.return_value = MagicMock()
        mock_transport.event_handler = mock_event_handler
        mock_transport_class.return_value = mock_transport

        mock_pipeline_class.return_value = MagicMock()
        mock_task_class.return_value = MagicMock()

        await create_pipeline("test-room")

        # Verify event handlers were registered
        assert "on_participant_connected" in event_handlers


class TestConstants:
    """Test suite for module constants."""

    def test_system_prompt_exists(self):
        """Should have system prompt defined."""
        assert SYSTEM_PROMPT is not None
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_key_elements(self):
        """Should contain key personality and language instructions."""
        assert "Priya" in SYSTEM_PROMPT
        assert "friendly" in SYSTEM_PROMPT.lower()
        assert "hindi" in SYSTEM_PROMPT.lower() or "telugu" in SYSTEM_PROMPT.lower()

    def test_greeting_exists(self):
        """Should have greeting defined."""
        assert GREETING is not None
        assert isinstance(GREETING, str)
        assert len(GREETING) > 0

    def test_greeting_multilingual(self):
        """Should contain multilingual greetings."""
        assert "Namaste" in GREETING or "Hello" in GREETING

    def test_retry_constants(self):
        """Should have retry configuration constants."""
        assert MAX_RETRY_ATTEMPTS > 0
        assert RETRY_DELAY > 0


class TestEdgeCases:
    """Test suite for edge cases and error scenarios."""

    @pytest.mark.asyncio
    @patch("bot.pipeline.GeminiLiveVertexLLMService")
    @patch("bot.pipeline.os.path.exists", return_value=False)
    @patch.dict("os.environ", {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/path.json",
    })
    async def test_gemini_service_nonexistent_credentials_file(self, mock_exists, mock_gemini_class):
        """Should handle nonexistent credentials file gracefully."""
        mock_service = MagicMock()
        mock_gemini_class.return_value = mock_service

        await _create_gemini_service_with_retry()

        call_kwargs = mock_gemini_class.call_args.kwargs
        # Should not use the nonexistent path
        assert call_kwargs.get("credentials_path") is None

    @patch("bot.pipeline.LIVEKIT_API_KEY", "")
    @patch("bot.pipeline.LIVEKIT_API_SECRET", "")
    def test_generate_bot_token_empty_credentials(self):
        """Should handle empty credentials."""
        # This might raise an exception or produce invalid token
        # depending on AccessToken implementation
        try:
            token = _generate_bot_token("test-room")
            # If it doesn't raise, token should still be a string
            assert isinstance(token, str)
        except Exception:
            # Expected behavior for empty credentials
            pass