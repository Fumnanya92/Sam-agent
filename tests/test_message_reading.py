#!/usr/bin/env python3
"""
Integration test for Sam's message reading functionality.
Simulates user saying "Sam, check my messages" and captures the response.
"""

import asyncio
import threading
import time
import sys
from pathlib import Path

# Add parent directory to path so we can import Sam modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import get_llm_output
from assistant.message_reader import read_latest_whatsapp_message
from memory.memory_manager import load_memory
from memory.temporary_memory import TemporaryMemory
from conversation_state import controller, State
from log.logger import get_logger

logger = get_logger("MessageTest")

class TestUI:
    """Mock UI class to capture Sam's responses during testing"""
    def __init__(self):
        self.logs = []
        self.speech_output = []
        
    def write_log(self, message):
        """Capture log messages"""
        print(f"[UI LOG] {message}")
        self.logs.append(message)
    
    def get_logs(self):
        """Return all captured logs"""
        return self.logs
    
    def clear_logs(self):
        """Clear captured logs"""
        self.logs.clear()
        self.speech_output.clear()

def mock_edge_speak(text, player=None, blocking=True):
    """Mock TTS function to capture what Sam would say"""
    print(f"[SAM SPEECH] {text}")
    if player:
        player.speech_output.append(text)
    
    # Simulate speech timing
    if blocking:
        time.sleep(0.5)  # Short delay to simulate speech

def test_message_reading_workflow():
    """
    Test the complete message reading workflow:
    1. Simulate user input: "Sam, check my messages"
    2. Process through LLM to get intent
    3. Execute message reading function
    4. Capture all outputs and logs
    """
    print("=" * 60)
    print("🧪 TESTING SAM MESSAGE READING WORKFLOW")
    print("=" * 60)
    
    # Create test UI
    test_ui = TestUI()
    
    # Create temporary memory
    temp_memory = TemporaryMemory()
    
    # Mock the edge_speak function
    import tts
    original_edge_speak = tts.edge_speak
    tts.edge_speak = mock_edge_speak
    
    try:
        print("\n📝 Step 1: Simulating user input...")
        user_text = "Sam, check my messages"
        print(f"👤 User says: '{user_text}'")
        
        print("\n🧠 Step 2: Processing through LLM...")
        
        # Load memory for LLM context
        long_term_memory = load_memory()
        
        def minimal_memory_for_prompt(memory: dict) -> dict:
            result = {}
            identity = memory.get("identity", {})
            preferences = memory.get("preferences", {})
            relationships = memory.get("relationships", {})
            
            if "name" in identity:
                result["user_name"] = identity["name"].get("value")
            
            return {k: v for k, v in result.items() if v}
        
        memory_for_prompt = minimal_memory_for_prompt(long_term_memory)
        
        # Get LLM response
        controller.set_state(State.THINKING)
        llm_output = get_llm_output(user_text=user_text, memory_block=memory_for_prompt)
        
        intent = llm_output.get("intent", "chat")
        parameters = llm_output.get("parameters", {})
        response = llm_output.get("text")
        
        print(f"🤖 LLM Response:")
        print(f"   Intent: {intent}")
        print(f"   Parameters: {parameters}")
        print(f"   Text: {response}")
        
        print("\n📱 Step 3: Executing message reading...")
        
        if intent == "read_messages":
            print("✅ Correct intent detected! Executing message reader...")
            
            # Run the message reader in a thread like the real system does
            def run_message_reader():
                try:
                    result = read_latest_whatsapp_message(player=test_ui)
                    print(f"📊 Message reader completed with result: {result}")
                except Exception as e:
                    print(f"❌ Message reader failed with error: {e}")
                    logger.error(f"Message reader test failed: {e}")
            
            # Start the message reader thread
            reader_thread = threading.Thread(target=run_message_reader, daemon=True)
            reader_thread.start()
            
            # Wait for completion (with timeout)
            reader_thread.join(timeout=30)  # 30 second timeout
            
            if reader_thread.is_alive():
                print("⏰ Message reader thread is still running (may be waiting for user interaction)")
            else:
                print("✅ Message reader thread completed")
        
        else:
            print(f"❌ Wrong intent detected: '{intent}' (expected 'read_messages')")
            print("🔍 Check the LLM prompt configuration")
        
        print("\n📊 Step 4: Test Results Summary")
        print("-" * 40)
        
        print(f"🎯 Intent Recognition: {'✅ PASS' if intent == 'read_messages' else '❌ FAIL'}")
        
        ui_logs = test_ui.get_logs()
        speech_outputs = test_ui.speech_output
        
        print(f"📝 UI Log Messages: {len(ui_logs)}")
        for i, log in enumerate(ui_logs):
            print(f"   {i+1}. {log}")
        
        print(f"🗣️ Speech Outputs: {len(speech_outputs)}")
        for i, speech in enumerate(speech_outputs):
            print(f"   {i+1}. {speech}")
        
        # Check for success indicators
        success_indicators = [
            "unread messages" in str(speech_outputs).lower(),
            "message" in str(speech_outputs).lower(),
            len(speech_outputs) > 0
        ]
        
        overall_success = any(success_indicators)
        print(f"\n🏆 Overall Test Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        if overall_success:
            print("✅ Sam successfully processed the message reading request!")
        else:
            print("❌ Sam failed to properly read messages. Check the logs above.")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.error(f"Message reading test exception: {e}")
        
    finally:
        # Restore original edge_speak function
        tts.edge_speak = original_edge_speak
        controller.set_state(State.IDLE)
        
    print("\n" + "=" * 60)
    print("🏁 TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    print("🚀 Starting Sam Message Reading Integration Test")
    print("⚠️  Make sure WhatsApp Desktop is installed and you have unread messages")
    print("⏳ Starting test in 3 seconds...")
    time.sleep(3)
    
    test_message_reading_workflow()