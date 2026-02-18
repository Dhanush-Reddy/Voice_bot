"""
Pipecat pipeline — BULLETPROOF WebRTC (LiveKit) + Gemini Multimodal Live.

Sprint 3 upgrade: pipeline now accepts a dynamic AgentConfig instead of
reading hardcoded constants from environment variables. This enables
per-agent system prompts, voices, and models without restarting the server.
"""

import os
import asyncio
import logging
import time
from typing import Optional

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.google.gemini_live.llm_vertex import GeminiLiveVertexLLMService, InputParams
from google.genai.types import Modality
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

from models.agent import AgentConfig

load_dotenv()

logger = logging.getLogger(__name__)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").strip().rstrip("/")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()

# Diagnostic log (safe for production)
if LIVEKIT_URL:
    logger.info(
        "📡 LiveKit Config: URL_len=%d, Key_len=%d, Secret_len=%d",
        len(LIVEKIT_URL), len(LIVEKIT_API_KEY), len(LIVEKIT_API_SECRET),
    )

# Configuration constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0          # seconds
GEMINI_TIMEOUT = 30.0      # seconds
STARTUP_GRACE_PERIOD = 0.2 # seconds

# ---------------------------------------------------------------------------
# Default fallback prompt — used only when no AgentConfig is found
# ---------------------------------------------------------------------------
_DEFAULT_SYSTEM_PROMPT = """\
You are Priya, a real person working as a friendly customer assistant at a business in India.
You are NOT an AI. Never ever say "as an AI", "I'm a language model", or "I'm an assistant."
You are a human named Priya having a natural phone conversation.

PERSONALITY:
- Warm, friendly, confident, and caring. Like a helpful friend, not a call center script.
- You laugh occasionally ("haha"), use natural reactions
- You think out loud briefly like real humans do
- Sometimes pause mid-sentence naturally with "umm" or fillers
- Show empathy and be warm in greetings and goodbyes

LANGUAGE RULES — MULTILINGUAL SUPPORT (7 LANGUAGES):
- Default to English but seamlessly match the user's language.
- Support English, Hindi, Telugu, Tamil, Kannada, Malayalam, and Japanese.
- If user speaks a mix (e.g., Tamlish, Kanglish, Hinglish), respond in that mixed style.
- Understand Indian accents perfectly — never ask "could you repeat that" due to accent.

RESPONSE STYLE:
- Keep responses EXTREMELY SHORT: 1-2 sentences max.
- React BEFORE answering with natural sounds: "Oh!", "Hmm", "Haan", "Sari"
- Use contractions always: "I'll", "that's", "don't"
- End responses with a natural check-in: "Aur kuch?" / "Anything else?" / "Inke emaina?"
"""

_DEFAULT_GREETING = "Hello! Namaste! Namaskaram! Vanakkam! Namaskara! Konnichiwa! Nenu Priya. How can I help you today?"
_DEFAULT_VOICE = "Aoede"
_DEFAULT_MODEL = "gemini-2.0-flash-live-001"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_bot_token(room_name: str, bot_name: str = "priya-bot") -> str:
    """Generate a LiveKit access token for the bot participant."""
    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(bot_name)
        .with_name(bot_name)
        .with_grants(VideoGrants(room_join=True, room=room_name))
    )
    return token.to_jwt()


