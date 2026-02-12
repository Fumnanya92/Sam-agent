from enum import Enum
import threading

# Initialize logging
from log.logger import get_logger, log_state_change
logger = get_logger("STATE")

class State(Enum):
    IDLE = 0
    LISTENING = 1
    THINKING = 2
    SPEAKING = 3

class ConversationController:
    def __init__(self):
        self.state = State.IDLE
        self.lock = threading.Lock()

    def set_state(self, new_state: State):
        with self.lock:
            old_state = self.state
            self.state = new_state
            if old_state != new_state:
                log_state_change(logger, old_state.name, new_state.name)

    def get_state(self):
        with self.lock:
            return self.state

    def is_speaking(self):
        return self.get_state() == State.SPEAKING

    def is_listening(self):
        return self.get_state() == State.LISTENING

# Module-level singleton controller for easy import across modules
controller = ConversationController()
