"""Live test for opening a registered project folder through the runtime path."""

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
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Open Project Folder Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_open_project_folder_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_open_folder_{uuid.uuid4().hex[:8]}"
    project_dir = tmp_dir / "local_open_target"
    project_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "open_project_folder_live.db"
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

        project_registry = ProjectRegistry(projects_path)
        register_result = project_registry.register(
            ProjectRecord(
                project_id="local-open-target",
                name="Local Open Target",
                root_path=str(project_dir),
                stack="html",
            )
        )
        _assert(register_result.ok, f"project registration failed: {register_result.error_message}")

        try:
            open_result = runtime.handle_text("open folder for project Local Open Target")
            _assert(open_result.ok, "runtime open project folder failed")
            _assert(open_result.metadata.get("intent") == "open_project_folder", "open folder intent mismatch")
            _assert(open_result.metadata.get("root_path") == str(project_dir), "open folder root path mismatch")

            audit_event_id = int(open_result.metadata["audit_event_id"])
            audit_result, audit_event = fetch_audit_event(db_path, audit_event_id)
            _assert(audit_result.ok and audit_event is not None, "open folder audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "open_project_folder", "open folder audit intent mismatch")
            print("[PASS] Runtime project folder open path")
        except Exception as exc:
            logger.fail_step("runtime_open_project_folder", str(exc))
            failures.append(f"Runtime project folder open path failed: {exc}")
        else:
            logger.pass_step("runtime_open_project_folder")

        try:
            missing_result = runtime.handle_text("open folder for project MissingProject")
            _assert(not missing_result.ok, "missing project open should fail")
            _assert(missing_result.next_action == "ask_user", "missing project open next_action mismatch")
            print("[PASS] Missing project folder handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_project_folder", str(exc))
            failures.append(f"Missing project folder handling failed: {exc}")
        else:
            logger.pass_step("missing_project_folder")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Open project folder live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All open project folder live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
