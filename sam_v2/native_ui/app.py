"""Native PyQt desktop shell for Sam v2."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, Qt
from PyQt6.QtWidgets import QApplication

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.result import SamResult

from .orb import OrbWindow
from .windows import DashboardWindow, IdleSceneWindow, TaskPopupWindow


class RuntimeRequestThread(QThread):
    def __init__(self, runtime: SamRuntime, text: str) -> None:
        super().__init__()
        self.runtime = runtime
        self.text = text
        self.result: SamResult | None = None

    def run(self) -> None:
        self.result = self.runtime.handle_text(self.text)


class NativeShellController:
    def __init__(self, *, runtime: SamRuntime, app: QApplication) -> None:
        self.runtime = runtime
        self.app = app
        self.idle_window = IdleSceneWindow()
        self.dashboard = DashboardWindow()
        self.task_popup = TaskPopupWindow()
        self.orb = OrbWindow()
        self.request_thread: RuntimeRequestThread | None = None
        self._active = False
        self._request_sequence = 0

        self.idle_window.activated.connect(self.activate)
        self.orb.clicked.connect(self.activate)
        self.dashboard.submitted.connect(self.submit_request)
        self.dashboard.idle_requested.connect(self.return_to_idle)
        self.dashboard.close_requested.connect(self.return_to_idle)
        self.task_popup.close_requested.connect(self.task_popup.hide)

        self._layout_windows(initial=True)
        self.dashboard.hide()
        self.task_popup.hide()

    def show(self) -> None:
        self.idle_window.showFullScreen()
        self.orb.show()

    def activate(self) -> None:
        if self._active:
            self.dashboard.raise_()
            self.task_popup.raise_()
            self.orb.raise_()
            return
        self._active = True
        self.orb.set_state("listening")
        self.idle_window.hide()
        self._layout_windows(initial=False)
        self.dashboard.show()
        self.task_popup.show()
        self.dashboard.raise_()
        self.task_popup.raise_()
        self.orb.raise_()
        self.dashboard.set_state("Ready")
        self.task_popup.set_task("Ready", "Idle", ["Waiting for your next instruction."])

    def return_to_idle(self) -> None:
        self._active = False
        self.dashboard.hide()
        self.task_popup.hide()
        self._layout_windows(initial=True)
        self.orb.set_state("idle")
        self.idle_window.showFullScreen()
        self.orb.raise_()

    def submit_request(self, text: str) -> None:
        if self.request_thread is not None and self.request_thread.isRunning():
            self.task_popup.append_line("Sam is already working on another request.")
            return

        self._request_sequence += 1
        sequence_id = self._request_sequence
        self.orb.set_state("thinking")
        self.dashboard.set_state("Thinking")
        self.task_popup.set_task(
            title="Active Task",
            status="Working",
            lines=[
                "Pilot accepted the request.",
                "Sam is routing the task through the runtime.",
            ],
        )
        self._queue_activity(sequence_id, 250, "Intent layer is classifying the request.")
        self._queue_activity(sequence_id, 650, "Named workers are standing by for execution.")
        self._queue_activity(sequence_id, 1150, "Sam is preparing the next safe action.")

        self.request_thread = RuntimeRequestThread(self.runtime, text)
        self.request_thread.finished.connect(self._finish_request)
        self.request_thread.start()

    def _finish_request(self) -> None:
        if self.request_thread is None:
            return
        result = self.request_thread.result or SamResult(
            status="failed",
            summary="Sam did not return a result.",
            next_action="ask_user",
        )
        state = "idle" if result.ok else "listening"
        self.orb.set_state(state)
        self.dashboard.set_state(result.status.upper())
        self.dashboard.append_response(self._format_result_text(result))
        self.task_popup.set_title(self._display_title(result))
        self.task_popup.set_status(result.status)
        self.task_popup.append_line("Completed.")
        for line in self._task_lines(result):
            self.task_popup.append_line(line)
        self.request_thread = None

    def _task_lines(self, result: SamResult) -> list[str]:
        lines = [
            result.summary,
            f"Next: {result.next_action or 'stop'}",
        ]
        if result.metadata.get("worker_updates"):
            lines.extend(result.metadata["worker_updates"])
        if result.metadata.get("delegation"):
            for item in result.metadata["delegation"][:4]:
                worker = item.get("worker_name", "worker")
                artifact = item.get("artifact") or item.get("file", "artifact")
                lines.append(f"{worker} handled {artifact}.")
        if result.error_message:
            lines.append(f"Error: {result.error_message}")
        return lines

    def _format_result_text(self, result: SamResult) -> str:
        intent = str(result.metadata.get("intent", "chat"))
        if intent == "capabilities":
            capabilities = result.metadata.get("available_capabilities", [])
            missing = result.metadata.get("missing_capabilities", [])
            lines = ["Sam:", result.summary, "", "What I can do right now:"]
            lines.extend(f"- {item.split(':', 1)[0].replace('_', ' ')}" for item in capabilities[:8])
            if missing:
                lines.extend(["", "Not ready yet:"])
                lines.extend(f"- {item.replace('_', ' ')}" for item in missing[:5])
            return "\n".join(lines)

        lines = ["Sam:", result.summary]
        if result.metadata.get("name") and intent not in {"chat", "project_details"}:
            lines.append(f"Project: {result.metadata['name']}")
        if result.metadata.get("root_path") and intent in {"scaffold_project", "run_project", "show_project_status"}:
            lines.append(f"Location: {result.metadata['root_path']}")
        if result.metadata.get("branch") and intent in {"show_project_status", "inspect_git_state", "inspect_project_repo"}:
            lines.append(f"Branch: {result.metadata['branch']}")
        if result.metadata.get("completed_items") and intent == "show_project_status":
            lines.append("")
            lines.append("Completed:")
            lines.extend(f"- {item}" for item in result.metadata["completed_items"][:3])
        if result.metadata.get("next_items") and intent == "show_project_status":
            lines.append("")
            lines.append("Next:")
            lines.extend(f"- {item}" for item in result.metadata["next_items"][:3])
        if result.status == "needs_approval":
            lines.append("")
            lines.append("Approval is required before I continue.")
        return "\n".join(lines)

    def _display_title(self, result: SamResult) -> str:
        if result.status == "needs_approval":
            return "Approval Required"
        if result.metadata.get("name"):
            return str(result.metadata["name"])
        intent = str(result.metadata.get("intent", "task")).replace("_", " ").title()
        return intent or "Task"

    def _queue_activity(self, sequence_id: int, delay_ms: int, line: str) -> None:
        def emit_if_current() -> None:
            if self.request_thread is None:
                return
            if sequence_id != self._request_sequence:
                return
            self.task_popup.append_line(line)

        QTimer.singleShot(delay_ms, emit_if_current)

    def _layout_windows(self, *, initial: bool) -> None:
        screen = self.app.primaryScreen()
        geometry = screen.availableGeometry() if screen is not None else self.app.primaryScreen().geometry()
        if geometry is None:
            return

        center_size = 220
        center_rect = geometry.adjusted(
            (geometry.width() - center_size) // 2,
            (geometry.height() - center_size) // 2,
            -((geometry.width() - center_size) // 2),
            -((geometry.height() - center_size) // 2),
        )
        orb_idle_rect = center_rect
        orb_active_rect = type(center_rect)(
            geometry.right() - 220,
            geometry.bottom() - 220,
            180,
            180,
        )
        dashboard_rect = type(center_rect)(
            geometry.right() - 470,
            geometry.top() + 56,
            430,
            680,
        )
        popup_rect = type(center_rect)(
            geometry.right() - 930,
            geometry.top() + 120,
            420,
            240,
        )

        if initial:
            self.orb.setGeometry(orb_idle_rect)
        else:
            self.orb.animate_to(orb_active_rect)
            self.dashboard.setGeometry(type(center_rect)(geometry.right(), dashboard_rect.y(), dashboard_rect.width(), dashboard_rect.height()))
            self.dashboard.animate_to(dashboard_rect)
            self.task_popup.setGeometry(type(center_rect)(popup_rect.x(), geometry.top() - popup_rect.height(), popup_rect.width(), popup_rect.height()))
            self.task_popup.animate_to(popup_rect)

def run_native_ui(*, data_dir: Path, db_path: Path) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Sam v2 Native UI")

    runtime = SamRuntime(
        db_path=db_path,
        memory_path=data_dir / "memory.json",
        session_path=data_dir / "session.json",
    )
    controller = NativeShellController(runtime=runtime, app=app)
    controller.show()

    exit_code = app.exec()
    runtime.shutdown()
    return exit_code
