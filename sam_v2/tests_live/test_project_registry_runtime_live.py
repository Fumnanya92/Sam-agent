"""Real project registry and identification validation through the runtime path."""

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
    print("=== Sam v2 Project Registry Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_registry_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_project_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "project_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        tools = SafeLocalTools()
        git_result, snapshot = tools.inspect_git_state(REPO_ROOT)
        _assert(git_result.ok and snapshot is not None, f"repo git inspection failed: {git_result.error_message}")

        project_registry = ProjectRegistry(projects_path)

        try:
            register_result = project_registry.register(
                ProjectRecord(
                    project_id="sam-agent",
                    name="Sam-agent",
                    root_path=str(REPO_ROOT),
                    stack="python",
                    test_command=["python", "-u", "sam_v2/tests_live/test_runtime_live.py"],
                    build_command=[],
                    active_branch=snapshot.branch,
                    important_files=["sam_v2/core/runtime.py", "sam_v2/intents/router.py"],
                )
            )
            _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

            list_result = runtime.handle_text("list my projects")
            _assert(list_result.ok, "runtime project listing failed")
            _assert("Sam-agent" in list_result.metadata.get("projects", []), "registered project missing from listing")
            print("[PASS] Runtime project listing uses registry")
        except Exception as exc:
            logger.fail_step("runtime_project_listing", str(exc))
            failures.append(f"Runtime project listing failed: {exc}")
        else:
            logger.pass_step("runtime_project_listing")

        try:
            detail_result = runtime.handle_text("show project Sam-agent")
            _assert(detail_result.ok, "runtime project detail request failed")
            _assert(detail_result.metadata.get("intent") == "project_details", "project detail intent mismatch")
            _assert(detail_result.metadata.get("project_id") == "sam-agent", "project id mismatch")
            _assert(detail_result.metadata.get("active_branch") == "rebuild/sam-clean-v2", "project branch mismatch")
            _assert("test_runtime_live.py" in " ".join(detail_result.metadata.get("test_command", [])), "project test command missing")
            print("[PASS] Runtime project identification and details")
        except Exception as exc:
            logger.fail_step("runtime_project_details", str(exc))
            failures.append(f"Runtime project details failed: {exc}")
        else:
            logger.pass_step("runtime_project_details")

        try:
            missing_result = runtime.handle_text("show project MissingProject")
            _assert(not missing_result.ok, "missing project should fail")
            _assert(missing_result.next_action == "ask_user", "missing project next action mismatch")
            print("[PASS] Missing project handled truthfully")
        except Exception as exc:
            logger.fail_step("runtime_missing_project", str(exc))
            failures.append(f"Missing project handling failed: {exc}")
        else:
            logger.pass_step("runtime_missing_project")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project registry runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All project registry runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
