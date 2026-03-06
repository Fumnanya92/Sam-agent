"""
Notification sound effects (Windows winsound — no external deps).
All calls are fire-and-forget (non-blocking).
"""
import sys
import threading


def _beep(freq: int, duration_ms: int):
    """Safe single beep — silently ignored on non-Windows."""
    try:
        import winsound
        winsound.Beep(freq, duration_ms)
    except Exception:
        pass


def _async(fn):
    threading.Thread(target=fn, daemon=True).start()


def play_wake():
    """Two quick high pings when 'Hey Sam' is detected."""
    def _t():
        _beep(880, 90)
        _beep(1100, 90)
    _async(_t)


def play_done():
    """Single soft descending note on completion."""
    _async(lambda: _beep(660, 140))


def play_error():
    """Three descending tones on error."""
    def _t():
        for freq in (660, 550, 440):
            _beep(freq, 110)
    _async(_t)


def play_reminder():
    """Alternating alert pattern when a reminder fires."""
    def _t():
        for freq in (880, 660, 880, 660):
            _beep(freq, 140)
    _async(_t)


def play_startup():
    """Ascending chord on Sam startup."""
    def _t():
        for freq in (440, 550, 660, 880):
            _beep(freq, 80)
    _async(_t)
