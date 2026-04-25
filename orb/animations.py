"""
orb/animations.py — Breathing and glow animation helpers for the Sam glass orb.

Both classes are driven by a QTimer and emit updated values through callback
functions so the OrbWidget can schedule a repaint without knowing animation
internals.
"""

import math
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor


# ── Colour palette ────────────────────────────────────────────────────────────

# Idle: soft emerald
_COLOR_IDLE = QColor(16, 185, 129, 51)          # rgba(16,185,129, 0.20)
# Listening: bright emerald
_COLOR_LISTENING = QColor(16, 185, 129, 153)    # rgba(16,185,129, 0.60)
# Thinking: amber/gold
_COLOR_THINKING = QColor(251, 191, 36, 102)     # rgba(251,191,36, 0.40)
# Speaking: vivid emerald
_COLOR_SPEAKING = QColor(16, 185, 129, 204)     # rgba(16,185,129, 0.80)

# Map state name → target glow colour
_STATE_COLORS: dict[str, QColor] = {
    "idle":      _COLOR_IDLE,
    "listening": _COLOR_LISTENING,
    "thinking":  _COLOR_THINKING,
    "speaking":  _COLOR_SPEAKING,
}

# Breathing period per state (seconds)
_STATE_PERIODS: dict[str, float] = {
    "idle":      4.0,
    "listening": 1.5,
    "thinking":  2.5,
    "speaking":  1.2,
}

# Scale amplitude (fraction of base size)
_SCALE_AMP = 0.05   # orb breathes ±5 % of its base size


class BreathingAnimation:
    """
    Drives a smooth sinusoidal scale oscillation.

    The callback receives a float scale factor centred on 1.0.
    Period and amplitude change when the state changes.
    """

    _TICK_MS = 16   # ~60 fps

    def __init__(self, on_scale_change):
        """
        Parameters
        ----------
        on_scale_change : callable(float)
            Called every tick with the current scale factor (e.g. 0.95 – 1.05).
        """
        self._callback = on_scale_change
        self._state = "idle"
        self._elapsed = 0.0         # seconds of accumulated time
        self._period = _STATE_PERIODS["idle"]

        self._timer = QTimer()
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_state(self, state: str) -> None:
        """Switch to a new animation state (idle/listening/thinking/speaking)."""
        if state not in _STATE_PERIODS:
            state = "idle"
        self._state = state
        self._period = _STATE_PERIODS[state]
        # Keep _elapsed so the transition is smooth rather than jumping.

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        self._elapsed += self._TICK_MS / 1000.0
        # InOutSine: sin wave normalised to [0, 1]
        phase = (self._elapsed % self._period) / self._period   # 0 – 1
        sine = math.sin(phase * math.pi * 2)                    # -1 – 1
        # Map to scale range 0.95 – 1.05
        scale = 1.0 + sine * _SCALE_AMP
        self._callback(scale)


class GlowAnimation:
    """
    Drives the glow colour and intensity.

    Rather than snapping to the target colour, it linearly interpolates
    (lerps) every tick for a smooth state-to-state cross-fade.
    """

    _TICK_MS = 16           # ~60 fps
    _LERP_SPEED = 0.04      # fraction of remaining gap closed per tick

    def __init__(self, on_color_change):
        """
        Parameters
        ----------
        on_color_change : callable(QColor)
            Called every tick with the current interpolated glow colour.
        """
        self._callback = on_color_change
        self._current = _color_to_floats(_COLOR_IDLE)
        self._target  = _color_to_floats(_COLOR_IDLE)

        self._timer = QTimer()
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_state(self, state: str) -> None:
        """Set the target glow colour for the given state."""
        target_qcolor = _STATE_COLORS.get(state, _COLOR_IDLE)
        self._target = _color_to_floats(target_qcolor)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        # Lerp each channel toward target
        self._current = tuple(
            c + (t - c) * self._LERP_SPEED
            for c, t in zip(self._current, self._target)
        )
        r, g, b, a = (int(round(v)) for v in self._current)
        self._callback(QColor(r, g, b, a))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _color_to_floats(color: QColor) -> tuple:
    return (
        float(color.red()),
        float(color.green()),
        float(color.blue()),
        float(color.alpha()),
    )
