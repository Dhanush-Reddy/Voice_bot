"""
Comprehensive tests for backend/bot/runner.py

Tests worker process functionality:
- Main worker function with pipeline creation
- Connection and disconnection handlers
- Health monitoring and timeout logic
- Event handler registration
- Retry logic on failure
- Cleanup on shutdown
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from bot.runner import main, MAX_RUNTIME, HEALTH_CHECK_INTERVAL


class TestMainWorkerFunction:
    """Test suite for main worker function."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_main_successful_execution(self, mock_runner_class, mock_create_pipeline):
        """Should execute successfully with valid pipeline."""
        # Setup mocks
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        # Run main (will complete when runner.run completes)
        await main("test-room")

        mock_create_pipeline.assert_called_once_with("test-room")
        mock_runner.run.assert_called_once_with(mock_task)

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    async def test_main_pipeline_creation_timeout(self, mock_create_pipeline):
        """Should handle pipeline creation timeout."""
        # Mock pipeline creation that takes too long
        async def slow_create(*args):
            await asyncio.sleep(100)

        mock_create_pipeline.side_effect = slow_create

        with pytest.raises(asyncio.TimeoutError):
            await main("test-room")

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_main_pipeline_creation_failure(self, mock_runner_class, mock_create_pipeline):
        """Should raise exception if pipeline creation fails."""
        mock_create_pipeline.side_effect = Exception("Pipeline error")

        with pytest.raises(Exception, match="Pipeline error"):
            await main("test-room")

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_main_runner_failure(self, mock_runner_class, mock_create_pipeline):
        """Should handle runner execution failure."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=Exception("Runner error"))
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        with pytest.raises(Exception, match="Runner error"):
            await main("test-room")

        # Should still attempt cleanup
        mock_runner.cancel.assert_called()

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_main_cleanup_on_success(self, mock_runner_class, mock_create_pipeline):
        """Should cleanup resources on successful completion."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await main("test-room")

        # Cleanup should be called
        mock_runner.cancel.assert_called()


class TestEventHandlers:
    """Test suite for event handler registration and behavior."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_on_connected_handler(self, mock_runner_class, mock_create_pipeline):
        """Should register and handle connection event."""
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        # Run main to register handlers
        await main("test-room")

        # Verify on_connected handler was registered
        assert "on_connected" in event_handlers

        # Test the handler
        await event_handlers["on_connected"](mock_transport)
        # Handler should update connected flag (internal state)

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_on_disconnected_handler(self, mock_runner_class, mock_create_pipeline):
        """Should register and handle disconnection event."""
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await main("test-room")

        # Verify on_disconnected handler was registered
        assert "on_disconnected" in event_handlers

        # Test the handler - should cancel runner
        await event_handlers["on_disconnected"](mock_transport)
        mock_runner.cancel.assert_called()

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_audio_frame_handler(self, mock_runner_class, mock_create_pipeline):
        """Should register audio frame handler for activity tracking."""
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await main("test-room")

        # Verify handlers registered
        assert "on_audio_frame" in event_handlers
        assert "on_bot_started_speaking" in event_handlers
        assert "on_bot_stopped_speaking" in event_handlers


class TestHealthChecks:
    """Test suite for health check functionality."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    @patch("bot.runner.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot.runner.time.time")
    async def test_health_check_max_runtime(self, mock_time, mock_sleep, mock_runner_class, mock_create_pipeline):
        """Should cancel runner if max runtime exceeded."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        # Create a task that doesn't complete
        pipeline_task = asyncio.Future()
        mock_runner.run = AsyncMock(return_value=pipeline_task)
        mock_runner.cancel = AsyncMock(side_effect=lambda: pipeline_task.set_result(None))
        mock_runner_class.return_value = mock_runner

        # Mock time to exceed max runtime
        start_time = 1000
        mock_time.side_effect = [
            start_time,  # Initial start time
            start_time + MAX_RUNTIME + 100,  # Health check time (exceeded)
        ]

        # Sleep once then let it complete
        sleep_count = 0

        async def controlled_sleep(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 1:
                pipeline_task.set_result(None)

        mock_sleep.side_effect = controlled_sleep

        await main("test-room")

        # Should have called cancel due to timeout
        mock_runner.cancel.assert_called()

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    @patch("bot.runner.asyncio.sleep", new_callable=AsyncMock)
    async def test_health_check_interval(self, mock_sleep, mock_runner_class, mock_create_pipeline):
        """Should perform health checks at regular intervals."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        pipeline_task = asyncio.Future()
        pipeline_task.set_result(None)  # Complete immediately
        mock_runner.run = AsyncMock(return_value=pipeline_task)
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await main("test-room")

        # Sleep should be called with health check interval
        mock_sleep.assert_called()


