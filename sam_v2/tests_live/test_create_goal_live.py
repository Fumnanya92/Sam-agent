"""Live test for Sam v2 goal creation through the runtime path."""

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
    print("=== Sam v2 Create Goal Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_create_goal_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_create_goal_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "create_goal_live.db"
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
            create_result = runtime.handle_text("create goal: Validate dedicated goal runtime path")
            _assert(create_result.ok, "runtime goal creation failed")
            _assert(create_result.metadata.get("intent") == "create_goal", "create goal intent mismatch")
            _assert(create_result.metadata.get("source"), "create goal source missing")
            goal_id = str(create_result.metadata.get("id", "")).strip()
            _assert(goal_id, "goal id missing from create result metadata")

            get_result, goal = goal_service.get_goal(goal_id)
            _assert(get_result.ok and goal is not None, "created goal not persisted")
            _assert(goal.title == "Validate dedicated goal runtime path", "created goal title mismatch")

            audit_event_id = int(create_result.metadata["audit_event_id"])
            audit_result, audit_event = fetch_audit_event(db_path, audit_event_id)
            _assert(audit_result.ok and audit_event is not None, "create goal audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "create_goal", "create goal audit intent mismatch")
            print("[PASS] Runtime goal create path")
        except Exception as exc:
            logger.fail_step("runtime_goal_create", str(exc))
            failures.append(f"Runtime goal create path failed: {exc}")
        else:
            logger.pass_step("runtime_goal_create")

        try:
            list_result = runtime.handle_text("list goals")
            _assert(list_result.ok, "runtime list goals failed")
            _assert(list_result.metadata.get("intent") == "list_goals", "list goals intent mismatch")
            _assert(
                "Validate dedicated goal runtime path" in list_result.metadata.get("titles", []),
                "created goal title missing from runtime list",
            )
            print("[PASS] Runtime goal list path")
        except Exception as exc:
            logger.fail_step("runtime_goal_list", str(exc))
            failures.append(f"Runtime goal list path failed: {exc}")
        else:
            logger.pass_step("runtime_goal_list")

        try:
            invalid_result = runtime.handle_text("create goal:   ")
            _assert(not invalid_result.ok, "blank goal title should fail")
            _assert(invalid_result.next_action == "ask_user", "blank goal next_action mismatch")
            _assert(invalid_result.error_message == "missing title", "blank goal error mismatch")
            print("[PASS] Blank goal title failure path")
        except Exception as exc:
            logger.fail_step("blank_goal_title_failure", str(exc))
            failures.append(f"Blank goal title failure path failed: {exc}")
        else:
            logger.pass_step("blank_goal_title_failure")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Create goal live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All create goal live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
