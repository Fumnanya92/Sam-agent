"""Real validation for external project worker blocking behavior."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.workers import CommandSpec, ToolingWorker

ATTENDANCE_APP = Path(r"C:\Users\DELL.COM\Desktop\Darey\attendance-app")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 External Project Worker Blocker Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_external_project_worker_blocker_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_external_blocker_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "external_worker_blocker_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            worker = ToolingWorker(db_path=db_path)
            result, task = worker.execute(
                CommandSpec(
                    name="attendance_external_flutter_test",
                    worker_type="test",
                    command=[r"C:\flutter\bin\flutter.bat", "test", r"test\attendance_model_test.dart"],
                    description="Run attendance-app test through worker on external repo path.",
                    cwd=ATTENDANCE_APP,
                    timeout_seconds=60,
                )
            )
            _assert(result.status == "blocked", "external project execution should be blocked")
            _assert(result.error_type == ErrorType.MISSING_PERMISSION, "unexpected error type")
            _assert(task.status == "failed", "worker task status mismatch")
            print("[PASS] External project execution blocks fast with truthful permission message")
        except Exception as exc:
            logger.fail_step("external_project_blocked_fast", str(exc))
            failures.append(f"External project blocker test failed: {exc}")
        else:
            logger.pass_step("external_project_blocked_fast")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] External project worker blocker live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All external project worker blocker checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
