from enum import Enum
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# Initialize logging
from log.logger import get_logger, log_state_change
logger = get_logger("STATE")

class State(Enum):
    IDLE = 0
    LISTENING = 1
    THINKING = 2
    SPEAKING = 3


@dataclass
class PendingAction:
    """Stores an action Sam is about to take, pending user confirmation.
    Prevents Sam from forgetting what it was going to do after asking 'shall I proceed?'
    """
    intent: str
    parameters: dict
    description: str       # human-readable description of what Sam will do
    callback: Callable     # the actual action function to run on confirm
    expires_at: float = field(default_factory=lambda: time.time() + 120)


class ConversationController:
    def __init__(self):
        self.state = State.IDLE
        self.lock = threading.Lock()
        self._pending: Optional[PendingAction] = None
        self._muted: bool = False
        self._mode: str = "normal"  # "normal" | "meeting" | "silent"

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

    # ── Pending action (confirmation gate) ───────────────────────────────────

    def set_pending(self, action: PendingAction):
        """Store a pending action. Sam will run it when the user says 'yes'."""
        with self.lock:
            self._pending = action
        logger.debug(f"Pending action stored: '{action.intent}' — '{action.description}'")

    def get_pending(self) -> Optional[PendingAction]:
        """Return the pending action if it hasn't expired. Returns None if expired."""
        with self.lock:
            if self._pending is None:
                return None
            if time.time() > self._pending.expires_at:
                logger.info("Pending action expired — clearing")
                self._pending = None
                return None
            return self._pending

    def clear_pending(self):
        """Clear any stored pending action."""
        with self.lock:
            self._pending = None

    # ── Mute flag ────────────────────────────────────────────────────────────

    def set_muted(self, muted: bool):
        """Mute or unmute Sam's voice. When muted, Sam sends notifications instead."""
        with self.lock:
            self._muted = muted
        logger.info(f"Sam {'muted' if muted else 'unmuted'}")

    def is_muted(self) -> bool:
        with self.lock:
            return self._muted

    # ── Mode ─────────────────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Set Sam's current mode: 'normal' | 'meeting' | 'silent'."""
        with self.lock:
            self._mode = mode
        logger.info(f"Sam mode → {mode}")

    def get_mode(self) -> str:
        with self.lock:
            return self._mode


# Module-level singleton controller for easy import across modules
controller = ConversationController()
