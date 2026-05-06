"""Live test for the Sam v2 memory foundation."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.memory import (
    TemporaryMemory,
    is_session_recent,
    load_last_session,
    load_memory,
    save_memory,
    save_session_state,
    update_memory,
)
from sam_v2.storage.db import fetch_audit_event, init_storage


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Memory Live Test ===")
    failures = []

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_memory_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session_state.json"
    db_path = tmp_dir / "memory_audit.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            load_result, memory = load_memory(memory_path)
            _assert(load_result.ok, "load_memory did not succeed for missing file")
            _assert(isinstance(memory, dict), "load_memory did not return a dict")
            print("[PASS] Empty memory bootstrap")
        except Exception as exc:
            failures.append(f"Bootstrap test failed: {exc}")

        try:
            save_result = save_memory(
                memory_path,
                {"identity": {"name": {"value": "Sam"}}},
                audit_db_path=db_path,
            )
            _assert(save_result.ok, f"save_memory failed: {save_result.error_message}")

            update_result, updated_memory = update_memory(
                memory_path,
                {"projects": {"active": {"value": "Sam-agent"}}},
                audit_db_path=db_path,
            )
            _assert(update_result.ok, f"update_memory failed: {update_result.error_message}")
            _assert(
                updated_memory["projects"]["active"]["value"] == "Sam-agent",
                "project update not persisted in memory object",
            )

            reloaded_result, reloaded = load_memory(memory_path)
            _assert(reloaded_result.ok, "reloaded memory failed")
            _assert(
                reloaded["identity"]["name"]["value"] == "Sam",
                "identity value was not persisted",
            )
            _assert(
                reloaded["projects"]["active"]["value"] == "Sam-agent",
                "project value was not persisted",
            )
            print("[PASS] Memory save/update/reload")
        except Exception as exc:
            failures.append(f"Persistent memory test failed: {exc}")

        try:
            session = {
                "timestamp": "2026-05-06T12:00:00",
                "git_project": "Sam-agent",
                "git_branch": "rebuild/sam-clean-v2",
            }
            save_session_result = save_session_state(session_path, session)
            _assert(save_session_result.ok, "session save failed")
            load_session_result, loaded_session = load_last_session(session_path)
            _assert(load_session_result.ok and loaded_session is not None, "session load failed")
            _assert(loaded_session["git_branch"] == "rebuild/sam-clean-v2", "session branch mismatch")
            _assert(is_session_recent({"timestamp": "2999-01-01T00:00:00"}, max_hours=1), "recent session check failed")
            print("[PASS] Session save/load")
        except Exception as exc:
            failures.append(f"Session test failed: {exc}")

        try:
            temp_memory = TemporaryMemory(max_history=2)
            temp_memory.set_pending_intent("open_project")
            temp_memory.update_parameters({"project": "Sam-agent"})
            temp_memory.set_last_user_text("open the repo")
            temp_memory.set_last_ai_response("opening it now")
            temp_memory.set_last_user_text("also show status")
            summary = temp_memory.get_context_summary()
            _assert(summary["pending_intent"] == "open_project", "pending intent mismatch")
            _assert(temp_memory.get_parameters()["project"] == "Sam-agent", "parameter mismatch")
            _assert(len(temp_memory.conversation_history) == 2, "history cap mismatch")
            print("[PASS] Temporary memory behavior")
        except Exception as exc:
            failures.append(f"Temporary memory test failed: {exc}")

        try:
            invalid_path = tmp_dir / "invalid_memory.json"
            invalid_path.write_text("{invalid", encoding="utf-8")
            invalid_result, invalid_memory = load_memory(invalid_path)
            _assert(not invalid_result.ok, "invalid JSON did not fail")
            _assert(isinstance(invalid_memory, dict), "invalid JSON did not return fallback memory")
            print("[PASS] Invalid JSON failure path")
        except Exception as exc:
            failures.append(f"Failure-path test failed: {exc}")

        try:
            audit_result, audit_event = fetch_audit_event(db_path, 1)
            _assert(audit_result.ok and audit_event is not None, "memory audit event missing")
            _assert(audit_event.event_type == "memory_saved", "unexpected audit event type")
            print("[PASS] Memory save audit logging")
        except Exception as exc:
            failures.append(f"Audit logging test failed: {exc}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        print("[FAIL] Memory live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("[PASS] All memory live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
