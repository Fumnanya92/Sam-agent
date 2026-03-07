"""
tests/test_dev_intelligence.py — Tests for Sam Dev Intelligence Phase 1

Covers:
  - TerminalRunner (actions/terminal.py)
  - git_intelligence (system/git_intelligence.py)
  - git_workflow skill (skills/git_workflow.py)
  - idea_capture skill (skills/idea_capture.py)
  - PatternLearner per-project tracking (system/pattern_learner.py)
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# =============================================================================
# TerminalRunner
# =============================================================================

class TestTerminalRunner(unittest.TestCase):

    def setUp(self):
        from actions.terminal import TerminalRunner
        self.runner = TerminalRunner()

    def test_initially_no_pending(self):
        self.assertFalse(self.runner.has_pending())
        self.assertIsNone(self.runner.get_pending())

    def test_schedule_sets_pending(self):
        self.runner.schedule("echo hello", "/tmp", "echo test")
        self.assertTrue(self.runner.has_pending())
        p = self.runner.get_pending()
        self.assertEqual(p["command"], "echo hello")
        self.assertEqual(p["description"], "echo test")

    def test_cancel_with_pending(self):
        self.runner.schedule("echo hi", "/tmp", "greeting")
        result = self.runner.cancel()
        self.assertFalse(self.runner.has_pending())
        self.assertIn("Cancelled", result)
        self.assertIn("greeting", result)

    def test_cancel_without_pending(self):
        result = self.runner.cancel()
        self.assertIn("Nothing to cancel", result)

    def test_execute_no_pending(self):
        result = self.runner.execute()
        self.assertIn("Nothing pending", result)

    def test_execute_clears_pending(self):
        self.runner.schedule("echo ok", os.getcwd(), "echo test")
        self.runner.execute()
        self.assertFalse(self.runner.has_pending())

    def test_execute_success_returns_output(self):
        self.runner.schedule("echo hello_world", os.getcwd(), "echo")
        result = self.runner.execute()
        self.assertIn("hello_world", result)

    def test_execute_failed_command_mentions_exit_code(self):
        self.runner.schedule("exit 1", os.getcwd(), "fail test")
        result = self.runner.execute()
        # Should mention failure
        self.assertTrue(
            "failed" in result.lower() or "exit" in result.lower(),
            f"Expected failure mention, got: {result}"
        )

    def test_execute_truncates_long_output(self):
        long_cmd = "python -c \"print('x' * 1000)\""
        self.runner.schedule(long_cmd, os.getcwd(), "long output")
        result = self.runner.execute()
        self.assertLessEqual(len(result), 500)

    def test_schedule_overwrites_previous_pending(self):
        self.runner.schedule("echo first", "/tmp", "first")
        self.runner.schedule("echo second", "/tmp", "second")
        p = self.runner.get_pending()
        self.assertEqual(p["command"], "echo second")


class TestGetCwd(unittest.TestCase):

    def test_falls_back_to_os_getcwd_when_no_session(self):
        from actions.terminal import get_cwd
        with patch("actions.terminal.Path.exists", return_value=False):
            result = get_cwd()
        self.assertTrue(len(result) > 0)

    def test_returns_git_cwd_from_session_state(self):
        from actions.terminal import get_cwd
        fake_data = {"git_cwd": os.getcwd()}
        fake_json = json.dumps(fake_data)
        with patch("actions.terminal.Path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data=fake_json)):
            result = get_cwd()
        # If the path exists get_cwd returns the git_cwd value
        self.assertIsInstance(result, str)


# =============================================================================
# git_intelligence
# =============================================================================

class TestGitIntelligenceEmptyCwd(unittest.TestCase):

    def test_non_existent_cwd_returns_empty_dict(self):
        from system.git_intelligence import get_git_status
        result = get_git_status("/path/that/does/not/exist/xyz123")
        # Should return a dict with empty lists and no crash
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("changed_files", []), [])

    def test_empty_cwd_string_returns_empty_dict(self):
        from system.git_intelligence import get_git_status
        result = get_git_status("")
        self.assertIsInstance(result, dict)

    def test_returns_expected_keys(self):
        from system.git_intelligence import get_git_status
        result = get_git_status("")
        expected_keys = {
            "changed_files", "staged_files", "unstaged_files",
            "untracked_files", "large_staged", "dep_changed",
            "danger", "branch", "ahead", "cwd",
        }
        self.assertTrue(expected_keys.issubset(result.keys()))


class TestGitIntelligenceRealRepo(unittest.TestCase):
    """Tests against the actual Sam-Agent repo (known to be a git repo)."""

    def setUp(self):
        self.cwd = str(Path(__file__).resolve().parent.parent)

    def test_get_git_status_runs_without_error(self):
        from system.git_intelligence import get_git_status
        result = get_git_status(self.cwd)
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result["changed_files"], list)
        self.assertIsInstance(result["staged_files"], list)

    def test_branch_is_non_empty_string(self):
        from system.git_intelligence import get_git_status
        result = get_git_status(self.cwd)
        # Sam-Agent is on a branch (not detached)
        self.assertIsInstance(result["branch"], str)
        self.assertGreater(len(result["branch"]), 0)

    def test_summarise_status_returns_string(self):
        from system.git_intelligence import summarise_status
        result = summarise_status(self.cwd)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_last_commit_message_non_empty(self):
        from system.git_intelligence import get_last_commit_message
        result = get_last_commit_message(self.cwd)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_recent_commits_returns_list(self):
        from system.git_intelligence import get_recent_commits
        result = get_recent_commits(self.cwd, n=3)
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 3)


class TestGitIntelligenceDangerDetection(unittest.TestCase):

    def test_merge_head_triggers_merging(self):
        from system.git_intelligence import get_git_status
        with tempfile.TemporaryDirectory() as tmpdir:
            # Init a real git repo
            subprocess.run(["git", "init", tmpdir], capture_output=True)
            # Create fake MERGE_HEAD
            (Path(tmpdir) / ".git" / "MERGE_HEAD").write_text("abc123")
            result = get_git_status(tmpdir)
            self.assertEqual(result["danger"], "MERGING")

    def test_rebase_merge_triggers_rebasing(self):
        from system.git_intelligence import get_git_status
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True)
            (Path(tmpdir) / ".git" / "rebase-merge").mkdir()
            result = get_git_status(tmpdir)
            self.assertEqual(result["danger"], "REBASING")

    def test_dep_file_change_detection(self):
        """A modified requirements.txt should appear in dep_changed."""
        from system.git_intelligence import get_git_status
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", tmpdir], capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir, capture_output=True
            )
            req = Path(tmpdir) / "requirements.txt"
            req.write_text("requests\n")
            result = get_git_status(tmpdir)
            self.assertIn("requirements.txt", result["dep_changed"])


# =============================================================================
# git_workflow skill
# =============================================================================

class TestGitWorkflowSkill(unittest.TestCase):

    def _make_ui(self):
        return MagicMock()

    def test_no_terminal_runner_commit_returns_error(self):
        from skills.git_workflow import _run_skill
        result = _run_skill({"_intent": "git_commit"}, self._make_ui())
        self.assertIn("Terminal", result)

    def test_no_terminal_runner_branch_returns_error(self):
        from skills.git_workflow import _run_skill
        result = _run_skill({"_intent": "git_branch", "branch_name": "feat/test"}, self._make_ui())
        self.assertIn("Terminal", result)

    def test_unknown_intent_returns_message(self):
        from skills.git_workflow import _run_skill
        result = _run_skill({"_intent": "unknown_xyz"}, self._make_ui())
        self.assertIn("Unknown", result)

    def test_diff_returns_string(self):
        from skills.git_workflow import _run_skill
        # Diff on Sam-Agent repo — just needs to not crash
        result = _run_skill({"_intent": "git_diff_summary"}, self._make_ui())
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_status_returns_string(self):
        from skills.git_workflow import _run_skill
        result = _run_skill({"_intent": "git_status_full"}, self._make_ui())
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_branch_no_name_asks_question(self):
        from skills.git_workflow import _run_skill
        mock_runner = MagicMock()
        result = _run_skill(
            {"_intent": "git_branch"},
            self._make_ui(),
            terminal_runner=mock_runner,
        )
        self.assertIn("name", result.lower())

    def test_branch_with_name_schedules_command(self):
        from skills.git_workflow import _run_skill
        mock_runner = MagicMock()
        with patch("skills.git_workflow._get_cwd", return_value=os.getcwd()):
            result = _run_skill(
                {"_intent": "git_branch", "branch_name": "feat/new-feature"},
                self._make_ui(),
                terminal_runner=mock_runner,
            )
        mock_runner.schedule.assert_called_once()
        self.assertIn("feat/new-feature", result)

    def test_branch_name_sanitised(self):
        """Spaces in branch name should become dashes."""
        from skills.git_workflow import _run_skill
        mock_runner = MagicMock()
        with patch("skills.git_workflow._get_cwd", return_value=os.getcwd()):
            result = _run_skill(
                {"_intent": "git_branch", "branch_name": "My New Feature"},
                self._make_ui(),
                terminal_runner=mock_runner,
            )
        call_args = mock_runner.schedule.call_args[0][0]  # first positional arg
        self.assertIn("my-new-feature", call_args)

    def test_commit_no_changes_returns_clean_message(self):
        """If workspace is clean, commit should say nothing to commit."""
        from skills.git_workflow import _run_skill
        mock_runner = MagicMock()
        clean_status = {
            "changed_files": [],
            "staged_files": [],
            "unstaged_files": [],
            "untracked_files": [],
            "large_staged": [],
            "dep_changed": [],
            "danger": None,
            "branch": "main",
            "ahead": 0,
            "cwd": os.getcwd(),
        }
        with patch("skills.git_workflow._get_cwd", return_value=os.getcwd()), \
             patch("system.git_intelligence.get_git_status", return_value=clean_status):
            result = _run_skill(
                {"_intent": "git_commit"},
                self._make_ui(),
                terminal_runner=mock_runner,
            )
        self.assertIn("Nothing to commit", result)


# =============================================================================
# idea_capture skill
# =============================================================================

class TestIdeaCaptureSkill(unittest.TestCase):

    def _make_ui(self):
        return MagicMock()

    def test_empty_idea_asks_clarification(self):
        from skills.idea_capture import _run
        result = _run({}, self._make_ui())
        self.assertIn("?", result)  # should ask a question

    def test_no_api_key_returns_helpful_message(self):
        from skills.idea_capture import _run
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            result = _run({"idea": "user rating system"}, self._make_ui())
        self.assertIn("API key", result)

    def test_slug_converts_spaces_to_dashes(self):
        from skills.idea_capture import _slug
        self.assertEqual(_slug("My New Feature"), "my-new-feature")

    def test_slug_strips_special_chars(self):
        from skills.idea_capture import _slug
        result = _slug("user auth (OAuth2)!")
        self.assertNotIn("(", result)
        self.assertNotIn("!", result)

    def test_slug_max_length(self):
        from skills.idea_capture import _slug
        long_text = "a" * 100
        self.assertLessEqual(len(_slug(long_text)), 60)

    def test_save_plan_creates_markdown_file(self):
        from skills.idea_capture import _save_plan
        plan = {
            "feature": "test-feature",
            "backend": ["Add DB model"],
            "api": ["GET /api/test"],
            "ui": ["TestComponent"],
            "scope": "small",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("skills.idea_capture.PLANS_DIR", Path(tmpdir)):
                filepath = _save_plan(plan, "test feature")
            # Check inside the with-block before cleanup
            self.assertTrue(filepath.exists())
            content = filepath.read_text(encoding="utf-8")
        self.assertIn("test-feature", content)
        self.assertIn("Add DB model", content)
        self.assertIn("GET /api/test", content)

    def test_run_with_openai_mock(self):
        from skills.idea_capture import _run
        fake_plan = {
            "feature": "vendor-rating",
            "backend": ["Rating model"],
            "api": ["/api/ratings"],
            "ui": ["RatingWidget"],
            "scope": "medium",
            "summary": "Vendor rating system ready to build.",
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}), \
             patch("skills.idea_capture._call_openai", return_value=fake_plan), \
             tempfile.TemporaryDirectory() as tmpdir, \
             patch("skills.idea_capture.PLANS_DIR", Path(tmpdir)):
            result = _run({"idea": "vendor rating system"}, self._make_ui())
        self.assertIn("Vendor rating", result)
        self.assertIn("Sam Notes", result)

    def test_run_openai_failure_returns_error(self):
        from skills.idea_capture import _run
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}), \
             patch("skills.idea_capture._call_openai", return_value=None):
            result = _run({"idea": "some feature"}, self._make_ui())
        self.assertIn("couldn't generate", result.lower())


# =============================================================================
# PatternLearner — per-project tracking
# =============================================================================

class TestPatternLearnerProjectTracking(unittest.TestCase):

    def setUp(self):
        # Use a temp file so tests don't pollute real patterns.json
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmpdir.name) / "patterns.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_learner(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            return PatternLearner()

    def test_record_focus_session_with_project_stores_data(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            pl.record_focus_session(30.0, project="sam-agent")
            ps = pl._data.get("project_sessions", {})
            self.assertIn("sam-agent", ps)
            self.assertEqual(len(ps["sam-agent"]), 1)
            self.assertEqual(ps["sam-agent"][0]["minutes"], 30.0)

    def test_record_focus_session_without_project_does_not_create_project_entry(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            pl.record_focus_session(30.0, project=None)
            ps = pl._data.get("project_sessions", {})
            self.assertEqual(ps, {})

    def test_get_project_time_today_sums_todays_sessions(self):
        from datetime import date
        from system.pattern_learner import PatternLearner
        today = date.today().isoformat()
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            pl.record_focus_session(45.0, project="attendance-app")
            pl.record_focus_session(30.0, project="attendance-app")
            total = pl.get_project_time_today("attendance-app")
        self.assertAlmostEqual(total, 75.0)

    def test_get_project_time_today_excludes_other_projects(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            pl.record_focus_session(60.0, project="project-a")
            pl.record_focus_session(25.0, project="project-b")
            total_a = pl.get_project_time_today("project-a")
            total_b = pl.get_project_time_today("project-b")
        self.assertAlmostEqual(total_a, 60.0)
        self.assertAlmostEqual(total_b, 25.0)

    def test_get_project_time_today_unknown_project_returns_zero(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            total = pl.get_project_time_today("nonexistent-project")
        self.assertEqual(total, 0.0)

    def test_project_sessions_capped_at_90(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            for _ in range(95):
                pl.record_focus_session(10.0, project="heavy-project")
            ps = pl._data["project_sessions"]["heavy-project"]
        self.assertEqual(len(ps), 90)

    def test_short_sessions_under_5_min_ignored(self):
        from system.pattern_learner import PatternLearner
        with patch("system.pattern_learner.PATTERNS_FILE", self._tmp_path):
            pl = PatternLearner()
            pl.record_focus_session(4.9, project="tiny-project")
            ps = pl._data.get("project_sessions", {})
        self.assertNotIn("tiny-project", ps)


# =============================================================================
# Skill loader discovers new skills
# =============================================================================

class TestNewSkillsDiscovery(unittest.TestCase):

    def test_git_workflow_intents_registered(self):
        from skills.loader import skill_loader
        for intent in ("git_commit", "git_branch", "git_diff_summary", "git_status_full"):
            self.assertTrue(
                skill_loader.has(intent),
                f"Expected skill_loader to know intent '{intent}'"
            )

    def test_idea_capture_intents_registered(self):
        from skills.loader import skill_loader
        for intent in ("capture_idea", "create_feature_plan", "plan_feature"):
            self.assertTrue(
                skill_loader.has(intent),
                f"Expected skill_loader to know intent '{intent}'"
            )

    def test_git_workflow_in_skill_list(self):
        from skills.loader import skill_loader
        names = [s["name"] for s in skill_loader.list_skills()]
        self.assertIn("git_workflow", names)

    def test_idea_capture_in_skill_list(self):
        from skills.loader import skill_loader
        names = [s["name"] for s in skill_loader.list_skills()]
        self.assertIn("idea_capture", names)


if __name__ == "__main__":
    unittest.main()
