import pyperclip


class ReplyController:
    """
    Handles draft confirmation logic.
    """

    def __init__(self):
        self.pending_draft = None
        self.pending_receiver = None

    def set_draft(self, receiver: str, draft_text: str):
        """Set a pending reply draft."""
        self.pending_receiver = receiver
        self.pending_draft = draft_text

    def clear(self):
        """Clear the pending draft."""
        self.pending_draft = None
        self.pending_receiver = None

    def has_pending(self) -> bool:
        """Check if there's a pending draft."""
        return self.pending_draft is not None

    def get_draft(self):
        """Get the current draft info."""
        return {
            "receiver": self.pending_receiver,
            "text": self.pending_draft
        }

    def copy_to_clipboard(self):
        """Copy the pending draft to clipboard."""
        if self.pending_draft:
            try:
                pyperclip.copy(self.pending_draft)
                return True
            except Exception as e:
                print(f"[ERROR] Failed to copy to clipboard: {e}")
                return False
        return False

    def get_confirmation_prompt(self):
        """Get the confirmation prompt for the user."""
        if not self.has_pending():
            return "No pending draft."
        
        return f"""
Sir, here is the proposed reply to {self.pending_receiver}:

"{self.pending_draft}"

Say:
- "Send it" (copies to clipboard for manual pasting)
- "Edit" (to modify the draft)
- "Cancel" (to discard)
"""
