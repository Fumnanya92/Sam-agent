"""
UI Test Tools — Autonomous UI test generation + live result broadcasting.
Ported from Jarvis src/actions/tools/ui-test.ts

Workflow:
  1. Sam reads project code to understand app structure
  2. Sam generates a test plan
  3. For each test: navigate → interact → assert
  4. Call broadcast_test_result() for each case (running/passed/failed)
  5. Final call with status="complete" and summary

Usage:
    from actions.tools.ui_test import broadcast_test_result
"""

import logging
from typing import Callable, Literal, Optional

logger = logging.getLogger("sam.tools.ui_test")

TestStatus = Literal["running", "passed", "failed", "complete"]
TestResult = Literal["pass", "fail", "error"]

_broadcast: Optional[Callable] = None


def set_broadcast(fn: Callable) -> None:
    """Wire in the WebSocket broadcast function from ws_service."""
    global _broadcast
    _broadcast = fn


async def broadcast_test_result(
    *,
    test_run_id: str,
    test_name: str,
    status: TestStatus,
    result: Optional[TestResult] = None,
    assertion: Optional[str] = None,
    error_message: Optional[str] = None,
    screenshot_base64: Optional[str] = None,
    summary_total: Optional[int] = None,
    summary_passed: Optional[int] = None,
    summary_failed: Optional[int] = None,
) -> str:
    """
    Broadcast a UI test result to the dashboard.
    Use the same test_run_id across all results for one test session.
    On failures, pass screenshot_base64 for visual evidence.
    Final call: status="complete" with summary_total/passed/failed.
    """
    if not test_run_id or not test_name:
        return "Error: test_run_id and test_name are required."

    payload: dict = {
        "testRunId": test_run_id,
        "testName": test_name,
        "status": status,
    }
    if result:
        payload["result"] = result
    if assertion:
        payload["assertion"] = assertion
    if error_message:
        payload["errorMessage"] = error_message
    if screenshot_base64:
        if screenshot_base64.startswith("data:"):
            screenshot_base64 = screenshot_base64.split(",", 1)[-1]
        payload["screenshotBase64"] = screenshot_base64
    if summary_total is not None:
        payload["summary"] = {
            "total": summary_total,
            "passed": summary_passed or 0,
            "failed": summary_failed or 0,
        }

    if _broadcast:
        await _broadcast("test_result", payload)
        result_str = f" [{result.upper()}]" if result else ""
        return f'Test result broadcast: "{test_name}"{result_str}'

    logger.warning("broadcast_test_result: broadcast not wired — dashboard not connected")
    return "Test result broadcast not available (dashboard not connected)."
