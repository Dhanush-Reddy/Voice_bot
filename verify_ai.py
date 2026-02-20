import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.call_log_service import call_log_service
from models.call_log import CallLogCreateRequest

async def verify():
    print("🚀 Starting AI Intelligence verification...")
    
    mock_transcript = [
        {"role": "agent", "content": "Hello! How can I help you today?"},
        {"role": "user", "content": "I'm looking for a 2BHK apartment in Whitefield."},
        {"role": "agent", "content": "I can certainly help with that. I have a few options available. Would you like to schedule a visit?"},
        {"role": "user", "content": "Yes, please. How about tomorrow at 11 AM?"},
        {"role": "agent", "content": "Perfect! I've booked that for you. See you tomorrow!"}
    ]
    
    request = CallLogCreateRequest(
        room_name="test-room",
        agent_id="default",
        duration_seconds=120,
        status="completed",
        transcript=mock_transcript
    )
    
    try:
        print("Generating AI intelligence...")
        summary, outcome = await call_log_service._generate_ai_intelligence(mock_transcript)
        
        print(f"✅ AI Summary: {summary}")
        print(f"✅ AI Outcome: {outcome}")
        
        if summary and outcome:
            print("✨ AI Verification successful!")
        else:
            print("⚠️ AI generated empty results. Check GEMINI_API_KEY.")
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify())
