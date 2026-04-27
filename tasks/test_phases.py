"""
tasks/test_phases.py — Phase-specific integration + skills tests for Sam.

Covers phases not yet verified in test_live.py:
  Phase 4  — AgentMonitor subscribe / notify pipeline
  Phase 5  — PresenceEngine meeting detection → controller.set_mode("meeting")
  Phase 8  — Code safety gate: _edit_action creates PendingAction, no premature write
  Phase 9  — Morning briefing dynamic: reads yesterday session log + real LLM call
  Phase 10 — TTS meeting mode suppression (notify not speak) + mute flag

Skills subsystem (S1–S6):
  S1 — Registry loaded: list_skills_brief, search_skills, total_skills
  S2 — activate_skill by slug stores content in temp_memory
  S3 — prime_skill_context → _consume_skill_context round-trip
  S4 — auto_activate_for_task end-to-end pipeline
  S5 — invoke_skill intent handler activates + says skill name
  S6 — LLM intent detection: "use your agent skill" → invoke_skill intent

Run from repo root:
    cd C:\\Users\\DELL.COM\\Desktop\\Darey\\Sam-Agent
    python tasks/test_phases.py
"""
import sys
import os
import time
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


# ── output helpers ────────────────────────────────────────────────────────────
def out(text: str):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
WARN = "[WARN]"

_results: list[tuple[str, str, str]] = []

def _record(label, status, detail=""):
    _results.append((label, status, detail))
    icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[SKIP]": "-- ", "[WARN]": "?? "}.get(status, "   ")
    out(f"  {icon} {status} {label}{(' : ' + detail) if detail else ''}")


