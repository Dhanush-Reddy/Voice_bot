"""
ConfigService — Sprint 3: Stateless Bot Runner

Fetches agent configuration from the AgentService with a TTL cache.
This decouples the bot pipeline from hardcoded environment variables,
allowing dynamic per-agent configuration without restarting the server.

Cache strategy:
  - TTL: 60 seconds (configurable via CONFIG_CACHE_TTL_SECONDS env var)
  - On cache miss: fetches from AgentService (in-memory now, Supabase in Sprint 4)
  - Hot-reload: call invalidate(agent_id) to force a fresh fetch on next access
"""

import logging
import time
import os
from typing import Optional

from models.agent import AgentConfig
from services.agent_service import agent_service

logger = logging.getLogger(__name__)

# TTL in seconds — configurable via environment variable
_TTL = int(os.getenv("CONFIG_CACHE_TTL_SECONDS", "60"))


class _CacheEntry:
    """A single cached agent config with an expiry timestamp."""

    __slots__ = ("config", "expires_at")

    def __init__(self, config: AgentConfig, ttl: int) -> None:
        self.config = config
        self.expires_at = time.monotonic() + ttl

    @property
    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class ConfigService:
    """
    Thread-safe (asyncio-safe) agent config cache with TTL and manual invalidation.

    Usage:
        config = await config_service.get(agent_id)
        config_service.invalidate(agent_id)   # force hot-reload
        config_service.invalidate_all()        # flush entire cache
    """

    def __init__(self, ttl: int = _TTL) -> None:
        self._ttl = ttl
        self._cache: dict[str, _CacheEntry] = {}
        logger.info("⚙️  ConfigService initialized (TTL=%ds)", ttl)

    async def get(self, agent_id: Optional[str] = None) -> Optional[AgentConfig]:
        """
        Return the AgentConfig for the given agent_id.

        - If agent_id is None, returns the default agent.
        - Returns None if the agent does not exist.
        - Caches results for self._ttl seconds.
        """
        # Resolve the key — use a sentinel for the default agent
        cache_key = agent_id or "__default__"

        # Cache hit (not expired)
        entry = self._cache.get(cache_key)
        if entry and not entry.is_expired:
            logger.debug("⚡ Config cache HIT for agent=%s", cache_key)
            return entry.config

        # Cache miss — fetch from service
        logger.info("🔄 Config cache MISS for agent=%s — fetching…", cache_key)
        if agent_id:
            config = await agent_service.get_agent(agent_id)
        else:
            config = await agent_service.get_default_agent()

        if config is None:
            logger.warning("⚠️  No config found for agent=%s", cache_key)
            return None

        # Store in cache
        self._cache[cache_key] = _CacheEntry(config, self._ttl)
        logger.info(
            "✅ Config cached for agent=%s (name=%s, voice=%s, ttl=%ds)",
            cache_key,
            config.name,
            config.voice_id,
            self._ttl,
        )
        return config

    def invalidate(self, agent_id: Optional[str] = None) -> None:
        """
        Invalidate the cache entry for a specific agent (hot-reload).
        Pass None to invalidate the default agent cache entry.
        """
        cache_key = agent_id or "__default__"
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info("🔥 Config cache invalidated for agent=%s", cache_key)
        else:
            logger.debug("Config cache: nothing to invalidate for agent=%s", cache_key)

    def invalidate_all(self) -> None:
        """Flush the entire config cache (e.g., after a bulk update)."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("🔥 Config cache flushed (%d entries cleared)", count)

    @property
    def cache_stats(self) -> dict:
        """Return cache statistics for the /api/health endpoint."""
        now = time.monotonic()
        entries = [
            {
                "key": k,
                "expires_in": max(0, round(v.expires_at - now)),
                "expired": v.is_expired,
            }
            for k, v in self._cache.items()
        ]
        return {
            "ttl_seconds": self._ttl,
            "entries": len(entries),
            "details": entries,
        }


# Singleton — import this everywhere
config_service = ConfigService()
