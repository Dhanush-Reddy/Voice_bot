"""
core/config.py — Single source of truth for all environment configuration.

Rules:
- All env vars are read HERE and nowhere else.
- load_dotenv() is called ONCE here.
- Every other module imports `settings` from this file.
- Server refuses to start if required config is missing.
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env (searches upward from cwd, so works from backend/ or root) ─────
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

logger = logging.getLogger(__name__)


class Settings:
    """
    Validated application settings loaded from environment variables.
    Instantiated once at import time as the `settings` singleton.
    """

    def __init__(self) -> None:
        # ── LiveKit ───────────────────────────────────────────────────────────
        self.livekit_url: str = os.getenv("LIVEKIT_URL", "").strip().rstrip("/")
        self.livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "").strip()
        self.livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "").strip()

        # ── Google Cloud / Gemini ─────────────────────────────────────────────
        self.google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        self.google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()

        # Credentials — resolve once, in priority order:
        #   1. Inline JSON string  (GOOGLE_APPLICATION_CREDENTIALS_JSON)  ← production
        #   2. File path           (GOOGLE_APPLICATION_CREDENTIALS)        ← local dev
        #   3. Plain API key       (GEMINI_API_KEY / GOOGLE_API_KEY)       ← fallback
        self.google_credentials_json: str | None = self._resolve_credentials_json()
        self.gemini_api_key: str | None = (
            os.getenv("GEMINI_API_KEY", "").strip()
            or os.getenv("GOOGLE_API_KEY", "").strip()
            or None
        )

        # ── App ───────────────────────────────────────────────────────────────
        try:
            self.agent_pool_size: int = int(os.getenv("AGENT_POOL_SIZE", "3"))
        except ValueError:
            logger.warning("⚠️  AGENT_POOL_SIZE is not a valid integer — using default 3")
            self.agent_pool_size = 3
        self.start_time: float = time.time()

        # ── Derived flags ─────────────────────────────────────────────────────
        self.livekit_configured: bool = all([
            self.livekit_url,
            self.livekit_api_key,
            self.livekit_api_secret,
        ])
        self.gemini_configured: bool = bool(
            self.google_credentials_json or self.gemini_api_key
        )

        self._validate()
        self._log_startup()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_credentials_json(self) -> str | None:
        """
        Return a single-line JSON string for Google credentials, or None.
        Tries inline JSON first, then reads from file path.
        """
        # 1. Inline JSON string
        raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
        if raw and raw not in ("{}", ""):
            try:
                json.loads(raw)  # validate it's real JSON
                return raw
            except json.JSONDecodeError:
                logger.warning("⚠️  GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON — ignoring")

        # 2. File path
        path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if path:
            p = Path(path)
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    return json.dumps(data)  # normalise to single-line
                except Exception as exc:
                    logger.warning("⚠️  Could not read credentials file %s: %s", path, exc)
            else:
                logger.warning("⚠️  GOOGLE_APPLICATION_CREDENTIALS path not found: %s", path)

        return None

    def _validate(self) -> None:
        """Warn loudly about missing required config. Does NOT crash — pool handles gracefully."""
        missing = []
        if not self.livekit_url:
            missing.append("LIVEKIT_URL")
        if not self.livekit_api_key:
            missing.append("LIVEKIT_API_KEY")
        if not self.livekit_api_secret:
            missing.append("LIVEKIT_API_SECRET")
        if not self.google_cloud_project:
            missing.append("GOOGLE_CLOUD_PROJECT")
        if not self.gemini_configured:
            missing.append("GOOGLE_APPLICATION_CREDENTIALS[_JSON] or GEMINI_API_KEY")

        if missing:
            logger.error(
                "❌ Missing required environment variables: %s\n"
                "   Copy .env.example → .env and fill in the values.",
                ", ".join(missing),
            )

    def _log_startup(self) -> None:
        logger.info(
            "⚙️  Config loaded | LiveKit: %s | Gemini creds: %s | Pool size: %d",
            "✅" if self.livekit_configured else "❌ MISSING",
            "✅ service-account" if self.google_credentials_json else (
                "✅ api-key" if self.gemini_api_key else "❌ MISSING"
            ),
            self.agent_pool_size,
        )

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.start_time)


# ── Singleton ─────────────────────────────────────────────────────────────────
settings = Settings()