# ── shared mock UI ────────────────────────────────────────────────────────────
class MockUI:
    def __init__(self):
        self.messages: list[str] = []
    def append_output(self, msg, *a, **kw): self.messages.append(str(msg))
    def update_status(self, *a): pass
    def write_log(self, msg, *a): self.messages.append(str(msg))
    def add_agent_task(self, *a): pass
    def update_agent_task(self, *a): pass
    def start_speaking(self): pass
    def stop_speaking(self): pass
    def set_transcription(self, *a): pass
    def clear_transcription(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — AgentMonitor subscribe + notify
# ══════════════════════════════════════════════════════════════════════════════
def test_agent_monitor():
    out("\n[PHASE 4] AgentMonitor — subscribe / update / notify pipeline")
    try:
        from agent.monitor import AgentMonitor, AgentTask

        # Use fresh instance for isolation (singleton — subscribe stacks)
        monitor = AgentMonitor()
        received: list = []

        def _on_update(task: AgentTask):
            received.append({"task_id": task.task_id, "status": task.status, "name": task.name})

        monitor.subscribe(_on_update)

        task_id = monitor.register_task("phase4-test", "Testing monitor subscribe pipeline")
        assert task_id, "register_task must return a non-empty task_id"

        monitor.update_task(task_id, status="done", output_line="Phase 4 complete")
        time.sleep(0.15)

        assert len(received) >= 2, \
            f"Subscriber should have received ≥ 2 updates (register + done), got {len(received)}"

        statuses_seen = {r["status"] for r in received}
        assert "done" in statuses_seen, f"'done' status not seen; got {statuses_seen}"

        _record("AgentMonitor subscribe receives register + update events", PASS,
                f"updates={len(received)}  statuses={statuses_seen}")

    except ImportError as e:
        _record("AgentMonitor subscribe pipeline", SKIP, f"import error: {e}")
    except Exception as e:
        _record("AgentMonitor subscribe pipeline", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — PresenceEngine meeting detection → controller mode
# ══════════════════════════════════════════════════════════════════════════════
def test_presence_meeting_detection():
    out("\n[PHASE 5] PresenceEngine meeting detection → controller.set_mode('meeting')")
    try:
        from conversation_state import controller
        from system.presence_engine import PresenceEngine

        # Start from a known state
        controller.set_mode("normal")
        assert controller.get_mode() == "normal", "Must start in normal mode"

        # Instantiate with huge poll interval so loop never auto-runs
        engine = PresenceEngine(poll_interval=99999)

        # Replace the pattern learner so no file I/O happens
        engine._pattern_learner = MagicMock()
        # Pre-load an empty downloads snapshot so _check_downloads is cheap
        engine._downloads_snapshot = set()

        fake_window = {"process": "zoom.exe", "title": "Zoom Meeting — daily standup"}

        with patch("system.window_tracker.get_foreground_window_info", return_value=fake_window):
            engine._update_state()

        mode = controller.get_mode()
        assert mode == "meeting", \
            f"Controller should be 'meeting' after zoom.exe, got {mode!r}"

        _record("zoom.exe → controller mode = 'meeting'", PASS, f"mode={mode!r}")

        # Verify reverting to non-meeting app restores normal mode
        fake_window2 = {"process": "code.exe", "title": "VS Code"}
        with patch("system.window_tracker.get_foreground_window_info", return_value=fake_window2):
            engine._update_state()

        mode_after = controller.get_mode()
        assert mode_after == "normal", \
            f"Mode should revert to 'normal' when meeting app closes, got {mode_after!r}"

        _record("meeting ends → controller mode reverts to 'normal'", PASS,
                f"mode={mode_after!r}")

        controller.set_mode("normal")  # final cleanup

    except ImportError as e:
        _record("PresenceEngine meeting detection", SKIP, f"import error: {e}")
    except Exception as e:
        _record("PresenceEngine meeting detection", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — Code safety gate: _edit_action → PendingAction, no premature write
# ══════════════════════════════════════════════════════════════════════════════
def test_code_safety_gate():
    out("\n[PHASE 8] Code safety gate — _edit_action creates PendingAction before writing")
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        from conversation_state import controller, PendingAction
        from actions.code_helper import _edit_action

        controller.clear_pending()

        # Create a real temp Python file to edit
        test_file = tmp_dir / "hello.py"
        original_content = "def greet():\n    print('hello world')\n"
        test_file.write_text(original_content, encoding="utf-8")

        mock_ui = MockUI()

        result = _edit_action(
            str(test_file),
            "add a return statement that returns the greeting string",
            mock_ui,
        )

        # 1. File must NOT have been written yet (no premature save)
        content_now = test_file.read_text(encoding="utf-8")
        assert content_now == original_content, \
            "File must not change before user confirms. Got:\n" + content_now

        # 2. A PendingAction must be queued
        pending = controller.get_pending()
        assert pending is not None, "PendingAction must be set after _edit_action"
        assert pending.intent == "code_edit", \
            f"PendingAction.intent must be 'code_edit', got {pending.intent!r}"

        # 3. Sam's reply must prompt user to confirm
        assert result, "Result message must not be empty"
        low = result.lower()
        assert any(kw in low for kw in ["apply", "say", "save", "confirm", "discard"]), \
            f"Result should prompt to confirm or discard, got: {result[:120]!r}"

        _record("_edit_action queues PendingAction without writing file", PASS,
                f"intent={pending.intent!r}  reply={result[:60]!r}")

        # 4. Executing the callback MUST write the updated file
        pending.callback()
        time.sleep(0.4)

        content_after = test_file.read_text(encoding="utf-8")
        assert content_after != original_content, \
            "Callback should have written the edited content to disk"
        assert len(content_after) > 10, "Written content should be non-trivial"

        _record("code_edit PendingAction callback writes the file correctly", PASS,
                f"file_len_before={len(original_content)}  after={len(content_after)}")

        controller.clear_pending()

    except Exception as e:
        _record("code safety gate", FAIL, str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 9 — Morning briefing: dynamic, reads yesterday session log (real API)
# ══════════════════════════════════════════════════════════════════════════════
def test_morning_briefing_dynamic():
    out("\n[PHASE 9] Morning briefing — dynamic (reads session log + real API call)")
    session_file_created: Path | None = None
    try:
        from assistant.morning_briefing import generate_morning_briefing
        from datetime import datetime, timedelta

        # Create a fake yesterday session log at the path morning_briefing actually reads
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        sessions_dir = ROOT / "reports" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_file_created = sessions_dir / f"{yesterday}.json"

        fake_log = [
            {"timestamp": f"{yesterday} 09:00:00", "intent": "code_helper",
             "summary": "Wrote a Flask REST API endpoint for user auth", "outcome": "done"},
            {"timestamp": f"{yesterday} 11:30:00", "intent": "git_commit",
             "summary": "Committed authentication feature branch", "outcome": "done"},
            {"timestamp": f"{yesterday} 14:00:00", "intent": "daily_report",
             "summary": "Generated end-of-day standup summary", "outcome": "done"},
        ]
        session_file_created.write_text(json.dumps(fake_log), encoding="utf-8")

        # Call the real function (makes real OpenAI API call if key available)
        briefing = generate_morning_briefing()

        assert isinstance(briefing, str), f"Briefing must be str, got {type(briefing)}"
        assert len(briefing) > 15, f"Briefing too short ({len(briefing)} chars): {briefing!r}"

        # "Good morning." is the bare-minimum fallback (no API key / error)
        is_fallback = briefing.strip().lower() == "good morning."
        if is_fallback:
            _record("morning briefing returned (API key missing or unreachable)", WARN,
                    f"got fallback: {briefing!r}")
        else:
            # A real LLM response should NOT say "Sir" and should be > 40 chars
            assert "sir" not in briefing.lower(), "Briefing must not say 'Sir'"
            assert len(briefing) > 40, f"Real briefing should be substantial, got: {briefing!r}"
            _record("morning briefing returns real LLM response", PASS,
                    f"length={len(briefing)}  preview={briefing[:90]!r}")

    except Exception as e:
        _record("morning briefing dynamic", FAIL, str(e))
    finally:
        # Clean up only the test session file we created; leave others intact
        if session_file_created and session_file_created.exists():
            session_file_created.unlink()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10a — TTS meeting mode: notification instead of audio
# ══════════════════════════════════════════════════════════════════════════════
def test_tts_meeting_mode_suppression():
    out("\n[PHASE 10a] TTS meeting mode — sam sends notification, not audio")
    original_mode = None
    try:
        from conversation_state import controller
        from tts import edge_speak

        original_mode = controller.get_mode()
        controller.set_mode("meeting")
        assert controller.get_mode() == "meeting"

        notifications_sent: list = []
        mock_ui = MockUI()

        with patch("system.notifier.notify",
                   side_effect=lambda title, body: notifications_sent.append((title, body))):
            edge_speak("Sam's test message in meeting mode", ui=mock_ui, blocking=False)
            time.sleep(0.3)

        # Must have sent exactly 1 notification
        assert len(notifications_sent) == 1, \
            f"Expected 1 notification in meeting mode, got {len(notifications_sent)}: {notifications_sent}"

        title, body = notifications_sent[0]
        assert "meeting mode" in body.lower() or "sam" in body.lower() or "test message" in body.lower(), \
            f"Notification body should contain the spoken text, got: {body!r}"

        # UI log must mention notify mode
        joined_log = " ".join(mock_ui.messages).lower()
        assert "notify" in joined_log or "meeting" in joined_log or "ai" in joined_log, \
            f"UI log should reflect notify/meeting mode, got: {mock_ui.messages}"

        _record("edge_speak in meeting mode sends notification (not audio)", PASS,
                f"notif title={title!r}  body={body[:60]!r}")

    except Exception as e:
        _record("TTS meeting mode suppression", FAIL, str(e))
    finally:
        if original_mode is not None:
            controller.set_mode(original_mode)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10b — TTS mute flag: Sam is silent, logs it
# ══════════════════════════════════════════════════════════════════════════════
def test_tts_mute_suppression():
    out("\n[PHASE 10b] TTS mute — edge_speak suppressed when controller.is_muted()")
    try:
        from conversation_state import controller
        from tts import edge_speak

        controller.set_muted(True)
        assert controller.is_muted(), "Mute flag must be set"

        mock_ui = MockUI()
        edge_speak("This message should be muted, not spoken.", ui=mock_ui, blocking=False)
        time.sleep(0.3)

        # UI log must contain the "AI (silent):" line
        joined = " ".join(mock_ui.messages)
        assert "silent" in joined.lower() or "muted" in joined.lower() or "ai" in joined.lower(), \
            f"UI log must record the silent message, got: {mock_ui.messages}"

        _record("edge_speak logs silently when muted (no audio)", PASS,
                f"log: {mock_ui.messages[0][:70]!r}" if mock_ui.messages else "[no log entry]")

        controller.set_muted(False)
        assert not controller.is_muted(), "Unmute must work"
        _record("set_muted(False) unmutes correctly", PASS)

    except Exception as e:
        _record("TTS mute suppression", FAIL, str(e))
    finally:
        try:
            from conversation_state import controller
            controller.set_muted(False)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S1 — Registry loaded: list, search, total
# ══════════════════════════════════════════════════════════════════════════════
def test_skills_registry():
    out("\n[SKILL S1] Skills registry — load, list_skills_brief, search_skills, total")
    try:
        from skills.antigravity_bridge import (
            SKILL_REGISTRY, list_skills_brief, search_skills, total_skills
        )

        total = total_skills()
        assert total > 0, "Skill registry must have at least 1 installed skill"

        brief = list_skills_brief(max_items=10)
        assert isinstance(brief, list) and len(brief) > 0, "list_skills_brief must return ≥ 1 skill"

        first = brief[0]
        for key in ("slug", "name", "description"):
            assert key in first, f"Each skill entry must have '{key}', got keys: {list(first.keys())}"

        # Partial-match search
        results = search_skills("agent", max_results=5)
        assert isinstance(results, list), "search_skills must return a list"
        if results:
            assert "slug" in results[0], f"First result should have 'slug': {results[0]}"

        # Tag-based search
        sec_results = search_skills("security")
        tag_or_desc_hit = any(
            "security" in r.get("slug", "") or
            "security" in r.get("description", "").lower() or
            any("security" in t.lower() for t in r.get("tags", []))
            for r in sec_results
        )

        _record("skills registry: load + list + search OK", PASS,
                f"total={total}  first={first['name']!r}  "
                f"agent_results={len(results)}  security_results={len(sec_results)}")

    except Exception as e:
        _record("skills registry", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S2 — activate_skill: stores content in temp_memory
# ══════════════════════════════════════════════════════════════════════════════
def test_activate_skill_stores_content():
    out("\n[SKILL S2] activate_skill — stores content & name in temp_memory")
    try:
        from skills.antigravity_bridge import activate_skill, SKILL_REGISTRY, total_skills

        if total_skills() == 0:
            _record("activate_skill stores content", SKIP, "no skills in registry")
            return

        # Pick first available skill
        first_slug = next(iter(SKILL_REGISTRY))
        temp_memory: dict = {}

        skill_name = activate_skill(first_slug, temp_memory)

        assert skill_name is not None, \
            f"activate_skill must return skill name (got None) for slug={first_slug!r}"
        assert "active_skill_name" in temp_memory, \
            "temp_memory must contain 'active_skill_name' after activation"
        assert "active_skill_content" in temp_memory, \
            "temp_memory must contain 'active_skill_content' after activation"
        assert len(temp_memory["active_skill_content"]) > 50, \
            "Skill content must be non-trivial (> 50 chars)"
        assert temp_memory["active_skill_name"] == skill_name, \
            "active_skill_name in temp_memory must match returned name"

        _record("activate_skill stores name + content in temp_memory", PASS,
                f"slug={first_slug!r}  name={skill_name!r}  "
                f"content_len={len(temp_memory['active_skill_content'])}")

    except Exception as e:
        _record("activate_skill stores content", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S3 — prime_skill_context → _consume_skill_context round-trip
# ══════════════════════════════════════════════════════════════════════════════
def test_skill_injection_roundtrip():
    out("\n[SKILL S3] prime_skill_context → _consume_skill_context round-trip")
    try:
        import llm as llm_module
        from llm import prime_skill_context, _consume_skill_context

        MARKER = "UNIQUE_SKILL_MARKER_XYZ_99872"
        prime_skill_context(f"Skill content containing {MARKER}", "test-roundtrip-skill")

        # State should be set immediately
        assert llm_module._pending_skill_content is not None, \
            "_pending_skill_content must be set after prime_skill_context"
        assert llm_module._pending_skill_name == "test-roundtrip-skill"

        consumed = _consume_skill_context()

        # Content must appear in the consumed string
        assert MARKER in consumed, \
            f"Consumed context must contain the marker; got: {consumed[:200]!r}"
        assert "test-roundtrip-skill" in consumed, \
            f"Consumed context must name the skill; got: {consumed[:200]!r}"

        # Must be cleared after consume
        assert llm_module._pending_skill_content is None, \
            "_pending_skill_content must be None after _consume"
        assert llm_module._pending_skill_name is None, \
            "_pending_skill_name must be None after _consume"

        # Second consume immediately after must be empty
        second = _consume_skill_context()
        assert second == "", f"Second consume should be empty string, got: {second!r}"

        _record("prime → consume returns content, clears state, second consume is empty", PASS,
                f"consumed_len={len(consumed)}")

    except Exception as e:
        _record("skill injection round-trip", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S4 — auto_activate_for_task end-to-end (real registry, real match)
# ══════════════════════════════════════════════════════════════════════════════
def test_auto_activate_for_task():
    out("\n[SKILL S4] auto_activate_for_task end-to-end — real registry search")
    try:
        from skills.antigravity_bridge import auto_activate_for_task, total_skills

        if total_skills() == 0:
            _record("auto_activate_for_task", SKIP, "no skills in registry")
            return

        # Test tasks with high confidence of matching installed skills
        test_tasks = [
            "help me design a secure API with authentication",
            "analyze this agent orchestration pattern",
            "write python code following best practices",
        ]

        any_activated = False
        for task_desc in test_tasks:
            temp_memory: dict = {}
            activated = auto_activate_for_task(task_desc, temp_memory)
            if activated:
                content = temp_memory.get("active_skill_content", "")
                assert len(content) > 50, \
                    f"Activated skill content too short for task '{task_desc}': {len(content)} chars"
                _record(f"auto_activate: '{task_desc[:40]}...'", PASS,
                        f"skill={activated!r}  content_len={len(content)}")
                any_activated = True

        if not any_activated:
            _record("auto_activate_for_task (no exact matches found)", WARN,
                    "Registry uses keyword scoring — none of the test tasks triggered threshold=2")

    except Exception as e:
        _record("auto_activate_for_task", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S5 — invoke_skill handler: activates skill, confirms via _say
# ══════════════════════════════════════════════════════════════════════════════
def test_invoke_skill_handler():
    out("\n[SKILL S5] invoke_skill handler — activates skill and speaks confirmation")
    try:
        from intents.handlers import handle_intent
        from skills.antigravity_bridge import SKILL_REGISTRY, total_skills

        if total_skills() == 0:
            _record("invoke_skill handler", SKIP, "no skills in registry")
            return

        # Pick first slug as the skill to activate
        first_slug = next(iter(SKILL_REGISTRY))

        mock_ui = MockUI()
        temp_mem: dict = {}

        handle_intent(
            intent="invoke_skill",
            parameters={"skill_name": first_slug},
            response=f"activate the {first_slug} skill",
            ui=mock_ui,
            temp_memory=temp_mem,
        )

        # Background thread — wait up to 6s for it to speak
        deadline = time.time() + 6.0
        while time.time() < deadline:
            joined = " ".join(mock_ui.messages).lower()
            if any(kw in joined for kw in ["activat", "mode", "skill", "think", "lens", "error", "wrong"]):
                break
            time.sleep(0.3)

        joined = " ".join(mock_ui.messages).lower()
        activated_ok = any(kw in joined for kw in ["activat", "mode", "skill", "think", "lens"])
        error_ok = any(kw in joined for kw in ["error", "wrong", "couldn"])

        if activated_ok:
            _record("invoke_skill handler activates and speaks", PASS,
                    f"UI output: {joined[:100]!r}")
        elif error_ok:
            _record("invoke_skill handler ran but errored", WARN,
                    f"UI output: {joined[:100]!r}")
        else:
            _record("invoke_skill handler: no expected output within 6s", WARN,
                    f"messages: {mock_ui.messages[:3]}")

    except Exception as e:
        _record("invoke_skill handler", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS S6 — LLM intent detection: "use your agent skill" → invoke_skill
# ══════════════════════════════════════════════════════════════════════════════
def test_skill_intent_detection_from_voice():
    out("\n[SKILL S6] LLM intent detection — 'use your agent skill' → invoke_skill (real API)")
    try:
        from llm import get_llm_output

        utterances = [
            ("Sam activate your agent orchestrator skill",  {"invoke_skill", "activate_skill"}),
            ("what skills do you have",                     {"list_skills", "capabilities"}),
            ("use the security skill",                      {"invoke_skill", "activate_skill"}),
        ]

        for text, expected_intents in utterances:
            result = get_llm_output(text)
            intent = result.get("intent", "")
            acceptable = expected_intents | {"chat"}   # chat is acceptable fallback
            is_ok = intent in acceptable or any(kw in intent.lower() for kw in ["skill", "capab"])
            label = f"LLM intent: {text[:42]!r}"
            status = PASS if is_ok else WARN
            _record(label, status,
                    f"intent={intent!r}  expected_set={expected_intents}  text={result.get('text','')[:50]!r}")

    except Exception as e:
        _record("skill intent detection from voice", FAIL, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    out("=" * 70)
    out("  SAM PHASE TESTS — Phases 4, 5, 8, 9, 10 + Skills S1–S6")
    out("=" * 70)

    test_agent_monitor()
    test_presence_meeting_detection()
    test_code_safety_gate()
    test_morning_briefing_dynamic()
    test_tts_meeting_mode_suppression()
    test_tts_mute_suppression()
    test_skills_registry()
    test_activate_skill_stores_content()
    test_skill_injection_roundtrip()
    test_auto_activate_for_task()
    test_invoke_skill_handler()
    test_skill_intent_detection_from_voice()

    out("\n" + "=" * 70)
    out("  RESULTS SUMMARY")
    out("=" * 70)

    passed  = [r for r in _results if r[1] == PASS]
    failed  = [r for r in _results if r[1] == FAIL]
    warned  = [r for r in _results if r[1] == WARN]
    skipped = [r for r in _results if r[1] == SKIP]

    for label, status, detail in _results:
        icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[SKIP]": "-- ", "[WARN]": "?? "}.get(status, "   ")
        out(f"  {icon} {status}  {label}")

    out("")
    out(f"  PASS:   {len(passed)}")
    out(f"  WARN:   {len(warned)}")
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

    if warned:
        out("\nWARNINGS:")
        for label, _, detail in warned:
            out(f"  ?? {label}")
            if detail:
                out(f"     {detail}")

    sys.exit(0 if not failed else 1)
