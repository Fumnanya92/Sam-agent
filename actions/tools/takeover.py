"""
Takeover Mode Tools — Sam assumes autonomous control of a task with live narration.
Ported from Jarvis src/actions/tools/takeover.ts

Workflow:
  1. takeover_begin(task) → banner appears in dashboard
  2. takeover_narrate(step) → banner updates before each action
  3. takeover_end(summary) → banner disappears

Usage:
    from actions.tools.takeover import takeover_begin, takeover_narrate, takeover_end
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger("sam.tools.takeover")

_broadcast: Optional[Callable] = None


def set_broadcast(fn: Callable) -> None:
    """Wire in the WebSocket broadcast function from ws_service."""
    global _broadcast
    _broadcast = fn


async def takeover_begin(task: str) -> str:
    """
    Signal that Sam is beginning autonomous control.
    Shows a takeover banner in the dashboard.
    """
    if not task:
        return "Error: task description is required."

    if _broadcast:
        await _broadcast("takeover_event", {
            "state": "active",
            "task": task,
            "stepNarration": "Initializing...",
        })
        logger.info(f"Takeover began: {task}")
    return f'Takeover mode active. Autonomously completing: "{task}". Narrating each step.'


async def takeover_narrate(step: str) -> str:
    """
    Narrate the next action during takeover. Call before every desktop/browser action.
    """
    if not step:
        return "Error: step narration is required."

    if _broadcast:
        await _broadcast("takeover_event", {
            "state": "active",
            "stepNarration": step,
        })
    return step


async def takeover_end(summary: str = "") -> str:
    """
    Signal that the autonomous task is complete. Dashboard banner disappears.
    """
    if _broadcast:
        await _broadcast("takeover_event", {
            "state": "ended",
            "stepNarration": summary or "Task complete.",
        })
        logger.info("Takeover ended.")
    return f"Takeover complete. {summary}"


async def takeover_cancel(reason: str = "") -> str:
    """Cancel an in-progress takeover (e.g. on error or user interrupt)."""
    if _broadcast:
        await _broadcast("takeover_event", {
            "state": "cancelled",
            "stepNarration": reason or "Cancelled.",
        })
    return f"Takeover cancelled. {reason}"
