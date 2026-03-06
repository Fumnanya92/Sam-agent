"""
tests/test_skills.py
Tests for:
  1. skills/loader.py — SkillLoader discovery and routing
  2. skills/pomodoro.py — timer initiation
  3. skills/standup.py — standup generation
  4. skills/commit_writer.py — commit message heuristics
  5. skills/focus_stats.py — analytics from PatternLearner
  6. skills/text_transform.py — clipboard transform (mocked LLM)
  7. memory/session_state.py — save/load round-trip
  8. presence_engine — session state written on VS Code close

Run with:
    python -m pytest tests/test_skills.py -v
"""

import sys
import os
import json
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# =============================================================================
# 1. SkillLoader — discovery
# =============================================================================

class TestSkillLoader(unittest.TestCase):

    def setUp(self):
        # Fresh loader for each test (don't use the module singleton)
        from skills.loader import SkillLoader
        self.loader = SkillLoader()
        self.loader.load()

    def test_skills_loaded(self):
        """At least 5 skills should auto-discover."""
        names = {m["name"] for m in self.loader.list_skills()}
        self.assertGreaterEqual(len(names), 5, f"Only found: {names}")

    def test_expected_skills_present(self):
        names = {m["name"] for m in self.loader.list_skills()}
        for expected in ("pomodoro", "standup", "commit_writer",
                         "focus_stats", "text_transform", "code_explainer"):
            self.assertIn(expected, names, f"'{expected}' skill missing")

    def test_has_returns_true_for_known_intent(self):
        self.assertTrue(self.loader.has("pomodoro"))
        self.assertTrue(self.loader.has("standup"))
        self.assertTrue(self.loader.has("commit_writer"))

    def test_has_returns_false_for_unknown_intent(self):
        self.assertFalse(self.loader.has("flip_pancakes"))

    def test_trigger_phrases_populated(self):
        phrases = self.loader.get_trigger_phrases()
        self.assertGreater(len(phrases), 10)
        self.assertTrue(any("pomodoro" in p.lower() for p, _ in phrases))

    def test_skill_run_returns_string(self):
        ui = MagicMock()
        result = self.loader.run("pomodoro", {}, ui)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 5)

    def test_unknown_skill_returns_none(self):
        ui = MagicMock()
        result = self.loader.run("flip_pancakes", {}, ui)
        self.assertIsNone(result)


# =============================================================================
# 2. Pomodoro skill
# =============================================================================

class TestPomodoroSkill(unittest.TestCase):

    def _run(self, parameters=None, reminder_engine=None):
        from skills.pomodoro import _run
        ui = MagicMock()
        return _run(parameters or {}, ui, reminder_engine=reminder_engine)

    def test_default_25_minutes(self):
        result = self._run()
        self.assertIn("25", result)

    def test_custom_duration(self):
        result = self._run({"minutes": 45})
        self.assertIn("45", result)

    def test_with_reminder_engine(self):
        engine = MagicMock()
        result = self._run({"minutes": 25}, reminder_engine=engine)
        # Reminder engine should be called twice (work block + break end)
        self.assertEqual(engine.add.call_count, 2)
        self.assertIn("25", result)

    def test_no_reminder_engine_still_works(self):
        result = self._run()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 5)


# =============================================================================
# 3. Standup skill
# =============================================================================

class TestStandupSkill(unittest.TestCase):

    def test_runs_without_crashing(self):
        from skills.standup import _run
        ui = MagicMock()
        result = _run({}, ui)
        self.assertIsInstance(result, str)

    def test_returns_message_even_with_no_data(self):
        from skills.standup import _run
        ui = MagicMock()
        with patch("skills.standup.load_last_session", return_value=None):
            result = _run({}, ui)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 5)

    def test_get_focus_summary_handles_empty(self):
        from skills.standup import _get_focus_summary
        result = _get_focus_summary({})
        # Should return empty string or a sentence — not crash
        self.assertIsInstance(result, str)


# =============================================================================
# 4. Commit writer — heuristics
# =============================================================================

class TestCommitWriter(unittest.TestCase):

    def test_infer_feat_type(self):
        from skills.commit_writer import _infer_commit_message
        diff = "src/api.py | 10 +++++\n 1 file changed, 10 insertions(+)"
        msg = _infer_commit_message(diff, ".")
        self.assertTrue(msg.startswith("feat") or msg.startswith("chore"))

    def test_infer_test_type(self):
        from skills.commit_writer import _infer_commit_message
        diff = "tests/test_api.py | 5 ++\n 1 file changed"
        msg = _infer_commit_message(diff, ".")
        self.assertTrue(msg.startswith("test"))

    def test_infer_docs_type(self):
        from skills.commit_writer import _infer_commit_message
        diff = "README.md | 3 +\n 1 file changed"
        msg = _infer_commit_message(diff, ".")
        self.assertTrue(msg.startswith("docs"))

    def test_conventional_format(self):
        from skills.commit_writer import _infer_commit_message
        diff = "src/utils.py | 8 ++\n 1 file changed"
        msg = _infer_commit_message(diff, ".")
        self.assertIn(":", msg)   # type: description

    def test_no_repo_returns_helpful_message(self):
        from skills.commit_writer import _run
        ui = MagicMock()
        with tempfile.TemporaryDirectory() as d:
            with patch("skills.commit_writer._find_repo_cwd", return_value=""):
                result = _run({}, ui)
        self.assertIn("git", result.lower())


