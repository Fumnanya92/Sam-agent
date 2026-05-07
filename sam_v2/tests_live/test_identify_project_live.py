"""Real project identification validation for Sam v2."""

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
    print("=== Sam v2 Identify Project Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_identify_project_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_identify_project_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "identify_project_live.db"
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

        records = [
            ProjectRecord(
                project_id="guest-welcome-attendance-app",
                name="Guest Welcome Attendance App",
                root_path=str(GUEST_WELCOME_ROOT),
                stack="flutter + supabase",
            ),
            ProjectRecord(
                project_id="doc-to-pptx",
                name="doc_to_pptx",
                root_path=str(DOC_TO_PPTX_ROOT),
                stack="python",
            ),
            ProjectRecord(
                project_id="focusflow-flutter",
                name="focusflow_flutter",
                root_path=str(FOCUSFLOW_ROOT),
                stack="flutter",
                test_command=["flutter", "test"],
                build_command=["flutter", "build", "apk", "--debug"],
            ),
            ProjectRecord(
                project_id="focusflow-docs",
                name="focusflow_docs",
                root_path=str(REPO_ROOT / "sam_v2" / "docs"),
                stack="markdown",
            ),
        ]
        for record in records:
            register_result = project_registry.register(record)
            _assert(register_result.ok, f"project registration failed for {record.project_id}: {register_result.error_message}")

        try:
            exact_result = runtime.handle_text("identify project doc_to_pptx")
            _assert(exact_result.ok, "exact project identification failed")
            _assert(exact_result.metadata.get("project_id") == "doc-to-pptx", "exact project id mismatch")
            _assert(Path(exact_result.metadata.get("root_path", "")).resolve() == DOC_TO_PPTX_ROOT.resolve(), "exact project path mismatch")
            print("[PASS] Exact project identification")
        except Exception as exc:
            logger.fail_step("exact_project_identification", str(exc))
            failures.append(f"Exact project identification failed: {exc}")
        else:
            logger.pass_step("exact_project_identification")

        try:
            partial_result = runtime.handle_text("identify project guest")
            _assert(partial_result.ok, "partial project identification failed")
            _assert(partial_result.metadata.get("project_id") == "guest-welcome-attendance-app", "partial project id mismatch")
            _assert(partial_result.metadata.get("stack") == "flutter + supabase", "partial project stack mismatch")
            print("[PASS] Partial project identification")
        except Exception as exc:
            logger.fail_step("partial_project_identification", str(exc))
            failures.append(f"Partial project identification failed: {exc}")
        else:
            logger.pass_step("partial_project_identification")

        try:
            ambiguous_result = runtime.handle_text("identify project focusflow")
            _assert(not ambiguous_result.ok, "ambiguous project identification should fail")
            _assert(ambiguous_result.next_action == "ask_user", "ambiguous project next action mismatch")
            matches = ambiguous_result.metadata.get("matches", [])
            _assert("focusflow_flutter" in matches, "ambiguous matches missing focusflow_flutter")
            _assert("focusflow_docs" in matches, "ambiguous matches missing focusflow_docs")
            print("[PASS] Ambiguous project identification asks for clarification")
        except Exception as exc:
            logger.fail_step("ambiguous_project_identification", str(exc))
            failures.append(f"Ambiguous project identification failed: {exc}")
        else:
            logger.pass_step("ambiguous_project_identification")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Identify project live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All identify project live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
