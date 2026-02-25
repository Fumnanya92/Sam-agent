import time
from tts import edge_speak
from conversation_state import controller, State

# NOTE: This file is now deprecated. 
# The send_message action has been replaced with the draft & confirm system.
# See automation/reply_drafter.py and automation/reply_controller.py

def send_message(parameters: dict, response: str | None = None, player=None, session_memory=None) -> bool:
    """
    DEPRECATED: Direct sending has been removed.
    Sam now uses the draft & confirm system instead.
    """
    
    msg = "Sir, direct message sending has been disabled. I now use the draft and confirmation system for your safety."
    
    if player:
        player.write_log(msg)
    controller.set_state(State.SPEAKING)
    edge_speak(msg, player, blocking=True)
    controller.set_state(State.IDLE)
    
    return False
