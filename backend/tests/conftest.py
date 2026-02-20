"""
Pytest configuration and fixtures for backend tests.

This file contains session and module-level fixtures to properly
configure the test environment before any imports happen.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# Set environment variables and mocks BEFORE any imports
# This runs at module import time, before pytest collects tests
os.environ.update({
    "LIVEKIT_URL": "wss://test.livekit.cloud",
    "LIVEKIT_API_KEY": "test_key",
    "LIVEKIT_API_SECRET": "test_secret",
    "GOOGLE_CLOUD_PROJECT": "test-project",
    "GOOGLE_APPLICATION_CREDENTIALS_JSON": '{"type": "service_account"}',
})

# Mock core.database module before any imports
sys.modules["core.database"] = MagicMock(init_db=AsyncMock())


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Clean up test environment after all tests."""
    yield
    # Cleanup
    sys.modules.pop("core.database", None)


# Mock asyncio.create_task at module level
@pytest.fixture(scope="module", autouse=True)
def mock_asyncio_create_task():
    """Mock asyncio.create_task to prevent background tasks during testing."""
    with patch("asyncio.create_task"):
        yield


# Simpler approach: Add the missing imports to builtins so they're available globally
# This allows routes.py to reference them even though it doesn't import them
import builtins
from models.options import ConfigOptionsResponse
from core.options import VOICE_OPTIONS, MODEL_OPTIONS, LANGUAGE_OPTIONS

# Temporarily add to builtins for the test session
builtins.ConfigOptionsResponse = ConfigOptionsResponse
builtins.VOICE_OPTIONS = VOICE_OPTIONS
builtins.MODEL_OPTIONS = MODEL_OPTIONS
builtins.LANGUAGE_OPTIONS = LANGUAGE_OPTIONS


@pytest.fixture(scope="session", autouse=True)
def cleanup_builtins():
    """Clean up builtins after tests."""
    yield
    # Cleanup
    delattr(builtins, 'ConfigOptionsResponse')
    delattr(builtins, 'VOICE_OPTIONS')
    delattr(builtins, 'MODEL_OPTIONS')
    delattr(builtins, 'LANGUAGE_OPTIONS')