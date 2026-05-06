"""Live test for the Sam v2 core runtime foundation."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import AuthorityConfig, AuthorityEngine
from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.memory.session import load_last_session
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    try:
        try:
            runtime = SamRuntime(
                db_path=db_path,
                memory_path=memory_path,
                session_path=session_path,
            )
            start_result = runtime.start()
            _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

            capabilities_result = runtime.handle_text("what can you do")
            _assert(capabilities_result.ok, "capabilities request failed")
            _assert(len(capabilities_result.metadata.get("capabilities", [])) >= 3, "capability list too small")
            print("[PASS] Runtime startup and capability request")
        except Exception as exc:
            logger.fail_step("runtime_start_and_capabilities", str(exc))
            failures.append(f"Runtime startup/capabilities test failed: {exc}")
        else:
            logger.pass_step("runtime_start_and_capabilities")

        try:
            create_result = runtime.handle_text("create goal: Ship runtime loop")
            _assert(create_result.ok, "create goal request failed")

            list_result = runtime.handle_text("list goals")
            _assert(list_result.ok, "list goals request failed")
            _assert(list_result.metadata.get("count", 0) >= 1, "goal list count mismatch")

            audit_result, audit_event = fetch_audit_event(db_path, int(create_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "runtime audit event missing")
            payload = json.loads(audit_event.metadata_json)
            _assert(payload["intent"] == "create_goal", "runtime audit intent mismatch")
            print("[PASS] Runtime request routing and audit logging")
        except Exception as exc:
            logger.fail_step("runtime_request_routing", str(exc))
            failures.append(f"Runtime routing test failed: {exc}")
        else:
            logger.pass_step("runtime_request_routing")

        try:
            governed_runtime = SamRuntime(
                db_path=db_path,
                memory_path=memory_path,
                session_path=session_path,
                authority_engine=AuthorityEngine(
                    AuthorityConfig(default_level=3, governed_categories=["write_data"])
                ),
            )
            gated_result = governed_runtime.handle_text("create goal: Needs approval")
            _assert(gated_result.status == "needs_approval", "approval gate did not trigger")
            _assert("approval_id" in gated_result.metadata, "approval id missing")
            print("[PASS] Runtime approval-gated request")
        except Exception as exc:
            logger.fail_step("runtime_approval_gating", str(exc))
            failures.append(f"Runtime approval test failed: {exc}")
        else:
            logger.pass_step("runtime_approval_gating")

        try:
            empty_result = runtime.handle_text("   ")
            _assert(not empty_result.ok, "empty request should fail")
            _assert(empty_result.error_message == "empty request", "empty request failure mismatch")

            session_result, session_state = load_last_session(session_path)
            _assert(session_result.ok and session_state is not None, "session state missing")
            _assert(session_state["request_count"] >= 3, "session request count too small")
            print("[PASS] Runtime failure handling and session persistence")
        except Exception as exc:
            logger.fail_step("runtime_failure_and_session", str(exc))
            failures.append(f"Runtime failure/session test failed: {exc}")
        else:
            logger.pass_step("runtime_failure_and_session")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
