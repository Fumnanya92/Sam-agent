"""
system/shell_broadcast.py — Real-time shell activity feed.

Any code that runs a subprocess calls notify_shell_cmd() so the user
can see what Sam is doing in the UI output panel and React dashboard.
"""
from __future__ import annotations
import logging

logger = logging.getLogger("sam.shell")

# Optional UI sink — set by main.py after UI starts
_ui_sink = None


def set_ui_sink(ui) -> None:
    """Wire the Tkinter/headless UI so shell activity appears in its output panel."""
    global _ui_sink
    _ui_sink = ui


def notify_shell_cmd(command: str, cwd: str = "", output: str = "") -> None:
    """Broadcast a shell command (and optional truncated output) to the UI."""
    cmd_short = command[:120] + ("…" if len(command) > 120 else "")
    line = f"[shell] $ {cmd_short}"
    if cwd:
        line = f"[shell:{_short_path(cwd)}] $ {cmd_short}"

    logger.info(line)

    # Tkinter / headless UI output panel
    if _ui_sink is not None:
        try:
            _ui_sink.append_output(line, "info")
            if output:
                snippet = output.strip()[:300]
                _ui_sink.append_output(f"  → {snippet}", "info")
        except Exception:
            pass

    # React dashboard via WebSocket
    try:
        from tts import broadcast_to_web
        payload: dict = {"command": cmd_short}
        if cwd:
            payload["cwd"] = _short_path(cwd)
        if output:
            payload["output"] = output.strip()[:300]
        broadcast_to_web("shell_activity", payload)
    except Exception:
        pass


def _short_path(path: str) -> str:
    """Shorten a path to the last two segments for display."""
    import os
    parts = path.replace("\\", "/").rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else path
