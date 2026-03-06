"""
skills/pomodoro.py — Focus timer skill.

Starts a 25-minute work timer (or custom duration) backed by ReminderEngine.
After each work block, Sam suggests a 5-minute break.

Trigger phrases:
  "start pomodoro"  /  "25 minute timer"  /  "focus timer"  /
  "pomodoro"  /  "start a focus session"
"""

from __future__ import annotations
from typing import Any


def _run(parameters: dict, ui: Any, **ctx) -> str:
    reminder_engine = ctx.get("reminder_engine")
    minutes = int(parameters.get("minutes") or 25)

    if reminder_engine is None:
        # Fall back: just speak a timer message — user handles the rest
        return (
            f"Pomodoro set for {minutes} minutes. "
            "Stay focused — I'll be here when it's done."
        )

    # Queue the work-block reminder
    reminder_engine.add(
        f"Pomodoro: {minutes}-minute block complete. Take a 5-minute break.",
        minutes=minutes,
    )

    # Queue the break-end reminder
    reminder_engine.add(
        "Break over. Ready for the next focus block?",
        minutes=minutes + 5,
    )

    return (
        f"Pomodoro started. {minutes} minutes of focus, then a 5-minute break. "
        "I'll let you know when it's done."
    )


SKILL_MANIFEST = {
    "name": "pomodoro",
    "description": "25-minute focus timer with automatic break reminder",
    "intents": ["pomodoro", "start_pomodoro", "focus_timer"],
    "trigger_phrases": [
        "start pomodoro",
        "pomodoro timer",
        "25 minute timer",
        "focus timer",
        "start a focus session",
        "start pomodoro session",
    ],
    "run": _run,
}
