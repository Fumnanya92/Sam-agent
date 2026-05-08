"""Live test for opening real local files through the Sam v2 runtime path."""

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
    print("=== Sam v2 Open File Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_open_file_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_open_file_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "open_file_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    readme_path = REPO_ROOT / "sam_v2" / "README.md"
    runtime_path = REPO_ROOT / "sam_v2" / "core" / "runtime.py"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            result = runtime.handle_text("open readme.md")
            _assert(result.ok, "open readme.md failed")
            _assert(result.metadata.get("intent") == "open_file", "open readme intent mismatch")
            _assert(Path(str(result.metadata.get("path", ""))).resolve() == readme_path.resolve(), "README path mismatch")
            audit_result, audit_event = fetch_audit_event(db_path, int(result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "open readme audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "open_file", "open readme audit intent mismatch")
            print("[PASS] open readme.md")
        except Exception as exc:
            logger.fail_step("open_readme", str(exc))
            failures.append(f"open readme.md failed: {exc}")
        else:
            logger.pass_step("open_readme")

        try:
            result = runtime.handle_text(f"open file {runtime_path}")
            _assert(result.ok, "open explicit runtime.py failed")
            _assert(result.metadata.get("intent") == "open_file", "open file intent mismatch")
            _assert(Path(str(result.metadata.get("path", ""))).resolve() == runtime_path.resolve(), "runtime.py path mismatch")
            print("[PASS] open explicit runtime.py path")
        except Exception as exc:
            logger.fail_step("open_explicit_runtime_path", str(exc))
            failures.append(f"open explicit runtime.py failed: {exc}")
        else:
            logger.pass_step("open_explicit_runtime_path")

        try:
            missing = runtime.handle_text("open file definitely_missing_file_12345.txt")
            _assert(not missing.ok, "missing file open should fail")
            _assert(missing.next_action == "ask_user", "missing file open next_action mismatch")
            print("[PASS] Missing file handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_file_open", str(exc))
            failures.append(f"Missing file open failed: {exc}")
        else:
            logger.pass_step("missing_file_open")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Open file live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All open file live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
