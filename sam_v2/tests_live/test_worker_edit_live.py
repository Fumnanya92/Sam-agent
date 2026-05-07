"""Real code-edit worker validation for Sam v2."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.workers import CommandSpec, FileEditSpec, ToolingWorker, worker_monitor


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=30)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}")


def main() -> int:
    print("=== Sam v2 Worker Edit Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_worker_edit_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_worker_edit_{uuid.uuid4().hex[:8]}"
    repo_dir = tmp_dir / "edit_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "worker_edit_live.db"

    calc_path = repo_dir / "calc.py"
    test_path = repo_dir / "test_calc.py"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        calc_path.write_text(
            "def add(a, b):\n"
            "    return a - b\n",
            encoding="utf-8",
        )
        test_path.write_text(
            "from calc import add\n"
            "assert add(2, 3) == 5\n"
            "print('calc test passed')\n",
            encoding="utf-8",
        )

        _run(["git", "init"], repo_dir)
        _run(["git", "config", "user.name", "Sam V2 Test"], repo_dir)
        _run(["git", "config", "user.email", "sam-v2-test@example.com"], repo_dir)
        _run(["git", "add", "calc.py", "test_calc.py"], repo_dir)
        _run(["git", "commit", "-m", "base broken calc"], repo_dir)

        worker = ToolingWorker(
            db_path=db_path,
            authority_engine=AuthorityEngine(AuthorityConfig(default_level=10)),
        )

        try:
            failing_result, failing_task = worker.execute(
                CommandSpec(
                    name="calc_test_before_fix",
                    worker_type="test",
                    command=[sys.executable, "test_calc.py"],
                    description="Run the broken calc test before editing code.",
                    cwd=repo_dir,
                )
            )
            _assert(not failing_result.ok, "pre-edit test should fail")
            _assert(failing_task.status == "failed", "pre-edit task status mismatch")
            _assert("AssertionError" in (failing_result.error_message or ""), "pre-edit failure should show assertion")
            print("[PASS] Real failing test before edit")
        except Exception as exc:
            logger.fail_step("failing_test_before_edit", str(exc))
            failures.append(f"Failing test before edit failed: {exc}")
        else:
            logger.pass_step("failing_test_before_edit")

        try:
            edit_result, edit_task = worker.execute_edit(
                FileEditSpec(
                    name="fix_calc_addition",
                    worker_type="code",
                    target_path=calc_path,
                    search_text="return a - b",
                    replace_text="return a + b",
                    description="Fix the calc add implementation in a real local git repo.",
                )
            )
            _assert(edit_result.ok, f"edit worker failed: {edit_result.error_message}")
            _assert(edit_task.status == "done", "edit task status mismatch")
            diff_text = edit_result.metadata.get("diff", "")
            _assert("-    return a - b" in diff_text, "diff missing removed line")
            _assert("+    return a + b" in diff_text, "diff missing added line")
            _assert("return a + b" in calc_path.read_text(encoding="utf-8"), "file was not updated")
            monitor_task = worker_monitor.get_task(edit_result.metadata["task_id"])
            _assert(monitor_task is not None and monitor_task.status == "done", "edit monitor state mismatch")
            print("[PASS] Worker edits code and returns diff")
        except Exception as exc:
            logger.fail_step("worker_edit", str(exc))
            failures.append(f"Worker edit failed: {exc}")
        else:
            logger.pass_step("worker_edit")

        try:
            diff_result, diff_task = worker.execute(
                CommandSpec(
                    name="repo_diff_after_edit",
                    worker_type="code",
                    command=["git", "diff", "--", "calc.py"],
                    description="Show the real git diff after the worker code edit.",
                    cwd=repo_dir,
                )
            )
            _assert(diff_result.ok, f"git diff failed: {diff_result.error_message}")
            _assert(diff_task.status == "done", "git diff task status mismatch")
            stdout = diff_result.metadata.get("stdout", "")
            _assert("-    return a - b" in stdout, "git diff missing removed line")
            _assert("+    return a + b" in stdout, "git diff missing added line")
            print("[PASS] Real git diff after worker edit")
        except Exception as exc:
            logger.fail_step("git_diff_after_edit", str(exc))
            failures.append(f"Git diff after edit failed: {exc}")
        else:
            logger.pass_step("git_diff_after_edit")

        try:
            passing_result, passing_task = worker.execute(
                CommandSpec(
                    name="calc_test_after_fix",
                    worker_type="test",
                    command=[sys.executable, "test_calc.py"],
                    description="Run the calc test after the worker code edit.",
                    cwd=repo_dir,
                )
            )
            _assert(passing_result.ok, f"post-edit test failed: {passing_result.error_message}")
            _assert(passing_task.status == "done", "post-edit task status mismatch")
            _assert("calc test passed" in passing_result.metadata.get("stdout", ""), "post-edit success output mismatch")
            print("[PASS] Real passing test after edit")
        except Exception as exc:
            logger.fail_step("passing_test_after_edit", str(exc))
            failures.append(f"Passing test after edit failed: {exc}")
        else:
            logger.pass_step("passing_test_after_edit")

        try:
            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    """
                    SELECT event_type, actor, summary
                    FROM audit_events
                    WHERE event_type IN ('worker_command_executed', 'worker_file_edited')
                    ORDER BY id ASC
                    """
                ).fetchall()
            _assert(any(row[0] == "worker_file_edited" for row in rows), "missing worker file edit audit row")
            _assert(any(row[0] == "worker_command_executed" for row in rows), "missing worker command audit row")
            print("[PASS] Worker edit audit trail")
        except Exception as exc:
            logger.fail_step("worker_edit_audit", str(exc))
            failures.append(f"Worker edit audit failed: {exc}")
        else:
            logger.pass_step("worker_edit_audit")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Worker edit live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All worker edit live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
