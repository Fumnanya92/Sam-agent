"""Live test for Sam v2 capability awareness and upgrade proposals."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.capabilities import CapabilityAwarenessService, build_default_registry
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import ProjectRecord, ProjectRegistry
from sam_v2.upgrades import UpgradeProposalManager


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Awareness Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_awareness_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_awareness_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    projects_path = tmp_dir / "projects.json"
    upgrades_path = tmp_dir / "upgrades.json"

    try:
        registry = build_default_registry()
        project_registry = ProjectRegistry(projects_path)
        upgrade_manager = UpgradeProposalManager(upgrades_path)
        awareness = CapabilityAwarenessService(
            registry,
            project_registry=project_registry,
            upgrade_manager=upgrade_manager,
        )

        try:
            register_result = project_registry.register(
                ProjectRecord(
                    project_id="sam-agent",
                    name="Sam-agent",
                    root_path=str(REPO_ROOT),
                    stack="python",
                    test_command=["python", "-u", "sam_v2/tests_live/test_runtime_live.py"],
                    build_command=[],
                    active_branch="rebuild/sam-clean-v2",
                )
            )
            _assert(register_result.ok, "project register failed")

            self_result = awareness.describe_self()
            _assert(self_result.ok, "awareness self-description failed")
            _assert("Sam-agent" in self_result.metadata["known_projects"], "known project missing")
            _assert(len(self_result.metadata["available_capabilities"]) >= 3, "capability count too small")
            print("[PASS] Capability and project self-awareness")
        except Exception as exc:
            logger.fail_step("capability_and_project_self_awareness", str(exc))
            failures.append(f"Awareness summary test failed: {exc}")
        else:
            logger.pass_step("capability_and_project_self_awareness")

        try:
            supported = awareness.check_request("Can you create goal records?")
            _assert(supported.ok, "supported capability check failed")
            _assert(supported.metadata["matched_capability"] == "create_goal", "supported capability mismatch")

            missing = awareness.check_request("Do you have browser worker support?")
            _assert(not missing.ok, "missing capability should fail")
            _assert(missing.error_type.value == "missing_capability", "missing capability error type mismatch")
            _assert(missing.metadata["upgradeable"] is True, "upgradeable flag mismatch")
            print("[PASS] Capability availability and missing-capability detection")
        except Exception as exc:
            logger.fail_step("capability_availability_detection", str(exc))
            failures.append(f"Capability detection test failed: {exc}")
        else:
            logger.pass_step("capability_availability_detection")

        try:
            proposal_result = awareness.propose_upgrade(
                "browser_worker",
                "Needed to automate real browser workflows.",
            )
            _assert(proposal_result.status == "needs_approval", "upgrade proposal should need approval")
            _assert("proposal_id" in proposal_result.metadata, "proposal id missing")

            list_result, proposals = upgrade_manager.list_proposals()
            _assert(list_result.ok and len(proposals) == 1, "upgrade proposal not stored")
            _assert(proposals[0].capability_name == "browser_worker", "stored proposal capability mismatch")
            print("[PASS] Controlled upgrade proposal flow")
        except Exception as exc:
            logger.fail_step("controlled_upgrade_proposal_flow", str(exc))
            failures.append(f"Upgrade proposal test failed: {exc}")
        else:
            logger.pass_step("controlled_upgrade_proposal_flow")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Awareness live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All awareness live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
