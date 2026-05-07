"""Real multi-project registry validation through the runtime path."""

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

GUEST_WELCOME_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\Guest-Welcome-attendance-app")
DOC_TO_PPTX_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\doc_to_pptx")
FOCUSFLOW_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\focusflow_flutter")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Multi-Project Registry Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_multi_project_registry_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_multi_project_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "multi_project_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        _assert(GUEST_WELCOME_ROOT.exists(), f"missing project path: {GUEST_WELCOME_ROOT}")
        _assert(DOC_TO_PPTX_ROOT.exists(), f"missing project path: {DOC_TO_PPTX_ROOT}")
        _assert(FOCUSFLOW_ROOT.exists(), f"missing project path: {FOCUSFLOW_ROOT}")

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        project_registry = ProjectRegistry(projects_path)

        try:
            records = [
                ProjectRecord(
                    project_id="guest-welcome-attendance-app",
                    name="Guest Welcome Attendance App",
                    root_path=str(GUEST_WELCOME_ROOT),
                    stack="flutter + supabase",
                    test_command=[],
                    build_command=[],
                ),
                ProjectRecord(
                    project_id="doc-to-pptx",
                    name="doc_to_pptx",
                    root_path=str(DOC_TO_PPTX_ROOT),
                    stack="python",
                    test_command=[],
                    build_command=[],
                ),
                ProjectRecord(
                    project_id="focusflow-flutter",
                    name="focusflow_flutter",
                    root_path=str(FOCUSFLOW_ROOT),
                    stack="flutter",
                    test_command=["flutter", "test"],
                    build_command=["flutter", "build", "apk", "--debug"],
                ),
            ]
            for record in records:
                register_result = project_registry.register(record)
                _assert(register_result.ok, f"project registration failed for {record.project_id}: {register_result.error_message}")

            list_result = runtime.handle_text("list my projects")
            _assert(list_result.ok, "runtime project listing failed")
            _assert(list_result.metadata.get("count") == 3, "project count mismatch")
            names = list_result.metadata.get("projects", [])
            _assert("Guest Welcome Attendance App" in names, "guest welcome project missing")
            _assert("doc_to_pptx" in names, "doc_to_pptx project missing")
            _assert("focusflow_flutter" in names, "focusflow project missing")
            print("[PASS] Runtime multi-project listing")
        except Exception as exc:
            logger.fail_step("runtime_multi_project_listing", str(exc))
            failures.append(f"Runtime multi-project listing failed: {exc}")
        else:
            logger.pass_step("runtime_multi_project_listing")

        try:
            exact_result = runtime.handle_text("show project doc_to_pptx")
            _assert(exact_result.ok, "exact project detail request failed")
            _assert(exact_result.metadata.get("project_id") == "doc-to-pptx", "exact project id mismatch")
            _assert(exact_result.metadata.get("stack") == "python", "exact project stack mismatch")
            _assert(Path(exact_result.metadata.get("root_path", "")).resolve() == DOC_TO_PPTX_ROOT.resolve(), "exact project path mismatch")
            print("[PASS] Runtime exact project selection")
        except Exception as exc:
            logger.fail_step("runtime_exact_project_selection", str(exc))
            failures.append(f"Runtime exact project selection failed: {exc}")
        else:
            logger.pass_step("runtime_exact_project_selection")

        try:
            partial_result = runtime.handle_text("show project focusflow")
            _assert(partial_result.ok, "partial project detail request failed")
            _assert(partial_result.metadata.get("project_id") == "focusflow-flutter", "partial project id mismatch")
            _assert(partial_result.metadata.get("stack") == "flutter", "partial project stack mismatch")
            _assert("flutter" in " ".join(partial_result.metadata.get("test_command", [])), "partial project test command missing")
            print("[PASS] Runtime partial project selection")
        except Exception as exc:
            logger.fail_step("runtime_partial_project_selection", str(exc))
            failures.append(f"Runtime partial project selection failed: {exc}")
        else:
            logger.pass_step("runtime_partial_project_selection")

        try:
            missing_result = runtime.handle_text("show project Unknown Workspace")
            _assert(not missing_result.ok, "missing project should fail")
            _assert(missing_result.next_action == "ask_user", "missing project next action mismatch")
            print("[PASS] Unknown project handled truthfully")
        except Exception as exc:
            logger.fail_step("runtime_unknown_project", str(exc))
            failures.append(f"Unknown project handling failed: {exc}")
        else:
            logger.pass_step("runtime_unknown_project")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Multi-project registry runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All multi-project registry runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
