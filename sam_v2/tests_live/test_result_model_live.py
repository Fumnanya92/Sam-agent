"""Cross-subsystem validation for SamResult and ErrorType behavior."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.core import SamRuntime
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import create_task, init_storage
from sam_v2.storage.models import TaskRecord
from sam_v2.workers import CommandSpec, ToolingWorker


ATTENDANCE_APP_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\attendance-app")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Result Model Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_result_model_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_result_model_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "result_model_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    bad_session_dir = tmp_dir / "session_as_directory"
    bad_session_dir.mkdir(parents=True, exist_ok=True)
    fail_script = tmp_dir / "result_fail.py"
    fail_script.write_text("raise SystemExit('result model worker failure path')\n", encoding="utf-8")

    try:
        try:
            init_result = init_storage(db_path)
            _assert(init_result.ok, f"storage init failed: {init_result.error_message}")
            _assert(init_result.status == "success", "storage init status mismatch")
            _assert(init_result.next_action == "stop", "storage init next_action mismatch")
            _assert(init_result.error_type is None, "storage init should not have an error type")
            print("[PASS] Success result shape")
        except Exception as exc:
            logger.fail_step("success_result_shape", str(exc))
            failures.append(f"Success result shape failed: {exc}")
        else:
            logger.pass_step("success_result_shape")

        try:
            bad_task = TaskRecord(title=None)  # type: ignore[arg-type]
            invalid_result, _ = create_task(db_path, bad_task)
            _assert(not invalid_result.ok, "invalid task insert should fail")
            _assert(invalid_result.status == "failed", "invalid task status mismatch")
            _assert(invalid_result.error_type == ErrorType.FILE_ACCESS_ERROR, "invalid task error type mismatch")
            _assert(invalid_result.next_action == "ask_user", "invalid task next_action mismatch")
            print("[PASS] Failed result shape")
        except Exception as exc:
            logger.fail_step("failed_result_shape", str(exc))
            failures.append(f"Failed result shape failed: {exc}")
        else:
            logger.pass_step("failed_result_shape")

        try:
            worker = ToolingWorker(db_path=db_path)
            worker_result, worker_task = worker.execute(
                CommandSpec(
                    name="result_model_fail",
                    worker_type="test",
                    command=[sys.executable, str(fail_script)],
                    description="Run an intentionally failing worker command for result-model validation.",
                    cwd=tmp_dir,
                )
            )
            _assert(not worker_result.ok, "worker failure should not succeed")
            _assert(worker_result.status == "failed", "worker failure status mismatch")
            _assert(worker_result.error_type == ErrorType.TEST_FAILED, "worker failure error type mismatch")
            _assert(worker_result.next_action == "retry", "worker failure next_action mismatch")
            _assert(worker_task.status == "failed", "worker task status mismatch")
            print("[PASS] Retryable failure result shape")
        except Exception as exc:
            logger.fail_step("retryable_failure_shape", str(exc))
            failures.append(f"Retryable failure result shape failed: {exc}")
        else:
            logger.pass_step("retryable_failure_shape")

        try:
            governed_runtime = SamRuntime(
                db_path=db_path,
                memory_path=memory_path,
                session_path=session_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["write_data"])
                ),
            )
            approval_result = governed_runtime.handle_text("create goal: Needs approval")
            _assert(approval_result.status == "needs_approval", "needs_approval status mismatch")
            _assert(approval_result.error_type == ErrorType.MISSING_PERMISSION, "needs_approval error type mismatch")
            _assert(approval_result.next_action == "request_approval", "needs_approval next_action mismatch")
            _assert("approval_id" in approval_result.metadata, "approval id missing")
            print("[PASS] Needs-approval result shape")
        except Exception as exc:
            logger.fail_step("needs_approval_shape", str(exc))
            failures.append(f"Needs-approval result shape failed: {exc}")
        else:
            logger.pass_step("needs_approval_shape")

        try:
            _assert(ATTENDANCE_APP_ROOT.exists(), f"attendance-app path missing: {ATTENDANCE_APP_ROOT}")
            blocked_worker = ToolingWorker(db_path=db_path)
            blocked_result, blocked_task = blocked_worker.execute(
                CommandSpec(
                    name="attendance_flutter_test",
                    worker_type="test",
                    command=["flutter", "test", r"test\attendance_model_test.dart"],
                    description="Attempt external attendance-app Flutter test from worker path.",
                    cwd=ATTENDANCE_APP_ROOT,
                    timeout_seconds=60,
                )
            )
            _assert(blocked_result.status == "blocked", "blocked result status mismatch")
            _assert(blocked_result.error_type == ErrorType.MISSING_PERMISSION, "blocked result error type mismatch")
            _assert(blocked_result.next_action == "ask_user", "blocked result next_action mismatch")
            _assert(blocked_task.status == "failed", "blocked worker task should end failed in monitor")
            print("[PASS] Blocked result shape")
        except Exception as exc:
            logger.fail_step("blocked_shape", str(exc))
            failures.append(f"Blocked result shape failed: {exc}")
        else:
            logger.pass_step("blocked_shape")

        try:
            partial_runtime = SamRuntime(
                db_path=db_path,
                memory_path=memory_path,
                session_path=bad_session_dir,
            )
            partial_result = partial_runtime.handle_text("what can you do")
            _assert(partial_result.status == "partial", "partial result status mismatch")
            _assert(partial_result.error_type == ErrorType.FILE_ACCESS_ERROR, "partial result error type mismatch")
            _assert(partial_result.next_action == "retry", "partial result next_action mismatch")
            _assert(partial_result.metadata.get("intent") == "capabilities", "partial result intent mismatch")
            print("[PASS] Partial result shape")
        except Exception as exc:
            logger.fail_step("partial_shape", str(exc))
            failures.append(f"Partial result shape failed: {exc}")
        else:
            logger.pass_step("partial_shape")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Result model live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All result model live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
