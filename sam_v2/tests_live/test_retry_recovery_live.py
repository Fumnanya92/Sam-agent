"""Real retry-decision validation for Sam v2."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.supervisor import ExecutionPlan, ExecutionStep, RecoveryPolicy, WorkflowBridge
from sam_v2.workers import CommandSpec, ToolingWorker


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=30)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}")


def _latest_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"no files matched {pattern} in {directory}")
    return matches[-1]


def main() -> int:
    print("=== Sam v2 Retry Recovery Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_retry_recovery_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_retry_recovery_{uuid.uuid4().hex[:8]}"
    repo_dir = tmp_dir / "retry_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "retry_recovery_live.db"

    flaky_script = repo_dir / "flaky_once.py"
    flag_path = repo_dir / "retry_once.flag"
    flaky_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"flag = Path(r'{flag_path.as_posix()}')",
                "if not flag.exists():",
                "    flag.write_text('created', encoding='utf-8')",
                "    raise SystemExit('first run fails on purpose for retry validation')",
                "print('second run succeeds after retry')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")
        _run(["git", "init"], repo_dir)
        _run(["git", "config", "user.name", "Sam V2 Test"], repo_dir)
        _run(["git", "config", "user.email", "sam-v2-test@example.com"], repo_dir)
        _run(["git", "add", "flaky_once.py"], repo_dir)
        _run(["git", "commit", "-m", "add flaky retry script"], repo_dir)

        try:
            if flag_path.exists():
                flag_path.unlink()
            worker = ToolingWorker(db_path=db_path)
            first_result, first_task = worker.execute(
                CommandSpec(
                    name="retry_probe_once",
                    worker_type="test",
                    command=[sys.executable, str(flaky_script)],
                    description="Run a flaky script once to capture a real retryable failure.",
                    cwd=repo_dir,
                )
            )
            _assert(not first_result.ok, "first flaky run should fail")
            _assert(first_task.status == "failed", "first flaky task status mismatch")
            _assert("first run fails on purpose" in (first_result.error_message or ""), "flaky failure message mismatch")
            decision = RecoveryPolicy().decide(first_result, attempt=1, max_attempts=2)
            _assert(decision.action == "retry", "recovery policy should choose retry")
            _assert(decision.should_retry, "recovery policy retry flag mismatch")
            print("[PASS] Recovery policy chooses retry from real failure output")
        except Exception as exc:
            logger.fail_step("recovery_policy_retry_decision", str(exc))
            failures.append(f"Recovery policy retry decision failed: {exc}")
        else:
            logger.pass_step("recovery_policy_retry_decision")

        try:
            if flag_path.exists():
                flag_path.unlink()
            bridge = WorkflowBridge(db_path=db_path)
            plan = ExecutionPlan(
                plan_id="retry-log-plan",
                goal="Validate retry behavior from real failure output and logs",
                steps=[
                    ExecutionStep(
                        step_id="retry-step",
                        title="Retry a flaky command once",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="retry_flaky_step",
                            worker_type="test",
                            command=[sys.executable, str(flaky_script)],
                            description="Run a flaky script and retry once after a real failure.",
                            cwd=repo_dir,
                        ),
                        max_attempts=2,
                    )
                ],
            )
            result = bridge.execute_plan(plan)
            _assert(result.ok, f"workflow bridge retry plan failed: {result.error_message}")
            _assert(result.metadata.get("completed_steps") == ["retry-step"], "completed steps mismatch")

            actions_dir = REPO_ROOT / "sam_v2" / "logs" / "actions"
            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            action_log = _latest_file(actions_dir, "sam_v2_workflow_retry-log-plan_*.jsonl")
            summary_log = _latest_file(summaries_dir, "sam_v2_workflow_retry-log-plan_*.json")
            action_lines = [json.loads(line) for line in action_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            summary_payload = json.loads(summary_log.read_text(encoding="utf-8"))

            _assert(
                any(item["action"] == "step_retrying" and item["status"] == "retry" for item in action_lines),
                "workflow action log missing retry event",
            )
            _assert(summary_payload["result"]["status"] == "success", "workflow summary status mismatch")
            _assert(summary_payload["result"]["metadata"]["completed_steps"] == ["retry-step"], "workflow summary steps mismatch")
            print("[PASS] Workflow bridge logs real retry and eventual success")
        except Exception as exc:
            logger.fail_step("workflow_bridge_retry_logging", str(exc))
            failures.append(f"Workflow bridge retry logging failed: {exc}")
        else:
            logger.pass_step("workflow_bridge_retry_logging")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Retry recovery live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All retry recovery live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
