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
from datetime import datetime
from typing import List, Optional, Union, Dict

from livekit.api import AccessToken, VideoGrants
from pipecat.frames.frames import TextFrame, TranscriptionFrame
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame, InputTextRawFrame

from pipecat.services.google import GeminiLiveLLMService, GeminiLiveVertexLLMService
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask

from core.config import settings
from models.agent import AgentConfig
from services.knowledge_service import knowledge_service

logger = logging.getLogger(__name__)

LIVEKIT_URL = settings.livekit_url
LIVEKIT_API_KEY = settings.livekit_api_key
LIVEKIT_API_SECRET = settings.livekit_api_secret

# Diagnostic log (safe for production)
if LIVEKIT_URL:
    logger.info(
        "📡 LiveKit Config: URL_len=%d, Key_len=%d, Secret_len=%d",
        len(LIVEKIT_URL),
        len(LIVEKIT_API_KEY),
        len(LIVEKIT_API_SECRET),
    )

# Configuration constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0  # seconds
GEMINI_TIMEOUT = 30.0  # seconds
STARTUP_GRACE_PERIOD = 2.0  # seconds (increased from 0.2s so user stream opens first)

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
_DEFAULT_VOICE = settings.default_bot_voice
_DEFAULT_MODEL = settings.default_bot_model


