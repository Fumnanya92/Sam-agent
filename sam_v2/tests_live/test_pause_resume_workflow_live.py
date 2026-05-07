"""Real pause/resume workflow validation for Sam v2."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.supervisor import ExecutionPlan, ExecutionStep, WorkflowBridge
from sam_v2.workers import CommandSpec


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Pause Resume Workflow Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_pause_resume_workflow_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_pause_resume_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "pause_resume_live.db"

    step_one = tmp_dir / "step_one.py"
    step_two = tmp_dir / "step_two.py"
    marker = tmp_dir / "step_one_done.txt"
    final_marker = tmp_dir / "workflow_finished.txt"

    step_one.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"Path(r'{marker.as_posix()}').write_text('step one complete', encoding='utf-8')",
                "print('step one done')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    step_two.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"marker = Path(r'{marker.as_posix()}')",
                f"final_marker = Path(r'{final_marker.as_posix()}')",
                "assert marker.exists()",
                "final_marker.write_text('workflow resumed and finished', encoding='utf-8')",
                "print('step two done')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")
        bridge = WorkflowBridge(db_path=db_path)

        try:
            plan = ExecutionPlan(
                plan_id="pause-resume-plan",
                goal="Pause and resume a real workflow",
                steps=[
                    ExecutionStep(
                        step_id="step-one",
                        title="Run the first real workflow command",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="pause_resume_step_one",
                            worker_type="test",
                            command=[sys.executable, str(step_one)],
                            description="Run the first step of the pause/resume workflow.",
                            cwd=REPO_ROOT,
                        ),
                    ),
                    ExecutionStep(
                        step_id="pause-here",
                        title="Pause after the first real step",
                        step_type="pause",
                        pause_reason="waiting for resume validation",
                    ),
                    ExecutionStep(
                        step_id="step-two",
                        title="Run the second real workflow command",
                        step_type="worker_command",
                        command_spec=CommandSpec(
                            name="pause_resume_step_two",
                            worker_type="test",
                            command=[sys.executable, str(step_two)],
                            description="Run the second step after workflow resume.",
                            cwd=REPO_ROOT,
                        ),
                    ),
                ],
            )
            pause_result = bridge.execute_plan(plan)
            _assert(pause_result.status == "partial", "workflow should pause with partial status")
            _assert(pause_result.next_action == "resume_workflow", "pause next_action mismatch")
            _assert(marker.exists(), "first step marker missing before pause")
            paused_plan_id = pause_result.metadata.get("paused_plan_id")
            _assert(isinstance(paused_plan_id, str) and paused_plan_id.strip(), "paused plan id missing")
            paused_store = bridge.paused_store_path
            _assert(paused_store.exists(), "paused workflow store missing")
            payload = json.loads(paused_store.read_text(encoding="utf-8"))
            _assert(len(payload) == 1, "expected one paused workflow record")
            _assert(payload[0]["remaining_steps"][0]["step_id"] == "step-two", "remaining step mismatch")
            print("[PASS] Workflow pauses and persists remaining steps")
        except Exception as exc:
            logger.fail_step("workflow_pause_persistence", str(exc))
            failures.append(f"Workflow pause persistence failed: {exc}")
        else:
            logger.pass_step("workflow_pause_persistence")

        try:
            resume_result = bridge.resume_plan(paused_plan_id)
            _assert(resume_result.ok, f"workflow resume failed: {resume_result.error_message}")
            _assert(resume_result.metadata.get("completed_steps") == ["step-one", "pause-here", "step-two"], "resumed completed steps mismatch")
            _assert(final_marker.exists(), "final marker missing after resume")
            payload = json.loads(bridge.paused_store_path.read_text(encoding="utf-8"))
            _assert(payload == [], "paused workflow store should be cleared after resume")
            print("[PASS] Workflow resumes and completes remaining real steps")
        except Exception as exc:
            logger.fail_step("workflow_resume_completion", str(exc))
            failures.append(f"Workflow resume completion failed: {exc}")
        else:
            logger.pass_step("workflow_resume_completion")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Pause/resume workflow live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All pause/resume workflow live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
