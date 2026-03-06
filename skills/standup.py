"""
skills/standup.py — Daily standup generator.

Builds a natural-language standup report from:
  - git log (commits from last 24 hours in the last known repo)
  - Sam Notes from today (if any)
  - Focus stats from PatternLearner

Trigger phrases:
  "generate standup"  /  "what did I do today"  /  "standup report"  /
  "daily standup"  /  "summarise my day"
"""

from __future__ import annotations
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


def _run(parameters: dict, ui: Any, **ctx) -> str:
    parts: list[str] = []

    # 1. Git commits from the last 24 hours
    git_context = _get_git_commits()
    if git_context:
        parts.append(git_context)

    # 2. Sam Notes from today
    notes_summary = _get_todays_notes()
    if notes_summary:
        parts.append(notes_summary)

    # 3. Focus stats
    focus_summary = _get_focus_summary(ctx)
    if focus_summary:
        parts.append(focus_summary)

    if not parts:
        return (
            "I couldn't find enough activity to build a standup yet. "
            "Try after you've logged some commits or notes."
        )

    today = date.today().strftime("%A, %B %d")
    return f"Here's your standup for {today}. " + " ".join(parts)


def _get_git_commits() -> str:
    """Return a summary of git commits from the last 24-hour window."""
    try:
        from memory.session_state import load_last_session
        session = load_last_session()
        cwd = (session or {}).get("git_cwd", "")
        if not cwd or not os.path.exists(os.path.join(cwd, ".git")):
            # Try current working directory
            cwd = os.getcwd()
            if not os.path.exists(os.path.join(cwd, ".git")):
                return ""

        result = subprocess.run(
            ["git", "log", "--oneline", "--since=24 hours ago", "--author=HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if not lines:
            return "No commits in the last 24 hours."
        n = len(lines)
        preview = lines[0].split(" ", 1)[-1] if lines else ""
        return (
            f"{n} commit{'s' if n > 1 else ''} pushed — "
            f"most recent: {preview}."
        )
    except Exception:
        return ""


def _get_todays_notes() -> str:
    """Return a note count from today's Sam Notes folders."""
    try:
        from datetime import datetime
        now = datetime.now()
        notes_dir = (
            Path.home() / "Documents" / "Sam Notes"
            / str(now.year) / now.strftime("%B")
        )
        if not notes_dir.exists():
            return ""
        files = list(notes_dir.glob("*.md"))
        if not files:
            return ""
        return f"{len(files)} note file{'s' if len(files) > 1 else ''} updated today in Sam Notes."
    except Exception:
        return ""


def _get_focus_summary(ctx: dict) -> str:
    """Return total focus time from PatternLearner if available."""
    try:
        from system.pattern_learner import PatternLearner
        pl = PatternLearner()
        sessions = pl._data.get("focus_sessions", [])
        today = date.today().isoformat()
        today_sessions = [s for s in sessions if s.get("date") == today]
        if not today_sessions:
            return ""
        total = sum(s.get("minutes", 0) for s in today_sessions)
        return f"Total focused coding time today: {int(total)} minutes."
    except Exception:
        return ""


SKILL_MANIFEST = {
    "name": "standup",
    "description": "Generate a daily standup from git commits, notes, and focus time",
    "intents": ["standup", "daily_standup", "standup_report", "summarise_day"],
    "trigger_phrases": [
        "generate standup",
        "daily standup",
        "standup report",
        "what did I do today",
        "summarise my day",
        "what have I done today",
        "create standup",
    ],
    "run": _run,
}
