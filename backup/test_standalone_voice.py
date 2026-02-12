#!/usr/bin/env python3
"""
Test script for Sam Standalone Voice Interface
Run this to test the new standalone window (no browser tabs!)
"""

import sys
import os

# Add the project root to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speech_standalone import record_voice_standalone
from log.logger import get_logger

logger = get_logger("TEST_STANDALONE")

def main():
    """Test the standalone voice interface"""
    print("\n" + "="*50)
    print("🎤 Sam Standalone Voice Interface Test")
    print("="*50)
    print("✅ No browser tabs will open!")
    print("✅ Small, compact standalone window")
    print("✅ Built-in Web Speech API")
    print("✅ Real-time WebSocket communication")
    print("-"*50)
    
    try:
        print("🚀 Starting standalone voice interface...")
        print("📝 Speak when the window appears...")
        
        # Test the standalone interface
        result = record_voice_standalone()
        
        print("\n" + "="*50)
        print("🎯 RESULT:")
        if result:
            print(f"✅ Transcription: '{result}'")
        else:
            print("❌ No speech detected or error occurred")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\n👋 Testing cancelled by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Microphone permissions enabled")
        print("2. Using Chrome/Edge browser engine")
        print("3. All dependencies installed (webview, etc.)")

if __name__ == "__main__":
    main()