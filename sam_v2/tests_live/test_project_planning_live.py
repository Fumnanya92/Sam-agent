"""Real project planning and delegation reporting validation for Sam v2."""

from __future__ import annotations

import sys
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
    print("=== Sam v2 Project Planning Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_planning_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    db_path = runtime_root / "planning_runtime.db"
    memory_path = runtime_root / "planning_memory.json"
    session_path = runtime_root / "planning_session.json"

    project_name = "Sam Tic Tac Planning"
    project_root = REPO_ROOT / "sam_v2" / "workspace" / "projects" / "sam_tic_tac_planning"

    runtime = SamRuntime(
        db_path=db_path,
        memory_path=memory_path,
        session_path=session_path,
    )

    try:
        scaffold_result = runtime.handle_text(f"start a new html game project called {project_name}")
        _assert(scaffold_result.ok, "project scaffolding prerequisite failed")

        plan_result = runtime.handle_text(f"plan project {project_name}")
        _assert(plan_result.ok, f"project planning failed: {plan_result.error_message or plan_result.summary}")
        _assert(plan_result.metadata.get("intent") == "plan_project", "plan intent mismatch")
        delegation = plan_result.metadata.get("delegation", [])
        _assert(len(delegation) == 3, "expected three delegated planning artifacts")
        worker_names = [item.get("worker_name") for item in delegation]
        _assert(worker_names == ["Mason", "Beacon", "Pilot"], f"unexpected worker order: {worker_names}")
        print("[PASS] Sam planned the project with named workers")
        logger.pass_step("plan_project")
    except Exception as exc:
        logger.fail_step("plan_project", str(exc))
        failures.append(f"Project planning failed: {exc}")

    try:
        implementation = project_root / "IMPLEMENTATION_PLAN.md"
        testing = project_root / "TESTING_PLAN.md"
        delegation_report = project_root / "DELEGATION.md"
        for path in [implementation, testing, delegation_report]:
            _assert(path.exists(), f"missing {path.name}")

        _assert("Mason" in delegation_report.read_text(encoding="utf-8"), "delegation report should mention Mason")
        _assert("Beacon" in delegation_report.read_text(encoding="utf-8"), "delegation report should mention Beacon")
        _assert("Pilot" in delegation_report.read_text(encoding="utf-8"), "delegation report should mention Pilot")
        _assert("Build slices" in implementation.read_text(encoding="utf-8"), "implementation plan content mismatch")
        _assert("Current checks" in testing.read_text(encoding="utf-8"), "testing plan content mismatch")
        print("[PASS] Sam wrote separate planning artifacts instead of one mixed file")
        logger.pass_step("planning_artifacts")
    except Exception as exc:
        logger.fail_step("planning_artifacts", str(exc))
        failures.append(f"Planning artifact validation failed: {exc}")

    try:
        report_result = runtime.handle_text(f"show delegation for project {project_name}")
        _assert(report_result.ok, f"delegation report retrieval failed: {report_result.error_message or report_result.summary}")
        _assert(report_result.metadata.get("intent") == "show_delegation", "delegation intent mismatch")
        report_text = report_result.metadata.get("delegation_report", "")
        _assert("Mason" in report_text and "Beacon" in report_text and "Pilot" in report_text, "delegation report text mismatch")
        print("[PASS] Sam can tell us who did what")
        logger.pass_step("show_delegation")
    except Exception as exc:
        logger.fail_step("show_delegation", str(exc))
        failures.append(f"Delegation reporting failed: {exc}")
    finally:
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project planning live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All project planning live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
