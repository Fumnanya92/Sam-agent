"""
Clipboard read action for Sam.
Reads whatever text is currently on the Windows clipboard.
"""
import pyperclip


def read_clipboard() -> str:
    """Return current clipboard text, or empty string if nothing / non-text."""
    try:
        text = pyperclip.paste()
        return text.strip() if text else ""
    except Exception:
        return ""
