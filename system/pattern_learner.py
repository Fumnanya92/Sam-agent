"""
pattern_learner.py — Lightweight behavioral pattern tracker.

Observes which apps the user opens and when, then:
  - Detects a stable morning routine (same core apps for 3+ days)
  - Surfaces a "prepare workspace?" suggestion once the pattern is stable
  - Tracks focus session lengths and surfaces a productivity insight
  - Persists a rolling 14-day log to memory/patterns.json

All data stays on the local machine. No external calls.
"""
import json
import threading
from collections import Counter
from datetime import datetime, date
from pathlib import Path
from typing import Optional

PATTERNS_FILE = Path(__file__).resolve().parent.parent / "memory" / "patterns.json"

# Apps opened within this many minutes of first use each day count as "morning routine"
MORNING_WINDOW_MINUTES = 15
# Need this many consistent days before suggesting a workspace
MIN_DAYS_TO_LEARN = 3

# Human-friendly display names
_FRIENDLY: dict[str, str] = {
    "code.exe":        "VS Code",
    "chrome.exe":      "Chrome",
    "msedge.exe":      "Edge",
    "whatsapp.exe":    "WhatsApp",
    "slack.exe":       "Slack",
    "firefox.exe":     "Firefox",
    "explorer.exe":    "File Explorer",
    "notepad.exe":     "Notepad",
    "outlook.exe":     "Outlook",
    "spotify.exe":     "Spotify",
    "discord.exe":     "Discord",
    "teams.exe":       "Teams",
}


def _friendly(process: str) -> str:
    return _FRIENDLY.get(process.lower(), process.replace(".exe", "").title())


class PatternLearner:
    """
    Thread-safe singleton consumed by PresenceEngine.

    Usage:
        learner = PatternLearner()
        learner.record_app("code.exe")           # call on every app switch
        learner.record_focus_session(90.5)       # call when a coding session ends
        suggestion = learner.get_morning_suggestion()   # None or a string
        insight    = learner.get_productivity_insight() # None or a string
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict = self._load()
        self._session_start: Optional[datetime] = None
        # Flag: morning suggestion already shown today
        self._morning_shown_today: Optional[str] = None  # stores today's date str

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_app(self, app: str):
        """Record that the user switched to `app` (process name, lowercase)."""
        if not app or app in ("", "unknown", "idle"):
            return

        now = datetime.now()
        today = date.today().isoformat()

        # Initialise daily session clock
        if self._session_start is None or self._session_start.date() < date.today():
            self._session_start = now

        minutes_since_start = (now - self._session_start).total_seconds() / 60

        with self._lock:
            if minutes_since_start <= MORNING_WINDOW_MINUTES:
                days: dict = self._data.setdefault("morning_sequences", {})
                seq: list = days.setdefault(today, [])
                if app not in seq:
                    seq.append(app)
                self._trim_old_days("morning_sequences")

            self._save()

    def record_focus_session(self, minutes: float):
        """Record a completed focus session (call when VS Code closes)."""
        if minutes < 5:
            return  # ignore tiny sessions
        hour = datetime.now().hour
        with self._lock:
            sessions: list = self._data.setdefault("focus_sessions", [])
            sessions.append({
                "hour":    hour,
                "minutes": round(minutes, 1),
                "date":    date.today().isoformat(),
            })
            # Keep rolling 90-session window
            if len(sessions) > 90:
                self._data["focus_sessions"] = sessions[-90:]
            self._save()

    def get_morning_suggestion(self) -> Optional[str]:
        """
        If a stable morning routine is detected and hasn't been shown today,
        return a suggestion string. Otherwise return None.
        """
        today = date.today().isoformat()
        if self._morning_shown_today == today:
            return None  # already surfaced today

        routine = self._detect_morning_routine()
        if routine is None:
            return None

        self._morning_shown_today = today
        names = [_friendly(a) for a in routine[:4]]
        joined = ", ".join(names[:-1]) + (" and " + names[-1] if len(names) > 1 else names[0])
        return f"I've noticed you usually open {joined} first thing. Want me to prepare your workspace?"

    def get_productivity_insight(self) -> Optional[str]:
        """Return a personal analytics insight if enough data exists."""
        with self._lock:
            sessions: list = self._data.get("focus_sessions", [])

        if len(sessions) < 5:
            return None

        # Group by hour of day — find the hour with most cumulative focus minutes
        hour_counts: Counter = Counter()
        for s in sessions[-30:]:
            hour_counts[s.get("hour", 0)] += s.get("minutes", 0)

        if not hour_counts:
            return None

        peak_hour, peak_mins = hour_counts.most_common(1)[0]
        label = f"{peak_hour}:00–{(peak_hour + 1):02d}:00"
        return f"Your deepest focus tends to be around {label}, averaging {int(peak_mins / min(30, len(sessions)))} min per session."

    def morning_routine_apps(self) -> list[str]:
        """Return the detected routine app list (empty list if not stable yet)."""
        return self._detect_morning_routine() or []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_morning_routine(self) -> Optional[list]:
        """
        Return apps that appear in the morning sequence for ≥50% of the last
        7 recorded days (minimum MIN_DAYS_TO_LEARN days required).
        """
        with self._lock:
            sequences: dict = self._data.get("morning_sequences", {})

        if len(sequences) < MIN_DAYS_TO_LEARN:
            return None

        recent = sorted(sequences.keys())[-7:]
        app_freq: Counter = Counter()
        for day in recent:
            for app in sequences[day]:
                app_freq[app] += 1

        threshold = max(MIN_DAYS_TO_LEARN, int(len(recent) * 0.5))
        routine = [app for app, count in app_freq.most_common() if count >= threshold]
        return routine if len(routine) >= 2 else None

    def _trim_old_days(self, key: str):
        """Keep only the most recent 14 days in a date-keyed dict."""
        d: dict = self._data.get(key, {})
        for old_key in sorted(d.keys())[:-14]:
            del d[old_key]

    def _load(self) -> dict:
        try:
            if PATTERNS_FILE.exists():
                return json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
            PATTERNS_FILE.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
