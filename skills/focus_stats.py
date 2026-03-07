"""
skills/focus_stats.py — Personal productivity analytics skill.

Surfaces insights from PatternLearner:
  - Peak focus hour
  - Average session length
  - Total coding time this week
  - Most-used morning apps

Trigger phrases:
  "how productive am I"  /  "focus stats"  /  "productivity report"  /
  "how long did I code"  /  "my stats"
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Any

from system.pattern_learner import PatternLearner


def _run(parameters: dict, ui: Any, **ctx) -> str:
    try:
        pl = PatternLearner()
        sessions = pl._data.get("focus_sessions", [])

        if len(sessions) < 2:
            return (
                "I don't have enough data yet — "
                "keep working and I'll learn your patterns over time."
            )

        # --- Total this week ---
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_sessions = [
            s for s in sessions
            if s.get("date", "") >= week_start.isoformat()
        ]
        week_total = sum(s.get("minutes", 0) for s in week_sessions)

        # --- Today ---
        today_sessions = [s for s in sessions if s.get("date") == today.isoformat()]
        today_total = sum(s.get("minutes", 0) for s in today_sessions)

        # --- Peak hour ---
        from collections import Counter
        hour_map: Counter = Counter()
        for s in sessions[-30:]:
            hour_map[s.get("hour", 0)] += s.get("minutes", 0)
        peak_hour, peak_mins = hour_map.most_common(1)[0] if hour_map else (9, 0)
        peak_label = f"{peak_hour}:00"

        # --- Average session ---
        avg = sum(s.get("minutes", 0) for s in sessions) / len(sessions)

        parts = []
        if today_total:
            parts.append(f"Today you've been focused for {int(today_total)} minutes.")
        if week_total:
            parts.append(f"This week: {int(week_total)} minutes across {len(week_sessions)} session{'s' if len(week_sessions) != 1 else ''}.")
        parts.append(f"Your peak focus hour is around {peak_label}.")
        parts.append(f"Average session length: {int(avg)} minutes.")

        return " ".join(parts)

    except Exception as e:
        return f"Couldn't load focus stats right now: {e}"


SKILL_MANIFEST = {
    "name": "focus_stats",
    "description": "Personal productivity analytics from focus session history",
    "intents": ["focus_stats", "productivity_report", "my_stats", "coding_stats"],
    "trigger_phrases": [
        "focus stats",
        "productivity report",
        "how productive am I",
        "my stats",
        "how long did I code today",
        "how much did I work today",
        "show me my focus stats",
        "coding stats",
    ],
    "run": _run,
}
