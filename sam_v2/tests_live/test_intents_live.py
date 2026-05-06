"""Live test for the Sam v2 intent and capability layer."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import init_storage
from sam_v2.intents import IntentRouter


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Intents Live Test ===")
    failures = []
    logger = TestRunLogger("test_intents_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_intents_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "intents_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        try:
            router = IntentRouter(db_path=db_path)
            result = router.handle("what can you do")
            _assert(result.ok, "capabilities intent failed")
            _assert(len(result.metadata["capabilities"]) >= 3, "capabilities list too small")
            print("[PASS] Capabilities intent")
        except Exception as exc:
            logger.fail_step("capabilities_intent", str(exc))
            failures.append(f"Capabilities intent test failed: {exc}")
        else:
            logger.pass_step("capabilities_intent")

        try:
            router = IntentRouter(db_path=db_path)
            create_goal = router.handle("create goal: Ship the intent layer")
            _assert(create_goal.ok, "create goal intent failed")

            list_goals = router.handle("list goals")
            _assert(list_goals.ok, "list goals intent failed")
            _assert(list_goals.metadata["count"] >= 1, "goal count mismatch")
            print("[PASS] Goal intents")
        except Exception as exc:
            logger.fail_step("goal_intents", str(exc))
            failures.append(f"Goal intent test failed: {exc}")
        else:
            logger.pass_step("goal_intents")

        try:
            router = IntentRouter(db_path=db_path)
            create_draft = router.handle("create draft: Weekly migration summary for Sam v2")
            _assert(create_draft.ok, "create draft intent failed")

            list_workflows = router.handle("list workflows")
            _assert(list_workflows.ok, "list workflows intent failed")
            _assert(list_workflows.metadata["count"] >= 1, "workflow count mismatch")
            print("[PASS] Workflow intents")
        except Exception as exc:
            logger.fail_step("workflow_intents", str(exc))
            failures.append(f"Workflow intent test failed: {exc}")
        else:
            logger.pass_step("workflow_intents")

        try:
            router = IntentRouter(db_path=db_path)
            chat_result = router.handle("hello there")
            _assert(chat_result.ok, "chat fallback failed")
            _assert(chat_result.metadata["intent"] == "chat", "chat fallback intent mismatch")
            print("[PASS] Chat fallback intent")
        except Exception as exc:
            logger.fail_step("chat_fallback", str(exc))
            failures.append(f"Chat fallback test failed: {exc}")
        else:
            logger.pass_step("chat_fallback")

        try:
            approval_manager = ApprovalManager(db_path)
            _assert(approval_manager.ensure_schema().ok, "approval schema init failed")
            authority = AuthorityEngine(
                AuthorityConfig(
                    default_level=3,
                    governed_categories=["write_data"],
                )
            )
            gated_router = IntentRouter(
                db_path=db_path,
                authority_engine=authority,
                approval_manager=approval_manager,
            )
            gated_result = gated_router.handle("create goal: Needs approval")
            _assert(gated_result.status == "needs_approval", "approval gating did not trigger")
            _assert("approval_id" in gated_result.metadata, "approval id missing from gated result")
            print("[PASS] Approval-gated write intent")
        except Exception as exc:
            logger.fail_step("approval_gating", str(exc))
            failures.append(f"Approval gating test failed: {exc}")
        else:
            logger.pass_step("approval_gating")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Intents live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All intent live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
