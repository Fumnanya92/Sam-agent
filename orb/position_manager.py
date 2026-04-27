"""
orb/position_manager.py — Save and restore the orb's desktop position.

Position is stored in ~/.sam/orb_position.json so it persists across restarts.
Falls back to bottom-right corner when no saved position exists.
"""

import json
import os
from pathlib import Path


_SAM_DIR = Path.home() / ".sam"
_POSITION_FILE = _SAM_DIR / "orb_position.json"

# Full window size used to compute the default bottom-right placement.
# Window = 120 base + 2×50 margin = 220 px; use 230 to add a 10 px buffer.
_WIN_SIZE = 230


def save_position(x: int, y: int) -> None:
    """Persist orb position to ~/.sam/orb_position.json."""
    try:
        _SAM_DIR.mkdir(parents=True, exist_ok=True)
        with open(_POSITION_FILE, "w", encoding="utf-8") as fh:
            json.dump({"x": x, "y": y}, fh)
    except OSError:
        pass  # Non-fatal — position just won't be remembered


def load_position(screen_width: int = 1920, screen_height: int = 1080) -> tuple[int, int]:
    """
    Return the saved (x, y) orb position.

    Falls back to (screen_right - 230, screen_bottom - 230) when no file exists
    or the file cannot be parsed.  The 230 offset accounts for the full window
    size (120 base + 100 margin) plus a 10 px buffer so the orb is never
    clipped at the screen edge.
    """
    default_x = screen_width - _WIN_SIZE
    default_y = screen_height - _WIN_SIZE

    if not _POSITION_FILE.exists():
        return default_x, default_y

    try:
        with open(_POSITION_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data["x"]), int(data["y"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return default_x, default_y
