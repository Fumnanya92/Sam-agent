"""
system/watchers/calendar_watcher.py — Emit events 10 minutes before calendar events.

Polls Google Calendar every 5 minutes. When an upcoming event is ≤10 minutes away
and hasn't been notified yet, emits "calendar_event_soon" on the bus.

The bus subscriber (proactive_reasoner or main.py) decides whether to speak or mute.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger("sam.watchers.calendar")

_POLL_INTERVAL = 300   # 5 minutes
_NOTIFY_AHEAD_SECS = 600  # 10 minutes


class CalendarWatcher:
    def __init__(self):
        self._notified: set[str] = set()  # event IDs already notified
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="CalendarWatcher")
        self._thread.start()
        logger.info("[CalendarWatcher] Started")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                self._check_upcoming()
            except Exception as e:
                logger.debug(f"[CalendarWatcher] Poll error: {e}")
            time.sleep(_POLL_INTERVAL)

    def _check_upcoming(self):
        try:
            from actions.workspace import get_today_events, _is_gws_available
            if not _is_gws_available():
                return
            events = get_today_events()
        except Exception:
            return

        now_ts = time.time()
        for ev in (events or []):
            event_id = ev.get("id") or ev.get("summary", "") + str(ev.get("start", ""))
            if event_id in self._notified:
                continue
            start_str = ev.get("start", {})
            if isinstance(start_str, dict):
                start_str = start_str.get("dateTime") or start_str.get("date", "")
            if not start_str:
                continue
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                event_ts = dt.timestamp()
                secs_until = event_ts - now_ts
                if 0 < secs_until <= _NOTIFY_AHEAD_SECS:
                    self._notified.add(event_id)
                    self._emit(ev, int(secs_until))
            except Exception:
                pass

    def _emit(self, event: dict, secs_until: int):
        try:
            from system.event_bus import bus
            mins = secs_until // 60
            bus.emit("calendar_event_soon", source="calendar_watcher", data={
                "summary": event.get("summary", "Meeting"),
                "secs_until": secs_until,
                "minutes_until": mins,
                "event": event,
            })
            logger.info(f"[CalendarWatcher] {event.get('summary')} in {mins} min")
        except Exception:
            pass


calendar_watcher = CalendarWatcher()
