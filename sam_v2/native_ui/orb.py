"""Animated floating orb for the Sam v2 native shell."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, QPropertyAnimation, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget


STATE_COLORS = {
    "idle": QColor(76, 201, 240, 120),
    "listening": QColor(120, 255, 214, 170),
    "thinking": QColor(255, 196, 61, 170),
    "working": QColor(0, 255, 208, 210),
}


class OrbVisual(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._phase = 0.0
        self._scale = 1.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(33)
        self._pulse_timer.timeout.connect(self._tick)
        self._pulse_timer.start()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_state(self, state: str) -> None:
        self._state = state if state in STATE_COLORS else "idle"
        self.update()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        speed = {
            "idle": 0.06,
            "listening": 0.14,
            "thinking": 0.10,
            "working": 0.18,
        }.get(self._state, 0.06)
        amplitude = {
            "idle": 0.03,
            "listening": 0.05,
            "thinking": 0.04,
            "working": 0.07,
        }.get(self._state, 0.03)
        self._phase += speed
        self._scale = 1.0 + (math.sin(self._phase) * amplitude)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        base_radius = (min(rect.width(), rect.height()) / 2) - 16
        radius = base_radius * self._scale
        glow_color = STATE_COLORS[self._state]

        glow = QRadialGradient(cx, cy, radius + 24)
        glow.setColorAt(0.0, glow_color)
        mid = QColor(glow_color)
        mid.setAlpha(max(20, glow_color.alpha() // 3))
        glow.setColorAt(0.5, mid)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(cx - radius - 24, cy - radius - 24, (radius + 24) * 2, (radius + 24) * 2))

        fill = QRadialGradient(cx - radius * 0.25, cy - radius * 0.35, radius * 1.2)
        fill.setColorAt(0.0, QColor(220, 250, 255, 120))
        fill.setColorAt(0.35, QColor(80, 210, 240, 80))
        fill.setColorAt(0.75, QColor(10, 31, 52, 185))
        fill.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(fill)
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(173, 245, 255, 130), 1.5))
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        painter.setPen(QColor(210, 252, 255))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "SAM")


class OrbWindow(QWidget):
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 180)
        self.visual = OrbVisual(self)
        self.visual.setGeometry(0, 0, 180, 180)
        self.visual.clicked.connect(self.clicked.emit)
        self._drag_origin: QPoint | None = None
        self._geometry_animation = QPropertyAnimation(self, b"geometry")
        self._geometry_animation.setDuration(650)

    def set_state(self, state: str) -> None:
        self.visual.set_state(state)

    def animate_to(self, target: QRect) -> None:
        self._geometry_animation.stop()
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(target)
        self._geometry_animation.start()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_origin = None
        super().mouseReleaseEvent(event)
