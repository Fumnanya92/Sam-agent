"""
actions/workspace.py — Google Workspace integration via the official gws CLI.

Wraps `gws` (https://github.com/googleworkspace/cli) for Calendar and Gmail.

One-time setup (user runs once):
    npm install -g @googleworkspace/cli
    gws auth setup      # wizard creates a Google Cloud project + enables APIs
    gws auth login      # browser OAuth consent — refresh token stored in OS keyring

After setup, all calls run fully headless.
"""
from __future__ import annotations

import base64
import json
import subprocess
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from typing import Optional

from log.logger import get_logger

logger = get_logger("WORKSPACE")


# ── helpers ──────────────────────────────────────────────────────────────────

def _gws(*args, timeout: int = 10) -> dict:
    """
    Run a gws command and return parsed JSON output.
    Raises FileNotFoundError if gws is not installed.
    Raises RuntimeError if the command fails.
    """
    cmd = ["gws"] + list(args)
    logger.debug(f"gws: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gws exited {result.returncode}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _format_time(dt_str: str) -> str:
    """Convert ISO datetime string to a natural spoken time like '2:30 PM'."""
    if not dt_str:
        return "unknown time"
    try:
        # All-day events have date-only strings
        if "T" not in dt_str:
            return datetime.fromisoformat(dt_str).strftime("%A %d %B")
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.strftime("%-I:%M %p").lstrip("0") or local.strftime("%I:%M %p")
    except Exception:
        return dt_str[:16]


def _is_gws_available() -> bool:
    try:
        subprocess.run(["gws", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Calendar ─────────────────────────────────────────────────────────────────

def get_today_events() -> list[dict]:
    """
    Return today's calendar events as a list of dicts.
    Each dict has keys: summary, start, end, location (optional).
    """
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = now.replace(hour=23, minute=59, second=59, microsecond=0)

    params = json.dumps({
        "calendarId": "primary",
        "timeMin": day_start.isoformat(),
        "timeMax": day_end.isoformat(),
        "maxResults": 10,
        "singleEvents": True,
        "orderBy": "startTime",
    })
    data = _gws("calendar", "events", "list", "--params", params)
    return data.get("items", [])


def get_next_event() -> Optional[dict]:
    """Return the next upcoming calendar event (within the next 24 hours)."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=24)
    params = json.dumps({
        "calendarId": "primary",
        "timeMin": now.isoformat(),
        "timeMax": future.isoformat(),
        "maxResults": 1,
        "singleEvents": True,
        "orderBy": "startTime",
    })
    data = _gws("calendar", "events", "list", "--params", params)
    items = data.get("items", [])
    return items[0] if items else None


def format_events_spoken(events: list[dict]) -> str:
    """Convert an event list to a natural spoken summary."""
    if not events:
        return "Nothing on the calendar today."
    lines = []
    for e in events[:5]:
        start_raw = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
        time_str = _format_time(start_raw)
        summary = e.get("summary", "Untitled event")
        location = e.get("location", "")
        if location:
            lines.append(f"{summary} at {time_str}, {location}")
        else:
            lines.append(f"{summary} at {time_str}")
    if len(lines) == 1:
        return f"One thing on the calendar today: {lines[0]}."
    joined = ", then ".join(lines[:-1]) + f", and {lines[-1]}"
    return f"Today: {joined}."


# ── Gmail ────────────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str) -> str:
    """
    Send an email via Gmail using gws.
    Returns a spoken-ready result string.
    """
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject or "(no subject)"
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    params   = json.dumps({"userId": "me"})
    body_json = json.dumps({"raw": raw})

    try:
        _gws("gmail", "users", "messages", "send",
             "--params", params, "--json", body_json, timeout=15)
        return f"Email sent to {to}."
    except RuntimeError as e:
        return f"Couldn't send the email: {e}"
    except FileNotFoundError:
        return "gws CLI is not installed. Run: npm install -g @googleworkspace/cli"


def create_draft(to: str, subject: str, body: str) -> str:
    """
    Create a Gmail draft (does not send).
    Returns a spoken-ready result string.
    """
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject or "(no subject)"
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    params    = json.dumps({"userId": "me"})
    body_json = json.dumps({"message": {"raw": raw}})

    try:
        _gws("gmail", "users", "drafts", "create",
             "--params", params, "--json", body_json, timeout=15)
        return f"Draft saved — email to {to} ready to review."
    except RuntimeError as e:
        return f"Couldn't create the draft: {e}"
    except FileNotFoundError:
        return "gws CLI is not installed. Run: npm install -g @googleworkspace/cli"
