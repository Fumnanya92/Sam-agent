"""
system/session_logger.py — Thread-safe session action logger.

Tracks every action Sam takes during a session so a daily report can be
generated at the end of the day. Each entry records the time, intent name,
a human-readable summary, and an outcome string.

Usage:
    from system.session_logger import session_logger
    session_logger.log_action("open_app", "Opened VS Code", "done")
    log = session_logger.get_today_log()
"""
from __future__ import annotations
import json
import threading
from datetime import datetime
from pathlib import Path

_REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "sessions"


class SessionLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._date = datetime.now().strftime("%Y-%m-%d")
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _session_file(self) -> Path:
        return _REPORTS_DIR / f"{self._date}.json"

    def _load(self):
        """Load existing session log for today (handles restarts mid-day)."""
        try:
            path = self._session_file()
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _save(self):
        """Persist current session to disk (called under lock)."""
        try:
            with open(self._session_file(), "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def log_action(self, intent: str, summary: str, outcome: str = "done"):
        """Append an action to today's session log.

        Args:
            intent:  LLM intent name (e.g. 'open_app', 'code_helper').
            summary: Human-readable one-line desc of what happened.
            outcome: 'done' | 'error' | 'cancelled' | 'pending'.
        """
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "intent": intent,
            "summary": summary[:200],
            "outcome": outcome,
        }
        with self._lock:
            # Roll date if midnight passed
            today = datetime.now().strftime("%Y-%m-%d")
            if today != self._date:
                self._date = today
                self._entries = []
            self._entries.append(entry)
            self._save()

    def get_today_log(self) -> list[dict]:
        """Return a copy of today's log entries."""
        with self._lock:
            return list(self._entries)

    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)


session_logger = SessionLogger()
