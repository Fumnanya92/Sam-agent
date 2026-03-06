"""
Unit tests for all new feature modules added in Phase 1–4.
No network calls, no real IMAP, no real audio output.
"""

import sys
import os
import threading
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ═════════════════════════════════════════════════════════════════════════════
# 1. REMINDER ENGINE  (actions/reminders.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestReminderEngine(unittest.TestCase):

    def _make_engine(self):
        from actions.reminders import ReminderEngine
        return ReminderEngine(speak_fn=None, ui=None)

    def test_add_returns_string_id(self):
        eng = self._make_engine()
        rid = eng.add("call boss", minutes=5)
        self.assertIsInstance(rid, str)
        self.assertTrue(len(rid) > 0)

    def test_list_reminders_includes_added(self):
        eng = self._make_engine()
        rid = eng.add("dentist", minutes=10)
        reminders = eng.list_reminders()
        labels = [r["label"] for r in reminders]
        self.assertIn("dentist", labels)

    def test_cancel_removes_reminder(self):
        eng = self._make_engine()
        rid = eng.add("meeting", minutes=2)
        result = eng.cancel(rid)
        self.assertTrue(result)
        self.assertEqual(eng.list_reminders(), [])

    def test_cancel_nonexistent_returns_false(self):
        eng = self._make_engine()
        result = eng.cancel("nonexistent-id")
        self.assertFalse(result)

    def test_list_reminders_excludes_done(self):
        eng = self._make_engine()
        rid = eng.add("gym", minutes=1)
        # Manually mark as done
        with eng._lock:
            eng._reminders[rid]["done"] = True
        self.assertEqual(eng.list_reminders(), [])

    def test_reminder_dict_fields(self):
        eng = self._make_engine()
        eng.add("errand", minutes=3)
        reminders = eng.list_reminders()
        self.assertEqual(len(reminders), 1)
        r = reminders[0]
        for field in ("id", "label", "fire_at", "done"):
            self.assertIn(field, r)

    def test_fire_calls_speak(self):
        speak_mock = MagicMock()
        from actions.reminders import ReminderEngine
        eng = ReminderEngine(speak_fn=speak_mock, ui=None)
        # Build a fake reminder and call _fire directly
        from datetime import datetime
        fake_reminder = {"id": "abc123", "label": "test alarm", "fire_at": datetime.now(), "done": True}
        with patch("system.sound_fx.play_reminder"):
            eng._fire(fake_reminder)
        speak_mock.assert_called_once()
        # Verify the spoken message mentions the label
        spoken_text = speak_mock.call_args[0][0]
        self.assertIn("test alarm", spoken_text)

    def test_default_seconds_clamped_to_60(self):
        """seconds=0 minutes=0 hours=0 should default to 60s, not create a negative timer."""
        eng = self._make_engine()
        rid = eng.add("zero test", seconds=0, minutes=0, hours=0)
        with eng._lock:
            r = eng._reminders[rid]
        from datetime import datetime
        delta = (r["fire_at"] - datetime.now()).total_seconds()
        self.assertGreater(delta, 50)   # close to 60 seconds away

    def test_start_and_stop_no_exception(self):
        eng = self._make_engine()
        eng.start()
        time.sleep(0.05)
        eng.stop()   # should not raise


# ═════════════════════════════════════════════════════════════════════════════
# 2. CLIPBOARD  (actions/clipboard_ops.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestClipboardOps(unittest.TestCase):

    @patch("pyperclip.paste", return_value="  hello world  ")
    def test_read_clipboard_strips_whitespace(self, _mock):
        from actions.clipboard_ops import read_clipboard
        result = read_clipboard()
        self.assertEqual(result, "hello world")

    @patch("pyperclip.paste", return_value="")
    def test_read_clipboard_empty_string(self, _mock):
        from actions.clipboard_ops import read_clipboard
        self.assertEqual(read_clipboard(), "")

    @patch("pyperclip.paste", return_value=None)
    def test_read_clipboard_none_returns_empty(self, _mock):
        from actions.clipboard_ops import read_clipboard
        self.assertEqual(read_clipboard(), "")

    @patch("pyperclip.paste", side_effect=Exception("clipboard error"))
    def test_read_clipboard_exception_returns_empty(self, _mock):
        from actions.clipboard_ops import read_clipboard
        self.assertEqual(read_clipboard(), "")


