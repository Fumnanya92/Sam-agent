"""
system/notifier.py — Windows toast notification helper

Call notify(title, body) from any thread. Falls back silently if winotify
is not installed or Windows notifications are unavailable.

Install: pip install winotify
"""
from __future__ import annotations
import threading
from pathlib import Path

_SAM_ROOT = Path(__file__).resolve().parent.parent

def _icon_path() -> str:
    """Return path to Sam's icon if it exists, else empty string."""
    candidates = [
        _SAM_ROOT / "static" / "sam_icon.png",
        _SAM_ROOT / "static" / "icon.png",
        _SAM_ROOT / "static" / "favicon.ico",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ""


def notify(title: str, body: str, duration: str = "short") -> None:
    """
    Send a Windows toast notification. Non-blocking — fires in a daemon thread.

    Args:
        title:    Notification title.
        body:     Notification body text.
        duration: 'short' (5s) or 'long' (25s).
    """
    def _fire():
        try:
            from winotify import Notification, audio  # type: ignore
            toast = Notification(
                app_id="Sam AI",
                title=title,
                msg=body,
                duration=duration,
                icon=_icon_path(),
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
        except ImportError:
            # winotify not installed — silent fallback
            try:
                import ctypes
                # MessageBox as last-resort visual alert (no sound, non-blocking)
                # Only used if winotify unavailable
                pass
            except Exception:
                pass
        except Exception:
            pass  # Never crash Sam over a notification failure

    threading.Thread(target=_fire, daemon=True).start()


def notify_task_done(task_name: str, detail: str = "") -> None:
    """Convenience: notify that an agent task completed successfully."""
    body = detail if detail else f"{task_name} finished."
    notify(f"✓ {task_name}", body)


def notify_task_error(task_name: str, error: str = "") -> None:
    """Convenience: notify that an agent task failed."""
    body = error[:120] if error else f"{task_name} encountered an error."
    notify(f"✗ {task_name}", body, duration="long")


def notify_sam_needs_input(question: str) -> None:
    """Sam needs something from the user — send a prominent toast."""
    notify("Sam needs your input", question[:200], duration="long")
