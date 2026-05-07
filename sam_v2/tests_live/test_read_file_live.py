"""Real runtime file-read validation for Sam v2."""

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
    print("=== Sam v2 Read File Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_read_file_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_read_file_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "read_file_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    readme_path = REPO_ROOT / "sam_v2" / "README.md"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            result = runtime.handle_text(f"read file {readme_path}")
            _assert(result.ok, "runtime file read failed")
            _assert(result.metadata.get("intent") == "read_file", "read_file intent mismatch")
            _assert(str(result.metadata.get("path", "")).endswith("sam_v2\\README.md") or str(result.metadata.get("path", "")).endswith("sam_v2/README.md"), "returned path mismatch")
            content = str(result.metadata.get("content", ""))
            _assert("Sam v2" in content, "expected README content missing")

            audit_result, audit_event = fetch_audit_event(db_path, int(result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "read file audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "read_file", "read file audit intent mismatch")
            print("[PASS] Runtime file read returns real repo file content")
        except Exception as exc:
            logger.fail_step("runtime_read_file", str(exc))
            failures.append(f"Runtime file read failed: {exc}")
        else:
            logger.pass_step("runtime_read_file")

        try:
            missing = runtime.handle_text(f"read file {tmp_dir / 'missing_file.txt'}")
            _assert(not missing.ok, "missing file should fail")
            _assert(missing.next_action == "ask_user", "missing file next action mismatch")
            _assert(missing.metadata.get("path"), "missing file path metadata missing")
            print("[PASS] Missing file read stays truthful")
        except Exception as exc:
            logger.fail_step("missing_file_read", str(exc))
            failures.append(f"Missing file read failed: {exc}")
        else:
            logger.pass_step("missing_file_read")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Read file live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All read file live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
