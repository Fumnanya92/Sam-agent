"""Real external repo inspection validation for Sam v2."""

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

FOCUSFLOW_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\focusflow_flutter")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 External Repo Inspection Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_external_repo_inspection_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_external_repo_inspection_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "external_repo_inspection_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        _assert(FOCUSFLOW_ROOT.exists(), f"missing project path: {FOCUSFLOW_ROOT}")

        project_registry = ProjectRegistry(projects_path)
        register_result = project_registry.register(
            ProjectRecord(
                project_id="focusflow-flutter",
                name="focusflow_flutter",
                root_path=str(FOCUSFLOW_ROOT),
                stack="flutter",
                test_command=["flutter", "test"],
                build_command=["flutter", "build", "apk", "--debug"],
                active_branch="main",
                important_files=["pubspec.yaml", "README.md"],
            )
        )
        _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )

        try:
            result = runtime.handle_text("inspect project focusflow")
            _assert(result.ok, "external repo inspection failed")
            _assert(result.metadata.get("intent") == "inspect_project_repo", "inspection intent mismatch")
            _assert(result.metadata.get("project_id") == "focusflow-flutter", "project id mismatch")
            _assert(result.metadata.get("branch") == "main", "branch mismatch")
            _assert(result.metadata.get("is_clean") is False, "expected dirty working tree")
            changed_files = result.metadata.get("changed_files", [])
            _assert(isinstance(changed_files, list) and len(changed_files) >= 1, "changed files missing")
            _assert("pubspec.yaml" in result.metadata.get("important_file_samples", {}), "pubspec sample missing")
            _assert("README.md" in result.metadata.get("important_file_samples", {}), "README sample missing")
            _assert(".git" in result.metadata.get("top_level_entries", []), "top-level repo entries missing .git")
            print("[PASS] External repo inspection through runtime path")
        except Exception as exc:
            logger.fail_step("external_repo_inspection", str(exc))
            failures.append(f"External repo inspection failed: {exc}")
        else:
            logger.pass_step("external_repo_inspection")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] External repo inspection live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All external repo inspection live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
