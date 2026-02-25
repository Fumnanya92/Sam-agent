import re
import os
from automation.whatsapp_dom import get_latest_message_from_open_chat
from automation.reply_drafter import generate_reply
from automation.reply_controller import ReplyController
from tts import edge_speak
from conversation_state import controller, State


SENSITIVE_PATTERNS = [
    r"\btransfer\b",
    r"\bmoney\b",
    r"\bbank\b",
    r"\baccount\b",
    r"\bpayment\b",
    r"\burgent\b",
    r"\bcredit\b",
    r"\bdebit\b",
    r"\bloan\b",
    r"\bpin\b",
]


class WhatsAppAIEngine:

    def __init__(self):
        self.reply_controller = ReplyController()

    # ---------------------------------------------------------
    # PUBLIC ENTRY - DRAFT & CONFIRM SYSTEM
    # ---------------------------------------------------------

    def handle_reply_flow(self, player=None):
        """Read latest message and generate a draft reply."""
        message = get_latest_message_from_open_chat()

        if not message:
            self._speak("Sir, I could not detect a message.", player)
            return

        if message["direction"] == "outgoing":
            self._speak("Sir, the latest message was sent by you.", player)
            return

        sender = message.get("sender")
        text = message.get("text")

        if not text:
            self._speak("Sir, the last message is media content.", player)
            return

        # Read the incoming message aloud
        self._speak(f"Sir, {sender} says: {text}", player)

        # Generate AI draft
        draft = generate_reply(text, sender)
        
        if not draft or "error" in draft.lower():
            self._speak("Sir, I could not generate a reply.", player)
            return

        # Store the draft
        self.reply_controller.set_draft(sender, draft)

        # Check if sensitive
        if self._is_sensitive(text) or self._is_sensitive(draft):
            self._speak(
                f"Sir, this appears to be a sensitive message. Here is my proposed reply: {draft}. Say 'send it', 'edit', or 'cancel'.",
                player,
            )
        else:
            self._speak(
                f"Sir, here is my proposed reply to {sender}: {draft}. Say 'send it', 'edit', or 'cancel'.",
                player,
            )

    # ---------------------------------------------------------
    # CONFIRMATION HANDLERS
    # ---------------------------------------------------------

    def confirm_send(self, player=None):
        """Handle 'send it' command - copies draft to clipboard."""
        if not self.reply_controller.has_pending():
            self._speak("Sir, there is no pending reply to send.", player)
            return

        draft_info = self.reply_controller.get_draft()
        success = self.reply_controller.copy_to_clipboard()
        
        if success:
            self._speak(f"Sir, reply to {draft_info['receiver']} copied to clipboard. You may paste and send manually.", player)
            self.reply_controller.clear()
        else:
            self._speak("Sir, I failed to copy the reply to clipboard.", player)

    def cancel_reply(self, player=None):
        """Handle 'cancel' command - discards the draft."""
        if not self.reply_controller.has_pending():
            self._speak("Sir, there is no pending reply to cancel.", player)
            return

        self.reply_controller.clear()
        self._speak("Understood, Sir. Draft discarded.", player)

    def edit_reply(self, new_text: str, player=None):
        """Handle 'edit' command - allows user to modify the draft."""
        if not self.reply_controller.has_pending():
            self._speak("Sir, there is no pending reply to edit.", player)
            return

        draft_info = self.reply_controller.get_draft()
        
        if new_text and new_text.strip():
            # Update with new text
            self.reply_controller.set_draft(draft_info['receiver'], new_text.strip())
            self._speak(f"Sir, reply updated to: {new_text.strip()}. Say 'send it' or 'cancel'.", player)
        else:
            # Just re-announce the current draft
            self._speak(f"Sir, current draft is: {draft_info['text']}. Please provide new text, or say 'send it' or 'cancel'.", player)

    def get_current_draft(self, player=None):
        """Get info about current pending draft."""
        if not self.reply_controller.has_pending():
            self._speak("Sir, there is no pending reply.", player)
            return None

        draft_info = self.reply_controller.get_draft()
        self._speak(f"Sir, pending reply to {draft_info['receiver']}: {draft_info['text']}", player)
        return draft_info

    # ---------------------------------------------------------
    # SENSITIVE DETECTION
    # ---------------------------------------------------------

    def _is_sensitive(self, text):
        """Check if message contains sensitive patterns."""
        text = text.lower()
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    # ---------------------------------------------------------
    # VOICE WRAPPER
    # ---------------------------------------------------------

    def _speak(self, text, player=None):
        """Speak text using TTS."""
        if player:
            player.write_log(text)

        controller.set_state(State.SPEAKING)
        edge_speak(text, player, blocking=True)
        controller.set_state(State.IDLE)
