"""Real test/build execution validation for Sam v2 supervisor."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.supervisor import ProjectProfile, SupervisorController, SupervisorRequest, WorkflowBridge


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
    print("=== Sam v2 Run Tests and Builds Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_run_tests_builds_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_run_tests_builds_{uuid.uuid4().hex[:8]}"
    repo_dir = tmp_dir / "project_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "run_tests_builds_live.db"

    app_path = repo_dir / "app.py"
    test_path = repo_dir / "test_app.py"
    build_ok_path = repo_dir / "build_ok.py"
    build_fail_path = repo_dir / "build_fail.py"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        app_path.write_text(
            "def greet():\n"
            "    return 'hello from build test'\n",
            encoding="utf-8",
        )
        test_path.write_text(
            "from app import greet\n"
            "assert greet() == 'hello from build test'\n"
            "print('project test passed')\n",
            encoding="utf-8",
        )
        build_ok_path.write_text(
            "from pathlib import Path\n"
            "dist = Path('dist')\n"
            "dist.mkdir(exist_ok=True)\n"
            "artifact = dist / 'artifact.txt'\n"
            "artifact.write_text('build complete', encoding='utf-8')\n"
            "print('project build passed')\n",
            encoding="utf-8",
        )
        build_fail_path.write_text(
            "raise SystemExit('intentional build failure for supervisor logging test')\n",
            encoding="utf-8",
        )

        _run(["git", "init"], repo_dir)
        _run(["git", "config", "user.name", "Sam V2 Test"], repo_dir)
        _run(["git", "config", "user.email", "sam-v2-test@example.com"], repo_dir)
        _run(["git", "add", "app.py", "test_app.py", "build_ok.py", "build_fail.py"], repo_dir)
        _run(["git", "commit", "-m", "add test/build scripts"], repo_dir)

        passing_profile = ProjectProfile(
            project_id="sample-project",
            root_path=repo_dir,
            test_command=[sys.executable, "test_app.py"],
            build_command=[sys.executable, "build_ok.py"],
            default_branch="master",
            stack="python",
        )
        failing_build_profile = ProjectProfile(
            project_id="sample-project-bad-build",
            root_path=repo_dir,
            test_command=[sys.executable, "test_app.py"],
            build_command=[sys.executable, "build_fail.py"],
            default_branch="master",
            stack="python",
        )

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(passing_profile)
            test_result = supervisor.execute(
                SupervisorRequest(
                    goal="Run tests for sample-project",
                    task_kind="test",
                    project_id="sample-project",
                )
            )
            _assert(test_result.ok, f"supervisor test execution failed: {test_result.error_message}")
            _assert(test_result.metadata.get("worker_type") == "test", "test worker type mismatch")

            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            summary_log = _latest_file(summaries_dir, f"sam_v2_workflow_{test_result.metadata['plan_id']}_*.json")
            payload = json.loads(summary_log.read_text(encoding="utf-8"))
            _assert(payload["result"]["status"] == "success", "test workflow summary status mismatch")
            print("[PASS] Real project test command through supervisor")
        except Exception as exc:
            logger.fail_step("supervisor_real_test_command", str(exc))
            failures.append(f"Supervisor real test command failed: {exc}")
        else:
            logger.pass_step("supervisor_real_test_command")

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(passing_profile)
            build_result = supervisor.execute(
                SupervisorRequest(
                    goal="Build sample-project",
                    task_kind="build",
                    project_id="sample-project",
                )
            )
            _assert(build_result.ok, f"supervisor build execution failed: {build_result.error_message}")
            _assert(build_result.metadata.get("worker_type") == "dev", "build worker type mismatch")
            artifact_path = repo_dir / "dist" / "artifact.txt"
            _assert(artifact_path.exists(), "build artifact missing")
            _assert(artifact_path.read_text(encoding="utf-8") == "build complete", "build artifact content mismatch")

            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            summary_log = _latest_file(summaries_dir, f"sam_v2_workflow_{build_result.metadata['plan_id']}_*.json")
            payload = json.loads(summary_log.read_text(encoding="utf-8"))
            _assert(payload["result"]["status"] == "success", "build workflow summary status mismatch")
            print("[PASS] Real project build command through supervisor")
        except Exception as exc:
            logger.fail_step("supervisor_real_build_command", str(exc))
            failures.append(f"Supervisor real build command failed: {exc}")
        else:
            logger.pass_step("supervisor_real_build_command")

        try:
            supervisor = SupervisorController(WorkflowBridge(db_path=db_path))
            supervisor.register_project(failing_build_profile)
            fail_result = supervisor.execute(
                SupervisorRequest(
                    goal="Build sample-project-bad-build",
                    task_kind="build",
                    project_id="sample-project-bad-build",
                )
            )
            _assert(not fail_result.ok, "failing build should not succeed")
            _assert(fail_result.status == "failed", "failing build status mismatch")

            summaries_dir = REPO_ROOT / "sam_v2" / "logs" / "summaries"
            summary_log = _latest_file(summaries_dir, f"sam_v2_workflow_{fail_result.metadata['plan_id']}_*.json")
            payload = json.loads(summary_log.read_text(encoding="utf-8"))
            _assert(payload["result"]["status"] == "failed", "failing build workflow summary status mismatch")
            _assert("intentional build failure" in (fail_result.error_message or ""), "failing build message mismatch")
            print("[PASS] Real failing build command through supervisor")
        except Exception as exc:
            logger.fail_step("supervisor_failing_build_command", str(exc))
            failures.append(f"Supervisor failing build command failed: {exc}")
        else:
            logger.pass_step("supervisor_failing_build_command")

        try:
            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    """
                    SELECT event_type, actor
                    FROM audit_events
                    WHERE event_type = 'worker_command_executed'
                    ORDER BY id ASC
                    """
                ).fetchall()
            _assert(len(rows) >= 2, "expected successful worker audit rows for test/build")
            _assert(any("sam_v2.workers.test" in row[1] for row in rows), "missing test worker audit row")
            _assert(any("sam_v2.workers.dev" in row[1] for row in rows), "missing build worker audit row")
            print("[PASS] Test/build audit trail")
        except Exception as exc:
            logger.fail_step("supervisor_test_build_audit", str(exc))
            failures.append(f"Supervisor test/build audit failed: {exc}")
        else:
            logger.pass_step("supervisor_test_build_audit")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Run tests and builds live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All run tests and builds live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
