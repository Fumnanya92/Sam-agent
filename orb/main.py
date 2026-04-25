"""
orb/main.py — Sam glass orb: a frameless, always-on-top PyQt6 desktop widget.

Visual design
-------------
- 120 × 120 px frosted-glass circle (idle), scales slightly when active
- Emerald (#10b981) inner glow with state-driven intensity
- Radial gradient fill for the frosted glass look
- Outer glow drawn with additive compositing via QPainter

Behaviour
---------
- Left-click  : open http://localhost:3142 in the default browser
- Right-click : context menu → Open Dashboard / Settings / Quit Sam
- Drag        : move the orb anywhere on the desktop
- Position is persisted in ~/.sam/orb_position.json
- Connects to ws://localhost:3142/ws and listens for system_status events
"""

import math
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QRadialGradient,
    QAction,
)
from PyQt6.QtNetwork import QAbstractSocket, QTcpSocket
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from orb.animations import BreathingAnimation, GlowAnimation
from orb.position_manager import load_position, save_position


# ── Constants ─────────────────────────────────────────────────────────────────

_DASHBOARD_URL = "http://localhost:3142"
_WS_HOST       = "localhost"
_WS_PORT       = 3142
_WS_PATH       = "/ws"

_BASE_SIZE     = 120          # px — idle diameter
_SCALE_MAX     = 1.08         # max scale during speaking/listening

# Orb fill colours (frosted glass layers)
_FILL_OUTER = QColor(6,   78,  59,  38)   # rgba(6,78,59,0.15)   — dark emerald shell
_FILL_WHITE = QColor(255, 255, 255, 51)   # rgba(255,255,255,0.2) — frosted overlay
_FILL_INNER = QColor(16,  185, 129, 77)   # rgba(16,185,129,0.30) — emerald-500 core

# Startup fade-in duration (ms)
_FADE_IN_MS  = 600
_SCALE_IN_MS = 700


# ═════════════════════════════════════════════════════════════════════════════
#  OrbWidget — does all the drawing
# ═════════════════════════════════════════════════════════════════════════════

