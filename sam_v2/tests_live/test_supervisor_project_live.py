"""Real project execution validation for the Sam v2 supervisor."""

from __future__ import annotations

import sqlite3
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
from sam_v2.supervisor import ProjectProfile, SupervisorController, SupervisorRequest, WorkflowBridge
from sam_v2.tools import SafeLocalTools


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Supervisor Project Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_supervisor_project_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_supervisor_project_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "supervisor_project_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        tools = SafeLocalTools()
        git_result, snapshot = tools.inspect_git_state(REPO_ROOT)
        _assert(git_result.ok and snapshot is not None, f"repo git inspection failed: {git_result.error_message}")

        profile = ProjectProfile(
            project_id="sam-agent",
            root_path=REPO_ROOT,
            test_command=[sys.executable, "-u", "sam_v2/tests_live/test_runtime_live.py"],
            build_command=[],
            default_branch=snapshot.branch,
            stack="python",
        )

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(profile)
            test_result = supervisor.execute(
                SupervisorRequest(
                    goal="Run tests for Sam-agent",
                    task_kind="test",
                    project_id="sam-agent",
                )
            )
            _assert(test_result.ok, f"real project test execution failed: {test_result.error_message}")
            _assert(test_result.metadata.get("worker_type") == "test", "worker type mismatch")
            with sqlite3.connect(db_path) as connection:
                row = connection.execute(
                    """
                    SELECT event_type, actor, summary
                    FROM audit_events
                    WHERE event_type = 'worker_command_executed'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
            _assert(row is not None, "worker audit event missing")
            _assert(row[0] == "worker_command_executed", "unexpected audit event type")
            _assert("sam_v2.workers.test" in row[1], "unexpected audit actor")
            print("[PASS] Real project test execution through supervisor")
        except Exception as exc:
            logger.fail_step("real_project_test_execution", str(exc))
            failures.append(f"Real project test execution failed: {exc}")
        else:
            logger.pass_step("real_project_test_execution")

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(profile)
            build_result = supervisor.execute(
                SupervisorRequest(
                    goal="Build Sam-agent",
                    task_kind="build",
                    project_id="sam-agent",
                )
            )
            _assert(not build_result.ok, "missing build command should fail")
            _assert(build_result.next_action == "ask_user", "missing build command next action mismatch")
            print("[PASS] Missing build command handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_build_command", str(exc))
            failures.append(f"Missing build command handling failed: {exc}")
        else:
            logger.pass_step("missing_build_command")

        try:
            governed_supervisor = SupervisorController(
                WorkflowBridge(
                    db_path=db_path,
                    authority_engine=AuthorityEngine(
                        AuthorityConfig(default_level=3, governed_categories=["execute_command"])
                    ),
                    approval_manager=ApprovalManager(db_path),
                )
            )
            governed_supervisor.register_project(profile)
            gated_result = governed_supervisor.execute(
                SupervisorRequest(
                    goal="Run tests for Sam-agent with approval",
                    task_kind="test",
                    project_id="sam-agent",
                )
            )
            _assert(gated_result.status == "needs_approval", "approval gating did not trigger")
            _assert("approval_id" in gated_result.metadata, "approval id missing")
            print("[PASS] Real project execution approval gating")
        except Exception as exc:
            logger.fail_step("real_project_approval_gating", str(exc))
            failures.append(f"Real project approval gating failed: {exc}")
        else:
            logger.pass_step("real_project_approval_gating")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Supervisor project live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All supervisor project live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
