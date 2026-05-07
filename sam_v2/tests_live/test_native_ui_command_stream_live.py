"""Native UI validation for visible worker command execution."""

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
    print("=== Sam v2 Native UI Command Stream Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_native_ui_command_stream_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"native_ui_cmd_{run_id}.db"
    memory_path = runtime_root / f"native_ui_cmd_{run_id}.json"
    session_path = runtime_root / f"native_ui_cmd_{run_id}.session.json"

    app = QApplication.instance() or QApplication([])
    runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
    controller = NativeShellController(runtime=runtime, app=app)

    project_name = f"Native UI Stream {uuid.uuid4().hex[:6]}"

    try:
        controller.show()
        controller.activate()

        controller.submit_request(f"build a web tictac game called {project_name}")
        _wait_for_request(controller)
        controller.submit_request("please run the game you created")
        _wait_for_request(controller)

        response_text = controller.dashboard.response_view.toPlainText()
        popup_text = controller.task_popup.body_view.toPlainText()

        _assert(project_name in response_text, "dashboard missing project name")
        _assert("Command: " in popup_text, "popup missing executed command")
        _assert("run_project.py" in popup_text, "popup missing run_project command")
        _assert("Folder: " in popup_text, "popup missing command folder")
        _assert(
            "launched project at " in popup_text or "launch target " in popup_text or "Browser target: " in popup_text,
            "popup missing launch output",
        )
        _assert("Pilot [dev] accepted:" in popup_text, "popup missing worker acceptance line")
        print("[PASS] Native UI shows worker command execution details")
        logger.pass_step("native_ui_command_stream")
    except Exception as exc:
        logger.fail_step("native_ui_command_stream", str(exc))
        failures.append(f"Native UI command stream failed: {exc}")
    finally:
        controller.idle_window.close()
        controller.dashboard.close()
        controller.task_popup.close()
        controller.orb.close()
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Native UI command stream live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All native UI command stream checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
