"""Real runtime-path memory and session validation for Sam v2."""

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
from sam_v2.memory.manager import load_memory
from sam_v2.memory.session import load_last_session
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Runtime Memory Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_memory_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_runtime_memory_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "runtime_memory_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )

        try:
            start_result = runtime.start()
            _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

            first_result = runtime.handle_text("what can you do")
            _assert(first_result.ok, "capability request failed")

            second_result = runtime.handle_text("create goal: Validate runtime memory")
            _assert(second_result.ok, "goal creation request failed")
            _assert(memory_path.exists(), "memory file was not created")
            _assert(session_path.exists(), "session file was not created")
            print("[PASS] Runtime requests created memory and session files")
        except Exception as exc:
            logger.fail_step("runtime_request_bootstrap", str(exc))
            failures.append(f"Runtime request bootstrap failed: {exc}")
        else:
            logger.pass_step("runtime_request_bootstrap")

        try:
            load_result, memory = load_memory(memory_path)
            _assert(load_result.ok, f"memory load failed: {load_result.error_message}")
            daily_state = memory.get("daily_state", {})
            _assert(daily_state.get("last_runtime_request", {}).get("value") == "create goal: Validate runtime memory", "last runtime request not persisted")
            _assert(daily_state.get("last_runtime_intent", {}).get("value") == "create_goal", "last runtime intent not persisted")
            _assert(daily_state.get("last_runtime_status", {}).get("value") == "success", "last runtime status not persisted")
            _assert(bool(daily_state.get("_last_updated_at", {}).get("value")), "memory update timestamp missing")
            print("[PASS] Runtime request details persisted to memory")
        except Exception as exc:
            logger.fail_step("runtime_memory_persistence", str(exc))
            failures.append(f"Runtime memory persistence failed: {exc}")
        else:
            logger.pass_step("runtime_memory_persistence")

        try:
            session_result, session_state = load_last_session(session_path)
            _assert(session_result.ok and session_state is not None, "session state load failed")
            _assert(session_state["request_count"] >= 2, "session request count too low")
            _assert(session_state["last_intent"] == "create_goal", "session last intent mismatch")
            _assert(session_state["last_status"] == "success", "session last status mismatch")
            _assert(len(session_state["history"]) >= 2, "session history too short")
            last_history = session_state["history"][-1]
            _assert(last_history["user_text"] == "create goal: Validate runtime memory", "session history last request mismatch")
            print("[PASS] Runtime session state persisted across requests")
        except Exception as exc:
            logger.fail_step("runtime_session_persistence", str(exc))
            failures.append(f"Runtime session persistence failed: {exc}")
        else:
            logger.pass_step("runtime_session_persistence")

        try:
            audit_result, audit_event = fetch_audit_event(db_path, int(second_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "runtime audit event missing")
            payload = json.loads(audit_event.metadata_json)
            _assert(payload["intent"] == "create_goal", "runtime audit intent mismatch")
            _assert(payload["request_count"] >= 2, "runtime audit request count mismatch")
            print("[PASS] Runtime audit trail stays aligned with memory/session state")
        except Exception as exc:
            logger.fail_step("runtime_memory_audit_alignment", str(exc))
            failures.append(f"Runtime audit alignment failed: {exc}")
        else:
            logger.pass_step("runtime_memory_audit_alignment")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Runtime memory live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All runtime memory live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
