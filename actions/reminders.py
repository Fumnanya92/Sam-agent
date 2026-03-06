"""
Reminder / Alarm engine for Sam.

Usage:
    engine = ReminderEngine(speak_fn, ui)
    engine.start()                                # call once at startup
    engine.add("call John", seconds=1200)         # set reminder
    engine.list_reminders() -> list[dict]
    engine.cancel(reminder_id)
    engine.stop()
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from log.logger import get_logger

logger = get_logger("REMINDERS")


class ReminderEngine:
    def __init__(self, speak_fn=None, ui=None):
        self._reminders: dict[str, dict] = {}   # id -> {label, fire_at, done}
        self._lock = threading.Lock()
        self._speak = speak_fn
        self._ui = ui
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self):
        """Start the background tick loop."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ReminderThread")
        self._thread.start()
        logger.info("Reminder engine started")

    def stop(self):
        self._running = False

    def add(self, label: str, seconds: int = 0, minutes: int = 0, hours: int = 0) -> str:
        """
        Schedule a reminder.
        Returns the reminder id.
        """
        total_seconds = seconds + minutes * 60 + hours * 3600
        if total_seconds <= 0:
            total_seconds = 60  # default 1 minute if nothing specified
        fire_at = datetime.now() + timedelta(seconds=total_seconds)
        rid = str(uuid.uuid4())[:8]
        with self._lock:
            self._reminders[rid] = {
                "id": rid,
                "label": label,
                "fire_at": fire_at,
                "done": False,
            }
        logger.info(f"Reminder set: '{label}' fires at {fire_at.strftime('%H:%M:%S')}")
        return rid

    def cancel(self, reminder_id: str) -> bool:
        with self._lock:
            if reminder_id in self._reminders:
                del self._reminders[reminder_id]
                return True
        return False

    def list_reminders(self) -> list:
        with self._lock:
            return [
                {
                    "id": r["id"],
                    "label": r["label"],
                    "fire_at": r["fire_at"].strftime("%H:%M"),
                    "done": r["done"],
                }
                for r in self._reminders.values()
                if not r["done"]
            ]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _loop(self):
        while self._running:
            now = datetime.now()
            to_fire = []
            with self._lock:
                for rid, r in list(self._reminders.items()):
                    if not r["done"] and now >= r["fire_at"]:
                        r["done"] = True
                        to_fire.append(r)
            for r in to_fire:
                self._fire(r)
            time.sleep(1)

    def _fire(self, reminder: dict):
        from system.sound_fx import play_reminder
        play_reminder()
        msg = f"Reminder: {reminder['label']}"
        logger.info(f"Reminder fired: {msg}")
        if self._ui:
            self._ui.write_log(f"⏰ {msg}")
        if self._speak:
            try:
                self._speak(msg, self._ui, blocking=False)
            except Exception as e:
                logger.error(f"Reminder speak failed: {e}")
