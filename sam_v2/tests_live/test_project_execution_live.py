"""Real delegated project-task execution validation for Sam v2."""

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
    print("=== Sam v2 Project Execution Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_execution_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    db_path = runtime_root / "execution_runtime.db"
    memory_path = runtime_root / "execution_memory.json"
    session_path = runtime_root / "execution_session.json"

    project_name = "Sam Tic Tac Execution"
    project_root = REPO_ROOT / "sam_v2" / "workspace" / "projects" / "sam_tic_tac_execution"

    runtime = SamRuntime(
        db_path=db_path,
        memory_path=memory_path,
        session_path=session_path,
    )

    try:
        scaffold_result = runtime.handle_text(f"start a new html game project called {project_name}")
        _assert(scaffold_result.ok, "project scaffolding prerequisite failed")
        plan_result = runtime.handle_text(f"plan project {project_name}")
        _assert(plan_result.ok, "project planning prerequisite failed")

        execute_result = runtime.handle_text(
            f"execute delegated task for project {project_name}: add score tracking"
        )
        _assert(execute_result.ok, f"execution failed: {execute_result.error_message or execute_result.summary}")
        _assert(execute_result.metadata.get("intent") == "execute_project_task", "execution intent mismatch")
        _assert("scaffold project ready" in execute_result.metadata.get("validation_stdout", ""), "validation output mismatch")
        delegation = execute_result.metadata.get("delegation", [])
        worker_names = [item.get("worker_name") for item in delegation]
        _assert("Mason" in worker_names and "Beacon" in worker_names and "Pilot" in worker_names, "named worker trace missing")
        print("[PASS] Sam executed the delegated task with named workers")
        logger.pass_step("execute_project_task")
    except Exception as exc:
        logger.fail_step("execute_project_task", str(exc))
        failures.append(f"Delegated execution failed: {exc}")

    try:
        index_text = (project_root / "index.html").read_text(encoding="utf-8")
        styles_text = (project_root / "styles.css").read_text(encoding="utf-8")
        app_text = (project_root / "app.js").read_text(encoding="utf-8")
        _assert('id="score-x"' in index_text and 'id="score-o"' in index_text, "scoreboard markup missing")
        _assert(".scoreboard {" in styles_text, "scoreboard styles missing")
        _assert("const scores = { X: 0, O: 0 };" in app_text, "scoreboard state missing")
        _assert("scores[player] += 1;" in app_text, "score increment logic missing")
        print("[PASS] Sam changed the real project files for the planned task")
        logger.pass_step("project_files_updated")
    except Exception as exc:
        logger.fail_step("project_files_updated", str(exc))
        failures.append(f"Project file update validation failed: {exc}")

    try:
        report_result = runtime.handle_text(f"show delegation for project {project_name}")
        _assert(report_result.ok, f"delegation lookup failed: {report_result.error_message or report_result.summary}")
        report_text = report_result.metadata.get("delegation_report", "")
        _assert("Mason completed the `add score tracking` implementation task." in report_text, "Mason completion missing")
        _assert("Beacon validated the updated project" in report_text, "Beacon validation missing")
        _assert("Pilot refreshed this delegation report" in report_text, "Pilot report refresh missing")
        print("[PASS] Sam updated the saved delegation report after execution")
        logger.pass_step("delegation_report_updated")
    except Exception as exc:
        logger.fail_step("delegation_report_updated", str(exc))
        failures.append(f"Delegation report update validation failed: {exc}")
    finally:
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project execution live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All project execution live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
