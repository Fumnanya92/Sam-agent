"""
daemon/ws_service.py — WebSocket broadcast manager for Sam's daemon.

Maintains connected clients and fans out typed events to all of them.
Supported event types:
  chat_message, task_event, screen_view, takeover_event,
  tutorial_step, test_result, system_status
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger("sam.ws_service")

SUPPORTED_EVENT_TYPES = {
    "chat_message",
    "task_event",
    "screen_view",
    "takeover_event",
    "tutorial_step",
    "test_result",
    "system_status",
}


class WebSocketManager:
    """Thread-safe manager that broadcasts events to all connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info(f"[WS] Client connected. Total: {len(self._clients)}")

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket client (called after close or error)."""
        async with self._lock:
            self._clients.discard(ws)
        logger.info(f"[WS] Client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, event_type: str, payload: dict) -> None:
        """
        Send a JSON event to every connected client.

        Silently drops clients that have disconnected mid-flight.
        Logs a warning for unknown event types but sends anyway.
        """
        if event_type not in SUPPORTED_EVENT_TYPES:
            logger.warning(
                f"[WS] Unknown event type '{event_type}'. "
                f"Supported: {sorted(SUPPORTED_EVENT_TYPES)}"
            )

        message = json.dumps({"type": event_type, "payload": payload})

        async with self._lock:
            dead: Set[WebSocket] = set()
            for client in self._clients:
                try:
                    await client.send_text(message)
                except Exception as exc:
                    logger.debug(f"[WS] Send failed ({exc}); removing client.")
                    dead.add(client)
            self._clients -= dead

        if dead:
            logger.info(f"[WS] Removed {len(dead)} dead client(s). Total: {len(self._clients)}")

    @property
    def client_count(self) -> int:
        return len(self._clients)


# Module-level singleton — import this everywhere
manager = WebSocketManager()
