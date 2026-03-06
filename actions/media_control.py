"""
Media control for Sam — YouTube Music + Windows media keys.

Play/pause, next, prev, and volume use Windows virtual media keys.
These work natively with YouTube Music open in any browser tab
because Chrome registers YTM as a Media Session handler.

play_query(query) opens YouTube Music search in the default browser.
No API keys or credentials required.
"""

import ctypes
import time
import webbrowser
from urllib.parse import quote
from log.logger import get_logger

logger = get_logger("MEDIA")

# Windows Virtual Key codes
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_UP        = 0xAF
VK_VOLUME_DOWN      = 0xAE
VK_VOLUME_MUTE      = 0xAD

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002

YTM_BASE = "https://music.youtube.com"


def _press_media_key(vk: int):
    """Send a single media key press via Win32 keybd_event."""
    try:
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.error(f"Media key press failed: {e}")


# ------------------------------------------------------------------ #
# Public controls
# ------------------------------------------------------------------ #

def play_pause() -> str:
    _press_media_key(VK_MEDIA_PLAY_PAUSE)
    return "Play/pause sent to YouTube Music."


def next_track() -> str:
    _press_media_key(VK_MEDIA_NEXT_TRACK)
    return "Skipped to next track."


def previous_track() -> str:
    _press_media_key(VK_MEDIA_PREV_TRACK)
    return "Back to previous track."


def volume_up() -> str:
    _press_media_key(VK_VOLUME_UP)
    return "Volume up."


def volume_down() -> str:
    _press_media_key(VK_VOLUME_DOWN)
    return "Volume down."


def mute_toggle() -> str:
    _press_media_key(VK_VOLUME_MUTE)
    return "Mute toggled."


def play_query(query: str) -> str:
    """
    Open YouTube Music in the default browser with a search for query.
    If query is empty, just opens YouTube Music home.
    """
    try:
        if query and query.strip():
            url = f"{YTM_BASE}/search?q={quote(query.strip())}"
            label = query.strip()
        else:
            url = YTM_BASE
            label = None

        webbrowser.open(url)

        if label:
            return f"Opening YouTube Music search for '{label}'."
        return "Opening YouTube Music."
    except Exception as e:
        logger.error(f"YouTube Music open failed: {e}")
        return "Couldn't open YouTube Music."


def _get_spotify():
    """No longer used — kept as stub so tests referencing it don't break."""
    return None
