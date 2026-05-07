"""Live validation for the runnable Sam v2 entrypoint."""

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
        raise AssertionError(f"sam_v2 entrypoint failed: {completed.stderr or completed.stdout}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"sam_v2 entrypoint did not return JSON: {exc}\n{completed.stdout}") from exc


def main() -> int:
    print("=== Sam v2 Main Entrypoint Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_main_entry_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    data_dir = temp_root / f"sam_v2_entry_{uuid.uuid4().hex[:8]}"
    project_name = f"Sam Entrypoint {uuid.uuid4().hex[:6]}"
    project_slug = project_name.lower().replace(" ", "_")
    project_root = REPO_ROOT / "sam_v2" / "workspace" / "projects" / project_slug

    try:
        try:
            capabilities = _run_sam(data_dir, "what can you do")
            _assert(capabilities["status"] == "success", "capabilities request failed")
            _assert(len(capabilities["metadata"].get("available_capabilities", [])) >= 3, "capability list too small")
            print("[PASS] Sam v2 entrypoint can boot and answer a runtime request")
        except Exception as exc:
            logger.fail_step("entry_boot", str(exc))
            failures.append(f"Entrypoint boot test failed: {exc}")
        else:
            logger.pass_step("entry_boot")

        try:
            scaffold = _run_sam(data_dir, f"start a new html game project called {project_name}")
            _assert(scaffold["status"] == "success", f"scaffold failed: {scaffold.get('error_message')}")
            _assert(project_root.exists(), "scaffolded project root missing")

            plan = _run_sam(data_dir, f"plan project {project_name}")
            _assert(plan["status"] == "success", "planning through entrypoint failed")

            execute = _run_sam(data_dir, f"execute delegated task for project {project_name}: add score tracking")
            _assert(execute["status"] == "success", "delegated execution through entrypoint failed")
            _assert(
                "scaffold project ready" in execute["metadata"].get("validation_stdout", ""),
                "validation output mismatch",
            )
            print("[PASS] Sam v2 entrypoint can scaffold, plan, and execute a delegated task")
        except Exception as exc:
            logger.fail_step("entry_project_flow", str(exc))
            failures.append(f"Entrypoint project flow failed: {exc}")
        else:
            logger.pass_step("entry_project_flow")

        try:
            report = _run_sam(data_dir, f"show delegation for project {project_name}")
            _assert(report["status"] == "success", "delegation lookup through entrypoint failed")
            report_text = report["metadata"].get("delegation_report", "")
            _assert("Mason" in report_text and "Beacon" in report_text and "Pilot" in report_text, "worker names missing")
            _assert("add score tracking" in report_text, "executed task not reflected in report")
            print("[PASS] Sam v2 entrypoint can report who did what")
        except Exception as exc:
            logger.fail_step("entry_delegation_report", str(exc))
            failures.append(f"Entrypoint delegation report failed: {exc}")
        else:
            logger.pass_step("entry_delegation_report")
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
        print("[FAIL] Main entrypoint live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All Sam v2 main entrypoint live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
