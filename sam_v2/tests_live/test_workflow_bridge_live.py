"""Live test for the Sam v2 workflow execution bridge."""

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
from sam_v2.storage.db import init_storage
from sam_v2.supervisor import ExecutionPlan, ExecutionStep, WorkflowBridge
from sam_v2.workers import CommandSpec


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Workflow Bridge Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_workflow_bridge_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workflow_bridge_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "workflow_bridge_live.db"

    hello_script = tmp_dir / "hello_bridge.py"
    hello_script.write_text("print('bridge ok')\n", encoding="utf-8")

    flaky_script = tmp_dir / "flaky_bridge.py"
    flaky_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "flag = Path('retry_once.flag')",
                "if not flag.exists():",
                "    flag.write_text('created', encoding='utf-8')",
                "    raise SystemExit('first run fails')",
                "print('second run succeeds')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            bridge = WorkflowBridge(db_path=db_path)
            plan = ExecutionPlan(
                plan_id="plan-success",
                goal="Run two safe bridge steps",
                steps=[
                    ExecutionStep(
                        step_id="step-1",
                        title="Run hello script",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="bridge_hello",
                            worker_type="code",
                            command=[sys.executable, str(hello_script)],
                            description="Run hello workflow bridge script.",
                            cwd=tmp_dir,
                        ),
                    ),
                    ExecutionStep(
                        step_id="step-2",
                        title="Retry flaky script once",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="bridge_flaky",
                            worker_type="test",
                            command=[sys.executable, str(flaky_script)],
                            description="Run flaky script that should succeed on retry.",
                            cwd=tmp_dir,
                        ),
                        max_attempts=2,
                    ),
                ],
            )
            result = bridge.execute_plan(plan)
            _assert(result.ok, "workflow bridge success plan failed")
            _assert(len(result.metadata["completed_steps"]) == 2, "completed step count mismatch")
            print("[PASS] Workflow bridge success and retry path")
        except Exception as exc:
            logger.fail_step("workflow_bridge_success_and_retry", str(exc))
            failures.append(f"Workflow bridge success/retry test failed: {exc}")
        else:
            logger.pass_step("workflow_bridge_success_and_retry")

        try:
            approval_manager = ApprovalManager(db_path)
            _assert(approval_manager.ensure_schema().ok, "approval schema init failed")
            governed_bridge = WorkflowBridge(
                db_path=db_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["execute_command"])
                ),
                approval_manager=approval_manager,
            )
            gated_plan = ExecutionPlan(
                plan_id="plan-approval",
                goal="Pause a plan for approval",
                steps=[
                    ExecutionStep(
                        step_id="step-approval",
                        title="Run governed command",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="bridge_governed",
                            worker_type="dev",
                            command=[sys.executable, str(hello_script)],
                            description="Run governed workflow bridge command.",
                            cwd=tmp_dir,
                        ),
                    )
                ],
            )
            gated_result = governed_bridge.execute_plan(gated_plan)
            _assert(gated_result.status == "needs_approval", "workflow bridge approval did not trigger")
            _assert("approval_id" in gated_result.metadata, "approval id missing from workflow bridge result")
            print("[PASS] Workflow bridge approval gating")
        except Exception as exc:
            logger.fail_step("workflow_bridge_approval_gating", str(exc))
            failures.append(f"Workflow bridge approval test failed: {exc}")
        else:
            logger.pass_step("workflow_bridge_approval_gating")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workflow bridge live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All workflow bridge live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
