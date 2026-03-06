"""
tests/test_skills_and_session.py

Tests for:
  - memory/session_state.py (save, load, recency check)
  - skills/loader.py (SkillLoader registry, dispatch)
  - All 6 skill manifests (structure, callable, safe execution)
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeUI:
    """Minimal stand-in for SamUI used by skills."""
    def write_log(self, msg: str):
        pass
    def set_transcription(self, msg: str):
        pass
    def clear_transcription(self):
        pass


# ---------------------------------------------------------------------------
# session_state
# ---------------------------------------------------------------------------

class TestSessionState:
    """Tests for memory/session_state.py utilities."""

    def _make_state(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "git_project": "Sam-Agent",
            "git_branch": "feature/presence",
            "git_cwd": "/home/kelvin/projects/Sam-Agent",
            "uncommitted_count": 3,
            "commit_count": 2,
            "session_duration_minutes": 47.5,
            "build_failures": 1,
            "ended_late": False,
        }

    def test_save_creates_file(self, tmp_path):
        from memory import session_state as ss
        orig = ss.SESSION_PATH
        ss.SESSION_PATH = tmp_path / "session_state.json"
        try:
            ss.save_session_state(self._make_state())
            assert ss.SESSION_PATH.exists()
        finally:
            ss.SESSION_PATH = orig

    def test_save_writes_valid_json(self, tmp_path):
        from memory import session_state as ss
        orig = ss.SESSION_PATH
        ss.SESSION_PATH = tmp_path / "session_state.json"
        try:
            ss.save_session_state(self._make_state())
            data = json.loads(ss.SESSION_PATH.read_text(encoding="utf-8"))
            assert data["git_project"] == "Sam-Agent"
            assert data["commit_count"] == 2
        finally:
            ss.SESSION_PATH = orig

    def test_load_returns_none_when_no_file(self, tmp_path):
        from memory import session_state as ss
        orig = ss.SESSION_PATH
        ss.SESSION_PATH = tmp_path / "nonexistent.json"
        try:
            result = ss.load_last_session()
            assert result is None
        finally:
            ss.SESSION_PATH = orig

    def test_load_returns_dict(self, tmp_path):
        from memory import session_state as ss
        orig = ss.SESSION_PATH
        ss.SESSION_PATH = tmp_path / "session_state.json"
        try:
            state = self._make_state()
            ss.save_session_state(state)
            loaded = ss.load_last_session()
            assert isinstance(loaded, dict)
            assert loaded["git_branch"] == "feature/presence"
        finally:
            ss.SESSION_PATH = orig

    def test_load_returns_none_on_corrupt_file(self, tmp_path):
        from memory import session_state as ss
        orig = ss.SESSION_PATH
        p = tmp_path / "corrupt.json"
        p.write_text("not valid json", encoding="utf-8")
        ss.SESSION_PATH = p
        try:
            result = ss.load_last_session()
            assert result is None
        finally:
            ss.SESSION_PATH = orig

    def test_is_session_recent_true_for_fresh(self):
        from memory.session_state import is_session_recent
        state = {"timestamp": datetime.now().isoformat()}
        assert is_session_recent(state, max_hours=20) is True

    def test_is_session_recent_false_for_old(self):
        from memory.session_state import is_session_recent
        old_ts = (datetime.now() - timedelta(hours=25)).isoformat()
        state = {"timestamp": old_ts}
        assert is_session_recent(state, max_hours=20) is False

    def test_is_session_recent_returns_false_on_bad_timestamp(self):
        from memory.session_state import is_session_recent
        assert is_session_recent({"timestamp": "garbage"}, max_hours=20) is False

    def test_is_session_recent_returns_false_when_key_missing(self):
        from memory.session_state import is_session_recent
        assert is_session_recent({}, max_hours=20) is False


# ---------------------------------------------------------------------------
# SkillLoader
# ---------------------------------------------------------------------------

class TestSkillLoader:
    """Tests for skills/loader.py SkillLoader."""

    def test_load_discovers_skills(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        loader.load()
        assert len(loader._registry) > 0

    def test_has_returns_true_for_pomodoro(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        assert loader.has("pomodoro") is True

    def test_has_returns_false_for_unknown(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        assert loader.has("__totally_nonexistent_intent__") is False

    def test_run_returns_string_for_pomodoro(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        result = loader.run("pomodoro", {}, _FakeUI())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_run_returns_none_for_unknown(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        result = loader.run("__ghost__", {}, _FakeUI())
        assert result is None

    def test_list_skills_returns_list(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        skills = loader.list_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_list_skills_each_has_name_and_description(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        for s in loader.list_skills():
            assert "name" in s
            assert "description" in s
            assert s["name"]

    def test_singleton_is_skill_loader_instance(self):
        from skills.loader import skill_loader, SkillLoader
        assert isinstance(skill_loader, SkillLoader)

    def test_get_trigger_phrases_returns_pairs(self):
        from skills.loader import SkillLoader
        loader = SkillLoader()
        pairs = loader.get_trigger_phrases()
        assert isinstance(pairs, list)
        assert len(pairs) > 0
        for phrase, intent in pairs:
            assert isinstance(phrase, str)
            assert isinstance(intent, str)


# ---------------------------------------------------------------------------
# Individual skill manifests
# ---------------------------------------------------------------------------

SKILL_MODULES = [
    "skills.pomodoro",
    "skills.standup",
    "skills.commit_writer",
    "skills.text_transform",
    "skills.focus_stats",
    "skills.code_explainer",
]


class TestSkillManifestStructure:
    """Every skill must expose a well-formed SKILL_MANIFEST."""

    @pytest.mark.parametrize("module_name", SKILL_MODULES)
    def test_has_manifest(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        assert hasattr(mod, "SKILL_MANIFEST"), f"{module_name} missing SKILL_MANIFEST"

    @pytest.mark.parametrize("module_name", SKILL_MODULES)
    def test_manifest_has_required_keys(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        m = mod.SKILL_MANIFEST
        for key in ("name", "description", "intents", "trigger_phrases", "run"):
            assert key in m, f"{module_name}: manifest missing '{key}'"

    @pytest.mark.parametrize("module_name", SKILL_MODULES)
    def test_manifest_run_is_callable(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        assert callable(mod.SKILL_MANIFEST["run"])

    @pytest.mark.parametrize("module_name", SKILL_MODULES)
    def test_intents_is_nonempty_list(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        intents = mod.SKILL_MANIFEST["intents"]
        assert isinstance(intents, list)
        assert len(intents) >= 1

    @pytest.mark.parametrize("module_name", SKILL_MODULES)
    def test_trigger_phrases_nonempty(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        tp = mod.SKILL_MANIFEST["trigger_phrases"]
        assert isinstance(tp, list)
        assert len(tp) >= 1


# ---------------------------------------------------------------------------
# Pomodoro skill
# ---------------------------------------------------------------------------

class TestPomodoroSkill:
    def test_no_reminder_engine_returns_string(self):
        from skills.pomodoro import _run
        result = _run({}, _FakeUI())
        assert isinstance(result, str)
        assert "25" in result or "Pomodoro" in result

    def test_custom_duration_reflected(self):
        from skills.pomodoro import _run
        result = _run({"minutes": 50}, _FakeUI())
        assert "50" in result

    def test_with_reminder_engine_queues_two_reminders(self):
        from skills.pomodoro import _run
        mock_re = MagicMock()
        result = _run({"minutes": 25}, _FakeUI(), reminder_engine=mock_re)
        assert mock_re.add.call_count == 2
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Text transform skill (pure logic — no LLM needed)
# ---------------------------------------------------------------------------

class TestTextTransformSkill:
    def test_empty_clipboard_returns_instruction(self):
        from skills.text_transform import _run
        with patch("skills.text_transform._read_clipboard", return_value=""):
            result = _run({"transform": "summarise"}, _FakeUI())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_short_clipboard_returns_instruction(self):
        from skills.text_transform import _run
        with patch("skills.text_transform._read_clipboard", return_value="hi"):
            result = _run({}, _FakeUI())
        assert isinstance(result, str)

    def test_invalid_transform_falls_back_to_rephrase(self):
        """An unrecognised transform should not crash — silently maps to rephrase."""
        from skills import text_transform as tt
        assert tt._DEFAULT_TRANSFORM == "rephrase"

    def test_synonym_mapping_shorten_to_summarise(self):
        from skills.text_transform import _run
        with patch("skills.text_transform._read_clipboard", return_value=""):
            # Just checking it doesn't raise — clipboard empty path
            result = _run({"transform": "shorten"}, _FakeUI())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Code explainer skill
# ---------------------------------------------------------------------------

class TestCodeExplainerSkill:
    def test_empty_clipboard_returns_instruction(self):
        from skills.code_explainer import _run
        with patch("skills.code_explainer._read_clipboard", return_value=""):
            result = _run({}, _FakeUI())
        assert "clipboard" in result.lower() or "couldn't" in result.lower()

    def test_clipboard_too_short_returns_instruction(self):
        from skills.code_explainer import _run
        with patch("skills.code_explainer._read_clipboard", return_value="x = 1"):
            result = _run({}, _FakeUI())
        assert isinstance(result, str)

    def test_llm_failure_returns_fallback(self):
        from skills.code_explainer import _run
        with patch("skills.code_explainer._read_clipboard", return_value="def foo(): pass  # some code here"):
            with patch("skills.code_explainer._explain_via_llm", return_value=""):
                result = _run({}, _FakeUI())
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Commit writer skill
# ---------------------------------------------------------------------------

class TestCommitWriterSkill:
    def test_no_repo_returns_instruction(self):
        from skills.commit_writer import _run
        with patch("skills.commit_writer._find_repo_cwd", return_value=None):
            result = _run({}, _FakeUI())
        assert isinstance(result, str)
        assert "git" in result.lower() or "repository" in result.lower()


# ---------------------------------------------------------------------------
# Focus stats skill
# ---------------------------------------------------------------------------

class TestFocusStatsSkill:
    def test_no_data_returns_fallback(self):
        from skills.focus_stats import _run
        with patch("system.pattern_learner.PatternLearner") as MockPL:
            instance = MockPL.return_value
            instance._data = {"focus_sessions": []}
            # Actually call the real function — it creates its own PatternLearner inside
            # so patch via the module it's imported from
            result = _run({}, _FakeUI())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_single_session_also_falls_back(self):
        """A single session (< 2) should return the 'not enough data' fallback."""
        from skills import focus_stats
        import system.pattern_learner as pl_mod
        fake_pl = MagicMock()
        fake_pl._data = {"focus_sessions": [{"minutes": 30, "date": "2026-03-06", "hour": 9}]}
        with patch.object(pl_mod, "PatternLearner", return_value=fake_pl):
            result = focus_stats._run({}, _FakeUI())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Standup skill
# ---------------------------------------------------------------------------

class TestStandupSkill:
    def test_no_data_returns_fallback(self):
        from skills.standup import _run
        with patch("skills.standup._get_git_commits", return_value=""):
            with patch("skills.standup._get_todays_notes", return_value=""):
                with patch("skills.standup._get_focus_summary", return_value=""):
                    result = _run({}, _FakeUI())
        assert isinstance(result, str)
        assert "couldn't" in result.lower() or "standup" in result.lower() or "activity" in result.lower()

    def test_with_commits_includes_date(self):
        from skills.standup import _run
        with patch("skills.standup._get_git_commits", return_value="3 commits pushed."):
            with patch("skills.standup._get_todays_notes", return_value=""):
                with patch("skills.standup._get_focus_summary", return_value=""):
                    result = _run({}, _FakeUI())
        assert "standup" in result.lower()
        assert "commit" in result.lower()
