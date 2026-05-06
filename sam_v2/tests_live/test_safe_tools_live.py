"""Real live validation for Sam v2 safe local tools."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event, init_storage
from sam_v2.tools import SafeLocalTools


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Safe Tools Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_safe_tools_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_safe_tools_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "safe_tools_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")
        tools = SafeLocalTools(db_path=db_path)

        try:
            read_result, content = tools.read_text_file(REPO_ROOT / "sam_v2" / "README.md")
            _assert(read_result.ok, f"file read failed: {read_result.error_message}")
            _assert(content is not None and "Sam v2" in content, "unexpected README content")
            print("[PASS] Real file read")
        except Exception as exc:
            logger.fail_step("real_file_read", str(exc))
            failures.append(f"Real file read failed: {exc}")
        else:
            logger.pass_step("real_file_read")

        try:
            list_result, entries = tools.list_directory(REPO_ROOT / "sam_v2")
            _assert(list_result.ok, f"directory list failed: {list_result.error_message}")
            _assert("core" in entries and "tests_live" in entries, "expected sam_v2 entries missing")
            print("[PASS] Real directory listing")
        except Exception as exc:
            logger.fail_step("real_directory_listing", str(exc))
            failures.append(f"Real directory listing failed: {exc}")
        else:
            logger.pass_step("real_directory_listing")

        try:
            command_result, payload = tools.run_safe_command(["git", "branch", "--show-current"], cwd=REPO_ROOT)
            _assert(command_result.ok, f"safe command failed: {command_result.error_message}")
            _assert(str(payload.get("stdout", "")).strip(), "branch output was empty")
            print("[PASS] Real safe command execution")
        except Exception as exc:
            logger.fail_step("real_safe_command", str(exc))
            failures.append(f"Real safe command failed: {exc}")
        else:
            logger.pass_step("real_safe_command")

        try:
            git_result, snapshot = tools.inspect_git_state(REPO_ROOT)
            _assert(git_result.ok and snapshot is not None, f"git inspection failed: {git_result.error_message}")
            _assert(snapshot.branch == "rebuild/sam-clean-v2", f"unexpected branch: {snapshot.branch}")
            print("[PASS] Real git inspection")
        except Exception as exc:
            logger.fail_step("real_git_inspection", str(exc))
            failures.append(f"Real git inspection failed: {exc}")
        else:
            logger.pass_step("real_git_inspection")

        try:
            blocked_result, _ = tools.run_safe_command(["powershell", "-Command", "Get-Date"], cwd=REPO_ROOT)
            _assert(blocked_result.status == "blocked", "unsafe command was not blocked")
            print("[PASS] Unsafe command blocked")
        except Exception as exc:
            logger.fail_step("unsafe_command_blocked", str(exc))
            failures.append(f"Unsafe command blocking failed: {exc}")
        else:
            logger.pass_step("unsafe_command_blocked")

        try:
            audit_result, audit_event = fetch_audit_event(db_path, 1)
            _assert(audit_result.ok and audit_event is not None, "safe tools audit event missing")
            print("[PASS] Safe tools audit logging")
        except Exception as exc:
            logger.fail_step("safe_tools_audit_logging", str(exc))
            failures.append(f"Safe tools audit logging failed: {exc}")
        else:
            logger.pass_step("safe_tools_audit_logging")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Safe tools live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All safe tools live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
