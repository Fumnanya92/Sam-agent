"""Live test for Sam v2 goal listing through the runtime path."""

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
from sam_v2.workflows import GoalService


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 List Goals Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_list_goals_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_list_goals_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "list_goals_live.db"
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

        goal_service = GoalService(db_path)

        try:
            seed_result, first_goal = goal_service.create_goal(title="List goals smoke one")
            _assert(seed_result.ok and first_goal is not None, "first seed goal create failed")
            seed_result_two, second_goal = goal_service.create_goal(title="List goals smoke two")
            _assert(seed_result_two.ok and second_goal is not None, "second seed goal create failed")

            list_result = runtime.handle_text("list goals")
            _assert(list_result.ok, "runtime list goals failed")
            _assert(list_result.metadata.get("intent") == "list_goals", "list goals intent mismatch")
            _assert(list_result.metadata.get("count", 0) >= 2, "list goals count mismatch")
            titles = list_result.metadata.get("titles", [])
            _assert("List goals smoke one" in titles, "first seeded goal missing from runtime list")
            _assert("List goals smoke two" in titles, "second seeded goal missing from runtime list")

            audit_event_id = int(list_result.metadata["audit_event_id"])
            audit_result, audit_event = fetch_audit_event(db_path, audit_event_id)
            _assert(audit_result.ok and audit_event is not None, "list goals audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "list_goals", "list goals audit intent mismatch")
            print("[PASS] Runtime goal list path")
        except Exception as exc:
            logger.fail_step("runtime_goal_list", str(exc))
            failures.append(f"Runtime goal list path failed: {exc}")
        else:
            logger.pass_step("runtime_goal_list")

        try:
            empty_db_path = tmp_dir / "empty_goals_live.db"
            empty_runtime = SamRuntime(
                db_path=empty_db_path,
                memory_path=tmp_dir / "empty_memory.json",
                session_path=tmp_dir / "empty_session.json",
            )
            empty_start = empty_runtime.start()
            _assert(empty_start.ok, f"empty runtime start failed: {empty_start.error_message}")

            empty_list = empty_runtime.handle_text("list goals")
            _assert(empty_list.ok, "empty runtime list goals failed")
            _assert(empty_list.metadata.get("count") == 0, "empty list goals count should be zero")
            _assert(empty_list.metadata.get("titles") == [], "empty list goals titles should be empty")
            print("[PASS] Empty goal list path")
        except Exception as exc:
            logger.fail_step("empty_goal_list", str(exc))
            failures.append(f"Empty goal list path failed: {exc}")
        else:
            logger.pass_step("empty_goal_list")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] List goals live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All list goals live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
