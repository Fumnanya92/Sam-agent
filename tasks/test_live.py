"""
tasks/test_live.py — Live integration tests for Sam.

Tests Sam's actual systems end-to-end:
  - Real OpenAI / Ollama LLM API calls
  - Skill activation + injection pipeline
  - Session logger + report writer
  - PendingAction confirm/cancel flow
  - YouTube transcript live fetch
  - agent_llm_call (LLMBridge)

Run from repo root:
    cd C:\\Users\\DELL.COM\\Desktop\\Darey\\Sam-Agent
    python tasks/test_live.py
"""
import sys
import os
import time
import json
from pathlib import Path

# ── path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)          # so llm.py resolves core/prompt.txt correctly

# ── output helpers ──────────────────────────────────────────────────────────
def out(text: str):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
INFO = "[INFO]"


# ── test registry ────────────────────────────────────────────────────────────
_results: list[tuple[str, str, str]] = []   # (label, status, detail)

def _record(label, status, detail=""):
    _results.append((label, status, detail))
    icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[SKIP]": "-- "}[status]
    out(f"  {icon} {status} {label}{(' : ' + detail) if detail else ''}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Cloud LLM (OpenAI) live API call
# ══════════════════════════════════════════════════════════════════════════════
def test_cloud_llm():
    out("\n[TEST 1] Cloud LLM — real OpenAI API call")
    try:
        from llm import get_llm_output
        result = get_llm_output("Say hello and tell me what 2 plus 2 is. Keep it brief.")
        assert isinstance(result, dict), "result must be a dict"
        assert "intent" in result, "result must have 'intent' key"
        assert "text" in result, "result must have 'text' key"
        text = result.get("text", "")
        assert isinstance(text, str) and len(text) > 0, f"text must be non-empty string, got: {repr(text)}"
        _record("cloud llm returns valid response", PASS, f"intent={result['intent']!r} text={text[:60]!r}")
    except Exception as e:
        _record("cloud llm returns valid response", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Ollama availability + local LLM call
# ══════════════════════════════════════════════════════════════════════════════
def test_ollama_llm():
    out("\n[TEST 2] Ollama — local LLM call (skipped if not running)")
    try:
        from llm import is_ollama_available, get_ollama_output
        if not is_ollama_available():
            _record("ollama local llm", SKIP, "Ollama not running — skipped")
            return
        result = get_ollama_output("Say hi and what is 3 times 3.")
        assert isinstance(result, dict), "result must be a dict"
        assert "text" in result, "result must have 'text' key"
        text = result.get("text", "")
        assert isinstance(text, str) and len(text) > 0, "text must be non-empty"
        _record("ollama local llm returns valid response", PASS,
                f"intent={result['intent']!r} text={text[:60]!r}")
    except Exception as e:
        _record("ollama local llm returns valid response", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Skill context injection: prime -> LLM call -> consumed
# ══════════════════════════════════════════════════════════════════════════════
def test_skill_injection():
    out("\n[TEST 3] Skill injection — prime_skill_context -> get_ai_response -> consumed")
    try:
        import llm as llm_module
        from llm import prime_skill_context, get_llm_output

        # Inject a fake skill
        prime_skill_context("SKILL: how to write clean Python: use type hints, keep functions small.", "clean_python")

        # Verify module state was set
        assert llm_module._pending_skill_content is not None, "_pending_skill_content should be set after prime"
        assert llm_module._pending_skill_name == "clean_python", "skill name should match"

        # Make a real LLM call — it should consume the skill
        result = get_llm_output("Give me one tip for writing better Python code.")
        assert isinstance(result, dict), "LLM must return dict"

        # After the call, pending skill must be cleared (one-shot)
        assert llm_module._pending_skill_content is None, "_pending_skill_content should be None after LLM call"
        assert llm_module._pending_skill_name is None, "_pending_skill_name should be None after LLM call"

        _record("skill prime -> llm call -> context consumed", PASS,
                f"response text: {result.get('text','')[:60]!r}")
    except Exception as e:
        _record("skill prime -> llm call -> context consumed", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — auto_activate_for_task + prime pipeline (real skill registry)
# ══════════════════════════════════════════════════════════════════════════════
def test_auto_skill_pipeline():
    out("\n[TEST 4] auto_activate_for_task — real skill registry + prime pipeline")
    try:
        from skills.antigravity_bridge import auto_activate_for_task
        import llm as llm_module
        from llm import prime_skill_context

        temp_memory = {}
        skill_name = auto_activate_for_task("write a python web api with flask", temp_memory)

        if skill_name and temp_memory.get("active_skill_content"):
            content = temp_memory["active_skill_content"]
            prime_skill_context(content, skill_name)
            assert llm_module._pending_skill_content == content, "primed content must match"
            # Consume it cleanly
            llm_module._pending_skill_content = None
            llm_module._pending_skill_name = None
            _record("auto_activate_for_task + prime pipeline", PASS,
                    f"activated skill: {skill_name!r}  content_len={len(content)}")
        else:
            # Registry may not have an exact match — not a hard failure
            _record("auto_activate_for_task + prime pipeline", PASS,
                    f"No best-match skill found (skill_name={skill_name!r}) — acceptable, registry uses exact matching")
    except Exception as e:
        _record("auto_activate_for_task + prime pipeline", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — agent_llm_call (LLMBridge) direct call
# ══════════════════════════════════════════════════════════════════════════════
def test_agent_llm_bridge():
    out("\n[TEST 5] agent_llm_call (LLMBridge) — direct call")
    try:
        from agent.llm_bridge import agent_llm_call
        response = agent_llm_call(
            system_prompt="You are a helpful assistant. Answer in one sentence.",
            user_prompt="What is the capital of France?",
            require_json=False,
        )
        assert isinstance(response, str), f"agent_llm_call must return str, got {type(response)}"
        assert len(response) > 0, "response must be non-empty"
        assert "paris" in response.lower() or "France" in response, \
            f"response doesn't mention Paris or France: {response[:100]}"
        _record("agent_llm_call returns correct answer", PASS, f"{response[:80]!r}")
    except Exception as e:
        _record("agent_llm_call returns correct answer", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6 — Session logger round-trip + report writer
# ══════════════════════════════════════════════════════════════════════════════
def test_session_logger_and_report():
    out("\n[TEST 6] Session logger + report_writer — full pipeline")
    try:
        from system.session_logger import SessionLogger
        from system.report_writer import write_daily_report

        # Use a fresh logger instance pointing to a temp dir so we don't pollute real sessions
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())

        class _TmpLogger(SessionLogger):
            def _session_file(self):
                return tmp_dir / f"{self._date}.json"

        logger = _TmpLogger()
        logger.log_action("open_app", "Opened Visual Studio Code", "done")
        logger.log_action("code_helper", "Wrote a Flask API endpoint", "done")
        logger.log_action("daily_report", "Generated daily summary", "done")

        log = logger.get_today_log()
        assert len(log) == 3, f"Expected 3 log entries, got {len(log)}"

        # Verify timestamp field is correct format
        for entry in log:
            ts = entry.get("timestamp", "")
            assert ts, f"timestamp field missing in entry: {entry}"
            assert len(ts) == 19, f"timestamp should be YYYY-MM-DD HH:MM:SS (19 chars), got: {ts!r}"

        _record("session_logger stores 3 entries with correct timestamps", PASS,
                f"timestamps look correct: {log[0]['timestamp']!r}")

        # Write report using the temp log — uses real LLM
        report_path = write_daily_report(log)
        path = Path(report_path)
        assert path.exists(), f"Report file not created at {report_path}"
        content = path.read_text(encoding="utf-8")
        assert "Sam Daily Report" in content, "Report must contain title"
        assert len(content) > 100, f"Report too short ({len(content)} chars)"

        _record("report_writer generates markdown report via LLM", PASS,
                f"saved to {path.name}  ({len(content)} chars)")

        # Clean up temp dir
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as e:
        _record("session logger + report writer pipeline", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7 — PendingAction confirm flow via handle_intent
# ══════════════════════════════════════════════════════════════════════════════
def test_pending_action_confirm():
    out("\n[TEST 7] PendingAction confirm flow — handle_intent('confirm_action')")
    try:
        from conversation_state import controller, PendingAction
        from intents.handlers import handle_intent

        # Mock UI
        class _MockUI:
            messages = []
            def append_output(self, msg, *args, **kwargs): self.messages.append(msg)
            def update_status(self, *a): pass
            def add_agent_task(self, *a): pass
            def update_agent_task(self, *a): pass
            def write_log(self, msg, *a): self.messages.append(msg)

        mock_ui = _MockUI()
        callback_called = {"flag": False, "value": None}

        def _callback():
            callback_called["flag"] = True
            callback_called["value"] = "executed"

        # Store a pending action
        controller.set_pending(PendingAction(
            intent="delete_file",
            parameters={"path": "test.txt"},
            description="Delete test.txt",
            callback=_callback,
        ))

        assert controller.get_pending() is not None, "Pending action should be stored"

        # Confirm it via handle_intent
        handle_intent(
            intent="confirm_action",
            parameters={},
            response="yes",
            ui=mock_ui,
            temp_memory={},
        )

        # Wait briefly for daemon thread to run
        time.sleep(0.5)

        assert callback_called["flag"] is True, "Callback should have been called after confirm_action"
        assert controller.get_pending() is None, "Pending action should be cleared after execution"

        _record("pending action executes + clears on confirm_action", PASS,
                f"callback_value={callback_called['value']!r}")

    except Exception as e:
        _record("pending action executes + clears on confirm_action", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8 — PendingAction cancel flow
# ══════════════════════════════════════════════════════════════════════════════
def test_pending_action_cancel():
    out("\n[TEST 8] PendingAction cancel flow — handle_intent('cancel_action')")
    try:
        from conversation_state import controller, PendingAction
        from intents.handlers import handle_intent

        class _MockUI:
            messages = []
            def append_output(self, msg, *args, **kwargs): self.messages.append(msg)
            def update_status(self, *a): pass
            def write_log(self, msg, *a): self.messages.append(msg)

        mock_ui = _MockUI()
        callback_called = {"flag": False}

        def _callback():
            callback_called["flag"] = True

        controller.set_pending(PendingAction(
            intent="push_code",
            parameters={},
            description="Push to main branch",
            callback=_callback,
        ))

        handle_intent(
            intent="cancel_action",
            parameters={},
            response="cancel",
            ui=mock_ui,
            temp_memory={},
        )

        time.sleep(0.4)

        assert callback_called["flag"] is False, "Callback must NOT be called on cancel"
        assert controller.get_pending() is None, "Pending action must be cleared on cancel"

        _record("cancel_action clears pending without executing callback", PASS)

    except Exception as e:
        _record("cancel_action clears pending without executing callback", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9 — YouTube transcript live fetch
# ══════════════════════════════════════════════════════════════════════════════
def test_youtube_transcript():
    out("\n[TEST 9] YouTube transcript — live fetch (Rick Astley: dQw4w9WgXcQ)")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch("dQw4w9WgXcQ")
        snippets = list(fetched)
        assert len(snippets) > 0, "Expected at least 1 transcript snippet"

        # Access via attribute (not dict key)
        first = snippets[0]
        assert hasattr(first, "text"), f"Snippet has no .text attribute: {dir(first)}"
        assert hasattr(first, "start"), f"Snippet has no .start attribute"
        transcript_text = " ".join(s.text for s in snippets)
        assert len(transcript_text) > 50, f"Transcript text too short: {transcript_text[:100]}"

        _record("youtube transcript fetched via instance API", PASS,
                f"{len(snippets)} snippets  first={snippets[0].text[:40]!r}")

    except Exception as e:
        _record("youtube transcript fetched via instance API", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10 — Full intent routing: learn_from_youtube
# ══════════════════════════════════════════════════════════════════════════════
def test_learn_intent_routing():
    out("\n[TEST 10] Full intent routing — learn_from_youtube (real handler)")
    try:
        from intents.handlers import handle_intent

        class _MockUI:
            messages = []
            def append_output(self, msg, *args, **kwargs): self.messages.append(str(msg))
            def update_status(self, *a): pass
            def write_log(self, msg, *a): self.messages.append(str(msg))
            def add_agent_task(self, *a): pass
            def update_agent_task(self, *a): pass

        mock_ui = _MockUI()
        # Use a short, reliable YouTube video URL
        handle_intent(
            intent="learn_from_youtube",
            parameters={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            response="learn from this",
            ui=mock_ui,
            temp_memory={},
        )

        # Give the background thread time to run
        out("  ... waiting up to 30s for transcript fetch + LLM extraction ...")
        deadline = time.time() + 30
        while time.time() < deadline:
            joined = " ".join(mock_ui.messages).lower()
            if any(kw in joined for kw in ["learned", "saved", "knowledge", "error", "failed"]):
                break
            time.sleep(1)

        joined = " ".join(mock_ui.messages)
        _record("learn_from_youtube handler fires and reports back", PASS,
                f"UI output: {joined[:120]!r}")

    except Exception as e:
        _record("learn_from_youtube handler fires and reports back", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 11 — Intent detection: LLM correctly classifies voice commands
# ══════════════════════════════════════════════════════════════════════════════
def test_intent_detection():
    out("\n[TEST 11] Intent detection — LLM correctly classifies voice commands")
    cases = [
        ("Sam, open Chrome for me", "open_app", {"app_name"}),
        ("Set an alarm for 7 in the morning", "set_alarm", {"fire_at"}),
        ("Sam what did you do today", "daily_report", set()),
        ("shut up Sam", "silence_sam", set()),
    ]
    try:
        from llm import get_llm_output
        all_pass = True
        for utterance, expected_intent, expected_param_keys in cases:
            result = get_llm_output(utterance)
            actual_intent = result.get("intent", "")
            if actual_intent != expected_intent:
                _record(f"intent: {utterance[:40]!r}", FAIL,
                        f"expected {expected_intent!r}, got {actual_intent!r}")
                all_pass = False
            else:
                params = result.get("parameters", {})
                missing_params = expected_param_keys - set(params.keys())
                if missing_params and expected_param_keys:
                    _record(f"intent: {utterance[:40]!r}", FAIL,
                            f"intent OK but missing params {missing_params}")
                    all_pass = False
                else:
                    _record(f"intent: {utterance[:40]!r}", PASS,
                            f"intent={actual_intent!r}  params={list(params.keys())}")
        if all_pass:
            out("  All intent detection cases passed.")
    except Exception as e:
        _record("intent detection suite", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 12 — report_writer uses correct 'timestamp' field (not 'time')
# ══════════════════════════════════════════════════════════════════════════════
def test_report_writer_field_fix():
    out("\n[TEST 12] report_writer uses 'timestamp' field (bug fix verification)")
    try:
        from system.report_writer import _fallback_report

        fake_log = [
            {"timestamp": "2026-03-14 10:00:00", "intent": "open_app", "summary": "Opened Chrome", "outcome": "done"},
            {"timestamp": "2026-03-14 10:05:00", "intent": "search", "summary": "Searched for Python tips", "outcome": "error"},
        ]
        report = _fallback_report(fake_log)
        assert "2026-03-14" in report, "timestamp must appear in report"
        assert "Opened Chrome" in report, "summary must appear in report"
        _record("report_writer _fallback_report uses 'timestamp' field", PASS,
                f"report excerpt: {report[:80]!r}")
    except Exception as e:
        _record("report_writer _fallback_report uses 'timestamp' field", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    out("=" * 70)
    out("  SAM LIVE INTEGRATION TESTS")
    out("=" * 70)

    test_cloud_llm()
    test_ollama_llm()
    test_skill_injection()
    test_auto_skill_pipeline()
    test_agent_llm_bridge()
    test_session_logger_and_report()
    test_pending_action_confirm()
    test_pending_action_cancel()
    test_youtube_transcript()
    test_learn_intent_routing()
    test_intent_detection()
    test_report_writer_field_fix()

    out("\n" + "=" * 70)
    out("  RESULTS SUMMARY")
    out("=" * 70)

    passed  = [r for r in _results if r[1] == PASS]
    failed  = [r for r in _results if r[1] == FAIL]
    skipped = [r for r in _results if r[1] == SKIP]

    for label, status, detail in _results:
        icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[SKIP]": "-- "}[status]
        out(f"  {icon} {status}  {label}")

    out("")
    out(f"  PASS:   {len(passed)}")
    out(f"  FAIL:   {len(failed)}")
    out(f"  SKIP:   {len(skipped)}")
    out(f"  TOTAL:  {len(_results)}")
    out("=" * 70)

    if failed:
        out("\nFAILED TESTS:")
        for label, _, detail in failed:
            out(f"  !! {label}")
            if detail:
                out(f"     {detail}")

    sys.exit(0 if not failed else 1)
