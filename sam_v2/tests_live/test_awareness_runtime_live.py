"""Real runtime-path validation for capability awareness and upgrade proposals."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.storage.db import fetch_audit_event
from sam_v2.upgrades import UpgradeProposalManager


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Awareness Runtime Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_awareness_runtime_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_awareness_runtime_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "awareness_runtime_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    projects_path = tmp_dir / "projects.json"
    upgrades_path = tmp_dir / "upgrades.json"

    try:
        project_registry = ProjectRegistry(projects_path)
        register_result = project_registry.register(
            ProjectRecord(
                project_id="sam-agent",
                name="Sam-agent",
                root_path=str(REPO_ROOT),
                stack="python",
                test_command=[sys.executable, "-u", "sam_v2/tests_live/test_runtime_live.py"],
                build_command=[],
                active_branch="rebuild/sam-clean-v2",
            )
        )
        _assert(register_result.ok, f"project register failed: {register_result.error_message}")

        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        try:
            capabilities_result = runtime.handle_text("Sam, what can you do?")
            _assert(capabilities_result.ok, "capability summary request failed")
            _assert(capabilities_result.metadata.get("intent") == "capabilities", "capability intent mismatch")
            _assert("available_capabilities" in capabilities_result.metadata, "available capabilities missing")
            _assert("Sam-agent" in capabilities_result.metadata.get("known_projects", []), "known project missing")
            audit_result, audit_event = fetch_audit_event(db_path, int(capabilities_result.metadata["audit_event_id"]))
            _assert(audit_result.ok and audit_event is not None, "capability audit event missing")
            print("[PASS] Runtime capability summary")
        except Exception as exc:
            logger.fail_step("runtime_capability_summary", str(exc))
            failures.append(f"Runtime capability summary failed: {exc}")
        else:
            logger.pass_step("runtime_capability_summary")

        try:
            missing_result = runtime.handle_text("Sam, do you have browser worker support?")
            _assert(not missing_result.ok, "missing capability request should not succeed")
            _assert(missing_result.metadata.get("intent") == "awareness_check", "missing capability intent mismatch")
            _assert(missing_result.error_type.value == "missing_capability", "missing capability error type mismatch")
            _assert(missing_result.metadata.get("missing_capability") == "browser_worker", "missing capability name mismatch")
            _assert(missing_result.next_action == "request_approval", "missing capability next action mismatch")
            print("[PASS] Runtime missing capability disclosure")
        except Exception as exc:
            logger.fail_step("runtime_missing_capability", str(exc))
            failures.append(f"Runtime missing capability disclosure failed: {exc}")
        else:
            logger.pass_step("runtime_missing_capability")

        try:
            proposal_result = runtime.handle_text("Sam, request upgrade for browser worker")
            _assert(proposal_result.status == "needs_approval", "upgrade proposal should need approval")
            _assert(proposal_result.metadata.get("intent") == "propose_upgrade", "upgrade proposal intent mismatch")
            _assert("proposal_id" in proposal_result.metadata, "proposal id missing")
            list_result, proposals = UpgradeProposalManager(upgrades_path).list_proposals()
            _assert(list_result.ok, "upgrade proposal store load failed")
            _assert(len(proposals) == 1, "expected one stored proposal")
            _assert(proposals[0].capability_name == "browser_worker", "stored proposal capability mismatch")
            print("[PASS] Runtime upgrade proposal flow")
        except Exception as exc:
            logger.fail_step("runtime_upgrade_proposal", str(exc))
            failures.append(f"Runtime upgrade proposal failed: {exc}")
        else:
            logger.pass_step("runtime_upgrade_proposal")

        try:
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            _assert(session_payload.get("request_count", 0) >= 3, "session request count mismatch")
            _assert(session_payload.get("last_intent") == "propose_upgrade", "last session intent mismatch")
            print("[PASS] Runtime awareness session/log path")
        except Exception as exc:
            logger.fail_step("runtime_awareness_session_path", str(exc))
            failures.append(f"Runtime awareness session path failed: {exc}")
        else:
            logger.pass_step("runtime_awareness_session_path")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Awareness runtime live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All awareness runtime live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
