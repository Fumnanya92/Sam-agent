"""Offscreen validation for native UI project action controls."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SAM_V2_NO_BROWSER"] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.native_ui.app import NativeShellController


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _wait_for_request(controller: NativeShellController, timeout_ms: int = 7000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    def maybe_finish() -> None:
        if controller.request_thread is None:
            loop.quit()
        else:
            QTimer.singleShot(50, maybe_finish)

    QTimer.singleShot(50, maybe_finish)
    loop.exec()


def main() -> int:
    print("=== Sam v2 Native UI Project Actions Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_native_ui_project_actions_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"native_ui_actions_{run_id}.db"
    memory_path = runtime_root / f"native_ui_actions_{run_id}.json"
    session_path = runtime_root / f"native_ui_actions_{run_id}.session.json"

    opened_paths: list[str] = []

    def fake_open_folder(path: str) -> None:
        opened_paths.append(path)

    app = QApplication.instance() or QApplication([])
    runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
    controller = NativeShellController(runtime=runtime, app=app, folder_opener=fake_open_folder)
    project_name = f"Native UI Actions {uuid.uuid4().hex[:6]}"

    try:
        controller.show()
        controller.activate()

        controller.submit_request(f"build a web tictac game called {project_name}")
        _wait_for_request(controller)
        controller.submit_request(f"plan project {project_name}")
        _wait_for_request(controller)
        controller._handle_show_status()
        _wait_for_request(controller)
        controller._handle_show_progress()
        _wait_for_request(controller)
        controller._handle_show_delegation()
        _wait_for_request(controller)
        controller._handle_run_again()
        _wait_for_request(controller)
        controller._handle_open_folder()

        response_text = controller.dashboard.response_view.toPlainText()
        popup_text = controller.task_popup.body_view.toPlainText()

        _assert(project_name in controller.dashboard.project_context_label.text(), "project context label missing project")
        _assert("show status for project" not in response_text.lower() or "Current project:" in controller.dashboard.project_context_label.text(), "project context not set")
        _assert("Delegation is tracked for this project." in response_text, "delegation action missing response")
        _assert("launch target " in response_text or "launched project at " in response_text, "run again action missing output")
        _assert(opened_paths and project_name.lower().replace(" ", "_") in opened_paths[0], "open folder action missing path")
        _assert("Opened folder:" in popup_text, "popup missing folder-open feedback")
        print("[PASS] Native UI project action controls can operate on the current project")
        logger.pass_step("native_ui_project_actions")
    except Exception as exc:
        logger.fail_step("native_ui_project_actions", str(exc))
        failures.append(f"Native UI project actions failed: {exc}")
    finally:
        controller.idle_window.close()
        controller.dashboard.close()
        controller.task_popup.close()
        controller.orb.close()
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Native UI project actions live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All native UI project action checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
