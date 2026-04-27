"""
Tutorial Mode Tools — Step-by-step visual guidance on screen.
Ported from Jarvis src/actions/tools/tutorial.ts

Workflow:
  1. Take a screenshot (screen_view.show_screen_from_capture)
  2. Optionally find the element coords (pyautogui.locateOnScreen / OCR)
  3. Call tutorial_step() — dashboard renders annotated screenshot + instruction

Usage:
    from actions.tools.tutorial import tutorial_step
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger("sam.tools.tutorial")

_broadcast: Optional[Callable] = None


def set_broadcast(fn: Callable) -> None:
    """Wire in the WebSocket broadcast function from ws_service."""
    global _broadcast
    _broadcast = fn


async def tutorial_step(
    *,
    tutorial_id: str,
    step_index: int,
    instruction: str,
    total_steps: Optional[int] = None,
    image_base64: Optional[str] = None,
    highlight_x: Optional[int] = None,
    highlight_y: Optional[int] = None,
    highlight_width: Optional[int] = None,
    highlight_height: Optional[int] = None,
    highlight_label: Optional[str] = None,
    complete: bool = False,
) -> str:
    """
    Broadcast one tutorial step to the dashboard.
    The UI renders a card: screenshot + amber highlight box + instruction text.
    TTS narrates the instruction automatically via the dashboard.
    """
    if not tutorial_id or not instruction:
        return "Error: tutorial_id and instruction are required."

    has_highlight = all(v is not None for v in [highlight_x, highlight_y, highlight_width, highlight_height])

    payload: dict = {
        "tutorialId": tutorial_id,
        "stepIndex": step_index,
        "instruction": instruction,
        "complete": complete,
    }
    if total_steps is not None:
        payload["totalSteps"] = total_steps
    if image_base64:
        # Strip data URI prefix if present
        if image_base64.startswith("data:"):
            image_base64 = image_base64.split(",", 1)[-1]
        payload["imageBase64"] = image_base64
    if has_highlight:
        payload["highlight"] = {
            "x": highlight_x,
            "y": highlight_y,
            "width": highlight_width,
            "height": highlight_height,
        }
        if highlight_label:
            payload["highlight"]["label"] = highlight_label

    if _broadcast:
        await _broadcast("tutorial_step", payload)
        return f"Tutorial step {step_index} broadcast to dashboard."

    logger.warning("tutorial_step: broadcast not wired — dashboard not connected")
    return "Tutorial broadcast not available (dashboard not connected)."
