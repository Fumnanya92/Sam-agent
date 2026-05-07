"""Offscreen validation for native UI Approvals and Logs surfaces."""

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
    print("=== Sam v2 Native UI Approvals/Logs Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_native_ui_approvals_logs_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"native_ui_approvals_logs_{run_id}.db"
    memory_path = runtime_root / f"native_ui_approvals_logs_{run_id}.json"
    session_path = runtime_root / f"native_ui_approvals_logs_{run_id}.session.json"

    app = QApplication.instance() or QApplication([])
    runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
    controller = NativeShellController(runtime=runtime, app=app, folder_opener=lambda _path: None)

    try:
        controller.show()
        controller.activate()

        controller.submit_request("what can you do")
        _wait_for_request(controller)
        controller.submit_request("Sam, push the changes")
        _wait_for_request(controller)
        controller._handle_show_approvals()
        _wait_for_request(controller)
        controller._handle_show_logs()

        response_text = controller.dashboard.response_view.toPlainText()
        approvals_summary = controller.dashboard.approvals_summary_label.text()
        logs_summary = controller.dashboard.logs_summary_label.text()
        popup_text = controller.task_popup.body_view.toPlainText()

        _assert("git.push" in response_text, "approvals response missing git.push")
        _assert("pending approval" in approvals_summary.lower(), "approvals summary missing pending state")
        _assert("git.push" in approvals_summary, "approvals summary missing tool name")
        _assert("summary log" in logs_summary.lower(), "logs summary missing summary count")
        _assert("Recent logs overview:" in response_text, "logs response missing overview")
        _assert("Loaded recent logs overview." in popup_text, "popup missing logs feedback")
        print("[PASS] Native UI Approvals and Logs surfaces reflect real approvals and log artifacts")
        logger.pass_step("native_ui_approvals_logs")
    except Exception as exc:
        logger.fail_step("native_ui_approvals_logs", str(exc))
        failures.append(f"Native UI Approvals/Logs surfaces failed: {exc}")
    finally:
        controller.idle_window.close()
        controller.dashboard.close()
        controller.task_popup.close()
        controller.orb.close()
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Native UI Approvals/Logs live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All native UI Approvals/Logs checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
