"""Live test for the Sam v2 diagnostics and reporting foundation."""

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
from sam_v2.workers import CommandSpec, ToolingWorker


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _latest_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise AssertionError(f"No log file matched {pattern} in {directory}")
    return matches[0]


def main() -> int:
    print("=== Sam v2 Diagnostics Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_diagnostics_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_diagnostics_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "diagnostics_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    fail_script = tmp_dir / "diag_fail.py"
    fail_script.write_text("raise SystemExit('diagnostics failure path')\n", encoding="utf-8")

    try:
        try:
            runtime = SamRuntime(db_path=db_path, memory_path=memory_path, session_path=session_path)
            runtime.handle_text("what can you do")

            actions_dir = REPO_ROOT / "sam_v2" / "logs" / "actions"
            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            action_log = _latest_file(actions_dir, "sam_v2_core_request_*.jsonl")
            summary_log = _latest_file(summaries_dir, "sam_v2_core_request_*.json")

            action_lines = action_log.read_text(encoding="utf-8").splitlines()
            _assert(any('"action": "request_completed"' in line for line in action_lines), "request_completed action missing")

            summary_payload = json.loads(summary_log.read_text(encoding="utf-8"))
            _assert(summary_payload["result"]["status"] == "success", "runtime summary status mismatch")
            print("[PASS] Runtime action and summary logging")
        except Exception as exc:
            logger.fail_step("runtime_action_and_summary_logging", str(exc))
            failures.append(f"Runtime diagnostics test failed: {exc}")
        else:
            logger.pass_step("runtime_action_and_summary_logging")

        try:
            worker = ToolingWorker(db_path=db_path)
            fail_result, _ = worker.execute(
                CommandSpec(
                    name="diagnostics_fail",
                    worker_type="test",
                    command=[sys.executable, str(fail_script)],
                    description="Run failing diagnostics worker script.",
                    cwd=tmp_dir,
                )
            )
            _assert(not fail_result.ok, "failing diagnostics worker should fail")

            errors_dir = REPO_ROOT / "sam_v2" / "logs" / "errors"
            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            error_log = _latest_file(errors_dir, "sam_v2.workers.test.jsonl")
            worker_summary = _latest_file(summaries_dir, "sam_v2_worker_diagnostics_fail_*.json")

            error_lines = error_log.read_text(encoding="utf-8").splitlines()
            _assert(any("worker_failed" in line for line in error_lines), "worker_failed error log missing")

            worker_summary_payload = json.loads(worker_summary.read_text(encoding="utf-8"))
            _assert(worker_summary_payload["result"]["status"] == "failed", "worker summary status mismatch")
            print("[PASS] Worker error and summary logging")
        except Exception as exc:
            logger.fail_step("worker_error_and_summary_logging", str(exc))
            failures.append(f"Worker diagnostics test failed: {exc}")
        else:
            logger.pass_step("worker_error_and_summary_logging")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Diagnostics live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All diagnostics live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
