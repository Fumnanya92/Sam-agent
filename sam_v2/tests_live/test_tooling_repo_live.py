"""Real repo-root validation for Sam v2 tooling workers."""

from __future__ import annotations

import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.workers import CommandSpec, ToolingWorker, worker_monitor


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Tooling Repo Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_tooling_repo_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_tooling_repo_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "tooling_repo_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            code_worker = ToolingWorker(db_path=db_path)
            code_result, code_task = code_worker.execute(
                CommandSpec(
                    name="repo_git_branch",
                    worker_type="code",
                    command=["git", "branch", "--show-current"],
                    description="Inspect the current repo branch from the Sam-agent repo root.",
                    cwd=REPO_ROOT,
                )
            )
            _assert(code_result.ok, f"repo code worker failed: {code_result.error_message}")
            _assert(code_task.status == "done", "repo code worker task status mismatch")
            _assert("rebuild/sam-clean-v2" in code_result.metadata.get("stdout", ""), "repo branch output mismatch")
            monitor_task = worker_monitor.get_task(code_result.metadata["task_id"])
            _assert(monitor_task is not None and monitor_task.status == "done", "repo code monitor state mismatch")
            print("[PASS] Repo code worker command")
        except Exception as exc:
            logger.fail_step("repo_code_worker", str(exc))
            failures.append(f"Repo code worker test failed: {exc}")
        else:
            logger.pass_step("repo_code_worker")

        try:
            test_worker = ToolingWorker(db_path=db_path)
            test_result, test_task = test_worker.execute(
                CommandSpec(
                    name="repo_runtime_test",
                    worker_type="test",
                    command=[sys.executable, "-u", "sam_v2/tests_live/test_runtime_live.py"],
                    description="Run the real Sam v2 runtime live test from the repo root.",
                    cwd=REPO_ROOT,
                    timeout_seconds=120,
                )
            )
            _assert(test_result.ok, f"repo test worker failed: {test_result.error_message}")
            _assert(test_task.status == "done", "repo test worker task status mismatch")
            _assert("[PASS] All runtime live checks passed" in test_result.metadata.get("stdout", ""), "repo test output mismatch")
            print("[PASS] Repo test worker command")
        except Exception as exc:
            logger.fail_step("repo_test_worker", str(exc))
            failures.append(f"Repo test worker test failed: {exc}")
        else:
            logger.pass_step("repo_test_worker")

        try:
            dev_worker = ToolingWorker(db_path=db_path)
            dev_result, dev_task = dev_worker.execute(
                CommandSpec(
                    name="repo_missing_test",
                    worker_type="dev",
                    command=[sys.executable, "-u", "sam_v2/tests_live/does_not_exist.py"],
                    description="Run a missing repo test file to prove truthful failure classification.",
                    cwd=REPO_ROOT,
                )
            )
            _assert(not dev_result.ok, "repo dev failure path should not succeed")
            _assert(dev_result.error_type.value == "command_failed", "repo dev failure error type mismatch")
            _assert(dev_task.status == "failed", "repo dev failure task status mismatch")
            _assert("does_not_exist.py" in (dev_result.error_message or ""), "repo dev failure message mismatch")
            print("[PASS] Repo dev worker failure path")
        except Exception as exc:
            logger.fail_step("repo_dev_failure_path", str(exc))
            failures.append(f"Repo dev failure-path test failed: {exc}")
        else:
            logger.pass_step("repo_dev_failure_path")

        try:
            governed_worker = ToolingWorker(
                db_path=db_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["execute_command"])
                ),
                approval_manager=ApprovalManager(db_path),
            )
            gated_result, gated_task = governed_worker.execute(
                CommandSpec(
                    name="repo_git_status",
                    worker_type="dev",
                    command=["git", "status", "--short"],
                    description="Run a governed repo-root git status command.",
                    cwd=REPO_ROOT,
                )
            )
            _assert(gated_result.status == "needs_approval", "repo approval gating did not trigger")
            _assert("approval_id" in gated_result.metadata, "repo approval id missing")
            _assert(gated_task.status == "needs_approval", "repo gated task status mismatch")
            print("[PASS] Repo worker approval gating")
        except Exception as exc:
            logger.fail_step("repo_worker_approval_gating", str(exc))
            failures.append(f"Repo approval gating test failed: {exc}")
        else:
            logger.pass_step("repo_worker_approval_gating")

        try:
            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    """
                    SELECT actor, summary
                    FROM audit_events
                    WHERE event_type = 'worker_command_executed'
                    ORDER BY id ASC
                    """
                ).fetchall()
            _assert(len(rows) >= 2, "expected repo-root worker audit events")
            _assert(any("sam_v2.workers.code" in row[0] for row in rows), "missing code worker audit row")
            _assert(any("sam_v2.workers.test" in row[0] for row in rows), "missing test worker audit row")
            print("[PASS] Repo worker audit trail")
        except Exception as exc:
            logger.fail_step("repo_worker_audit_trail", str(exc))
            failures.append(f"Repo worker audit trail test failed: {exc}")
        else:
            logger.pass_step("repo_worker_audit_trail")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Tooling repo live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All tooling repo live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