# =============================================================================
# 5. Focus stats
# =============================================================================

class TestFocusStats(unittest.TestCase):

    def test_returns_message_with_no_data(self):
        from skills.focus_stats import _run
        ui = MagicMock()
        with patch("skills.focus_stats.PatternLearner") as MockPL:
            inst = MockPL.return_value
            inst._data = {"focus_sessions": []}
            result = _run({}, ui)
        self.assertIn("enough data", result.lower())

    def test_returns_stats_with_data(self):
        from skills.focus_stats import _run
        from datetime import date
        ui = MagicMock()
        today = date.today().isoformat()
        fake_sessions = [{"date": today, "hour": 9, "minutes": 45.0}] * 3
        with patch("skills.focus_stats.PatternLearner") as MockPL:
            inst = MockPL.return_value
            inst._data = {"focus_sessions": fake_sessions}
            result = _run({}, ui)
        self.assertIn("minutes", result.lower())


# =============================================================================
# 6. Text transform — no LLM call
# =============================================================================

class TestTextTransform(unittest.TestCase):

    def test_empty_clipboard_returns_friendly_message(self):
        from skills.text_transform import _run
        ui = MagicMock()
        with patch("skills.text_transform._read_clipboard", return_value=""):
            result = _run({"transform": "summarise"}, ui)
        self.assertIn("clipboard", result.lower())

    def test_successful_transform(self):
        from skills.text_transform import _run
        ui = MagicMock()
        with (
            patch("skills.text_transform._read_clipboard",
                  return_value="The quick brown fox jumps over the lazy dog."),
            patch("skills.text_transform._transform_via_llm",
                  return_value="A fox jumped over a dog."),
            patch("skills.text_transform._write_clipboard"),
        ):
            result = _run({"transform": "summarise"}, ui)
        self.assertIn("clipboard", result.lower())
        self.assertIn("summarise", result.lower())

    def test_llm_failure_returns_helpful_message(self):
        from skills.text_transform import _run
        ui = MagicMock()
        with (
            patch("skills.text_transform._read_clipboard", return_value="some text"),
            patch("skills.text_transform._transform_via_llm", return_value=""),
        ):
            result = _run({"transform": "rephrase"}, ui)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 5)


# =============================================================================
# 7. session_state.py — round-trip
# =============================================================================

class TestSessionState(unittest.TestCase):

    def test_save_and_load(self):
        from memory.session_state import save_session_state, load_last_session
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("memory.session_state.SESSION_PATH",
                       Path(tmpdir) / "session_state.json"):
                sample = {
                    "timestamp": datetime.now().isoformat(),
                    "git_project": "AccessCode",
                    "git_branch": "feature/auth",
                    "git_cwd": "/projects/AccessCode",
                    "uncommitted_count": 3,
                    "commit_count": 2,
                    "session_duration_minutes": 87.5,
                    "build_failures": 1,
                    "ended_late": False,
                }
                save_session_state(sample)
                loaded = load_last_session()
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["git_project"], "AccessCode")
                self.assertEqual(loaded["commit_count"], 2)

    def test_missing_file_returns_none(self):
        from memory.session_state import load_last_session
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("memory.session_state.SESSION_PATH",
                       Path(tmpdir) / "nonexistent.json"):
                result = load_last_session()
                self.assertIsNone(result)

    def test_is_session_recent_within_window(self):
        from memory.session_state import is_session_recent
        session = {"timestamp": datetime.now().isoformat()}
        self.assertTrue(is_session_recent(session, max_hours=20))

    def test_is_session_recent_outside_window(self):
        from memory.session_state import is_session_recent
        old_ts = datetime(2025, 1, 1, 8, 0, 0).isoformat()
        session = {"timestamp": old_ts}
        self.assertFalse(is_session_recent(session, max_hours=20))


# =============================================================================
# 8. PresenceEngine — session state written on VS Code close
# =============================================================================

class TestPresenceEngineSessionWrite(unittest.TestCase):

    def test_save_session_called_on_vscode_close(self):
        from system.presence_engine import PresenceEngine
        engine = PresenceEngine(poll_interval=9999)

        saved_states = []

        def fake_save(state: dict):
            saved_states.append(state)

        with patch("system.presence_engine.PresenceEngine._save_session_state",
                   side_effect=fake_save):
            # Simulate: was in focused mode, now switches to idle
            from system.window_tracker import get_foreground_window_info
            with patch("system.window_tracker.get_foreground_window_info",
                       return_value={"process": "code.exe", "title": "Sam-Agent — VS Code", "pid": 1}):
                engine._update_state()  # go into focused mode

            with patch("system.window_tracker.get_foreground_window_info",
                       return_value={"process": "explorer.exe", "title": "File Explorer", "pid": 2}):
                engine._update_state()  # leave focused mode → triggers save

        self.assertEqual(len(saved_states), 1,
                         "save_session_state should have been called once on VS Code close")
        state = saved_states[0]
        self.assertIn("session_duration_minutes", state)
        self.assertIn("timestamp", state)


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    unittest.main()
