"""Live test for the Sam v2 tooling worker foundation."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event, init_storage
from sam_v2.workers import CommandSpec, ToolingWorker, WorkerQueue, worker_monitor


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Workers Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_workers_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workers_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "workers_live.db"
    hello_script = tmp_dir / "hello_worker.py"
    fail_script = tmp_dir / "fail_worker.py"
    hello_script.write_text("print('worker hello')\n", encoding="utf-8")
    fail_script.write_text("raise SystemExit('worker fail path')\n", encoding="utf-8")

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            worker = ToolingWorker(db_path=db_path)
            queue = WorkerQueue(worker)
            queue_result = queue.submit(
                CommandSpec(
                    name="python_smoke",
                    worker_type="code",
                    command=[sys.executable, str(hello_script)],
                    description="Run a tiny Python smoke script.",
                    cwd=tmp_dir,
                )
            )
            _assert(queue_result.ok, "queue submit failed")
            run_result = queue.run_next()
            _assert(run_result.ok, "queued worker run failed")
            _assert(run_result.metadata["task_status"] == "done", "worker task did not finish done")
            _assert("worker hello" in run_result.metadata["stdout"], "worker stdout mismatch")
            task = worker_monitor.get_task(run_result.metadata["task_id"])
            _assert(task is not None and task.status == "done", "monitor task state mismatch")
            print("[PASS] Worker queue, command execution, and monitor tracking")
        except Exception as exc:
            logger.fail_step("worker_queue_and_monitor", str(exc))
            failures.append(f"Worker queue/monitor test failed: {exc}")
        else:
            logger.pass_step("worker_queue_and_monitor")

        try:
            audit_result, audit_event = fetch_audit_event(db_path, int(run_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "worker audit event missing")
            _assert("tiny Python smoke script" in audit_event.summary, "worker audit summary mismatch")
            print("[PASS] Worker audit logging")
        except Exception as exc:
            logger.fail_step("worker_audit_logging", str(exc))
            failures.append(f"Worker audit test failed: {exc}")
        else:
            logger.pass_step("worker_audit_logging")

        try:
            test_worker = ToolingWorker(db_path=db_path)
            fail_result, fail_task = test_worker.execute(
                CommandSpec(
                    name="python_failure",
                    worker_type="test",
                    command=[sys.executable, str(fail_script)],
                    description="Run an intentionally failing Python test script.",
                    cwd=tmp_dir,
                )
            )
            _assert(not fail_result.ok, "failing worker should not succeed")
            _assert(fail_result.error_type.value == "test_failed", "failing test worker error type mismatch")
            _assert(fail_task.status == "failed", "failing worker task status mismatch")
            print("[PASS] Worker failure path")
        except Exception as exc:
            logger.fail_step("worker_failure_path", str(exc))
            failures.append(f"Worker failure-path test failed: {exc}")
        else:
            logger.pass_step("worker_failure_path")

        try:
            approval_manager = ApprovalManager(db_path)
            _assert(approval_manager.ensure_schema().ok, "approval schema init failed")
            governed_worker = ToolingWorker(
                db_path=db_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["execute_command"])
                ),
                approval_manager=approval_manager,
            )
            gated_result, gated_task = governed_worker.execute(
                CommandSpec(
                    name="governed_python",
                    worker_type="dev",
                    command=[sys.executable, str(hello_script)],
                    description="Run a governed command that should require approval.",
                    cwd=tmp_dir,
                )
            )
            _assert(gated_result.status == "needs_approval", "approval gating did not trigger")
            _assert("approval_id" in gated_result.metadata, "approval id missing")
            _assert(gated_task.status == "needs_approval", "task status mismatch for gated worker")
            print("[PASS] Worker approval gating")
        except Exception as exc:
            logger.fail_step("worker_approval_gating", str(exc))
            failures.append(f"Worker approval test failed: {exc}")
        else:
            logger.pass_step("worker_approval_gating")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workers live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All worker live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
