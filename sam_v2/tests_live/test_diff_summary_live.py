"""Real diff summarization validation for Sam v2."""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import DiffSummaryService
from sam_v2.storage.db import init_storage
from sam_v2.workers import CommandSpec, FileEditSpec, ToolingWorker


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=30)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}")


def main() -> int:
    print("=== Sam v2 Diff Summary Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_diff_summary_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_diff_summary_{uuid.uuid4().hex[:8]}"
    repo_dir = tmp_dir / "diff_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "diff_summary_live.db"

    calc_path = repo_dir / "calc.py"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        calc_path.write_text(
            "def add(a, b):\n"
            "    return a - b\n",
            encoding="utf-8",
        )

        _run(["git", "init"], repo_dir)
        _run(["git", "config", "user.name", "Sam V2 Test"], repo_dir)
        _run(["git", "config", "user.email", "sam-v2-test@example.com"], repo_dir)
        _run(["git", "add", "calc.py"], repo_dir)
        _run(["git", "commit", "-m", "base broken calc"], repo_dir)

        worker = ToolingWorker(
            db_path=db_path,
            authority_engine=AuthorityEngine(AuthorityConfig(default_level=10)),
        )
        summary_service = DiffSummaryService()

        try:
            edit_result, _edit_task = worker.execute_edit(
                FileEditSpec(
                    name="fix_calc_for_diff_summary",
                    worker_type="code",
                    target_path=calc_path,
                    search_text="return a - b",
                    replace_text="return a + b",
                    description="Fix the calc implementation before summarizing the diff.",
                )
            )
            _assert(edit_result.ok, f"edit worker failed: {edit_result.error_message}")

            diff_result, _diff_task = worker.execute(
                CommandSpec(
                    name="diff_after_edit_for_summary",
                    worker_type="code",
                    command=["git", "diff", "--", "calc.py"],
                    description="Capture the real git diff after a worker edit.",
                    cwd=repo_dir,
                )
            )
            _assert(diff_result.ok, f"git diff failed: {diff_result.error_message}")
            diff_text = diff_result.metadata.get("stdout", "")
            _assert(diff_text.strip(), "git diff output should not be empty")
            print("[PASS] Real git diff captured")
        except Exception as exc:
            logger.fail_step("real_git_diff_capture", str(exc))
            failures.append(f"Real git diff capture failed: {exc}")
        else:
            logger.pass_step("real_git_diff_capture")

        try:
            summary_result, summary = summary_service.summarize(diff_text)
            _assert(summary_result.ok and summary is not None, f"diff summary failed: {summary_result.error_message}")
            _assert(summary.total_files == 1, "diff summary file count mismatch")
            _assert(summary.total_added_lines == 1, "diff summary added line count mismatch")
            _assert(summary.total_removed_lines == 1, "diff summary removed line count mismatch")
            _assert(summary.files[0].path == "calc.py", "diff summary file path mismatch")
            _assert("calc.py (+1/-1)" in summary.text, "summary text missing file fragment")
            _assert("Total line changes: +1/-1." in summary.text, "summary text missing totals")
            print("[PASS] Diff summary matches real diff")
        except Exception as exc:
            logger.fail_step("diff_summary_accuracy", str(exc))
            failures.append(f"Diff summary accuracy failed: {exc}")
        else:
            logger.pass_step("diff_summary_accuracy")

        try:
            empty_result, empty_summary = summary_service.summarize("")
            _assert(not empty_result.ok, "empty diff should fail")
            _assert(empty_summary is None, "empty diff should not return a summary")
            print("[PASS] Empty diff failure path")
        except Exception as exc:
            logger.fail_step("diff_summary_empty_failure", str(exc))
            failures.append(f"Diff summary empty failure test failed: {exc}")
        else:
            logger.pass_step("diff_summary_empty_failure")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Diff summary live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All diff summary live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
