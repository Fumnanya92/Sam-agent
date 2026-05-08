"""Live test for Sam v2 workspace duplicate inspection and cleanup."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    print("=== Sam v2 Workspace Cleanup Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_workspace_cleanup_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workspace_cleanup_{uuid.uuid4().hex[:8]}"
    workspace_root = tmp_dir / "workspace"
    projects_root = workspace_root / "projects"
    runtime_root = workspace_root / "runtime"
    projects_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "workspace_cleanup_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    try:
        for name in ("sam_tic_tac_progress", "sam_tic_tac_progress_0c72e4b9", "sam_tic_tac_progress_cb56828c"):
            _write(projects_root / name / "README.md", f"# {name}\n")
        for name in ("conversation_variation_aaaaaa", "conversation_variation_bbbbbb"):
            _write(projects_root / name / "README.md", f"# {name}\n")

        for name in (
            "native_ui_11111111.db",
            "native_ui_11111111.json",
            "native_ui_11111111.session.json",
            "native_ui_22222222.db",
            "native_ui_22222222.json",
            "native_ui_22222222.session.json",
            "memory.json",
        ):
            _write(runtime_root / name, name)

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
            workspace_root=workspace_root,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            inspect_result = runtime.handle_text("inspect the workspace and organize it")
            _assert(inspect_result.ok, "workspace inspection failed")
            _assert(inspect_result.metadata.get("intent") == "inspect_workspace_cleanup", "inspect intent mismatch")
            _assert(inspect_result.metadata.get("project_duplicate_count", 0) >= 2, "project duplicate groups missing")
            _assert(inspect_result.metadata.get("runtime_duplicate_count", 0) >= 1, "runtime duplicate groups missing")
            proposed = inspect_result.metadata.get("proposed_delete_paths", [])
            _assert(any("sam_tic_tac_progress_" in path for path in proposed), "project delete proposals missing")
            _assert(any("native_ui_11111111" in path or "native_ui_22222222" in path for path in proposed), "runtime delete proposals missing")
            audit_result, audit_event = fetch_audit_event(db_path, int(inspect_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "workspace inspection audit missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "inspect_workspace_cleanup", "workspace inspection audit intent mismatch")
            print("[PASS] Workspace cleanup inspection path")
        except Exception as exc:
            logger.fail_step("workspace_cleanup_inspection", str(exc))
            failures.append(f"Workspace cleanup inspection failed: {exc}")
        else:
            logger.pass_step("workspace_cleanup_inspection")

        try:
            cleanup_result = runtime.handle_text("confirm cleanup workspace duplicates")
            _assert(cleanup_result.ok, "workspace cleanup failed")
            _assert(cleanup_result.metadata.get("intent") == "cleanup_workspace_duplicates", "cleanup intent mismatch")
            deleted_paths = cleanup_result.metadata.get("deleted_paths", [])
            _assert(deleted_paths, "cleanup deleted no paths")
            _assert((projects_root / "sam_tic_tac_progress").exists(), "canonical project should remain")
            _assert(not (projects_root / "sam_tic_tac_progress_0c72e4b9").exists(), "duplicate project should be deleted")
            _assert(not (projects_root / "sam_tic_tac_progress_cb56828c").exists(), "second duplicate project should be deleted")
            remaining_runtime = sorted(item.name for item in runtime_root.iterdir())
            _assert("memory.json" in remaining_runtime, "non-duplicate runtime file should remain")
            _assert(len([item for item in remaining_runtime if item.startswith("native_ui_")]) == 3, "one native_ui runtime set should remain")
            print("[PASS] Workspace cleanup execution path")
        except Exception as exc:
            logger.fail_step("workspace_cleanup_execution", str(exc))
            failures.append(f"Workspace cleanup execution failed: {exc}")
        else:
            logger.pass_step("workspace_cleanup_execution")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workspace cleanup live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All workspace cleanup live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
