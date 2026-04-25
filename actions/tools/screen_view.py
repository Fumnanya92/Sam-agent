"""
Screen View Tool — Broadcast screenshots to the Sam dashboard.
Ported from Jarvis src/actions/tools/screen-view.ts

Usage:
    from actions.tools.screen_view import show_screen, close_screen_view
    show_screen(image_base64="...", label="Chrome — Gmail")
"""

import asyncio
import base64
import logging
from typing import Callable, Optional

logger = logging.getLogger("sam.tools.screen_view")

SCREEN_VIEW_ID = "sam-screen-view"

# Injected at startup by daemon/main.py via set_broadcast()
_broadcast: Optional[Callable] = None


def set_broadcast(fn: Callable) -> None:
    """Wire in the WebSocket broadcast function from ws_service."""
    global _broadcast
    _broadcast = fn


async def show_screen(image_base64: str, label: str = "") -> str:
    """
    Broadcast a screenshot to the dashboard live panel.
    image_base64: base64-encoded PNG/JPEG
    label: short description e.g. "Chrome — Gmail"
    """
    if not image_base64 or len(image_base64) < 10:
        return "Error: image_base64 is required and must be valid base64 data."

    # Validate base64 — strip data URI prefix if present
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[-1]

    if _broadcast:
        await _broadcast("screen_view", {
            "viewId": SCREEN_VIEW_ID,
            "imageBase64": image_base64,
            "active": True,
            "label": label or "",
        })
        return f"Screen view broadcast to dashboard{f' ({label})' if label else ''}."

    logger.warning("show_screen: broadcast not wired — dashboard not connected")
    return "Screen view not available (dashboard not connected)."


async def close_screen_view() -> str:
    """Close the live screen panel in the dashboard."""
    if _broadcast:
        await _broadcast("screen_view", {
            "viewId": SCREEN_VIEW_ID,
            "imageBase64": "",
            "active": False,
        })
    return "Screen view panel closed."


async def show_screen_from_capture() -> str:
    """
    Convenience: capture the current screen via Sam's mss and broadcast it.
    Requires: mss, Pillow (for PNG encoding)
    """
    try:
        import mss
        import mss.tools
        from io import BytesIO

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

        b64 = base64.b64encode(png_bytes).decode()
        return await show_screen(b64, label="Desktop")
    except ImportError:
        return "Error: mss is required for screen capture. pip install mss"
    except Exception as e:
        return f"Error capturing screen: {e}"
