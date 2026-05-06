"""Live test for the Sam v2 approvals foundation."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.approvals import (
    ApprovalManager,
    AuthorityAuditTrail,
    AuthorityConfig,
    AuthorityEngine,
    ContextRule,
    PerActionOverride,
)
from sam_v2.storage.db import init_storage


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Approvals Live Test ===")
    failures = []

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_approvals_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "approvals_live.db"

    try:
        init_result = init_storage(db_path)
        _assert(init_result.ok, f"storage init failed: {init_result.error_message}")

        approval_manager = ApprovalManager(db_path)
        audit_trail = AuthorityAuditTrail(db_path)

        _assert(approval_manager.ensure_schema().ok, "approval schema init failed")
        _assert(audit_trail.ensure_schema().ok, "audit schema init failed")

        try:
            engine = AuthorityEngine(
                AuthorityConfig(
                    default_level=3,
                    governed_categories=["execute_command"],
                    overrides=[PerActionOverride(action="send_email", allowed=False)],
                    context_rules=[
                        ContextRule(
                            id="rule-1",
                            action="access_browser",
                            condition="always",
                            params={},
                            effect="require_approval",
                            description="Browser actions require explicit approval in this test.",
                        )
                    ],
                )
            )

            governed = engine.check(
                agent_id="agent-1",
                agent_level=6,
                role_id="operator",
                tool_name="terminal.run",
                action_category="execute_command",
            )
            _assert(governed.allowed and governed.requires_approval, "governed category decision mismatch")

            denied = engine.check(
                agent_id="agent-1",
                agent_level=9,
                role_id="operator",
                tool_name="mail.send",
                action_category="send_email",
            )
            _assert(not denied.allowed, "override deny decision mismatch")

            browser = engine.check(
                agent_id="agent-1",
                agent_level=9,
                role_id="operator",
                tool_name="browser.open",
                action_category="access_browser",
            )
            _assert(browser.allowed and browser.requires_approval, "context rule decision mismatch")
            print("[PASS] Authority engine decisions")
        except Exception as exc:
            failures.append(f"Authority engine test failed: {exc}")

        try:
            create_result, request = approval_manager.create_request(
                agent_id="agent-1",
                agent_name="Sam",
                tool_name="terminal.run",
                tool_arguments={"command": "pytest"},
                action_category="execute_command",
                reason="Need to run project test suite.",
            )
            _assert(create_result.ok and request is not None, "approval request create failed")

            pending_result, pending = approval_manager.list_pending()
            _assert(pending_result.ok and len(pending) == 1, "pending approvals list mismatch")

            approve_result, approved = approval_manager.approve(request.id, "user")
            _assert(approve_result.ok and approved is not None, "approve request failed")

            executed_result = approval_manager.mark_executed(request.id, "pytest passed")
            _assert(executed_result.ok, "mark executed failed")
            print("[PASS] Approval request lifecycle")
        except Exception as exc:
            failures.append(f"Approval lifecycle test failed: {exc}")

        try:
            audit_result, record = audit_trail.log(
                agent_id="agent-1",
                agent_name="Sam",
                tool_name="terminal.run",
                action_category="execute_command",
                authority_decision="approval_required",
                approval_id=request.id if 'request' in locals() and request is not None else None,
                executed=True,
                execution_time_ms=1200,
            )
            _assert(audit_result.ok and record is not None, "audit log create failed")

            query_result, records = audit_trail.query(limit=10)
            _assert(query_result.ok and len(records) >= 1, "audit query failed")
            _assert(records[0].authority_decision == "approval_required", "audit decision mismatch")
            print("[PASS] Authority audit logging")
        except Exception as exc:
            failures.append(f"Authority audit test failed: {exc}")

        try:
            failure_result, failure_request = approval_manager.approve("missing-request", "user")
            _assert(not failure_result.ok and failure_request is None, "missing approval did not fail")
            print("[PASS] Invalid approval transition failure path")
        except Exception as exc:
            failures.append(f"Failure-path test failed: {exc}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        print("[FAIL] Approvals live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("[PASS] All approvals live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
