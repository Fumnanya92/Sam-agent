"""Offscreen smoke test for the Sam v2 native UI shell."""

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


def main() -> int:
    print("=== Sam v2 Native UI Smoke Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_native_ui_smoke")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"native_ui_{run_id}.db"
    memory_path = runtime_root / f"native_ui_{run_id}.json"
    session_path = runtime_root / f"native_ui_{run_id}.session.json"

    app = QApplication.instance() or QApplication([])
    runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
    controller = NativeShellController(runtime=runtime, app=app)

    try:
        controller.show()
        controller.activate()
        _assert(controller.dashboard.isVisible(), "dashboard did not become visible")
        _assert(controller.task_popup.isVisible(), "task popup did not become visible")

        controller.submit_request("what can you do")
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)

        def maybe_finish() -> None:
            if controller.request_thread is None:
                loop.quit()
            else:
                QTimer.singleShot(50, maybe_finish)

        QTimer.singleShot(50, maybe_finish)
        loop.exec()

        _assert(controller.request_thread is None, "runtime request thread did not finish")
        response_text = controller.dashboard.response_view.toPlainText()
        _assert("available_capabilities" in response_text or "capabilities" in response_text.lower(), "dashboard missing runtime response")
        _assert('"status"' not in response_text, "dashboard is still showing raw SamResult JSON")
        popup_text = controller.task_popup.body_view.toPlainText()
        _assert("Next:" in popup_text, "task popup missing next-step summary")
        print("[PASS] Native shell can activate and route a real runtime request")
        logger.pass_step("native_ui_smoke")
    except Exception as exc:
        logger.fail_step("native_ui_smoke", str(exc))
        failures.append(f"Native UI smoke failed: {exc}")
    finally:
        controller.idle_window.close()
        controller.dashboard.close()
        controller.task_popup.close()
        controller.orb.close()
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Native UI smoke test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All native UI smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
