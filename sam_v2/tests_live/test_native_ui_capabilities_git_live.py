"""Offscreen validation for native UI Capabilities and Git State surfaces."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    print("=== Sam v2 Native UI Capabilities/Git Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_native_ui_capabilities_git_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"native_ui_capabilities_git_{run_id}.db"
    memory_path = runtime_root / f"native_ui_capabilities_git_{run_id}.json"
    session_path = runtime_root / f"native_ui_capabilities_git_{run_id}.session.json"

    app = QApplication.instance() or QApplication([])
    runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
    controller = NativeShellController(runtime=runtime, app=app, folder_opener=lambda _path: None)
    project_name = f"Capability Git {uuid.uuid4().hex[:6]}"

    try:
        controller.show()
        controller.activate()

        controller.submit_request(f"build a web tictac game called {project_name}")
        _wait_for_request(controller)
        controller._handle_show_capabilities()
        _wait_for_request(controller)
        controller._handle_show_git_state()
        _wait_for_request(controller)

        response_text = controller.dashboard.response_view.toPlainText()
        capabilities_summary = controller.dashboard.capabilities_summary_label.text()
        git_summary = controller.dashboard.git_state_summary_label.text()

        _assert("What I can do right now:" in response_text, "capabilities response missing details")
        _assert("available capability" in capabilities_summary.lower(), "capabilities summary missing count")
        _assert("branch" in git_summary.lower(), "git state summary missing branch")
        _assert(project_name in git_summary, "git state summary missing current project name")
        _assert("Git state for" in response_text, "git state response missing summary")
        print("[PASS] Native UI Capabilities and Git State surfaces reflect real runtime data")
        logger.pass_step("native_ui_capabilities_git")
    except Exception as exc:
        logger.fail_step("native_ui_capabilities_git", str(exc))
        failures.append(f"Native UI Capabilities/Git surfaces failed: {exc}")
    finally:
        controller.idle_window.close()
        controller.dashboard.close()
        controller.task_popup.close()
        controller.orb.close()
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Native UI Capabilities/Git live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All native UI Capabilities/Git checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
