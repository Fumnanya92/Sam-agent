#!/usr/bin/env python3
"""
Quick test runner for Sam's message reading functionality.
Run this to quickly test if message reading is working.
"""

import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def quick_test():
    """Run a quick test of message reading without detailed logging"""
    print("🔍 Quick Message Reading Test")
    print("-" * 30)
    
    try:
        from assistant.message_reader import read_latest_whatsapp_message
        from log.logger import get_logger
        
        logger = get_logger("QuickTest")
        
        class SimpleUI:
            def __init__(self):
                self.messages = []
            
            def write_log(self, message):
                self.messages.append(message)
                print(f"📱 {message}")
            
            def start_speaking(self):
                """Required by TTS system"""
                pass
                
            def stop_speaking(self):
                """Required by TTS system"""
                pass
        
        test_ui = SimpleUI()
        
        print("🚀 Running message reader...")
        start_time = time.time()
        
        result = read_latest_whatsapp_message(player=test_ui)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n📊 Results:")
        print(f"   ⏱️  Duration: {duration:.2f} seconds")
        print(f"   ✅ Success: {result}")
        print(f"   📝 Messages captured: {len(test_ui.messages)}")
        
        if result:
            print("🎉 Test PASSED - Message reading worked!")
        else:
            print("❌ Test FAILED - Check the logs for details")
            
    except Exception as e:
        print(f"💥 Test crashed: {e}")
        return False
    
    return result

def test_llm_intent_recognition():
    """Test if LLM recognizes message reading intent"""
    print("\n🧠 Testing LLM Intent Recognition")
    print("-" * 35)
    
    try:
        from llm import get_llm_output
        
        test_phrases = [
            "Sam, check my messages",
            "Check my messages",
            "Read my messages", 
            "Any new messages?",
            "What messages do I have?",
        ]
        
        for phrase in test_phrases:
            print(f"Testing: '{phrase}'")
            
            try:
                result = get_llm_output(user_text=phrase, memory_block={})
                intent = result.get("intent", "unknown")
                
                if intent == "read_messages":
                    print(f"   ✅ Correctly identified as 'read_messages'")
                else:
                    print(f"   ❌ Incorrectly identified as '{intent}'")
                    
            except Exception as e:
                print(f"   💥 LLM error: {e}")
        
    except Exception as e:
        print(f"💥 LLM test crashed: {e}")

if __name__ == "__main__":
    print("🚀 Sam Message Reading Quick Tests")
    print("=" * 40)
    
    # Test LLM intent recognition first
    test_llm_intent_recognition()
    
    print("\n" + "=" * 40)
    
    # Ask user if they want to run the actual message reading test
    response = input("🤔 Do you want to test actual WhatsApp message reading? (y/n): ").lower().strip()
    
    if response in ['y', 'yes']:
        print("\n⚠️  Make sure:")
        print("   📱 WhatsApp Desktop is open")
        print("   💬 You have unread messages")
        print("   🖱️  You won't move the mouse during the test")
        
        input("\nPress Enter when ready...")
        
        quick_test()
    else:
        print("Skipping WhatsApp test.")
    
    print("\n🏁 Quick tests completed!")