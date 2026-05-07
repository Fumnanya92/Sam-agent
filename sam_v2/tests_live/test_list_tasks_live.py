"""Real task listing validation for Sam v2."""

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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 List Tasks Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_list_tasks_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_list_tasks_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "list_tasks_live.db"
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

        runtime.handle_text("create task: Review the dashboard panels")
        runtime.handle_text("create task: Wire list tasks into runtime")
        runtime.handle_text("create task: Update the handoff note")

        try:
            list_result = runtime.handle_text("list tasks")
            _assert(list_result.ok, "list tasks request failed")
            _assert(list_result.metadata.get("intent") == "list_tasks", "list tasks intent mismatch")
            tasks = list_result.metadata.get("tasks", [])
            _assert(len(tasks) == 3, f"expected 3 tasks, got {len(tasks)}")
            titles = [item["title"] for item in tasks]
            _assert("Wire list tasks into runtime" in titles, "expected task title missing")
            _assert(all("status" in item for item in tasks), "task status missing from metadata")
            print("[PASS] Runtime task listing returns real SQLite-backed tasks")
        except Exception as exc:
            logger.fail_step("runtime_list_tasks", str(exc))
            failures.append(f"Runtime task listing failed: {exc}")
        else:
            logger.pass_step("runtime_list_tasks")

        try:
            fresh_runtime = SamRuntime(
                db_path=tmp_dir / "empty_list_tasks_live.db",
                memory_path=tmp_dir / "fresh_memory.json",
                session_path=tmp_dir / "fresh_session.json",
            )
            fresh_start = fresh_runtime.start()
            _assert(fresh_start.ok, f"fresh runtime start failed: {fresh_start.error_message}")
            empty_result = fresh_runtime.handle_text("list tasks")
            _assert(empty_result.ok, "empty task list should still succeed")
            _assert(empty_result.next_action == "ask_user", "empty task list next action mismatch")
            _assert(empty_result.metadata.get("count") == 0, "empty task list count mismatch")
            print("[PASS] Empty task listing stays truthful")
        except Exception as exc:
            logger.fail_step("empty_list_tasks", str(exc))
            failures.append(f"Empty task listing failed: {exc}")
        else:
            logger.pass_step("empty_list_tasks")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] List tasks live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All list tasks live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
