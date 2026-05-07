"""Real project progress reporting validation for Sam v2."""

from __future__ import annotations

import sys
import uuid
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
    print("=== Sam v2 Project Progress Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_progress_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex[:8]
    db_path = runtime_root / f"progress_runtime_{run_id}.db"
    memory_path = runtime_root / f"progress_memory_{run_id}.json"
    session_path = runtime_root / f"progress_session_{run_id}.json"

    project_name = f"Sam Tic Tac Progress {run_id}"

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
        _assert(execute_result.ok, "project execution prerequisite failed")

        progress_result = runtime.handle_text(f"show progress for project {project_name}")
        _assert(progress_result.ok, f"progress request failed: {progress_result.error_message or progress_result.summary}")
        _assert(progress_result.metadata.get("intent") == "show_project_progress", "progress intent mismatch")
        completed_items = progress_result.metadata.get("completed_items", [])
        next_items = progress_result.metadata.get("next_items", [])
        worker_updates = progress_result.metadata.get("worker_updates", [])
        _assert(len(completed_items) >= 1, "missing completed progress items")
        _assert(len(next_items) >= 2, "missing next progress items")
        _assert(any("Mason completed" in item for item in worker_updates), "missing Mason worker update")
        _assert(any("Beacon validated" in item for item in worker_updates), "missing Beacon worker update")
        _assert(any("Pilot refreshed" in item for item in worker_updates), "missing Pilot worker update")
        print("[PASS] Sam can summarize real project progress from saved planning state")
        logger.pass_step("show_project_progress")
    except Exception as exc:
        logger.fail_step("show_project_progress", str(exc))
        failures.append(f"Project progress reporting failed: {exc}")
    finally:
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project progress live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All project progress live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