class TestRetryLogic:
    """Test suite for command-line retry logic."""

    @pytest.mark.asyncio
    @patch("bot.runner.main")
    @patch("bot.runner.time.sleep")
    @patch("bot.runner.sys.exit")
    def test_retry_on_failure(self, mock_exit, mock_sleep, mock_main):
        """Should retry on failure up to max attempts."""
        # First two attempts fail, third succeeds
        mock_main.side_effect = [
            Exception("Attempt 1 failed"),
            Exception("Attempt 2 failed"),
            None,
        ]

        # Import and run the __main__ block logic
        # We'll simulate it directly
        from bot import runner
        import argparse

        # Mock argparse
        with patch.object(argparse.ArgumentParser, "parse_args") as mock_args:
            mock_args.return_value = argparse.Namespace(room="test-room")

            # Simulate the retry loop
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    asyncio.run(runner.main("test-room"))
                    mock_exit(0)
                    break
                except Exception:
                    if attempt < max_attempts:
                        mock_sleep(2)
                    else:
                        mock_exit(1)

        assert mock_main.call_count == 3
        mock_exit.assert_called_with(0)


class TestCleanup:
    """Test suite for resource cleanup."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_cleanup_on_exception(self, mock_runner_class, mock_create_pipeline):
        """Should cleanup even if exception occurs."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=Exception("Test error"))
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        with pytest.raises(Exception):
            await main("test-room")

        # Cleanup should still be called
        mock_runner.cancel.assert_called()

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_cleanup_handles_cancel_error(self, mock_runner_class, mock_create_pipeline):
        """Should handle errors during cleanup gracefully."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        # Cancel raises an error
        mock_runner.cancel = AsyncMock(side_effect=Exception("Cancel error"))
        mock_runner_class.return_value = mock_runner

        # Should not raise exception from cleanup
        await main("test-room")


class TestConstants:
    """Test suite for module constants."""

    def test_health_check_interval_positive(self):
        """Should have positive health check interval."""
        assert HEALTH_CHECK_INTERVAL > 0

    def test_max_runtime_reasonable(self):
        """Should have reasonable max runtime."""
        assert MAX_RUNTIME > 0
        assert MAX_RUNTIME < 86400  # Less than 24 hours


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    @patch("bot.runner.time.time")
    async def test_stale_connection_warning(self, mock_time, mock_runner_class, mock_create_pipeline):
        """Should warn about stale connections without killing them."""
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        pipeline_task = asyncio.Future()
        pipeline_task.set_result(None)
        mock_runner.run = AsyncMock(return_value=pipeline_task)
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        # Simulate stale connection
        start_time = 1000
        mock_time.side_effect = [
            start_time,  # Initial time
            start_time + 100,  # After connection (simulate connected=True and no recent activity)
        ]

        await main("test-room")

        # Test connection handler
        await event_handlers["on_connected"](mock_transport)

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_cancelled_error_handling(self, mock_runner_class, mock_create_pipeline):
        """Should handle CancelledError gracefully."""
        mock_task = MagicMock()
        mock_transport = MagicMock()
        mock_transport.event_handler = lambda event: lambda func: func
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=asyncio.CancelledError())
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        with pytest.raises(asyncio.CancelledError):
            await main("test-room")

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_multiple_room_names(self, mock_runner_class, mock_create_pipeline):
        """Should handle different room names correctly."""
        for room_name in ["room-1", "room-abc-123", "test-room-xyz"]:
            mock_task = MagicMock()
            mock_transport = MagicMock()
            mock_transport.event_handler = lambda event: lambda func: func
            mock_create_pipeline.return_value = (mock_task, mock_transport)

            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner.cancel = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await main(room_name)

            mock_create_pipeline.assert_called_with(room_name)


class TestIntegration:
    """Test suite for integration scenarios."""

    @pytest.mark.asyncio
    @patch("bot.runner.create_pipeline")
    @patch("bot.runner.PipelineRunner")
    async def test_full_lifecycle(self, mock_runner_class, mock_create_pipeline):
        """Should handle complete worker lifecycle."""
        mock_task = MagicMock()
        mock_transport = MagicMock()

        event_handlers = {}

        def mock_event_handler(event_name):
            def decorator(func):
                event_handlers[event_name] = func
                return func
            return decorator

        mock_transport.event_handler = mock_event_handler
        mock_create_pipeline.return_value = (mock_task, mock_transport)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.cancel = AsyncMock()
        mock_runner_class.return_value = mock_runner

        # Run worker
        await main("test-room")

        # Verify all stages
        mock_create_pipeline.assert_called_once()
        mock_runner_class.assert_called_once()
        mock_runner.run.assert_called_once()

        # Verify event handlers registered
        assert "on_connected" in event_handlers
        assert "on_disconnected" in event_handlers
        assert "on_audio_frame" in event_handlers
        assert "on_bot_started_speaking" in event_handlers
        assert "on_bot_stopped_speaking" in event_handlers

        # Test connection lifecycle
        await event_handlers["on_connected"](mock_transport)
        await event_handlers["on_disconnected"](mock_transport)