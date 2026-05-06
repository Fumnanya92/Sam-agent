"""
system/watchers/system_watcher.py — Watch Windows Application Event Log for errors.

Polls every 60 seconds. Emits "system_error" events for new application crashes
(Error/Critical level) that occurred since last check.

Requires: pywin32 (win32evtlog). Silently skips if unavailable.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger("sam.watchers.system")

_POLL_INTERVAL = 60  # seconds


class SystemErrorWatcher:
    def __init__(self):
        self._last_check: datetime | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._available: bool | None = None  # cached availability check

    def start(self):
        if self._running:
            return
        self._running = True
        self._last_check = datetime.now() - timedelta(seconds=_POLL_INTERVAL)
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="SystemErrorWatcher")
        self._thread.start()
        logger.info("[SystemErrorWatcher] Started")

    def stop(self):
        self._running = False

    def _is_available(self) -> bool:
        if self._available is None:
            try:
                import win32evtlog  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
                logger.debug("[SystemErrorWatcher] pywin32 not available — skipping")
        return self._available

    def _poll_loop(self):
        while self._running:
            try:
                if self._is_available():
                    self._check_event_log()
            except Exception as e:
                logger.debug(f"[SystemErrorWatcher] Poll error: {e}")
            time.sleep(_POLL_INTERVAL)

    def _check_event_log(self):
        try:
            import win32evtlog
            import win32con

            handle = win32evtlog.OpenEventLog(None, "Application")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            events = win32evtlog.ReadEventLog(handle, flags, 0)
            win32evtlog.CloseEventLog(handle)

            now = datetime.now()
            cutoff = self._last_check or (now - timedelta(seconds=_POLL_INTERVAL))
            self._last_check = now

            for ev in (events or []):
                try:
                    ev_time = ev.TimeGenerated
                    if isinstance(ev_time, datetime) and ev_time < cutoff:
                        break
                    # Only Error (1) and Critical (2) event types
                    if ev.EventType not in (win32con.EVENTLOG_ERROR_TYPE,):
                        continue
                    source = str(ev.SourceName or "")
                    msg = str(ev.StringInserts or "")[:200] if ev.StringInserts else ""
                    self._emit(source, msg)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[SystemErrorWatcher] Event log read failed: {e}")

    def _emit(self, source: str, message: str):
        try:
            from system.event_bus import bus
            bus.emit("system_error", source="system_watcher", data={
                "source": source,
                "message": message,
            })
            logger.info(f"[SystemErrorWatcher] Error from {source}: {message[:80]}")
        except Exception:
            pass


system_error_watcher = SystemErrorWatcher()
