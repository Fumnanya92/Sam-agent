"""Real pending approval listing validation for Sam v2."""

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
    print("=== Sam v2 List Approvals Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_list_approvals_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_list_approvals_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "list_approvals_live.db"
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

        runtime.handle_text("Sam, push the changes")

        try:
            approvals_result = runtime.handle_text("show pending approvals")
            _assert(approvals_result.ok, "list approvals request failed")
            _assert(approvals_result.metadata.get("intent") == "list_approvals", "list approvals intent mismatch")
            approvals = approvals_result.metadata.get("approvals", [])
            _assert(len(approvals) >= 1, "expected at least one pending approval")
            first = approvals[0]
            _assert(first.get("tool_name") == "git.push", "approval tool mismatch")
            _assert(first.get("status") == "pending", "approval status mismatch")
            print("[PASS] Runtime pending approvals listing returns real SQLite-backed approvals")
        except Exception as exc:
            logger.fail_step("runtime_list_approvals", str(exc))
            failures.append(f"Runtime approvals listing failed: {exc}")
        else:
            logger.pass_step("runtime_list_approvals")

        try:
            fresh_runtime = SamRuntime(
                db_path=tmp_dir / "empty_list_approvals_live.db",
                memory_path=tmp_dir / "fresh_memory.json",
                session_path=tmp_dir / "fresh_session.json",
            )
            fresh_start = fresh_runtime.start()
            _assert(fresh_start.ok, f"fresh runtime start failed: {fresh_start.error_message}")
            empty_result = fresh_runtime.handle_text("list approvals")
            _assert(empty_result.ok, "empty approvals list should still succeed")
            _assert(empty_result.metadata.get("count") == 0, "empty approvals count mismatch")
            print("[PASS] Empty approvals listing stays truthful")
        except Exception as exc:
            logger.fail_step("empty_list_approvals", str(exc))
            failures.append(f"Empty approvals listing failed: {exc}")
        else:
            logger.pass_step("empty_list_approvals")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] List approvals live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All list approvals live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
