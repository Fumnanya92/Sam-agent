"""Real tic-tac-toe project creation, recall, and run validation for Sam v2."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import AuthorityConfig, AuthorityEngine
from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.memory.manager import load_memory
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.workers import FileWriteSpec, ToolingWorker


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tic Tac Toe</title>
  <style>
    body { font-family: Arial, sans-serif; display: grid; place-items: center; min-height: 100vh; background: #f3f4f6; }
    .game { text-align: center; }
    .board { display: grid; grid-template-columns: repeat(3, 90px); gap: 8px; margin: 16px auto; }
    button.cell { width: 90px; height: 90px; font-size: 2rem; border: 0; border-radius: 12px; background: white; box-shadow: 0 4px 12px rgba(0,0,0,.08); cursor: pointer; }
    #status { font-weight: 700; }
  </style>
</head>
<body>
  <main class="game">
    <h1>Tic Tac Toe</h1>
    <p id="status">Player X's turn</p>
    <section class="board" id="board"></section>
    <button id="reset">Reset</button>
  </main>
  <script>
    const board = document.getElementById("board");
    const status = document.getElementById("status");
    const reset = document.getElementById("reset");
    let cells = Array(9).fill("");
    let player = "X";
    let winner = "";
    const wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
    function draw() {
      board.innerHTML = "";
      cells.forEach((value, index) => {
        const button = document.createElement("button");
        button.className = "cell";
        button.textContent = value;
        button.addEventListener("click", () => play(index));
        board.appendChild(button);
      });
      status.textContent = winner ? winner : `Player ${player}'s turn`;
    }
    function play(index) {
      if (cells[index] || winner) return;
      cells[index] = player;
      const line = wins.find(([a,b,c]) => cells[a] && cells[a] === cells[b] && cells[b] === cells[c]);
      if (line) {
        winner = `Player ${player} wins!`;
      } else if (cells.every(Boolean)) {
        winner = "It's a draw!";
      } else {
        player = player === "X" ? "O" : "X";
      }
      draw();
    }
    reset.addEventListener("click", () => {
      cells = Array(9).fill("");
      player = "X";
      winner = "";
      draw();
    });
    draw();
  </script>
</body>
</html>
"""

RUN_GAME = """from pathlib import Path

index_path = Path("index.html")
content = index_path.read_text(encoding="utf-8")
assert "<title>Tic Tac Toe</title>" in content
assert "Player X's turn" in content
assert "function play(index)" in content
print("tic tac game ready")
"""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Tic Tac Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_tic_tac_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_tic_tac_{uuid.uuid4().hex[:8]}"
    project_dir = tmp_dir / "tic_tac_html"
    project_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "tic_tac_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"

    try:
        writer = ToolingWorker(
            db_path=db_path,
            authority_engine=AuthorityEngine(AuthorityConfig(default_level=10)),
        )
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        project_registry = ProjectRegistry(projects_path)

        try:
            html_result, _html_task = writer.execute_write(
                FileWriteSpec(
                    name="write_tic_tac_index",
                    worker_type="code",
                    target_path=project_dir / "index.html",
                    content=INDEX_HTML,
                    description="Write a minimal HTML tic-tac-toe game.",
                )
            )
            _assert(html_result.ok, f"index.html write failed: {html_result.error_message}")

            runner_result, _runner_task = writer.execute_write(
                FileWriteSpec(
                    name="write_tic_tac_runner",
                    worker_type="code",
                    target_path=project_dir / "run_game.py",
                    content=RUN_GAME,
                    description="Write a simple run check for the tic-tac-toe game.",
                )
            )
            _assert(runner_result.ok, f"run_game.py write failed: {runner_result.error_message}")

            register_result = project_registry.register(
                ProjectRecord(
                    project_id="tic-tac-html",
                    name="tic_tac_html",
                    root_path=str(project_dir),
                    stack="html + javascript",
                    run_command=[sys.executable, "run_game.py"],
                    important_files=["index.html", "run_game.py"],
                )
            )
            _assert(register_result.ok, f"project registration failed: {register_result.error_message}")
            _assert((project_dir / "index.html").exists(), "index.html was not created")
            _assert((project_dir / "run_game.py").exists(), "run_game.py was not created")
            print("[PASS] Sam worker created minimal tic-tac project files")
        except Exception as exc:
            logger.fail_step("create_tic_tac_project", str(exc))
            failures.append(f"Tic-tac project creation failed: {exc}")
        else:
            logger.pass_step("create_tic_tac_project")

        try:
            show_result = runtime.handle_text("show project tic-tac-html")
            _assert(show_result.ok, "project lookup failed")
            _assert(show_result.metadata.get("project_id") == "tic-tac-html", "project id mismatch")
            _assert(Path(show_result.metadata.get("root_path", "")).resolve() == project_dir.resolve(), "project path mismatch")

            memory_result, memory = load_memory(memory_path)
            _assert(memory_result.ok, f"memory load failed: {memory_result.error_message}")
            stored_project_id = memory.get("daily_state", {}).get("last_project_id", {}).get("value")
            _assert(stored_project_id == "tic-tac-html", "last_project_id memory mismatch")
            print("[PASS] Sam remembers where the tic-tac project is")
        except Exception as exc:
            logger.fail_step("remember_project_location", str(exc))
            failures.append(f"Project recall failed: {exc}")
        else:
            logger.pass_step("remember_project_location")

        try:
            run_result = runtime.handle_text("run it")
            _assert(run_result.ok, f"run it failed: {run_result.error_message}")
            _assert(run_result.metadata.get("intent") == "run_project", "run intent mismatch")
            _assert(run_result.metadata.get("project_id") == "tic-tac-html", "run project id mismatch")
            _assert("tic tac game ready" in run_result.metadata.get("stdout", ""), "run output mismatch")
            print("[PASS] Sam can run the remembered tic-tac project when asked")
        except Exception as exc:
            logger.fail_step("run_remembered_project", str(exc))
            failures.append(f"Run remembered project failed: {exc}")
        else:
            logger.pass_step("run_remembered_project")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Tic Tac runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All tic-tac runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
