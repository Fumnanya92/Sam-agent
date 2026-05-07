"""Real modular project scaffolding validation for Sam v2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.memory.manager import load_memory
from sam_v2.projects import ProjectRegistry


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Project Scaffold Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_project_scaffold_live")

    runtime_root = REPO_ROOT / "sam_v2" / "workspace" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    db_path = runtime_root / "scaffold_runtime.db"
    memory_path = runtime_root / "memory.json"
    session_path = runtime_root / "session.json"
    projects_path = runtime_root / "projects.json"

    project_name = "Sam Tic Tac Modular"
    project_id = "sam_tic_tac_modular"
    project_root = REPO_ROOT / "sam_v2" / "workspace" / "projects" / project_id

    runtime = SamRuntime(
        db_path=db_path,
        memory_path=memory_path,
        session_path=session_path,
    )

    try:
        scaffold_result = runtime.handle_text(f"start a new html game project called {project_name}")
        _assert(scaffold_result.ok, f"scaffold failed: {scaffold_result.error_message or scaffold_result.summary}")
        _assert(scaffold_result.metadata.get("intent") == "scaffold_project", "intent mismatch")
        _assert(Path(scaffold_result.metadata.get("root_path", "")).resolve() == project_root.resolve(), "root path mismatch")
        delegation = scaffold_result.metadata.get("delegation", [])
        _assert(isinstance(delegation, list) and len(delegation) >= 6, "delegation trace missing")
        _assert(all(item.get("worker_name") == "Mason" for item in delegation), "worker naming mismatch")
        _assert("Mason scaffolded" in scaffold_result.summary, "summary should mention named worker")
        print(f"[PASS] Sam scaffolded a modular project at {project_root}")
        logger.pass_step("scaffold_project")
    except Exception as exc:
        logger.fail_step("scaffold_project", str(exc))
        failures.append(f"Project scaffolding failed: {exc}")

    try:
        expected_files = ["index.html", "styles.css", "app.js", "README.md", "PLAN.md", "run_project.py"]
        for filename in expected_files:
            _assert((project_root / filename).exists(), f"missing {filename}")

        index_text = (project_root / "index.html").read_text(encoding="utf-8")
        styles_text = (project_root / "styles.css").read_text(encoding="utf-8")
        app_text = (project_root / "app.js").read_text(encoding="utf-8")
        _assert('href="styles.css"' in index_text, "index should link stylesheet")
        _assert('src="app.js"' in index_text, "index should load app script")
        _assert("function playTurn(index)" in app_text, "game logic should live in app.js")
        _assert(".board {" in styles_text, "styles should be separated into styles.css")
        print("[PASS] Sam scaffolded separate modules instead of one dumped file")
        logger.pass_step("modular_structure")
    except Exception as exc:
        logger.fail_step("modular_structure", str(exc))
        failures.append(f"Modular structure validation failed: {exc}")

    try:
        project_registry = ProjectRegistry(projects_path)
        registry_result, project = project_registry.get_project(project_id)
        _assert(registry_result.ok and project is not None, "project was not registered")
        _assert(Path(project.root_path).resolve() == project_root.resolve(), "registered project path mismatch")

        show_result = runtime.handle_text("show project Sam Tic Tac Modular")
        _assert(show_result.ok, "project lookup failed")
        _assert(show_result.metadata.get("project_id") == project_id, "project details mismatch")

        memory_result, memory = load_memory(memory_path)
        _assert(memory_result.ok, f"memory load failed: {memory_result.error_message}")
        stored_project_id = memory.get("daily_state", {}).get("last_project_id", {}).get("value")
        _assert(stored_project_id == project_id, "last_project_id memory mismatch")
        print("[PASS] Sam registered and remembered the scaffolded project location")
        logger.pass_step("register_and_remember")
    except Exception as exc:
        logger.fail_step("register_and_remember", str(exc))
        failures.append(f"Registry/memory validation failed: {exc}")

    try:
        previous_no_browser = os.environ.get("SAM_V2_NO_BROWSER")
        os.environ["SAM_V2_NO_BROWSER"] = "1"
        run_result = runtime.handle_text("run it")
        _assert(run_result.ok, f"run it failed: {run_result.error_message or run_result.summary}")
        _assert(run_result.metadata.get("project_id") == project_id, "run project id mismatch")
        _assert(run_result.metadata.get("worker_name") == "Pilot", "run worker should be named Pilot")
        _assert("launch target " in run_result.metadata.get("stdout", ""), "run output mismatch")
        print("[PASS] Sam can run the remembered scaffolded project later")
        logger.pass_step("run_project")
    except Exception as exc:
        logger.fail_step("run_project", str(exc))
        failures.append(f"Run remembered scaffold failed: {exc}")
    finally:
        if previous_no_browser is None:
            os.environ.pop("SAM_V2_NO_BROWSER", None)
        else:
            os.environ["SAM_V2_NO_BROWSER"] = previous_no_browser
        runtime.shutdown()

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Project scaffold live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print(f"[PASS] All scaffold live checks passed; project saved at {project_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