class OrbWidget(QWidget):
    """Paints the frosted-glass orb.  Animation state is driven externally."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # We own a transparent background; the window handles WA_TranslucentBackground
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._scale      = 1.0
        self._glow_color = QColor(16, 185, 129, 51)   # start dim
        self._state      = "idle"

        # Thinking-ring angle, advanced each frame while in "thinking" state
        self._ring_angle  = 0.0
        self._ring_timer  = QTimer(self)
        self._ring_timer.setInterval(16)
        self._ring_timer.timeout.connect(self._advance_ring)

    # ── Public setters (called from animations) ───────────────────────────────

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.update()   # schedule repaint

    def set_glow_color(self, color: QColor) -> None:
        self._glow_color = color
        self.update()

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "thinking":
            self._ring_timer.start()
        else:
            self._ring_timer.stop()
        self.update()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2

        # Effective radius after breathing scale
        base_r = (min(w, h) / 2) - 8   # 8 px margin so glow isn't clipped
        r = base_r * self._scale

        # ── 1. Outer glow ──────────────────────────────────────────────────
        painter.save()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )
        glow_color = QColor(self._glow_color)
        glow_r = r + 20
        grad = QRadialGradient(cx, cy, glow_r)
        grad.setColorAt(0.0, glow_color)
        mid = QColor(glow_color)
        mid.setAlpha(glow_color.alpha() // 3)
        grad.setColorAt(0.5, mid)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
        painter.restore()

        # ── 2. Frosted glass fill ──────────────────────────────────────────
        # Layer A: dark emerald shell
        painter.save()
        grad2 = QRadialGradient(cx, cy - r * 0.2, r)
        grad2.setColorAt(0.0, _FILL_INNER)
        grad2.setColorAt(0.6, _FILL_OUTER)
        grad2.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        painter.restore()

        # Layer B: white frosted overlay (lighter near the top-left)
        painter.save()
        grad3 = QRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 1.1)
        grad3.setColorAt(0.0, _FILL_WHITE)
        grad3.setColorAt(0.7, QColor(255, 255, 255, 10))
        grad3.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(grad3))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        painter.restore()

        # ── 3. Edge rim highlight ──────────────────────────────────────────
        painter.save()
        rim_color = QColor(16, 185, 129, 80)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        from PyQt6.QtGui import QPen
        painter.setPen(QPen(rim_color, 1.2))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        painter.restore()

        # ── 4. Thinking ring ──────────────────────────────────────────────
        if self._state == "thinking":
            painter.save()
            from PyQt6.QtGui import QPen, QConicalGradient
            ring_r = r + 10
            # Amber arc
            amber = QColor(251, 191, 36, 180)
            pen = QPen(amber, 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Draw a 270° arc that rotates over time
            start_angle = int(self._ring_angle * 16)    # Qt uses 1/16th degree
            span_angle  = 270 * 16
            painter.drawArc(
                QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2),
                start_angle, span_angle
            )
            painter.restore()

        # ── 5. Speaking pulse rings ────────────────────────────────────────
        if self._state == "speaking":
            self._draw_pulse_rings(painter, cx, cy, r)

    def _draw_pulse_rings(self, painter: QPainter, cx: float, cy: float, r: float):
        """Draw two fading outward rings to suggest the orb is emitting sound."""
        glow_alpha = self._glow_color.alpha()
        for offset in (14, 28):
            ring_r = r + offset
            ring_alpha = max(0, int(glow_alpha * (1.0 - offset / 40.0)))
            c = QColor(16, 185, 129, ring_alpha)
            from PyQt6.QtGui import QPen
            painter.save()
            painter.setPen(QPen(c, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))
            painter.restore()

    # ── Thinking ring ticker ──────────────────────────────────────────────────

    def _advance_ring(self):
        self._ring_angle = (self._ring_angle + 2.5) % 360
        self.update()


# ═════════════════════════════════════════════════════════════════════════════
#  SamOrb — frameless always-on-top window
# ═════════════════════════════════════════════════════════════════════════════

class SamOrb(QMainWindow):
    """
    Top-level frameless window hosting the OrbWidget.

    Responsibilities
    ----------------
    - Window flags: frameless, always on top, transparent background
    - Drag-to-move via mouse press/move events
    - Left-click → open dashboard URL
    - Right-click → context menu
    - Save/restore position via position_manager
    - WebSocket connection for state updates
    - Fade-in on startup via QPropertyAnimation on windowOpacity
    """

    # pyqtSignal emitted when the state changes (for subclass/test hooks)
    state_changed = pyqtSignal(str)

    # ── pyqtProperty for the fade-in animation ────────────────────────────────
    def _get_opacity(self) -> float:
        return self.windowOpacity()

    def _set_opacity(self, value: float) -> None:
        self.setWindowOpacity(value)

    opacity = pyqtProperty(float, fget=_get_opacity, fset=_set_opacity)

    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool           # hides from taskbar on most platforms
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # ── Size ──────────────────────────────────────────────────────────────
        margin = 50   # extra space so outer glow + rings aren't clipped
        win_size = _BASE_SIZE + margin * 2
        self.setFixedSize(win_size, win_size)

        # ── Central widget ────────────────────────────────────────────────────
        self._orb = OrbWidget(self)
        self._orb.setGeometry(0, 0, win_size, win_size)
        self.setCentralWidget(self._orb)

        # ── Position ──────────────────────────────────────────────────────────
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            sx, sy = geo.width(), geo.height()
        else:
            sx, sy = 1920, 1080
        x, y = load_position(sx, sy)
        self.move(x, y)

        # ── Drag state ────────────────────────────────────────────────────────
        self._drag_start_pos: QPoint | None = None

        # ── Animations ────────────────────────────────────────────────────────
        self._breathing = BreathingAnimation(self._orb.set_scale)
        self._glow      = GlowAnimation(self._orb.set_glow_color)
        self._breathing.start()
        self._glow.start()

        # ── Current state ─────────────────────────────────────────────────────
        self._state = "idle"

        # ── Fade-in on startup ────────────────────────────────────────────────
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"opacity")
        self._fade_anim.setDuration(_FADE_IN_MS)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

        # ── WebSocket (deferred — connect after show()) ───────────────────────
        self._ws_socket: QTcpSocket | None = None
        self._ws_connected = False
        self._ws_buffer = b""
        # Retry connection every 5 s if not connected
        self._ws_retry_timer = QTimer(self)
        self._ws_retry_timer.setInterval(5000)
        self._ws_retry_timer.timeout.connect(self._connect_ws)
        QTimer.singleShot(500, self._connect_ws)

    # ── State management ──────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Set animation state: idle | listening | thinking | speaking."""
        if state not in ("idle", "listening", "thinking", "speaking"):
            state = "idle"
        if state == self._state:
            return
        self._state = state
        self._breathing.set_state(state)
        self._glow.set_state(state)
        self._orb.set_state(state)
        self.state_changed.emit(state)

    # ── WebSocket connection ───────────────────────────────────────────────────

    def _connect_ws(self) -> None:
        if self._ws_connected:
            return
        try:
            self._ws_socket = QTcpSocket(self)
            self._ws_socket.connected.connect(self._on_ws_connected)
            self._ws_socket.readyRead.connect(self._on_ws_data)
            self._ws_socket.disconnected.connect(self._on_ws_disconnected)
            self._ws_socket.errorOccurred.connect(self._on_ws_error)
            self._ws_socket.connectToHost(_WS_HOST, _WS_PORT)
            self._ws_retry_timer.stop()
        except Exception:
            # Network not available — silently retry
            self._ws_retry_timer.start()

    def _on_ws_connected(self) -> None:
        """Perform the HTTP upgrade handshake for WebSocket."""
        import base64, os
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {_WS_PATH} HTTP/1.1\r\n"
            f"Host: {_WS_HOST}:{_WS_PORT}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self._ws_socket.write(handshake.encode())
        self._ws_connected = True
        self._ws_buffer = b""

    def _on_ws_data(self) -> None:
        """Read raw bytes; parse minimal WebSocket frames looking for JSON."""
        import json as _json
        data = bytes(self._ws_socket.readAll())
        self._ws_buffer += data

        # After the upgrade the server sends HTTP 101 — skip it
        if b"\r\n\r\n" in self._ws_buffer and self._ws_buffer.startswith(b"HTTP/"):
            _, _, self._ws_buffer = self._ws_buffer.partition(b"\r\n\r\n")

        # Parse WebSocket frames (text frames only, no masking from server)
        while len(self._ws_buffer) >= 2:
            b0, b1 = self._ws_buffer[0], self._ws_buffer[1]
            opcode = b0 & 0x0F
            masked  = (b1 & 0x80) != 0
            length  = b1 & 0x7F

            if length == 126:
                if len(self._ws_buffer) < 4:
                    break
                length = int.from_bytes(self._ws_buffer[2:4], "big")
                header_len = 4
            elif length == 127:
                if len(self._ws_buffer) < 10:
                    break
                length = int.from_bytes(self._ws_buffer[2:10], "big")
                header_len = 10
            else:
                header_len = 2

            mask_len = 4 if masked else 0
            total = header_len + mask_len + length
            if len(self._ws_buffer) < total:
                break   # wait for more data

            payload = self._ws_buffer[header_len + mask_len: total]
            if masked:
                mask = self._ws_buffer[header_len: header_len + 4]
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            self._ws_buffer = self._ws_buffer[total:]

            # opcode 1 = text frame
            if opcode == 1:
                try:
                    msg = _json.loads(payload.decode("utf-8", errors="replace"))
                    if msg.get("type") == "system_status":
                        state = msg.get("state", "idle")
                        self.set_state(state)
                except Exception:
                    pass

    def _on_ws_disconnected(self) -> None:
        self._ws_connected = False
        self._ws_socket = None
        self.set_state("idle")
        self._ws_retry_timer.start()

    def _on_ws_error(self, _error) -> None:
        self._ws_connected = False
        self._ws_retry_timer.start()

    # ── Mouse interaction ─────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_start_pos is not None:
                delta = event.globalPosition().toPoint() - self._drag_start_pos - self.frameGeometry().topLeft()
                # Only treat as a click if the orb barely moved (drag < 5 px)
                if abs(delta.x()) < 5 and abs(delta.y()) < 5:
                    self._open_dashboard()
                save_position(self.x(), self.y())
            self._drag_start_pos = None
            event.accept()

    # ── Context menu ──────────────────────────────────────────────────────────

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d1f17;
                border: 1px solid #10b981;
                border-radius: 6px;
                color: #d1fae5;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #064e3b;
            }
        """)

        open_action     = QAction("Open Dashboard", self)
        settings_action = QAction("Settings", self)
        quit_action     = QAction("Quit Sam", self)

        open_action.triggered.connect(self._open_dashboard)
        settings_action.triggered.connect(self._open_settings)
        quit_action.triggered.connect(self._quit)

        menu.addAction(open_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(global_pos)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_dashboard(self) -> None:
        webbrowser.open(_DASHBOARD_URL)

    def _open_settings(self) -> None:
        webbrowser.open(f"{_DASHBOARD_URL}/settings")

    def _quit(self) -> None:
        save_position(self.x(), self.y())
        QApplication.quit()

    # ── Window close ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        save_position(self.x(), self.y())
        self._breathing.stop()
        self._glow.stop()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    orb = SamOrb()
    orb.show()
    sys.exit(app.exec())
