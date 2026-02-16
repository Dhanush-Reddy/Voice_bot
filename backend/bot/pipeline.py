"""
Pipecat pipeline definition — WebRTC (LiveKit) + Gemini Multimodal Live S2S.
Optimized for ultra-low latency, human-like Hinglish conversation.
"""

import os
import asyncio
import logging
import time

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.google.gemini_live import GeminiLiveLLMService
from google.genai.types import HttpOptions
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

load_dotenv()

logger = logging.getLogger(__name__)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# ---------------------------------------------------------------------------
# System Prompt — Ultra-human, Hinglish-native persona
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are Priya, a real person working as a friendly customer assistant at a business in India.
You are NOT an AI. Never ever say "as an AI", "I'm a language model", or "I'm an assistant."
You are a human named Priya having a natural phone conversation.

PERSONALITY:
- Warm, friendly, confident, and caring. Like a helpful friend, not a call center script.
- You laugh occasionally ("haha"), use natural reactions ("oh accha!", "hmm", "arre wah!", "oho!")
- You think out loud briefly ("ek second, sochne do..." / "haan haan, samajh gayi")
- Sometimes pause mid-sentence naturally with "umm" or "toh..." like real humans do
- Show empathy: "oh no, that's frustrating" / "arre, tension mat lo"
- Be warm in greetings and goodbyes

LANGUAGE RULES:
- Default to English but seamlessly switch to Hinglish when the user speaks Hindi or mixes languages
- Understand Indian English accents perfectly — never ask "could you repeat that" due to accent
- Understand Indian slang and filler words: "yaar", "na", "bhai", "accha", "theek hai", "haan", "matlab"
- Use common Hinglish naturally: "Haan sure, main help karti hoon", "Koi baat nahi", "Bilkul!"
- If user speaks pure Hindi, respond in Hindi with some English words mixed in (natural Hinglish)

RESPONSE STYLE — THIS IS CRITICAL:
- Keep responses EXTREMELY SHORT: 1-2 sentences max. Like a real phone call.
- Never give long paragraphs or bullet points — you're on a phone, not writing an email
- React BEFORE answering: "Oh! Accha, toh..." / "Hmm, right right..." / "Haan haan..."
- Use contractions always: "I'll", "that's", "don't", "won't" — never formal English
- If you don't understand, say it naturally: "Sorry, zara dubara bologe?" NOT "Could you please repeat"
- End responses with a natural check-in: "Aur kuch?" / "Makes sense?" / "Theek hai?"
"""

# ---------------------------------------------------------------------------
# Greeting that fires when user joins — instant connection feel
# ---------------------------------------------------------------------------
GREETING = "Hello! Kaise hain aap? Main Priya, aapki kaise help karun?"


def _generate_bot_token(room_name: str) -> str:
    """Generate a LiveKit access token for the bot participant."""
    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("priya-bot")
        .with_name("Priya")
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
    )
    return token.to_jwt()


async def create_pipeline(room_name: str) -> PipelineTask:
    """Build and return the Pipecat pipeline task for a given LiveKit room."""

    start_time = time.time()

    # Generate a bot token for this room
    bot_token = _generate_bot_token(room_name)

    # --- Transport (LiveKit WebRTC) ---
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=bot_token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    stop_secs=0.25,       # 250ms silence = speech done (fast detection)
                    min_volume=0.3,       # sensitive to quiet speech / Indian accents
                )
            ),
        ),
    )

    # --- AI Brain: Gemini Multimodal Live (native S2S, lowest latency) ---
    logger.info("🧠 Initializing Gemini 2.0 Flash service...")
    gemini_live_service = GeminiLiveLLMService(
        api_key=os.getenv("GOOGLE_API_KEY", ""),
        model="gemini-2.0-flash",   # Tier 1 verified model
        system_instruction=SYSTEM_PROMPT,
        voice_id="Puck",            # stable and clear voice
    )

    # --- Pipeline topology ---
    pipeline = Pipeline(
        [
            transport.input(),
            gemini_live_service,
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,  # barge-in support
            enable_metrics=True,
        ),
    )

    setup_time = time.time() - start_time
    logger.info("⚡ Pipeline created in %.0fms for room %s", setup_time * 1000, room_name)

    # --- Barge-in is handled automatically by Gemini Multimodal Live ---
    # when allow_interruptions=True is set in PipelineParams.
    # No manual on_participant_speaking handler needed if it's not supported.
    
    @gemini_live_service.event_handler("on_error")
    async def on_llm_error(service, error):
        logger.error("❌ Gemini LLM Error: %s", error)

    @gemini_live_service.event_handler("on_connected")
    async def on_llm_connected(service):
        logger.info("🟢 Gemini Live WebSocket connected and ready!")

    # --- Instant greeting: bot speaks first when user joins ---
    @transport.event_handler("on_participant_connected")
    async def on_user_joined(transport, participant):
        # args usually (participant,)
        # Check if it's the user and not the bot itself
        if participant.identity == "priya-bot":
            return

        join_time = time.time()
        logger.info("👤 User joined room %s — waiting 1s before greeting", room_name)
        await asyncio.sleep(1.0)
        logger.info("🎤 Sending greeting now...")
        await gemini_live_service.push_frame(TextFrame(text=GREETING))
        greet_time = time.time() - join_time
        logger.info("✅ Greeting dispatched in %.0fms", greet_time * 1000)

    return task, transport
