"""Native shell windows for the Sam v2 desktop experience."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class IdleSceneWindow(QWidget):
    activated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(90, 90, 90, 90)
        layout.addStretch()

        title = QLabel("SAM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        title.setStyleSheet("color: #dffcff; letter-spacing: 8px;")

        subtitle = QLabel("Idle mode\nClick the orb to wake Sam")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: rgba(223, 252, 255, 0.72); font-size: 18px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        from PyQt6.QtGui import QLinearGradient, QPainter

        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(3, 10, 20, 245))
        gradient.setColorAt(0.5, QColor(4, 22, 36, 235))
        gradient.setColorAt(1.0, QColor(0, 6, 12, 245))
        painter.fillRect(self.rect(), gradient)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)


class DashboardWindow(QWidget):
    submitted = pyqtSignal(str)
    idle_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(430, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame { background: rgba(6, 18, 31, 228); border: 1px solid rgba(132, 246, 255, 0.18); border-radius: 24px; }"
            "QLabel { color: #dffcff; }"
        )
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QLabel("Sam Dashboard")
        header.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
        layout.addWidget(header)

        self.state_label = QLabel("Idle")
        self.state_label.setStyleSheet("color: #77f7ff; font-size: 13px; text-transform: uppercase;")
        layout.addWidget(self.state_label)

        self.response_view = QPlainTextEdit()
        self.response_view.setReadOnly(True)
        self.response_view.setStyleSheet(
            "QPlainTextEdit { background: rgba(8, 29, 48, 0.95); color: #e9ffff; border: 1px solid rgba(132, 246, 255, 0.10); border-radius: 18px; padding: 12px; font-size: 14px; }"
        )
        layout.addWidget(self.response_view, 1)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Ask Sam to do something...")
        self.input_line.setStyleSheet(
            "QLineEdit { background: rgba(8, 29, 48, 0.95); color: white; border: 1px solid rgba(132, 246, 255, 0.16); border-radius: 16px; padding: 14px; font-size: 14px; }"
        )
        self.input_line.returnPressed.connect(self._emit_submit)
        layout.addWidget(self.input_line)

        controls = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._emit_submit)
        self.idle_button = QPushButton("Idle Scene")
        self.idle_button.clicked.connect(self.idle_requested.emit)
        for button in (self.run_button, self.idle_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background: rgba(18, 79, 116, 0.95); color: white; border: 0; border-radius: 14px; padding: 12px 16px; font-weight: 600; }"
                "QPushButton:hover { background: rgba(26, 119, 165, 0.95); }"
            )
            controls.addWidget(button)
        layout.addLayout(controls)

        self._geometry_animation = QPropertyAnimation(self, b"geometry")
        self._geometry_animation.setDuration(520)

    def _emit_submit(self) -> None:
        text = self.input_line.text().strip()
        if text:
            self.submitted.emit(text)
            self.input_line.clear()

    def set_state(self, state: str) -> None:
        self.state_label.setText(state)

    def append_response(self, text: str) -> None:
        existing = self.response_view.toPlainText().strip()
        joined = f"{existing}\n\n{text}".strip() if existing else text
        self.response_view.setPlainText(joined)
        self.response_view.verticalScrollBar().setValue(self.response_view.verticalScrollBar().maximum())

    def animate_to(self, target: QRect) -> None:
        self._geometry_animation.stop()
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(target)
        self._geometry_animation.start()


class TaskPopupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 240)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame { background: rgba(3, 16, 28, 236); border: 1px solid rgba(111, 244, 255, 0.20); border-radius: 20px; }"
            "QLabel { color: #dffcff; }"
        )
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        self.title_label = QLabel("No active task")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
        layout.addWidget(self.title_label)

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: #77f7ff; font-size: 12px; text-transform: uppercase;")
        layout.addWidget(self.status_label)

        self.body_view = QPlainTextEdit()
        self.body_view.setReadOnly(True)
        self.body_view.setStyleSheet(
            "QPlainTextEdit { background: rgba(8, 29, 48, 0.9); color: #e9ffff; border: 1px solid rgba(132, 246, 255, 0.10); border-radius: 14px; padding: 10px; }"
        )
        layout.addWidget(self.body_view, 1)

        self._drag_offset: QPoint | None = None
        self._geometry_animation = QPropertyAnimation(self, b"geometry")
        self._geometry_animation.setDuration(420)

    def set_task(self, title: str, status: str, lines: list[str]) -> None:
        self.title_label.setText(title)
        self.status_label.setText(status)
        self.body_view.setPlainText("\n".join(lines).strip())

    def append_line(self, line: str) -> None:
        existing = self.body_view.toPlainText().strip()
        self.body_view.setPlainText(f"{existing}\n{line}".strip() if existing else line)

    def animate_to(self, target: QRect) -> None:
        self._geometry_animation.stop()
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(target)
        self._geometry_animation.start()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)
