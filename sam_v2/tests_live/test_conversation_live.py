"""Real conversation validation for Sam v2 using the runtime + Ollama path."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.core import SamRuntime
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event


def _project_root_from_result(result):
    root_path = result.metadata.get("root_path")
    return Path(root_path) if root_path else None


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _result_summary(result) -> str:
    return (
        f"status={result.status}, next_action={result.next_action}, "
        f"intent={result.metadata.get('intent')}, source={result.metadata.get('source')}, "
        f"summary={result.summary!r}"
    )


def main() -> int:
    print("=== Sam v2 Conversation Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_conversation_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_conversation_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_dir / "conversation_live.db"
    memory_path = tmp_dir / "memory.json"
    session_path = tmp_dir / "session.json"
    created_projects: list[Path] = []

    try:
        runtime = SamRuntime(
            db_path=db_path,
            memory_path=memory_path,
            session_path=session_path,
        )
        start_result = runtime.start()
        _assert(start_result.ok, f"runtime start failed: {start_result.error_message}")

        cases = [
            {
                "name": "normal_chat",
                "prompt": "Hey Sam, how are you today?",
                "check": lambda result: (
                    result.ok
                    and result.metadata.get("intent") == "chat"
                    and bool(result.summary.strip())
                ),
                "expected": "conversational chat response",
            },
            {
                "name": "direct_command_projects",
                "prompt": "Sam, list my projects",
                "check": lambda result: (
                    result.metadata.get("intent") != "chat"
                    and result.next_action in {"stop", "ask_user"}
                ),
                "expected": "non-chat project retrieval or truthful ask",
            },
            {
                "name": "goal_request",
                "prompt": "Sam, help me fix a broken app",
                "check": lambda result: result.next_action in {"ask_user", "plan", "stop"} and result.metadata.get("intent") != "chat",
                "expected": "goal-aware plan or clarifying response",
            },
            {
                "name": "ambiguous_request",
                "prompt": "Sam, check that thing from yesterday",
                "check": lambda result: result.next_action == "ask_user" or result.metadata.get("intent") == "clarify",
                "expected": "clarification request",
            },
            {
                "name": "coding_request",
                "prompt": "Sam, inspect this repo and tell me what is broken",
                "check": lambda result: result.next_action in {"ask_user", "plan", "stop"} and result.metadata.get("intent") != "chat",
                "expected": "repo-aware inspect/plan decision",
            },
            {
                "name": "approval_sensitive_request",
                "prompt": "Sam, push the changes",
                "check": lambda result: result.status in {"needs_approval", "blocked"},
                "expected": "approval gate before push-like action",
            },
            {
                "name": "natural_project_request",
                "prompt": f"please create a tic tac game called Conversation Smoke {uuid.uuid4().hex[:6]}",
                "check": lambda result: (
                    result.ok
                    and result.metadata.get("intent") == "scaffold_project"
                    and bool(result.metadata.get("root_path"))
                ),
                "expected": "natural scaffold request should create a modular project",
            },
            {
                "name": "natural_web_game_request",
                "prompt": f"build a web tictac game called Conversation Web Smoke {uuid.uuid4().hex[:6]}",
                "check": lambda result: (
                    result.ok
                    and result.metadata.get("intent") == "scaffold_project"
                    and bool(result.metadata.get("root_path"))
                ),
                "expected": "web tictac phrasing should route into modular scaffolding",
            },
        ]

        for case in cases:
            try:
                result = runtime.handle_text(case["prompt"])
                project_root = _project_root_from_result(result)
                if project_root is not None:
                    created_projects.append(project_root)
                audit_id = result.metadata.get("audit_event_id")
                _assert(audit_id is not None, "missing audit_event_id")
                audit_result, audit_event = fetch_audit_event(db_path, int(audit_id))
                _assert(audit_result.ok and audit_event is not None, "missing persisted audit event")
                _assert(case["check"](result), f"expected {case['expected']}; got {_result_summary(result)}")
                print(f"[PASS] {case['name']}: {result.summary}")
            except Exception as exc:
                logger.fail_step(case["name"], str(exc))
                failures.append(f"{case['name']} failed: {exc}")
            else:
                logger.pass_step(
                    case["name"],
                    {
                        "prompt": case["prompt"],
                        "status": result.status,
                        "next_action": result.next_action,
                        "intent": result.metadata.get("intent"),
                        "source": result.metadata.get("source"),
                        "summary": result.summary,
                    },
                )

        followup_project_name = f"Conversation Followup {uuid.uuid4().hex[:6]}"
        try:
            create_result = runtime.handle_text(f"build a web tictac game called {followup_project_name}")
            followup_root = _project_root_from_result(create_result)
            if followup_root is not None:
                created_projects.append(followup_root)
            _assert(create_result.ok, f"followup scaffold failed: {_result_summary(create_result)}")

            run_result = runtime.handle_text("please run the game you created")
            _assert(run_result.ok, f"followup run failed: {_result_summary(run_result)}")
            _assert(run_result.metadata.get("intent") == "run_project", "followup run intent mismatch")
            _assert(run_result.metadata.get("name") == followup_project_name, "followup run project mismatch")

            where_result = runtime.handle_text("where is it?")
            _assert(where_result.ok, f"followup location failed: {_result_summary(where_result)}")
            _assert(where_result.metadata.get("intent") == "project_details", "followup details intent mismatch")
            _assert(where_result.metadata.get("name") == followup_project_name, "followup details project mismatch")
            _assert(str(where_result.metadata.get("root_path", "")).strip(), "followup details missing root path")
            print(f"[PASS] project_followups: {where_result.summary}")
        except Exception as exc:
            logger.fail_step("project_followups", str(exc))
            failures.append(f"project_followups failed: {exc}")
        else:
            logger.pass_step(
                "project_followups",
                {
                    "project_name": followup_project_name,
                    "run_summary": run_result.summary,
                    "location_summary": where_result.summary,
                },
            )
    finally:
        for project_root in created_projects:
            try:
                shutil.rmtree(project_root, ignore_errors=True)
            except Exception:
                pass
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Conversation live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All conversation live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
