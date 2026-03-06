"""
session_state.py — persist last work-session context across Sam restarts.

Written by PresenceEngine when a VS Code session ends (or Sam shuts down).
Read by main.py at boot to build a context-aware greeting.
"""
import json
from datetime import datetime
from pathlib import Path

SESSION_PATH = Path(__file__).parent / "session_state.json"


def save_session_state(state: dict) -> None:
    """Persist session context to disk (atomic write)."""
    try:
        SESSION_PATH.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # never crash Sam on a state-save failure


def load_last_session() -> dict | None:
    """
    Return the last session dict or None if no file exists / parse error.

    Expected keys (all optional — always use .get()):
      timestamp, git_project, git_branch, git_cwd,
      uncommitted_count, commit_count,
      session_duration_minutes, build_failures, ended_late
    """
    try:
        if not SESSION_PATH.exists():
            return None
        raw = SESSION_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def is_session_recent(session: dict, max_hours: int = 20) -> bool:
    """
    Return True if the session was saved within the last `max_hours`.
    Prevents Sam from referencing a session from days ago.
    """
    try:
        ts = datetime.fromisoformat(session.get("timestamp", ""))
        delta = datetime.now() - ts
        return delta.total_seconds() < max_hours * 3600
    except Exception:
        return False