# ═════════════════════════════════════════════════════════════════════════════
# 3. FILE OPERATIONS  (actions/file_ops.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestFileOps(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_note_returns_path(self):
        from actions.file_ops import create_note, NOTES_DIR
        path, _ = create_note("Test Note", "Some content")
        self.assertTrue(Path(path).exists())
        Path(path).unlink()  # cleanup

    def test_create_note_content_in_file(self):
        from actions.file_ops import create_note
        path, _ = create_note("My Note", "hello content")
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("hello content", text)
        self.assertIn("My Note", text)
        Path(path).unlink()

    def test_create_note_sanitises_title(self):
        from actions.file_ops import create_note
        path, _ = create_note("a/b:c*d?e", "x")
        # path should be valid (no invalid chars)
        self.assertTrue(Path(path).exists())
        Path(path).unlink()

    def test_append_to_log_creates_file(self):
        from actions import file_ops
        original_log = file_ops.DAILY_LOG
        tmp_log = Path(self.tmp) / "test_log.txt"
        file_ops.DAILY_LOG = tmp_log
        try:
            file_ops.append_to_log("test entry")
            self.assertTrue(tmp_log.exists())
            self.assertIn("test entry", tmp_log.read_text(encoding="utf-8"))
        finally:
            file_ops.DAILY_LOG = original_log

    def test_append_to_log_appends(self):
        from actions import file_ops
        original_log = file_ops.DAILY_LOG
        tmp_log = Path(self.tmp) / "log2.txt"
        file_ops.DAILY_LOG = tmp_log
        try:
            file_ops.append_to_log("first")
            file_ops.append_to_log("second")
            content = tmp_log.read_text(encoding="utf-8")
            self.assertIn("first", content)
            self.assertIn("second", content)
        finally:
            file_ops.DAILY_LOG = original_log

    def test_find_files_finds_match(self):
        from actions.file_ops import find_files
        test_file = Path(self.tmp) / "budget_2024.xlsx"
        test_file.write_text("x")
        results = find_files("budget", search_root=self.tmp)
        self.assertTrue(any("budget" in r for r in results))

    def test_find_files_no_match(self):
        from actions.file_ops import find_files
        results = find_files("xyzzy_nonexistent_zzz", search_root=self.tmp)
        self.assertEqual(results, [])

    def test_find_files_capped_at_max_results(self):
        from actions.file_ops import find_files
        for i in range(8):
            (Path(self.tmp) / f"match_{i}.txt").write_text("x")
        results = find_files("match", search_root=self.tmp, max_results=3)
        self.assertLessEqual(len(results), 3)

    def test_open_path_returns_false_on_invalid(self):
        from actions.file_ops import open_path
        result = open_path("/nonexistent/path/that/does/not/exist.xyz")
        self.assertFalse(result)


# ═════════════════════════════════════════════════════════════════════════════
# 4. EMAIL READER  (actions/email_reader.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestEmailReader(unittest.TestCase):

    def test_returns_error_when_no_credentials(self):
        """Without creds in env or config, should return error dict."""
        from actions.email_reader import get_unread_emails
        # Patch config to return empty and clear env vars
        with patch("actions.email_reader._load_config", return_value={}), \
             patch.dict(os.environ, {}, clear=False):
            # Remove vars if set
            os.environ.pop("EMAIL_ADDRESS", None)
            os.environ.pop("EMAIL_PASSWORD", None)
            result = get_unread_emails()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])

    def test_load_config_missing_file_returns_empty(self):
        from actions.email_reader import _load_config
        with patch("pathlib.Path.exists", return_value=False):
            cfg = _load_config()
        self.assertEqual(cfg, {})

    def test_decode_header_plain_ascii(self):
        from actions.email_reader import _decode_header
        result = _decode_header("Hello World")
        self.assertEqual(result, "Hello World")

    def test_decode_header_none_empty(self):
        from actions.email_reader import _decode_header
        result = _decode_header(None)
        self.assertIsInstance(result, str)

    def test_imap_error_returns_error_dict(self):
        from actions.email_reader import get_unread_emails
        with patch("actions.email_reader._load_config",
                   return_value={"email_address": "a@b.com", "email_password": "pw"}), \
             patch("imaplib.IMAP4_SSL", side_effect=Exception("connection refused")):
            result = get_unread_emails()
        self.assertIn("error", result[0])


