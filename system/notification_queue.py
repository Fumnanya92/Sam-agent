"""
system/notification_queue.py — Pending notification queue for Sam.

Background tasks (reminders, proactive reasoner, presence engine, morning
briefing, task completions) enqueue messages here instead of calling
edge_speak directly.  A single drainer in the ai_loop speaks them only when
Sam is idle, so they never interrupt an active conversation.

Usage:
    from system.notification_queue import notification_queue
    notification_queue.enqueue("Your reminder: stand up.", source="reminder")
"""

import queue
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PendingNotification:
    message: str
    source: str = "background"   # 'reminder' | 'proactive' | 'presence' | 'briefing' | 'task'
    priority: int = 0            # higher = delivered first when batching
    urgent: bool = False         # if True, the drainer will not add a natural prefix


class NotificationQueue:
    """Thread-safe queue of pending notifications for Sam to deliver conversationally."""

    def __init__(self) -> None:
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = 0            # tie-breaker so dataclasses don't need __lt__
        self._lock = threading.Lock()

    def enqueue(
        self,
        message: str,
        source: str = "background",
        priority: int = 0,
        urgent: bool = False,
    ) -> None:
        """Add a notification.  Silently drops empty messages."""
        msg = (message or "").strip()
        if not msg:
            return
        with self._lock:
            self._seq += 1
            # PriorityQueue is min-heap; negate priority so higher priority → lower number
            self._queue.put((-priority, self._seq, PendingNotification(
                message=msg,
                source=source,
                priority=priority,
                urgent=urgent,
            )))

    def drain(self) -> list[PendingNotification]:
        """Remove and return all pending notifications (highest priority first)."""
        items: list[PendingNotification] = []
        try:
            while True:
                _, _, notif = self._queue.get_nowait()
                items.append(notif)
        except queue.Empty:
            pass
        return items

    def has_pending(self) -> bool:
        return not self._queue.empty()

    def size(self) -> int:
        return self._queue.qsize()

    def format_for_speech(self, items: list[PendingNotification]) -> str:
        """
        Wrap queued notifications in natural conversational language.
        Sam sounds like he's mentioning things in passing, not reading a list.
        """
        if not items:
            return ""

        # Separate reminders (urgent, keep exact text) from advisory items
        reminders = [n for n in items if n.source == "reminder"]
        others    = [n for n in items if n.source != "reminder"]

        parts: list[str] = []

        # Reminders first — they're time-sensitive
        for r in reminders:
            parts.append(r.message)

        # Advisory items get a conversational prefix
        if others:
            if len(others) == 1:
                n = others[0]
                if n.urgent:
                    parts.append(n.message)
                elif n.source == "briefing":
                    parts.append(f"Also, here's your morning briefing: {n.message}")
                else:
                    parts.append(f"Oh — by the way, {n.message}")
            else:
                intro = "A few things while we were talking"
                joined = ". Also, ".join(n.message for n in others)
                parts.append(f"{intro}: {joined}.")

        return "  ".join(parts)


# Module-level singleton — import this everywhere
notification_queue = NotificationQueue()
