import threading

# Global state to prevent Sam from hearing himself
is_sam_speaking = threading.Event()

# Dictation mode — when True, voice input is typed into the foreground window
_dictation_mode: bool = False


def get_dictation_mode() -> bool:
    return _dictation_mode


def set_dictation_mode(value: bool) -> None:
    global _dictation_mode
    _dictation_mode = value