# ═════════════════════════════════════════════════════════════════════════════
# 5. MEDIA CONTROL  (actions/media_control.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestMediaControl(unittest.TestCase):

    def _patched(self):
        """Patch ctypes win32 call so no hardware is touched."""
        return patch("ctypes.windll.user32.keybd_event")

    def test_volume_up_returns_string(self):
        from actions.media_control import volume_up
        with self._patched():
            result = volume_up()
        self.assertIsInstance(result, str)
        self.assertIn("up", result.lower())

    def test_volume_down_returns_string(self):
        from actions.media_control import volume_down
        with self._patched():
            result = volume_down()
        self.assertIsInstance(result, str)

    def test_mute_toggle_returns_string(self):
        from actions.media_control import mute_toggle
        with self._patched():
            result = mute_toggle()
        self.assertIsInstance(result, str)

    def test_next_track_returns_string(self):
        from actions.media_control import next_track
        with self._patched():
            result = next_track()
        self.assertIsInstance(result, str)

    def test_previous_track_returns_string(self):
        from actions.media_control import previous_track
        with self._patched():
            result = previous_track()
        self.assertIsInstance(result, str)

    def test_play_pause_returns_string(self):
        from actions.media_control import play_pause
        with self._patched():
            result = play_pause()
        self.assertIsInstance(result, str)
        self.assertIn("YouTube Music", result)

    def test_play_query_opens_browser(self):
        from actions.media_control import play_query
        with patch("webbrowser.open") as mock_open:
            result = play_query("lofi beats")
        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        self.assertIn("music.youtube.com", url)
        self.assertIn("lofi", url)
        self.assertIn("lofi beats", result)

    def test_play_query_empty_opens_ytm_home(self):
        from actions.media_control import play_query
        with patch("webbrowser.open") as mock_open:
            result = play_query("")
        url = mock_open.call_args[0][0]
        self.assertEqual(url, "https://music.youtube.com")

    def test_play_query_browser_error_returns_string(self):
        from actions.media_control import play_query
        with patch("webbrowser.open", side_effect=Exception("no browser")):
            result = play_query("afrobeats")
        self.assertIsInstance(result, str)
        self.assertIn("Couldn't", result)

    def test_get_spotify_stub_returns_none(self):
        from actions.media_control import _get_spotify
        self.assertIsNone(_get_spotify())

    def test_vk_constants_correct(self):
        import actions.media_control as mc
        self.assertEqual(mc.VK_MEDIA_PLAY_PAUSE, 0xB3)
        self.assertEqual(mc.VK_MEDIA_NEXT_TRACK, 0xB0)
        self.assertEqual(mc.VK_MEDIA_PREV_TRACK, 0xB1)
        self.assertEqual(mc.VK_VOLUME_UP, 0xAF)
        self.assertEqual(mc.VK_VOLUME_DOWN, 0xAE)
        self.assertEqual(mc.VK_VOLUME_MUTE, 0xAD)

    def test_ytm_base_url(self):
        import actions.media_control as mc
        self.assertEqual(mc.YTM_BASE, "https://music.youtube.com")


# ═════════════════════════════════════════════════════════════════════════════
# 6. AIRCRAFT RADAR  (actions/aircraft_report.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestAircraftReport(unittest.TestCase):

    def test_get_box_known_region(self):
        from actions.aircraft_report import _get_box, REGION_BOXES
        box = _get_box("nigeria")
        self.assertEqual(box, REGION_BOXES["nigeria"])

    def test_get_box_case_insensitive(self):
        from actions.aircraft_report import _get_box, REGION_BOXES
        self.assertEqual(_get_box("LAGOS"), REGION_BOXES["lagos"])

    def test_get_box_unknown_returns_default(self):
        from actions.aircraft_report import _get_box, DEFAULT_BOX
        self.assertEqual(_get_box("mars"), DEFAULT_BOX)

    def test_get_flights_network_error_returns_error_key(self):
        from actions.aircraft_report import get_flights_over
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.ConnectionError("timeout")):
            result = get_flights_over("nigeria")
        self.assertIn("error", result)

    def test_get_flights_empty_states(self):
        from actions.aircraft_report import get_flights_over
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"states": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = get_flights_over("lagos")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["flights"], [])

    def test_get_flights_parses_states(self):
        from actions.aircraft_report import get_flights_over
        # OpenSky state vector: index 1=callsign, 2=origin, 9=speed_ms, 13=altitude
        fake_state = [None, "BAW123  ", "United Kingdom", None, None,
                      None, None, None, None, 250.0,
                      None, None, None, 10000.0, None, None, None]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"states": [fake_state]}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = get_flights_over("uk")
        self.assertEqual(result["count"], 1)
        flight = result["flights"][0]
        self.assertEqual(flight["callsign"], "BAW123")
        self.assertEqual(flight["origin_country"], "United Kingdom")
        self.assertEqual(flight["altitude_m"], 10000)

    def test_describe_flights_no_aircraft(self):
        from actions.aircraft_report import describe_flights
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"states": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            text = describe_flights("Lagos")
        self.assertIn("No aircraft", text)

    def test_describe_flights_formats_altitude_and_speed(self):
        from actions.aircraft_report import describe_flights
        fake_state = [None, "AXB9  ", "Nigeria", None, None,
                      None, None, None, None, 200.0,
                      None, None, None, 5000.0, None, None, None]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"states": [fake_state]}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            text = describe_flights("Nigeria")
        self.assertIn("ft", text)
        self.assertIn("knots", text)
        self.assertIn("AXB9", text)

    def test_all_regions_in_region_boxes(self):
        from actions.aircraft_report import REGION_BOXES
        expected = {"nigeria", "lagos", "abuja", "uk", "london",
                    "usa", "new york", "europe", "germany", "france", "south africa"}
        self.assertTrue(expected.issubset(set(REGION_BOXES.keys())))


