"""
Quick test of WebSocket speech
"""
from speech_to_text_websocket import record_voice

print("Testing WebSocket speech...")
text = record_voice()
print(f"Result: {text}")