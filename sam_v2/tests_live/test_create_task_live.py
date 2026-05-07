"""Real task creation validation for Sam v2."""

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
from sam_v2.storage import fetch_task
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Create Task Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_create_task_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_create_task_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "create_task_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            create_result = runtime.handle_text("create task: Validate storage task path")
            _assert(create_result.ok, "runtime task creation failed")
            _assert(create_result.metadata.get("intent") == "create_task", "task intent mismatch")
            task_id = int(create_result.metadata["id"])

            fetch_result, task = fetch_task(db_path, task_id)
            _assert(fetch_result.ok and task is not None, "created task could not be fetched")
            _assert(task.title == "Validate storage task path", "task title mismatch")
            _assert(task.status == "pending", "task status mismatch")
            _assert(task.priority == "medium", "task priority mismatch")

            audit_result, audit_event = fetch_audit_event(db_path, int(create_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "task audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "create_task", "task audit intent mismatch")
            print("[PASS] Runtime task create and SQLite fetch path")
        except Exception as exc:
            logger.fail_step("runtime_task_create_fetch", str(exc))
            failures.append(f"Runtime task create/fetch failed: {exc}")
        else:
            logger.pass_step("runtime_task_create_fetch")

        try:
            empty_result = runtime.handle_text("create task:   ")
            _assert(not empty_result.ok, "empty task title should fail")
            _assert(empty_result.next_action == "ask_user", "empty task next action mismatch")
            _assert(empty_result.error_message == "missing title", "empty task error mismatch")
            print("[PASS] Empty task title failure path")
        except Exception as exc:
            logger.fail_step("empty_task_failure", str(exc))
            failures.append(f"Empty task failure path failed: {exc}")
        else:
            logger.pass_step("empty_task_failure")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Create task live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All create task live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
