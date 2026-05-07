"""Real task tracking validation for Sam v2."""

from __future__ import annotations

import json
import shutil
import sqlite3
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
    print("=== Sam v2 Track Task Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_track_task_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_track_task_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "track_task_live.db"
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

        create_result = runtime.handle_text("create task: Validate task tracking path")
        _assert(create_result.ok, "task creation bootstrap failed")
        task_id = int(create_result.metadata["id"])

        try:
            update_result = runtime.handle_text(f"update task {task_id}: in_progress | runtime picked this up")
            _assert(update_result.ok, "task update failed")
            _assert(update_result.metadata.get("intent") == "update_task", "task update intent mismatch")

            fetch_result, task = fetch_task(db_path, task_id)
            _assert(fetch_result.ok and task is not None, "updated task could not be fetched")
            _assert(task.status == "in_progress", "task status was not updated")
            _assert(task.notes == "runtime picked this up", "task notes were not updated")

            audit_result, audit_event = fetch_audit_event(db_path, int(update_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "task update audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "update_task", "task update audit intent mismatch")
            print("[PASS] Runtime task update persists to SQLite")
        except Exception as exc:
            logger.fail_step("runtime_task_update", str(exc))
            failures.append(f"Runtime task update failed: {exc}")
        else:
            logger.pass_step("runtime_task_update")

        try:
            second_update = runtime.handle_text(f"update task {task_id}: done | tracking validated")
            _assert(second_update.ok, "second task update failed")

            fetch_result, task = fetch_task(db_path, task_id)
            _assert(fetch_result.ok and task is not None, "second updated task could not be fetched")
            _assert(task.status == "done", "second task status mismatch")
            _assert(task.notes == "tracking validated", "second task notes mismatch")

            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    """
                    SELECT summary, metadata_json
                    FROM audit_events
                    WHERE event_type = 'runtime_request_handled'
                    ORDER BY id ASC
                    """
                ).fetchall()
            update_intents = []
            for row in rows:
                payload = json.loads(row[1])
                if payload.get("intent") == "update_task":
                    update_intents.append(payload.get("intent"))
            _assert(len(update_intents) >= 2, "expected at least two task update audit rows")
            print("[PASS] Task tracking history survives multiple runtime updates")
        except Exception as exc:
            logger.fail_step("multiple_task_updates", str(exc))
            failures.append(f"Multiple task updates failed: {exc}")
        else:
            logger.pass_step("multiple_task_updates")

        try:
            invalid_result = runtime.handle_text("update task abc: done | nope")
            _assert(not invalid_result.ok, "invalid task id should fail")
            _assert(invalid_result.next_action == "ask_user", "invalid task id next action mismatch")
            print("[PASS] Invalid task update failure path")
        except Exception as exc:
            logger.fail_step("invalid_task_update_failure", str(exc))
            failures.append(f"Invalid task update failure failed: {exc}")
        else:
            logger.pass_step("invalid_task_update_failure")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Track task live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All track task live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
