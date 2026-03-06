"""
Global hotkey listener — press Ctrl+Alt+S anywhere to wake Sam.
Uses the `keyboard` library (pip install keyboard).
Falls back silently if not installed or not on Windows.
"""

import threading
import time
from log.logger import get_logger

logger = get_logger("HOTKEY")

DEFAULT_HOTKEY = "ctrl+alt+s"


class HotkeyListener:
    def __init__(self, hotkey: str = DEFAULT_HOTKEY):
        self._hotkey = hotkey
        self._callbacks: list = []
        self._running = False

    def add_callback(self, fn):
        """Register a zero-argument callback to trigger on hotkey press."""
        self._callbacks.append(fn)

    def start(self):
        """Start listening in a background daemon thread."""
        self._running = True
        t = threading.Thread(target=self._listen, daemon=True, name="HotkeyThread")
        t.start()
        logger.info(f"Hotkey listener started — trigger: {self._hotkey}")

    def stop(self):
        self._running = False
        try:
            import keyboard
            keyboard.remove_hotkey(self._hotkey)
        except Exception:
            pass

    def _listen(self):
        try:
            import keyboard
            keyboard.add_hotkey(self._hotkey, self._trigger, suppress=False)
            while self._running:
                time.sleep(0.1)
        except ImportError:
            logger.warning("'keyboard' package not installed — hotkey disabled. Run: pip install keyboard")
        except Exception as e:
            logger.error(f"Hotkey listener failed: {e}")

    def _trigger(self):
        logger.info(f"Hotkey triggered: {self._hotkey}")
        for fn in self._callbacks:
            try:
                fn()
            except Exception as e:
                logger.error(f"Hotkey callback error: {e}")
