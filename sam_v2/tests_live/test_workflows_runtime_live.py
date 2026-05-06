"""Runtime-backed validation for Sam v2 task/goal/pipeline workflows."""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event
from sam_v2.workflows import GoalService, PipelineService


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Workflows Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_workflows_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workflows_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "workflows_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        goal_service = GoalService(db_path)
        pipeline_service = PipelineService(db_path)

        try:
            create_goal = runtime.handle_text("create goal: Validate workflow runtime path")
            _assert(create_goal.ok, "runtime goal creation failed")
            _assert(create_goal.metadata.get("intent") == "create_goal", "runtime goal intent mismatch")

            list_goals = runtime.handle_text("list goals")
            _assert(list_goals.ok, "runtime list goals failed")
            _assert(list_goals.metadata.get("count", 0) >= 1, "runtime goal count mismatch")
            _assert(
                "Validate workflow runtime path" in list_goals.metadata.get("titles", []),
                "created goal title missing from runtime list",
            )

            audit_result, audit_event = fetch_audit_event(db_path, int(create_goal.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "runtime goal audit event missing")
            audit_payload = json.loads(audit_event.metadata_json)
            _assert(audit_payload.get("intent") == "create_goal", "runtime goal audit intent mismatch")
            print("[PASS] Runtime goal create/list path")
        except Exception as exc:
            logger.fail_step("runtime_goal_create_list", str(exc))
            failures.append(f"Runtime goal create/list failed: {exc}")
        else:
            logger.pass_step("runtime_goal_create_list")

        try:
            goal_result, goals = goal_service.list_goals(status="active")
            _assert(goal_result.ok and goals, "goal fetch after runtime create failed")
            created_goal = next((item for item in goals if item.title == "Validate workflow runtime path"), None)
            _assert(created_goal is not None, "created goal not found for score update")

            update_result, updated_goal = goal_service.update_score(
                created_goal.id,
                0.82,
                "Runtime workflow path validated",
            )
            _assert(update_result.ok and updated_goal is not None, "goal score update failed")
            _assert(updated_goal.health == "on_track", "goal health mismatch after update")
            print("[PASS] Goal score update path")
        except Exception as exc:
            logger.fail_step("goal_score_update", str(exc))
            failures.append(f"Goal score update failed: {exc}")
        else:
            logger.pass_step("goal_score_update")

        try:
            create_draft = runtime.handle_text("create draft: Workflow runtime draft for validation")
            _assert(create_draft.ok, "runtime draft creation failed")
            _assert(create_draft.metadata.get("intent") == "create_draft", "runtime draft intent mismatch")

            list_workflows = runtime.handle_text("list workflows")
            _assert(list_workflows.ok, "runtime list workflows failed")
            _assert(list_workflows.metadata.get("count", 0) >= 1, "runtime workflow count mismatch")
            _assert(
                "Workflow runtime draft for validation" in list_workflows.metadata.get("titles", []),
                "runtime draft title missing from workflow list",
            )
            print("[PASS] Runtime workflow draft create/list path")
        except Exception as exc:
            logger.fail_step("runtime_workflow_create_list", str(exc))
            failures.append(f"Runtime workflow draft create/list failed: {exc}")
        else:
            logger.pass_step("runtime_workflow_create_list")

        try:
            document_result, documents = pipeline_service.list_documents(limit=20)
            _assert(document_result.ok and documents, "pipeline list after runtime create failed")
            created_document = next(
                (item for item in documents if item.title == "Workflow runtime draft for validation"),
                None,
            )
            _assert(created_document is not None, "created pipeline document not found")

            invalid_publish_result, invalid_publish = pipeline_service.publish(created_document.id, "log")
            _assert(not invalid_publish_result.ok and invalid_publish is None, "publish-before-approve should fail")
            _assert(invalid_publish_result.next_action == "ask_user", "invalid publish next_action mismatch")

            review_result, reviewed = pipeline_service.submit_for_review(created_document.id)
            _assert(review_result.ok and reviewed is not None and reviewed.stage == "review", "review transition failed")

            approve_result, approved = pipeline_service.approve(created_document.id)
            _assert(approve_result.ok and approved is not None and approved.stage == "approved", "approve transition failed")

            publish_result, published = pipeline_service.publish(created_document.id, "log")
            _assert(publish_result.ok and published is not None and published.stage == "published", "publish transition failed")
            _assert(published.published_channel == "log", "published channel mismatch")
            print("[PASS] Pipeline review/approve/publish path")
        except Exception as exc:
            logger.fail_step("pipeline_transition_flow", str(exc))
            failures.append(f"Pipeline transition flow failed: {exc}")
        else:
            logger.pass_step("pipeline_transition_flow")

        try:
            with sqlite3.connect(db_path) as connection:
                audit_rows = connection.execute(
                    """
                    SELECT event_type
                    FROM audit_events
                    WHERE event_type IN (
                        'goal_created',
                        'goal_score_updated',
                        'pipeline_draft_created',
                        'pipeline_stage_changed'
                    )
                    ORDER BY id ASC
                    """
                ).fetchall()
            event_types = [row[0] for row in audit_rows]
            _assert("goal_created" in event_types, "goal_created audit missing")
            _assert("goal_score_updated" in event_types, "goal_score_updated audit missing")
            _assert("pipeline_draft_created" in event_types, "pipeline_draft_created audit missing")
            _assert(event_types.count("pipeline_stage_changed") >= 3, "expected at least three pipeline stage audits")
            print("[PASS] Workflow audit trail")
        except Exception as exc:
            logger.fail_step("workflow_audit_trail", str(exc))
            failures.append(f"Workflow audit trail failed: {exc}")
        else:
            logger.pass_step("workflow_audit_trail")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workflows runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All workflows runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
