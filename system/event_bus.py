"""
system/event_bus.py — Lightweight publish/subscribe event bus.

Events are dicts with at minimum: {"type": str, "source": str, "data": dict, "ts": float}

Usage:
    from system.event_bus import bus

    # Publish
    bus.emit("file_changed", source="file_watcher", data={"path": "/foo/bar.py"})

    # Subscribe
    def on_event(event):
        print(event)
    bus.subscribe("file_changed", on_event)
    bus.subscribe("*", on_event)  # wildcard: all events

    # Unsubscribe
    bus.unsubscribe("file_changed", on_event)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Callable

logger = logging.getLogger("sam.event_bus")


class EventBus:
    """Thread-safe pub/sub bus. Callbacks run on a dedicated delivery thread."""

    def __init__(self):
        self._subs: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        # Delivery queue — keeps callbacks off the emitter's thread
        import queue
        self._queue: queue.Queue = queue.Queue()
        self._delivery_thread = threading.Thread(
            target=self._deliver_loop, daemon=True, name="EventBusDelivery"
        )
        self._delivery_thread.start()

    # ── Public ──────────────────────────────────────────────────────────────

    def emit(self, event_type: str, source: str = "", data: dict | None = None) -> None:
        """Publish an event. Non-blocking — delivery happens asynchronously."""
        event = {
            "type": event_type,
            "source": source,
            "data": data or {},
            "ts": time.time(),
        }
        self._queue.put(event)

    def subscribe(self, event_type: str, callback: Callable[[dict], None]) -> None:
        """Subscribe to events of type `event_type` (or '*' for all)."""
        with self._lock:
            if callback not in self._subs[event_type]:
                self._subs[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            try:
                self._subs[event_type].remove(callback)
            except ValueError:
                pass

    def subscriber_count(self, event_type: str = "") -> int:
        with self._lock:
            if event_type:
                return len(self._subs.get(event_type, []))
            return sum(len(v) for v in self._subs.values())

    # ── Internal ────────────────────────────────────────────────────────────

    def _deliver_loop(self):
        while True:
            try:
                event = self._queue.get(timeout=1)
                self._dispatch(event)
            except Exception:
                pass  # queue.Empty or other transient

    def _dispatch(self, event: dict):
        event_type = event["type"]
        with self._lock:
            targets = (
                list(self._subs.get(event_type, []))
                + list(self._subs.get("*", []))
            )
        for cb in targets:
            try:
                cb(event)
            except Exception as e:
                logger.warning(f"[EventBus] Callback error for '{event_type}': {e}")


# Singleton
bus = EventBus()
