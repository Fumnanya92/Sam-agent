"""Live test for Sam v2 workflow foundations."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.storage.db import fetch_audit_event, init_storage
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.workflows import GoalService, PipelineService, ensure_workflow_schema


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Workflows Live Test ===")
    failures = []
    logger = TestRunLogger("test_workflows_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_workflows_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "workflows_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")
        schema_result = ensure_workflow_schema(db_path)
        _assert(schema_result.ok, f"workflow schema init failed: {schema_result.error_message}")

        goal_service = GoalService(db_path)
        pipeline_service = PipelineService(db_path)

        try:
            create_result, goal = goal_service.create_goal(
                title="Ship Sam v2 foundations",
                level="objective",
                success_criteria="Storage, daemon, memory, approvals, workflows all migrated",
                tags=["sam_v2", "migration"],
            )
            _assert(create_result.ok and goal is not None, "goal create failed")

            update_result, updated_goal = goal_service.update_score(goal.id, 0.65, "Workflow layer added")
            _assert(update_result.ok and updated_goal is not None, "goal score update failed")
            _assert(updated_goal.health == "at_risk", "goal health mapping mismatch")

            list_result, goals = goal_service.list_goals(status="active")
            _assert(list_result.ok and len(goals) >= 1, "goal list failed")
            print("[PASS] Goal create/update/list")
        except Exception as exc:
            logger.fail_step("goal_create_update_list", str(exc))
            failures.append(f"Goal workflow test failed: {exc}")
        else:
            logger.pass_step("goal_create_update_list")

        try:
            draft_result, draft = pipeline_service.create_draft(
                title="Migration update",
                body="Storage and daemon foundations are in place.",
                content_type="report",
                tags=["status"],
            )
            _assert(draft_result.ok and draft is not None, "draft create failed")

            invalid_publish_result, invalid_publish = pipeline_service.publish(draft.id, "log")
            _assert(not invalid_publish_result.ok and invalid_publish is None, "publish-before-approve did not fail")

            review_result, in_review = pipeline_service.submit_for_review(draft.id)
            _assert(review_result.ok and in_review is not None and in_review.stage == "review", "submit for review failed")

            approve_result, approved = pipeline_service.approve(draft.id)
            _assert(approve_result.ok and approved is not None and approved.stage == "approved", "approve failed")

            publish_result, published = pipeline_service.publish(draft.id, "log")
            _assert(publish_result.ok and published is not None and published.stage == "published", "publish failed")
            print("[PASS] Pipeline draft/review/approve/publish")
        except Exception as exc:
            logger.fail_step("pipeline_flow", str(exc))
            failures.append(f"Pipeline workflow test failed: {exc}")
        else:
            logger.pass_step("pipeline_flow")

        try:
            audit_result, audit_event = fetch_audit_event(db_path, 1)
            _assert(audit_result.ok and audit_event is not None, "workflow audit event missing")
            print("[PASS] Workflow audit logging")
        except Exception as exc:
            logger.fail_step("workflow_audit_logging", str(exc))
            failures.append(f"Workflow audit test failed: {exc}")
        else:
            logger.pass_step("workflow_audit_logging")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Workflows live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All workflow live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
