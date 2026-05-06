"""Real repo inspection validation for Sam v2."""

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
    print("=== Sam v2 Repo Inspection Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_repo_inspection_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_repo_inspection_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "repo_inspection_live.db"
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
                test_command=["python", "-u", "sam_v2/tests_live/test_runtime_live.py"],
                build_command=[],
                active_branch=snapshot.branch,
                important_files=["sam_v2/README.md", "sam_v2/core/runtime.py"],
            )
        )
        _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )

        try:
            result = runtime.handle_text("inspect project Sam-agent")
            _assert(result.ok, "runtime repo inspection failed")
            _assert(result.metadata.get("intent") == "inspect_project_repo", "inspection intent mismatch")
            _assert(result.metadata.get("project_id") == "sam-agent", "project id mismatch")
            _assert(result.metadata.get("branch") == "rebuild/sam-clean-v2", "branch mismatch")
            _assert(isinstance(result.metadata.get("top_level_entries"), list), "missing top-level entries")
            _assert("sam_v2" in result.metadata.get("top_level_entries", []), "repo root listing missing sam_v2")
            important_samples = result.metadata.get("important_file_samples", {})
            _assert("sam_v2/README.md" in important_samples, "important file sample missing")
            print("[PASS] Runtime repo inspection on registered project")
        except Exception as exc:
            logger.fail_step("runtime_repo_inspection", str(exc))
            failures.append(f"Runtime repo inspection failed: {exc}")
        else:
            logger.pass_step("runtime_repo_inspection")

        try:
            missing_result = runtime.handle_text("inspect project MissingProject")
            _assert(not missing_result.ok, "missing project inspection should fail")
            _assert(missing_result.next_action == "ask_user", "missing project next action mismatch")
            print("[PASS] Missing project repo inspection handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_project_repo_inspection", str(exc))
            failures.append(f"Missing project repo inspection failed: {exc}")
        else:
            logger.pass_step("missing_project_repo_inspection")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Repo inspection live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All repo inspection live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
