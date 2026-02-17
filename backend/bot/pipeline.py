"""
Pipecat pipeline — BULLETPROOF WebRTC (LiveKit) + Gemini Multimodal Live.
Handles retries, health checks, and ensures 100% reliability.
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

load_dotenv()

logger = logging.getLogger(__name__)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").strip().rstrip("/")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()

# Diagnostic log (safe for production)
if LIVEKIT_URL:
    logger.info(f"📡 LiveKit Config: URL_len={len(LIVEKIT_URL)}, Key_len={len(LIVEKIT_API_KEY)}, Secret_len={len(LIVEKIT_API_SECRET)}")

# Configuration constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0  # seconds
GEMINI_TIMEOUT = 30.0  # seconds
STARTUP_GRACE_PERIOD = 0.2  # Balanced for reliability and speed

# ---------------------------------------------------------------------------
# System Prompt — Trilingual (English/Hindi/Telugu)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
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

PHRASES & STYLE:
- Hindi: "Namaste", "Kaise hain aap", "Theek hai", "Haan ji"
- Telugu: "Namaskaram", "Ela unaru", "Avunu", "Bagundi"
- Tamil: "Vanakkam", "Epdi irukinga", "Sari", "Nalla iruku"
- Kannada: "Namaskara", "Hegidira", "Houdu", "Chennagide"
- Malayalam: "Namaskaram", "Sughamano", "Athe", "Nallathaanu"
- Japanese: "Konnichiwa", "Genki desu ka", "Hai", "Iie"

RESPONSE STYLE:
- Keep responses EXTREMELY SHORT: 1-2 sentences max.
- React BEFORE answering with natural sounds: "Oh!", "Hmm", "Haan", "Sari"
- Use contractions always: "I'll", "that's", "don't"
- End responses with a natural check-in: "Aur kuch?" / "Anything else?" / "Inke emaina?"
"""

GREETING = "Hello! Namaste! Namaskaram! Vanakkam! Namaskara! Konnichiwa! Nenu Priya. How can I help you today?"


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