# ── Model Mapping ─────────────────────────────────────────────────────────────
# Maps Vertex AI model names to Gemini API names
VERTEX_TO_API_MODEL_MAP: Dict[str, str] = {
    "gemini-2.0-flash-live-001": "gemini-2.0-flash-exp",
    "gemini-2.5-flash-preview-native-audio-dialog": "gemini-2.5-flash-native-audio-preview-12-2025",
}


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
) -> Union[GeminiLiveLLMService, GeminiLiveVertexLLMService]:
    """
    Create a Gemini Live service with retry logic.

    Accepts dynamic system_prompt, voice_id, and model so each agent
    can have its own personality and configuration.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.info(
                "🧠 Gemini connection attempt %d/%d…", attempt, MAX_RETRY_ATTEMPTS
            )

            creds_json = settings.google_credentials_json
            gemini_api_key = settings.gemini_api_key
            location = settings.google_cloud_location

            # ── Choose auth strategy ──────────────────────────────────────────
            # Priority:
            #   1. Vertex AI with service account JSON (production / Render)
            #   2. Gemini API key (local dev — no service account needed)
            use_vertex = bool(creds_json)

            # ── Model Mapping ──────────────────────────────────────────
            # Normalize model names to ensure compatibility with Multimodal Live API
            mapped_model = VERTEX_TO_API_MODEL_MAP.get(model, model)
            
            # 💡 SPECIAL FALLBACK FOR VERTEX AI
            if use_vertex and "2.0" in mapped_model:
                # If 2.0 is not supported in the project yet for Live API, try the verified native-audio ID
                vertex_model = "google/gemini-live-2.5-flash-native-audio"
            else:
                vertex_model = mapped_model

            if use_vertex:
                logger.info(
                    "🧠 Vertex AI: location=%s, project=%s, voice=%s, model=%s",
                    location,
                    settings.google_cloud_project,
                    voice_id,
                    vertex_model,
                )
                service = GeminiLiveVertexLLMService(
                    project_id=settings.google_cloud_project,
                    location=location,
                    credentials=creds_json,
                    model=vertex_model,
                    system_instruction=system_prompt,
                    voice_id=voice_id,
                    transcribe_user=True,
                    transcribe_assistant=True,
                )
            elif gemini_api_key:
                # Gemini API (AI Studio) requires 'models/' prefix
                api_studio_model = mapped_model
                if not api_studio_model.startswith("models/"):
                    api_studio_model = f"models/{api_studio_model}"

                logger.info(
                    "🧠 Gemini API key: voice=%s, model=%s",
                    voice_id,
                    api_studio_model,
                )
                service = GeminiLiveLLMService(
                    api_key=gemini_api_key,
                    model=api_studio_model,
                    system_instruction=system_prompt,
                    voice_id=voice_id,
                    transcribe_user=True,
                    transcribe_assistant=True,
                )
            else:
                raise RuntimeError(
                    "No Gemini credentials found. Set GEMINI_API_KEY (local dev) or "
                    "GOOGLE_APPLICATION_CREDENTIALS_JSON (production)."
                )

            logger.info(
                "✅ Gemini service created (voice=%s, model=%s)", voice_id, model
            )
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
    transcript_data: Optional[list] = None,
) -> tuple[PipelineTask, LiveKitTransport]:
    """
    Build and return the Pipecat pipeline task.

    Args:
        room_name:    The LiveKit room to join.
        agent_config: Dynamic agent configuration fetched from ConfigService.
                      Falls back to the hardcoded default if None.
        transcript_data: A list to collect (role, content, timestamp) tuples.
    """
    start_time = time.time()

    # ── Resolve config ──────────────────────────────────────────────────────
    if agent_config:
        system_prompt = agent_config.system_prompt
        voice_id = agent_config.voice_id
        model = agent_config.model
        first_message = agent_config.first_message or _DEFAULT_GREETING
        bot_name = f"agent-{agent_config.id[:8]}"
        logger.info(
            "🤖 Using dynamic config: agent=%s name=%s voice=%s model=%s",
            agent_config.id,
            agent_config.name,
            voice_id,
            model,
        )
    else:
        system_prompt = _DEFAULT_SYSTEM_PROMPT
        voice_id = _DEFAULT_VOICE
        model = _DEFAULT_MODEL
        first_message = _DEFAULT_GREETING
        bot_name = "priya-bot"
        logger.info("🤖 Using default fallback config (no agent_config provided)")

    # ── RAG: inject knowledge base context into system prompt ───────────────
    if agent_config and agent_config.id:
        try:
            rag_results = await knowledge_service.search(
                agent_id=agent_config.id,
                query="general context about the business",
                top_k=3,
            )
            if rag_results:
                rag_context = "\n\n".join(
                    f"[Source: {r.filename or 'document'}]\n{r.text}"
                    for r in rag_results
                )
                system_prompt = (
                    system_prompt
                    + "\n\n---\nKNOWLEDGE BASE (use this to answer questions accurately):\n"
                    + rag_context
                )
                logger.info(
                    "📚 RAG: injected %d chunks into system prompt for agent=%s",
                    len(rag_results),
                    agent_config.id,
                )
        except Exception as rag_err:
            logger.warning("⚠️  RAG injection failed (continuing without): %s", rag_err)

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

    # ── Custom Transcript Collector ─────────────────────────────────────────
    class TranscriptCollector(FrameProcessor):
        def __init__(self, transcript_list):
            super().__init__()
            self._transcript_list = transcript_list

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            # ⚠️ CRITICAL: Must call super() to track StartFrame/Pipeline state
            await super().process_frame(frame, direction)

            if isinstance(frame, TranscriptionFrame):
                self._transcript_list.append({
                    "role": "user",
                    "content": frame.text,
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.debug(f"📝 User transcript collected: {frame.text}")
            elif isinstance(frame, TextFrame):
                # Only collect assistant text if it has content
                if frame.text.strip():
                    self._transcript_list.append({
                        "role": "assistant",
                        "content": frame.text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.debug(f"📝 Assistant transcript collected: {frame.text}")

            await self.push_frame(frame, direction)

    transcript_collector = TranscriptCollector(transcript_data)

    # ── Pipeline ────────────────────────────────────────────────────────────
    logger.info("🔧 Creating pipeline…")
    try:
        pipeline = Pipeline(
            [
                transport.input(),
                gemini_live_service,
                transcript_collector,
                transport.output()
            ]
        )
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

    @output_transport.event_handler("on_started_speaking")
    async def on_started_speaking() -> None:
        logger.info("🗣️ Bot STARTED speaking")

    @output_transport.event_handler("on_stopped_speaking")
    async def on_stopped_speaking() -> None:
        logger.info("🤐 Bot STOPPED speaking")

    @gemini_live_service.event_handler("on_error")
    async def on_llm_error(
        service: Union[GeminiLiveLLMService, GeminiLiveVertexLLMService], error: Exception
    ) -> None:
        logger.error("❌ Gemini LLM Error: %s", error)

    # ── Greeting on participant join ─────────────────────────────────────────
    greeting_sent = False

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport: LiveKitTransport, participant: object) -> None:
        nonlocal greeting_sent

        try:
            identity = (
                participant.identity
                if hasattr(participant, "identity")
                else str(participant)
            )
        except Exception:
            identity = str(participant)

        logger.info("[GREETING] First participant joined: %s", identity)

        # Skip bot's own connection event
        if identity == bot_name:
            logger.info("[GREETING] Skipping bot self-connection")
            return

        if greeting_sent:
            logger.info("[GREETING] Greeting already sent, skipping")
            return

        greeting_sent = True
        logger.info(
            "👤 User joined room %s — waiting %.1fs for stability…",
            room_name,
            STARTUP_GRACE_PERIOD,
        )
        await asyncio.sleep(STARTUP_GRACE_PERIOD)

        for attempt in range(1, 4):
            try:
                logger.info("🎤 Sending greeting (attempt %d)…", attempt)
                # We prompt the Gemini Live model to *say* the greeting since there is no separate TTS
                prompt = f"Please introduce yourself by saying exactly: {first_message}"
                await gemini_live_service.push_frame(InputTextRawFrame(text=prompt))
                logger.info("✅ Greeting sent on attempt %d", attempt)
                break
            except Exception as exc:
                logger.error("❌ Greeting attempt %d failed: %s", attempt, exc)
                if attempt < 3:
                    await asyncio.sleep(0.5)
                else:
                    logger.error("❌ All greeting attempts failed")

    return task, transport