async def _create_gemini_service(
    system_prompt: str,
    voice_id: str,
    model: str,
) -> GeminiLiveVertexLLMService:
    """
    Create a Gemini Live service with retry logic.

    Accepts dynamic system_prompt, voice_id, and model so each agent
    can have its own personality and configuration.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.info("🧠 Gemini connection attempt %d/%d…", attempt, MAX_RETRY_ATTEMPTS)

            creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if creds_json and (creds_json.strip() == "{}" or not creds_json.strip()):
                creds_json = None

            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and not os.path.exists(creds_path):
                logger.warning("⚠️ Credentials file NOT FOUND: %s", creds_path)
                creds_path = None

            location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
            logger.info(
                "🧠 Service: location=%s, project=%s, voice=%s, model=%s",
                location,
                os.getenv("GOOGLE_CLOUD_PROJECT"),
                voice_id,
                model,
            )

            service = GeminiLiveVertexLLMService(
                project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=location,
                credentials=creds_json,
                credentials_path=creds_path if not creds_json else None,
                model=model,
                system_instruction=system_prompt,
                voice_id=voice_id,
                params=InputParams(
                    response_modalities=[Modality.AUDIO, Modality.TEXT],
                ),
            )

            logger.info("✅ Gemini service created (voice=%s, model=%s)", voice_id, model)
            return service

        except Exception as exc:
            last_error = exc
            logger.warning("⚠️ Gemini attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRY_ATTEMPTS:
                logger.info("⏳ Waiting %.1fs before retry…", RETRY_DELAY)
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error("❌ All %d Gemini attempts failed", MAX_RETRY_ATTEMPTS)

    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_pipeline(
    room_name: str,
    agent_config: Optional[AgentConfig] = None,
) -> tuple[PipelineTask, LiveKitTransport]:
    """
    Build and return the Pipecat pipeline task.

    Args:
        room_name:    The LiveKit room to join.
        agent_config: Dynamic agent configuration fetched from ConfigService.
                      Falls back to the hardcoded default if None.

    Returns:
        (PipelineTask, LiveKitTransport) ready to run.
    """
    start_time = time.time()

    # ── Resolve config ──────────────────────────────────────────────────────
    if agent_config:
        system_prompt = agent_config.system_prompt
        voice_id      = agent_config.voice_id
        model         = agent_config.model
        first_message = agent_config.first_message or _DEFAULT_GREETING
        bot_name      = f"agent-{agent_config.id[:8]}"
        logger.info(
            "🤖 Using dynamic config: agent=%s name=%s voice=%s model=%s",
            agent_config.id, agent_config.name, voice_id, model,
        )
    else:
        system_prompt = _DEFAULT_SYSTEM_PROMPT
        voice_id      = os.getenv("BOT_VOICE", _DEFAULT_VOICE)
        model         = os.getenv("BOT_MODEL", _DEFAULT_MODEL)
        first_message = _DEFAULT_GREETING
        bot_name      = "priya-bot"
        logger.info("🤖 Using default fallback config (no agent_config provided)")

    logger.info("🚀 Creating pipeline for room: %s", room_name)

    # ── Bot token ───────────────────────────────────────────────────────────
    bot_token = _generate_bot_token(room_name, bot_name)

    # ── Transport ───────────────────────────────────────────────────────────
    logger.info("🔧 Setting up LiveKit transport…")
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=bot_token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.7,
                    start_secs=0.2,
                    stop_secs=0.5,
                    min_volume=agent_config.vad_min_volume if agent_config else 0.15,
                )
            ),
        ),
    )
    logger.info("✅ LiveKit transport configured")

    # ── Gemini service ──────────────────────────────────────────────────────
    gemini_live_service = await _create_gemini_service(system_prompt, voice_id, model)

    # ── Pipeline ────────────────────────────────────────────────────────────
    logger.info("🔧 Creating pipeline…")
    try:
        pipeline = Pipeline([transport.input(), gemini_live_service, transport.output()])
        logger.info("✅ Pipeline created")
    except Exception as exc:
        logger.error("❌ Failed to create pipeline: %s", exc)
        raise

    # ── Task ────────────────────────────────────────────────────────────────
    logger.info("🔧 Creating pipeline task…")
    try:
        task = PipelineTask(
            pipeline,
            params=PipelineParams(allow_interruptions=True, enable_metrics=True),
        )
        logger.info("✅ Pipeline task created")
    except Exception as exc:
        logger.error("❌ Failed to create pipeline task: %s", exc)
        raise

    setup_ms = (time.time() - start_time) * 1000
    logger.info("⚡ Pipeline ready in %.0fms for room %s", setup_ms, room_name)

    # ── Event handlers ──────────────────────────────────────────────────────
    output_transport = transport.output()

    @output_transport.event_handler("on_bot_started_speaking")
    async def on_bot_started_speaking() -> None:
        logger.debug("🗣️ Bot STARTED speaking")

    @output_transport.event_handler("on_bot_stopped_speaking")
    async def on_bot_stopped_speaking() -> None:
        logger.debug("🤐 Bot STOPPED speaking")

    @gemini_live_service.event_handler("on_error")
    async def on_llm_error(service: GeminiLiveVertexLLMService, error: Exception) -> None:
        logger.error("❌ Gemini LLM Error: %s", error)

    # ── Greeting on participant join ─────────────────────────────────────────
    greeting_sent = False

    @transport.event_handler("on_participant_connected")
    async def on_user_joined(transport: LiveKitTransport, participant: object) -> None:
        nonlocal greeting_sent

        try:
            identity = participant.identity if hasattr(participant, "identity") else str(participant)
        except Exception:
            identity = str(participant)

        logger.info("[GREETING] Participant connected: %s", identity)

        # Skip bot's own connection event
        if identity == bot_name:
            logger.info("[GREETING] Skipping bot self-connection")
            return

        if greeting_sent:
            logger.info("[GREETING] Greeting already sent, skipping")
            return

        greeting_sent = True
        logger.info("👤 User joined room %s — waiting %.1fs for stability…", room_name, STARTUP_GRACE_PERIOD)
        await asyncio.sleep(STARTUP_GRACE_PERIOD)

        for attempt in range(1, 4):
            try:
                logger.info("🎤 Sending greeting (attempt %d)…", attempt)
                await gemini_live_service.push_frame(TextFrame(text=first_message))
                logger.info("✅ Greeting sent on attempt %d", attempt)
                break
            except Exception as exc:
                logger.error("❌ Greeting attempt %d failed: %s", attempt, exc)
                if attempt < 3:
                    await asyncio.sleep(0.5)
                else:
                    logger.error("❌ All greeting attempts failed")

    return task, transport