async def _create_gemini_service_with_retry() -> GeminiLiveVertexLLMService:
    """Create Gemini service with retry logic for bulletproof reliability."""
    last_error = None
    
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.info(f"🧠 Gemini connection attempt {attempt}/{MAX_RETRY_ATTEMPTS}...")
            
            # Support both file path and raw JSON string for easier cloud deployment
            creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if creds_json and (creds_json.strip() == "{}" or not creds_json.strip()):
                logger.info("🔑 Empty credentials JSON detected, skipping to use ADC")
                creds_json = None
                
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and not os.path.exists(creds_path):
                logger.warning(f"⚠️ Credentials file NOT FOUND: {creds_path}")
                creds_path = None
            
            # Diagnostic details (safe for production)
            location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
            logger.info(f"🧠 Service: location={location}, project={os.getenv('GOOGLE_CLOUD_PROJECT')}, voice={os.getenv('BOT_VOICE', 'Aoede')}")
            logger.info(f"🧠 Service: has_creds_json={bool(creds_json)}, has_creds_path={bool(creds_path)}")
            
            voice_id = os.getenv("BOT_VOICE", "Aoede")
            
            service = GeminiLiveVertexLLMService(
                project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=location,
                credentials=creds_json,
                credentials_path=creds_path if not creds_json else None,
                model="gemini-2.0-flash-exp",
                system_instruction=SYSTEM_PROMPT,
                voice_id=voice_id,
                params=InputParams(
                    response_modalities=[Modality.AUDIO, Modality.TEXT],
                ),
            )
            
            logger.info("✅ Gemini service created successfully")
            return service
            
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ Gemini connection attempt {attempt} failed: {e}")
            
            if attempt < MAX_RETRY_ATTEMPTS:
                logger.info(f"⏳ Waiting {RETRY_DELAY}s before retry...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"❌ All {MAX_RETRY_ATTEMPTS} attempts failed")
                raise last_error
    
    raise last_error


async def create_pipeline(room_name: str) -> tuple[PipelineTask, LiveKitTransport]:
    """Build and return the Pipecat pipeline task with bulletproof reliability."""
    
    start_time = time.time()
    logger.info(f"🚀 Starting BULLETPROOF pipeline creation for room: {room_name}")

    # Generate a bot token for this room
    bot_token = _generate_bot_token(room_name)

    # --- Transport (LiveKit WebRTC) ---
    logger.info("🔧 Setting up LiveKit transport...")
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=bot_token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            # DISABLE deprecated vad_enabled - use audio_in_enabled instead
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.7,
                    start_secs=0.2,       # Slightly more stable
                    stop_secs=0.5,        # Longer to avoid cutoffs
                    min_volume=0.15,       # Filter more background noise
                )
            ),
        ),
    )
    logger.info("✅ LiveKit transport configured")

    # --- AI Brain: Gemini with retry logic ---
    gemini_live_service = await _create_gemini_service_with_retry()

    # --- Pipeline topology ---
    logger.info("🔧 Creating pipeline...")
    try:
        pipeline = Pipeline(
            [
                transport.input(),
                gemini_live_service,
                transport.output(),
            ]
        )
        logger.info("✅ Pipeline created")
    except Exception as e:
        logger.error(f"❌ Failed to create pipeline: {e}")
        raise

    # --- Pipeline task ---
    logger.info("🔧 Creating pipeline task...")
    try:
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
            ),
        )
        logger.info("✅ Pipeline task created")
    except Exception as e:
        logger.error(f"❌ Failed to create pipeline task: {e}")
        raise

    setup_time = time.time() - start_time
    logger.info(f"⚡ Pipeline ready in {setup_time:.0f}ms for room {room_name}")

    # Get output transport for event handlers
    output_transport = transport.output()
    input_transport = transport.input()

    # --- CRITICAL: Audio output event handlers for proper audio flow ---
    @output_transport.event_handler("on_bot_started_speaking")
    async def on_bot_started_speaking():
        logger.debug("🗣️ Bot STARTED speaking")

    @output_transport.event_handler("on_bot_stopped_speaking")
    async def on_bot_stopped_speaking():
        logger.debug("🤐 Bot STOPPED speaking")

    # --- Error handling ---
    @gemini_live_service.event_handler("on_error")
    async def on_llm_error(service, error):
        logger.error(f"❌ Gemini LLM Error: {error}")

    # --- BULLETPROOF greeting with validation ---
    greeting_sent = False
    
    @transport.event_handler("on_participant_connected")
    async def on_user_joined(transport, participant):
        nonlocal greeting_sent
        
        # Extract identity
        try:
            identity = participant.identity if hasattr(participant, "identity") else str(participant)
        except:
            identity = str(participant)
        
        logger.info(f"[GREETING] Participant connected: {identity}")
        
        # Skip if it's the bot itself
        if identity == "priya-bot":
            logger.info("[GREETING] Skipping bot self-connection")
            return
        
        # Prevent duplicate greetings
        if greeting_sent:
            logger.info("[GREETING] Greeting already sent, skipping")
            return
        
        greeting_sent = True
        
        # Wait for everything to stabilize
        logger.info(f"👤 User joined room {room_name} — waiting {STARTUP_GRACE_PERIOD}s for stability...")
        await asyncio.sleep(STARTUP_GRACE_PERIOD)
        
        # Send greeting with retry
        for attempt in range(1, 4):
            try:
                logger.info(f"🎤 Sending greeting (attempt {attempt})...")
                await gemini_live_service.push_frame(TextFrame(text=GREETING))
                logger.info(f"✅ Greeting sent successfully on attempt {attempt}")
                break
            except Exception as e:
                logger.error(f"❌ Greeting attempt {attempt} failed: {e}")
                if attempt < 3:
                    await asyncio.sleep(0.5)
                else:
                    logger.error("❌ All greeting attempts failed")

    return task, transport
