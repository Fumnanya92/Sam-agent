"""Real approval-before-push validation for Sam v2."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import ApprovalManager
from sam_v2.core import SamRuntime
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.tools import SafeLocalTools


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Push Approval Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_push_approval_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_push_approval_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "push_approval_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        tools = SafeLocalTools()
        git_result, snapshot = tools.inspect_git_state(REPO_ROOT)
        _assert(git_result.ok and snapshot is not None, f"repo git inspection failed: {git_result.error_message}")

        project_registry = ProjectRegistry(projects_path)
        register_result = project_registry.register(
            ProjectRecord(
                project_id="sam-agent",
                name="Sam-agent",
                root_path=str(REPO_ROOT),
                stack="python",
                test_command=["python", "-u", "sam_v2/tests_live/test_runtime_live.py"],
                build_command=[],
                active_branch=snapshot.branch,
                important_files=["sam_v2/intents/router.py", "sam_v2/approvals/manager.py"],
            )
        )
        _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

        approval_manager = ApprovalManager(db_path)

        try:
            list_result, projects = project_registry.list_projects()
            _assert(list_result.ok, "project registry listing failed")
            _assert(any(project.project_id == "sam-agent" for project in projects), "registered project missing")
            print("[PASS] Real repo context prepared")
        except Exception as exc:
            logger.fail_step("real_repo_context", str(exc))
            failures.append(f"Real repo context failed: {exc}")
        else:
            logger.pass_step(
                "real_repo_context",
                {"project_count": len(projects), "branch": snapshot.branch},
            )

        try:
            result = runtime.handle_text("Sam, push the changes")
            _assert(result.status == "needs_approval", "push request should require approval")
            _assert(result.error_type == ErrorType.MISSING_PERMISSION, "push request error type mismatch")
            _assert(result.next_action == "request_approval", "push request next action mismatch")
            approval_id = result.metadata.get("approval_id")
            _assert(isinstance(approval_id, str) and approval_id.strip(), "approval id missing")

            approval_result, approval = approval_manager.get(approval_id)
            _assert(approval_result.ok and approval is not None, "approval request was not stored")
            _assert(approval.status == "pending", "approval request should stay pending")
            _assert(approval.tool_name == "git.push", "approval tool name mismatch")
            _assert(approval.action_category == "execute_command", "approval action category mismatch")
            _assert("push" in approval.reason.lower(), "approval reason should mention push")
            _assert(approval.executed_at is None, "push approval should not be marked executed")
            _assert(approval.execution_result is None, "push approval should have no execution result")
            print("[PASS] Push request creates pending approval before execution")
        except Exception as exc:
            logger.fail_step("push_request_needs_approval", str(exc))
            failures.append(f"Push approval gate failed: {exc}")
        else:
            logger.pass_step(
                "push_request_needs_approval",
                {
                    "approval_id": approval.id,
                    "status": result.status,
                    "next_action": result.next_action,
                },
            )

        try:
            pending_result, pending = approval_manager.list_pending()
            _assert(pending_result.ok, "pending approvals listing failed")
            _assert(any(item.id == approval.id for item in pending), "push approval missing from pending list")
            print("[PASS] Push approval remains queued and unexecuted")
        except Exception as exc:
            logger.fail_step("push_approval_pending_queue", str(exc))
            failures.append(f"Push approval queue validation failed: {exc}")
        else:
            logger.pass_step(
                "push_approval_pending_queue",
                {"pending_count": len(pending)},
            )
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Push approval live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All push approval live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
