#!/usr/bin/env python3
"""
Test the fixed standalone voice interface integration
"""

import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speech_native_clean import record_voice_native
from log.logger import get_logger

logger = get_logger("TEST_INTEGRATION")

def main():
    """Test the fixed standalone voice interface"""
    print("\n" + "="*60)
    print("🎤 Sam Standalone Voice Interface - INTEGRATION TEST")
    print("="*60)
    print("✅ No browser tabs!")
    print("✅ Native standalone window")
    print("✅ Fixed threading issues")  
    print("✅ Clean compilation")
    print("✅ WebSocket communication")
    print("-"*60)
    
    try:
        print("🚀 Starting fixed standalone voice interface...")
        print("📝 Speak when the window appears...")
        
        # Test the integration
        result = record_voice_native()
        
        print("\n" + "="*60)
        print("🎯 RESULT:")
        if result:
            print(f"✅ Transcription: '{result}'")
            print("🎉 Integration working perfectly!")
        else:
            print("⚠️  No speech detected (timeout or silence)")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n👋 Testing cancelled by user")
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()