"""Real runtime git-state inspection validation for Sam v2."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.tools import SafeLocalTools


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Git State Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_git_state_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_git_state_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "git_state_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        tools = SafeLocalTools()
        git_result, snapshot = tools.inspect_git_state(REPO_ROOT)
        _assert(git_result.ok and snapshot is not None, f"git inspection bootstrap failed: {git_result.error_message}")

        project_registry = ProjectRegistry(projects_path)
        register_result = project_registry.register(
            ProjectRecord(
                project_id="sam-agent",
                name="Sam-agent",
                root_path=str(REPO_ROOT),
                stack="python",
                active_branch=snapshot.branch,
            )
        )
        _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )

        try:
            result = runtime.handle_text("inspect git state for project Sam-agent")
            _assert(result.ok, "runtime git-state inspection failed")
            _assert(result.metadata.get("intent") == "inspect_git_state", "git-state intent mismatch")
            _assert(result.metadata.get("project_id") == "sam-agent", "project id mismatch")
            _assert(result.metadata.get("branch") == "rebuild/sam-clean-v2", "branch mismatch")
            _assert(isinstance(result.metadata.get("is_clean"), bool), "missing clean/dirty flag")
            _assert(isinstance(result.metadata.get("changed_files"), list), "changed files missing")
            _assert(isinstance(result.metadata.get("staged_files"), list), "staged files missing")
            _assert(isinstance(result.metadata.get("unstaged_files"), list), "unstaged files missing")
            _assert(isinstance(result.metadata.get("untracked_files"), list), "untracked files missing")
            print("[PASS] Runtime git state inspection on registered project")
        except Exception as exc:
            logger.fail_step("runtime_git_state_inspection", str(exc))
            failures.append(f"Runtime git state inspection failed: {exc}")
        else:
            logger.pass_step("runtime_git_state_inspection")

        try:
            missing_result = runtime.handle_text("inspect git state for project MissingProject")
            _assert(not missing_result.ok, "missing project git-state inspection should fail")
            _assert(missing_result.next_action == "ask_user", "missing project next action mismatch")
            print("[PASS] Missing project git-state inspection handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_project_git_state", str(exc))
            failures.append(f"Missing project git-state inspection failed: {exc}")
        else:
            logger.pass_step("missing_project_git_state")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Git state runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All git state runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
