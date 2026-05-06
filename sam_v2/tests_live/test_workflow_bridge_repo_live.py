"""Real in-repo validation for workflow bridge failure and retry behavior."""

from __future__ import annotations

import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.supervisor import ExecutionPlan, ExecutionStep, WorkflowBridge
from sam_v2.workers import CommandSpec


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Workflow Bridge Repo Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_workflow_bridge_repo_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workflow_bridge_repo_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "workflow_bridge_repo_live.db"

    flaky_script = tmp_dir / "repo_flaky_once.py"
    flaky_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"flag = Path(r'{(tmp_dir / 'repo_retry_once.flag').as_posix()}')",
                "if not flag.exists():",
                "    flag.write_text('created', encoding='utf-8')",
                "    raise SystemExit('first run fails on purpose')",
                "print('second run succeeds from repo path')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    always_fail_script = tmp_dir / "repo_always_fail.py"
    always_fail_script.write_text(
        "raise SystemExit('repo hard fail for bridge classification')\n",
        encoding="utf-8",
    )

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            bridge = WorkflowBridge(db_path=db_path)
            retry_plan = ExecutionPlan(
                plan_id="repo-plan-retry",
                goal="Prove workflow bridge retry behavior from repo root",
                steps=[
                    ExecutionStep(
                        step_id="step-pass",
                        title="Run real runtime live test from repo root",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="repo_runtime_live",
                            worker_type="test",
                            command=[sys.executable, "-u", "sam_v2/tests_live/test_runtime_live.py"],
                            description="Run the real runtime live test from the Sam-agent repo root.",
                            cwd=REPO_ROOT,
                            timeout_seconds=120,
                        ),
                    ),
                    ExecutionStep(
                        step_id="step-retry",
                        title="Retry a flaky repo-root command once",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="repo_retry_once",
                            worker_type="test",
                            command=[sys.executable, str(flaky_script)],
                            description="Run a flaky command from the Sam-agent repo root and retry once.",
                            cwd=REPO_ROOT,
                        ),
                        max_attempts=2,
                    ),
                ],
            )
            retry_result = bridge.execute_plan(retry_plan)
            _assert(retry_result.ok, f"repo retry plan failed: {retry_result.error_message}")
            _assert(len(retry_result.metadata.get("completed_steps", [])) == 2, "repo retry plan did not complete both steps")
            with sqlite3.connect(db_path) as connection:
                completed_rows = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE event_type = 'worker_command_executed'
                    """
                ).fetchone()
            _assert(completed_rows is not None and completed_rows[0] >= 2, "expected audit rows for completed repo-root commands")
            print("[PASS] Workflow bridge retry path from repo root")
        except Exception as exc:
            logger.fail_step("workflow_bridge_repo_retry", str(exc))
            failures.append(f"Workflow bridge repo retry test failed: {exc}")
        else:
            logger.pass_step("workflow_bridge_repo_retry")

        try:
            bridge = WorkflowBridge(db_path=db_path)
            fail_plan = ExecutionPlan(
                plan_id="repo-plan-fail",
                goal="Prove workflow bridge failure classification from repo root",
                steps=[
                    ExecutionStep(
                        step_id="step-fail",
                        title="Run an always-failing command from repo root",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="repo_always_fail",
                            worker_type="test",
                            command=[sys.executable, str(always_fail_script)],
                            description="Run an always-failing command from the Sam-agent repo root.",
                            cwd=REPO_ROOT,
                        ),
                        max_attempts=2,
                    )
                ],
            )
            fail_result = bridge.execute_plan(fail_plan)
            _assert(not fail_result.ok, "repo failure plan should not succeed")
            _assert(fail_result.status == "failed", "repo failure plan status mismatch")
            _assert(fail_result.error_type == "test_failed", "repo failure plan error type mismatch")
            _assert(fail_result.metadata.get("attempt") == 2, "repo failure plan should stop after second attempt")
            print("[PASS] Workflow bridge failure classification from repo root")
        except Exception as exc:
            logger.fail_step("workflow_bridge_repo_failure_classification", str(exc))
            failures.append(f"Workflow bridge repo failure classification failed: {exc}")
        else:
            logger.pass_step("workflow_bridge_repo_failure_classification")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workflow bridge repo live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All workflow bridge repo live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
