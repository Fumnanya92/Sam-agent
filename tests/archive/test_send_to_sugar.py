"""
Quick test: Send message to Sugar using Sam's send_message API
Tests the same flow that voice commands use
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.send_message import send_message
from memory.temporary_memory import TemporaryMemory

def test_send_to_sugar():
    print("\n" + "="*70)
    print("TEST: Send Message via Sam's API")
    print("="*70)
    
    # Prepare parameters like LLM would provide
    parameters = {
        "receiver": "Sugar",
        "message_text": "hello sugar, how are you. are you awake",
        "platform": "WhatsApp"
    }
    
    print(f"\n[INFO] Calling send_message() with:")
    print(f"  Receiver: {parameters['receiver']}")
    print(f"  Message: {parameters['message_text']}")
    print(f"  Platform: {parameters['platform']}")
    print("\n" + "-"*70)
    
    # Create session memory like main.py does
    session_memory = TemporaryMemory()
    
    # Call Sam's send_message action (same as voice command)
    send_message(
        parameters=parameters,
        player=None,  # No UI for test
        session_memory=session_memory
    )
    
    print("\n" + "="*70)
    print("Test completed - check WhatsApp to verify message was sent")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_send_to_sugar()

