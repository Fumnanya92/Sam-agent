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

# Orb size used to compute the default bottom-right placement.
_ORB_SIZE = 120


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

    Falls back to (screen_right - 150, screen_bottom - 200) when no file exists
    or the file cannot be parsed.
    """
    default_x = screen_width - _ORB_SIZE - 150
    default_y = screen_height - _ORB_SIZE - 200

    if not _POSITION_FILE.exists():
        return default_x, default_y

    try:
        with open(_POSITION_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data["x"]), int(data["y"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return default_x, default_y
