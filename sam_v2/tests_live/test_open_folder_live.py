"""Live test for opening real local folders through the Sam v2 runtime path."""

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
    print("=== Sam v2 Open Folder Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_open_folder_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_open_folder_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "open_folder_live.db"
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

        expected_targets = {
            "open downloads": Path.home() / "Downloads",
            "open documents": Path.home() / "Documents",
            "open sam-agent": REPO_ROOT,
        }

        for request_text, expected_path in expected_targets.items():
            try:
                _assert(expected_path.exists() and expected_path.is_dir(), f"expected folder missing: {expected_path}")
                result = runtime.handle_text(request_text)
                _assert(result.ok, f"{request_text} failed")
                _assert(result.metadata.get("intent") == "open_folder", f"{request_text} intent mismatch")
                _assert(
                    Path(str(result.metadata.get("path", ""))).resolve() == expected_path.resolve(),
                    f"{request_text} opened wrong path",
                )
                audit_event_id = int(result.metadata["audit_event_id"])
                audit_result, audit_event = fetch_audit_event(db_path, audit_event_id)
                _assert(audit_result.ok and audit_event is not None, f"{request_text} audit event missing")
                audit_payload = json.loads(audit_event.metadata_json)
                _assert(audit_payload.get("intent") == "open_folder", f"{request_text} audit intent mismatch")
                print(f"[PASS] {request_text}")
            except Exception as exc:
                logger.fail_step(request_text.replace(" ", "_"), str(exc))
                failures.append(f"{request_text} failed: {exc}")
            else:
                logger.pass_step(request_text.replace(" ", "_"))

        try:
            missing_result = runtime.handle_text("open folder does-not-exist-xyz")
            _assert(not missing_result.ok, "missing folder open should fail")
            _assert(missing_result.next_action == "ask_user", "missing folder open next_action mismatch")
            print("[PASS] Missing folder handled truthfully")
        except Exception as exc:
            logger.fail_step("missing_folder", str(exc))
            failures.append(f"Missing folder handling failed: {exc}")
        else:
            logger.pass_step("missing_folder")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Open folder live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All open folder live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
