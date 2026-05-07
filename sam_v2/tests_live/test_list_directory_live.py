"""Real runtime directory-list validation for Sam v2."""

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


def main() -> int:
    print("=== Sam v2 List Directory Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_list_directory_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_list_directory_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "list_directory_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    sam_v2_dir = REPO_ROOT / "sam_v2"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            result = runtime.handle_text(f"list folder {sam_v2_dir}")
            _assert(result.ok, "runtime directory list failed")
            _assert(result.metadata.get("intent") == "list_directory", "list_directory intent mismatch")
            entries = result.metadata.get("entries", [])
            _assert(isinstance(entries, list) and entries, "entries missing")
            _assert("core" in entries or "tests_live" in entries, "expected sam_v2 entries missing")

            audit_result, audit_event = fetch_audit_event(db_path, int(result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "directory list audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "list_directory", "directory list audit intent mismatch")
            print("[PASS] Runtime directory listing returns real repo entries")
        except Exception as exc:
            logger.fail_step("runtime_list_directory", str(exc))
            failures.append(f"Runtime directory listing failed: {exc}")
        else:
            logger.pass_step("runtime_list_directory")

        try:
            missing = runtime.handle_text(f"list folder {tmp_dir / 'missing_dir'}")
            _assert(not missing.ok, "missing directory should fail")
            _assert(missing.next_action == "ask_user", "missing directory next action mismatch")
            _assert(missing.metadata.get("path"), "missing directory path metadata missing")
            print("[PASS] Missing directory listing stays truthful")
        except Exception as exc:
            logger.fail_step("missing_directory_list", str(exc))
            failures.append(f"Missing directory listing failed: {exc}")
        else:
            logger.pass_step("missing_directory_list")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] List directory live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All list directory live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
