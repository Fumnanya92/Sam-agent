"""Native PyQt desktop shell for Sam v2."""

from __future__ import annotations

import sys
import time
import os
from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, Qt
from PyQt6.QtWidgets import QApplication

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.result import SamResult
from sam_v2.memory.manager import load_memory
from sam_v2.workers import worker_monitor

from .orb import OrbWindow
from .windows import DashboardWindow, IdleSceneWindow, TaskPopupWindow


def _debug_print(message: str) -> None:
    print(f"[SAM_UI] {message}", flush=True)


class RuntimeRequestThread(QThread):
    def __init__(self, runtime: SamRuntime, text: str) -> None:
        super().__init__()
        self.runtime = runtime
        self.text = text
        self.result: SamResult | None = None

    def run(self) -> None:
        _debug_print(f"Runtime request thread started for: {self.text!r}")
        self.result = self.runtime.handle_text(self.text)
        if self.result is not None:
            _debug_print(
                "Runtime request thread finished with "
                f"status={self.result.status} intent={self.result.metadata.get('intent', '')!r} "
                f"summary={self.result.summary!r}"
            )


class NativeShellController:
    def __init__(self, *, runtime: SamRuntime, app: QApplication, folder_opener=None) -> None:
        self.runtime = runtime
        self.app = app
        self.folder_opener = folder_opener or self._default_folder_opener
        self.idle_window = IdleSceneWindow()
        self.dashboard = DashboardWindow()
        self.task_popup = TaskPopupWindow()
        self.orb = OrbWindow()
        self.request_thread: RuntimeRequestThread | None = None
        self._active = False
        self._request_sequence = 0
        self._request_started_at = 0.0
        self._seen_worker_tasks: dict[str, int] = {}
        self._current_project: dict[str, str] = {}
        self._worker_poll_timer = QTimer()
        self._worker_poll_timer.setInterval(120)
        self._worker_poll_timer.timeout.connect(self._consume_worker_updates)

        self.idle_window.activated.connect(self.activate)
        self.orb.clicked.connect(self.activate)
        self.dashboard.submitted.connect(self.submit_request)
        self.dashboard.idle_requested.connect(self.return_to_idle)
        self.dashboard.close_requested.connect(self.return_to_idle)
        self.dashboard.open_folder_requested.connect(self._handle_open_folder)
        self.dashboard.run_again_requested.connect(self._handle_run_again)
        self.dashboard.show_status_requested.connect(self._handle_show_status)
        self.dashboard.show_delegation_requested.connect(self._handle_show_delegation)
        self.dashboard.show_progress_requested.connect(self._handle_show_progress)
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
        self._refresh_project_context()
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
            _debug_print("Rejected request because another request is still running.")
            return

        self._request_sequence += 1
        sequence_id = self._request_sequence
        self._request_started_at = time.time()
        self._seen_worker_tasks = {}
        _debug_print(f"Submitting request #{sequence_id}: {text!r}")
        self.orb.set_state("thinking")
        self.dashboard.set_state("Thinking")
        self.dashboard.append_chat_message("You", text)
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
        self._worker_poll_timer.start()
        self.request_thread.start()

    def _finish_request(self) -> None:
        if self.request_thread is None:
            return
        self._consume_worker_updates()
        self._worker_poll_timer.stop()
        result = self.request_thread.result or SamResult(
            status="failed",
            summary="Sam did not return a result.",
            next_action="ask_user",
        )
        _debug_print(
            "Completing request with "
            f"status={result.status} intent={result.metadata.get('intent', '')!r} "
            f"worker={result.metadata.get('worker_name', '')!r}"
        )
        self._remember_project(result)
        state = "idle" if result.ok else "listening"
        self.orb.set_state(state)
        self.dashboard.set_state(result.status.upper())
        self.dashboard.append_chat_message("Sam", self._format_result_text(result))
        self._refresh_project_context()
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
        if result.metadata.get("worker_name"):
            lines.append(f"Worker: {result.metadata['worker_name']}")
        if result.metadata.get("run_command"):
            lines.append(f"Command: {' '.join(result.metadata['run_command'])}")
        if result.metadata.get("stdout"):
            stdout_text = str(result.metadata["stdout"]).strip()
            if stdout_text:
                lines.append(f"Output: {stdout_text.splitlines()[-1]}")
                for line in stdout_text.splitlines():
                    if "launched project at " in line:
                        lines.append(f"Browser target: {line.split('launched project at ', 1)[1]}")
                    if "launch target " in line:
                        lines.append(f"Browser target: {line.split('launch target ', 1)[1]}")
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
            lines = [result.summary, "", "What I can do right now:"]
            lines.extend(f"- {item.split(':', 1)[0].replace('_', ' ')}" for item in capabilities[:8])
            if missing:
                lines.extend(["", "Not ready yet:"])
                lines.extend(f"- {item.replace('_', ' ')}" for item in missing[:5])
            return "\n".join(lines)

        lines = [result.summary]
        if result.metadata.get("name") and intent not in {"chat", "project_details"}:
            lines.append(f"Project: {result.metadata['name']}")
        if result.metadata.get("root_path") and intent in {"scaffold_project", "run_project", "show_project_status"}:
            lines.append(f"Location: {result.metadata['root_path']}")
        if result.metadata.get("stdout") and intent == "run_project":
            stdout_text = str(result.metadata["stdout"]).strip()
            launch_line = next(
                (
                    line
                    for line in stdout_text.splitlines()
                    if "launched project at " in line or "launch target " in line
                ),
                "",
            )
            if launch_line:
                if "launched project at " in launch_line:
                    lines.append(f"Launched: {launch_line.split('launched project at ', 1)[1]}")
                else:
                    lines.append(f"Launch target: {launch_line.split('launch target ', 1)[1]}")
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

    def _remember_project(self, result: SamResult) -> None:
        if result.metadata.get("project_id"):
            self._current_project["project_id"] = str(result.metadata["project_id"])
        if result.metadata.get("name"):
            self._current_project["name"] = str(result.metadata["name"])
        if result.metadata.get("root_path"):
            self._current_project["root_path"] = str(result.metadata["root_path"])

    def _refresh_project_context(self) -> None:
        if not self._current_project:
            self._load_project_context_from_memory()
        self.dashboard.set_project_context(
            self._current_project.get("name"),
            self._current_project.get("root_path"),
        )

    def _load_project_context_from_memory(self) -> None:
        memory_result, memory = load_memory(self.runtime.memory_path)
        if not memory_result.ok:
            return
        daily_state = memory.get("daily_state", {})
        project_id = str(daily_state.get("last_project_id", {}).get("value", "")).strip()
        project_name = str(daily_state.get("last_project_name", {}).get("value", "")).strip()
        root_path = str(daily_state.get("last_project_root_path", {}).get("value", "")).strip()
        if project_id:
            self._current_project["project_id"] = project_id
        if project_name:
            self._current_project["name"] = project_name
        if root_path:
            self._current_project["root_path"] = root_path

    def _current_project_name(self) -> str:
        if not self._current_project:
            self._load_project_context_from_memory()
        return self._current_project.get("name", "")

    def _current_project_root(self) -> str:
        if not self._current_project:
            self._load_project_context_from_memory()
        return self._current_project.get("root_path", "")

    def _handle_run_again(self) -> None:
        if not self._current_project_name():
            self._show_operator_feedback("Sam", "I don't have a current project yet. Ask me to create, inspect, or show one first.")
            return
        self.submit_request("run it")

    def _handle_show_status(self) -> None:
        project_name = self._current_project_name()
        if not project_name:
            self._show_operator_feedback("Sam", "I don't have a current project yet. Ask me to create, inspect, or show one first.")
            return
        self.submit_request(f"show status for project {project_name}")

    def _handle_show_delegation(self) -> None:
        project_name = self._current_project_name()
        if not project_name:
            self._show_operator_feedback("Sam", "I don't have a current project yet. Ask me to create, inspect, or show one first.")
            return
        self.submit_request(f"show delegation for project {project_name}")

    def _handle_show_progress(self) -> None:
        project_name = self._current_project_name()
        if not project_name:
            self._show_operator_feedback("Sam", "I don't have a current project yet. Ask me to create, inspect, or show one first.")
            return
        self.submit_request(f"show progress for project {project_name}")

    def _handle_open_folder(self) -> None:
        root_path = self._current_project_root()
        project_name = self._current_project_name() or "project"
        if not root_path:
            self._show_operator_feedback("Sam", "I don't have a current project folder yet. Ask me to create, inspect, or show one first.")
            return
        try:
            self.folder_opener(root_path)
            self.task_popup.append_line(f"Opened folder: {root_path}")
            self.dashboard.append_chat_message("Sam", f"I opened the folder for {project_name}.\nLocation: {root_path}")
            _debug_print(f"Opened project folder: {root_path}")
        except Exception as exc:
            self.task_popup.append_line(f"Failed to open folder: {exc}")
            self.dashboard.append_chat_message("Sam", f"I couldn't open the folder for {project_name}.\nError: {exc}")
            _debug_print(f"Failed to open project folder {root_path}: {exc!r}")

    def _show_operator_feedback(self, speaker: str, text: str) -> None:
        self.dashboard.append_chat_message(speaker, text)
        self.task_popup.append_line(text)

    @staticmethod
    def _default_folder_opener(path: str) -> None:
        os.startfile(path)

    def _consume_worker_updates(self) -> None:
        if self.request_thread is None:
            return
        tasks = worker_monitor.list_tasks()
        for task in tasks:
            if task.created_at < self._request_started_at:
                continue

            seen_lines = self._seen_worker_tasks.get(task.task_id, -1)
            if seen_lines == -1:
                self.task_popup.append_line(f"{task.worker_name} [{task.worker_type}] accepted: {task.description}")
                _debug_print(
                    f"Worker accepted task task_id={task.task_id} worker={task.worker_name} "
                    f"type={task.worker_type} description={task.description!r}"
                )
                self._seen_worker_tasks[task.task_id] = 0
                seen_lines = 0

            new_lines = task.output_lines[seen_lines:]
            for line in new_lines:
                self.task_popup.append_line(line)
                _debug_print(f"Worker output task_id={task.task_id}: {line}")

            self._seen_worker_tasks[task.task_id] = len(task.output_lines)

            if task.status == "done" and seen_lines != len(task.output_lines):
                self.task_popup.append_line(f"{task.worker_name} finished successfully.")
                _debug_print(f"Worker task completed task_id={task.task_id} worker={task.worker_name}")
            elif task.status == "failed" and seen_lines != len(task.output_lines):
                self.task_popup.append_line(f"{task.worker_name} failed: {task.error_message}")
                _debug_print(
                    f"Worker task failed task_id={task.task_id} worker={task.worker_name} "
                    f"error={task.error_message!r}"
                )
            elif task.status == "needs_approval" and seen_lines != len(task.output_lines):
                self.task_popup.append_line(f"{task.worker_name} is waiting for approval.")
                _debug_print(f"Worker task needs approval task_id={task.task_id} worker={task.worker_name}")

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
