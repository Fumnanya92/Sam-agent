"""Live test for the Sam v2 supervisor architecture foundation."""

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
from sam_v2.supervisor import ProjectProfile, SupervisorController, SupervisorRequest, WorkflowBridge


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Supervisor Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_supervisor_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_supervisor_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "supervisor_live.db"
    project_dir = tmp_dir / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    test_script = project_dir / "run_tests.py"
    test_script.write_text("print('tests passed')\n", encoding="utf-8")
    build_script = project_dir / "build_project.py"
    build_script.write_text("print('build passed')\n", encoding="utf-8")
    cmd_script = project_dir / "run_code.py"
    cmd_script.write_text("print('code path passed')\n", encoding="utf-8")

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        profile = ProjectProfile(
            project_id="demo",
            root_path=project_dir,
            test_command=[sys.executable, str(test_script)],
            build_command=[sys.executable, str(build_script)],
            default_branch="main",
            stack="python",
        )

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(profile)

            test_result = supervisor.execute(
                SupervisorRequest(
                    goal="Run tests for demo project",
                    task_kind="test",
                    project_id="demo",
                )
            )
            _assert(test_result.ok, "supervisor test execution failed")
            _assert(test_result.metadata["worker_type"] == "test", "test worker type mismatch")

            build_result = supervisor.execute(
                SupervisorRequest(
                    goal="Build the demo project",
                    task_kind="build",
                    project_id="demo",
                )
            )
            _assert(build_result.ok, "supervisor build execution failed")
            _assert(build_result.metadata["role_name"] == "dev-lead", "build role mismatch")
            print("[PASS] Supervisor project test/build routing")
        except Exception as exc:
            logger.fail_step("supervisor_project_routing", str(exc))
            failures.append(f"Supervisor project routing test failed: {exc}")
        else:
            logger.pass_step("supervisor_project_routing")

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            command_result = supervisor.execute(
                SupervisorRequest(
                    goal="Run command: " + f"{sys.executable} {cmd_script}",
                    task_kind="command",
                )
            )
            _assert(command_result.ok, "supervisor command execution failed")
            _assert(command_result.metadata["role_name"] == "system-admin", "command role mismatch")
            print("[PASS] Supervisor generic command routing")
        except Exception as exc:
            logger.fail_step("supervisor_command_routing", str(exc))
            failures.append(f"Supervisor command routing test failed: {exc}")
        else:
            logger.pass_step("supervisor_command_routing")

        try:
            governed_bridge = WorkflowBridge(
                db_path=db_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["execute_command"])
                ),
                approval_manager=ApprovalManager(db_path),
            )
            governed = SupervisorController(governed_bridge)
            governed.register_project(profile)
            gated_result = governed.execute(
                SupervisorRequest(
                    goal="Run tests for demo project with approval",
                    task_kind="test",
                    project_id="demo",
                )
            )
            _assert(gated_result.status == "needs_approval", "supervisor approval gating did not trigger")
            _assert("approval_id" in gated_result.metadata, "supervisor approval id missing")
            print("[PASS] Supervisor approval-aware execution")
        except Exception as exc:
            logger.fail_step("supervisor_approval_gating", str(exc))
            failures.append(f"Supervisor approval test failed: {exc}")
        else:
            logger.pass_step("supervisor_approval_gating")

        try:
            missing_project = SupervisorController(WorkflowBridge(db_path=db_path))
            missing_result = missing_project.execute(
                SupervisorRequest(
                    goal="Run tests for missing project",
                    task_kind="test",
                    project_id="unknown",
                )
            )
            _assert(not missing_result.ok, "missing project should fail")
            _assert(missing_result.error_type.value == "missing_capability", "missing project error type mismatch")
            print("[PASS] Supervisor missing project failure path")
        except Exception as exc:
            logger.fail_step("supervisor_missing_project", str(exc))
            failures.append(f"Supervisor missing project test failed: {exc}")
        else:
            logger.pass_step("supervisor_missing_project")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Supervisor live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All supervisor live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