# ═════════════════════════════════════════════════════════════════════════════
# 7. SOUND FX  (system/sound_fx.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestSoundFx(unittest.TestCase):
    """Sound functions call winsound.Beep in daemon threads.
    We only verify they are callable and return promptly without raising."""

    def setUp(self):
        # Silence actual beeps during tests
        self._patcher = patch("winsound.Beep")
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_play_wake_callable(self):
        from system.sound_fx import play_wake
        play_wake()   # should not raise

    def test_play_done_callable(self):
        from system.sound_fx import play_done
        play_done()

    def test_play_error_callable(self):
        from system.sound_fx import play_error
        play_error()

    def test_play_reminder_callable(self):
        from system.sound_fx import play_reminder
        play_reminder()

    def test_play_startup_callable(self):
        from system.sound_fx import play_startup
        play_startup()

    def test_all_functions_return_none(self):
        import system.sound_fx as sfx
        for fn_name in ("play_wake", "play_done", "play_error", "play_reminder", "play_startup"):
            fn = getattr(sfx, fn_name)
            result = fn()
            self.assertIsNone(result, f"{fn_name} should return None")

    def test_beep_exception_does_not_propagate(self):
        """If winsound.Beep raises (non-Windows), the module should absorb it."""
        with patch("winsound.Beep", side_effect=OSError("no audio device")):
            from system.sound_fx import play_error
            play_error()   # must not raise


# ═════════════════════════════════════════════════════════════════════════════
# 8. HOTKEY LISTENER  (system/hotkey_listener.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestHotkeyListener(unittest.TestCase):

    def test_default_hotkey_value(self):
        from system.hotkey_listener import HotkeyListener, DEFAULT_HOTKEY
        self.assertEqual(DEFAULT_HOTKEY, "ctrl+alt+s")
        hl = HotkeyListener()
        self.assertEqual(hl._hotkey, "ctrl+alt+s")

    def test_custom_hotkey(self):
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener(hotkey="ctrl+shift+q")
        self.assertEqual(hl._hotkey, "ctrl+shift+q")

    def test_add_callback_registers(self):
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener()
        fn = lambda: None
        hl.add_callback(fn)
        self.assertIn(fn, hl._callbacks)

    def test_trigger_calls_all_callbacks(self):
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener()
        results = []
        hl.add_callback(lambda: results.append(1))
        hl.add_callback(lambda: results.append(2))
        hl._trigger()
        self.assertEqual(results, [1, 2])

    def test_trigger_bad_callback_does_not_crash(self):
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener()
        hl.add_callback(lambda: 1 / 0)   # will raise ZeroDivisionError
        hl._trigger()   # should catch the error, not propagate

    def test_stop_without_keyboard_package(self):
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener()
        hl._running = True
        with patch.dict(sys.modules, {"keyboard": None}):
            hl.stop()   # should not raise even if keyboard is unavailable
        self.assertFalse(hl._running)

    def test_listen_handles_import_error_gracefully(self):
        """If keyboard is not installed, _listen() should log warning and return."""
        from system.hotkey_listener import HotkeyListener
        hl = HotkeyListener()
        with patch.dict(sys.modules, {"keyboard": None}):
            # Should complete without raising
            t = threading.Thread(target=hl._listen, daemon=True)
            t.start()
            t.join(timeout=1.0)
            self.assertFalse(t.is_alive())


if __name__ == "__main__":
    unittest.main()
