"""Real project status reporting validation for Sam v2."""

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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_sam(data_dir: Path, text: str) -> dict:
    command = [
        sys.executable,
        "-m",
        "sam_v2",
        "--data-dir",
        str(data_dir),
        "--once",
        text,
        "--json",
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode not in {0, 2}:
        raise AssertionError(f"sam_v2 status request failed: {completed.stderr or completed.stdout}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"sam_v2 status request did not return JSON: {exc}\n{completed.stdout}") from exc


def main() -> int:
    print("=== Sam v2 Project Status Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_status_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    data_dir = temp_root / f"sam_v2_status_{uuid.uuid4().hex[:8]}"
    project_name = f"Sam Status {uuid.uuid4().hex[:6]}"
    project_slug = project_name.lower().replace(" ", "_")
    project_root = REPO_ROOT / "sam_v2" / "workspace" / "projects" / project_slug

    try:
        try:
            scaffold = _run_sam(data_dir, f"start a new html game project called {project_name}")
            _assert(scaffold["status"] == "success", "scaffold prerequisite failed")
            plan = _run_sam(data_dir, f"plan project {project_name}")
            _assert(plan["status"] == "success", "planning prerequisite failed")
            execute = _run_sam(data_dir, f"execute delegated task for project {project_name}: add score tracking")
            _assert(execute["status"] == "success", "execution prerequisite failed")

            status = _run_sam(data_dir, f"show status for project {project_name}")
            _assert(status["status"] == "success", "status request failed")
            _assert(status["metadata"].get("intent") == "show_project_status", "status intent mismatch")
            _assert(status["metadata"].get("branch"), "missing branch in project status")
            _assert(isinstance(status["metadata"].get("is_clean"), bool), "missing clean/dirty flag")
            _assert(isinstance(status["metadata"].get("changed_files", []), list), "missing changed files list")
            _assert(len(status["metadata"].get("completed_items", [])) >= 1, "missing completed items")
            _assert(len(status["metadata"].get("next_items", [])) >= 2, "missing next items")
            _assert(any("Mason completed" in item for item in status["metadata"].get("worker_updates", [])), "missing Mason update")
            _assert("completed implementation milestone" in status["summary"], "summary missing progress language")
            print("[PASS] Sam can merge repo inspection and saved project progress in one status report")
            logger.pass_step("show_project_status")
        except Exception as exc:
            logger.fail_step("show_project_status", str(exc))
            failures.append(f"Project status reporting failed: {exc}")
    finally:
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            shutil.rmtree(project_root, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project status live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All project status live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
