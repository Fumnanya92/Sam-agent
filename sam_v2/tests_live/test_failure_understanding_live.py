"""Real failure-understanding validation on focusflow_flutter."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.projects import FailureAnalysisService, resolve_flutter_command

FOCUSFLOW_ROOT = Path(r"C:\Users\DELL.COM\Desktop\Darey\focusflow_flutter")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Failure Understanding Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_failure_understanding_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_failure_understanding_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    flutter_bin = resolve_flutter_command()
    service = FailureAnalysisService()

    try:
        _assert(FOCUSFLOW_ROOT.exists(), f"missing project path: {FOCUSFLOW_ROOT}")

        try:
            pass_result, pass_analysis = service.run_command(
                project_id="focusflow-flutter",
                command=[flutter_bin, "test", r"test\core\services\encrypted_storage_test.dart"],
                cwd=FOCUSFLOW_ROOT,
                timeout_seconds=240,
            )
            _assert(pass_result.ok, f"expected passing test command to succeed: {pass_result.error_message}")
            _assert(pass_analysis is None, "passing command should not produce failure analysis")
            print("[PASS] Real passing project test command")
        except Exception as exc:
            logger.fail_step("passing_project_test_command", str(exc))
            failures.append(f"Passing project test command failed: {exc}")
        else:
            logger.pass_step("passing_project_test_command")

        try:
            fail_result, fail_analysis = service.run_command(
                project_id="focusflow-flutter",
                command=[flutter_bin, "test", r"test\missing_test.dart"],
                cwd=FOCUSFLOW_ROOT,
                timeout_seconds=240,
            )
            _assert(not fail_result.ok, "expected missing test target to fail")
            _assert(fail_analysis is not None, "expected failure analysis to be returned")
            _assert(fail_analysis.category == "missing_test_target", "failure category mismatch")
            _assert(
                (
                    "does not exist" in fail_analysis.explanation.lower()
                    or "test target" in fail_analysis.explanation.lower()
                ),
                "failure explanation mismatch",
            )
            _assert(fail_result.next_action == "ask_user", "failure next_action mismatch")
            _assert(
                any(
                    ("No file or variants found for" in line) or ("Failed to load" in line) or ("Does not exist" in line)
                    for line in fail_analysis.evidence_lines
                ),
                "failure evidence missing",
            )
            print("[PASS] Real failure explanation and next action")
        except Exception as exc:
            logger.fail_step("real_failure_explanation", str(exc))
            failures.append(f"Real failure explanation failed: {exc}")
        else:
            logger.pass_step(
                "real_failure_explanation",
                {
                    "category": fail_analysis.category,
                    "next_action": fail_result.next_action,
                    "evidence_lines": fail_analysis.evidence_lines,
                },
            )
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Failure understanding live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All failure understanding live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
