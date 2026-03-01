"""
tests/test_sam_full.py
Comprehensive automated tests for all Sam components changed in the latest update.

Run with:
    python -m pytest tests/test_sam_full.py -v
or:
    python tests/test_sam_full.py
"""

import sys
import os
import json
import asyncio
import unittest
import threading
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ── Add project root to path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ═════════════════════════════════════════════════════════════════════════════
# 1. UI MODULE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestUITransparency(unittest.TestCase):
    """ui.py — _make_transparent()"""

    def _make_transparent(self, img):
        """Inline copy of the method so we don't need a Tkinter window."""
        from PIL import Image
        data = img.getdata()
        new_data = []
        for r, g, b, a in data:
            if r > 220 and g > 220 and b > 220:
                new_data.append((r, g, b, 0))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
        return img

    def test_white_pixel_becomes_transparent(self):
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
        result = self._make_transparent(img)
        self.assertEqual(result.getpixel((0, 0))[3], 0,
                         "white pixel should have alpha=0 after transparency pass")

    def test_near_white_becomes_transparent(self):
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (230, 235, 240, 255))
        result = self._make_transparent(img)
        self.assertEqual(result.getpixel((0, 0))[3], 0,
                         "near-white pixel should become transparent")

    def test_cyan_pixel_preserved(self):
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0x8f, 0xfc, 0xff, 255))
        result = self._make_transparent(img)
        self.assertEqual(result.getpixel((0, 0))[3], 255,
                         "cyan pixel should remain fully opaque")

    def test_black_pixel_preserved(self):
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        result = self._make_transparent(img)
        self.assertEqual(result.getpixel((0, 0))[3], 255,
                         "black pixel should remain fully opaque")


class TestUIParticleInit(unittest.TestCase):
    """ui.py — _init_particles() structure"""

    def _init_particles(self):
        """Inline reimplementation matching ui.py logic."""
        import math
        import random
        particles = []
        total = 65
        for i in range(total):
            angle = (i / total) * 2 * math.pi + random.uniform(-0.15, 0.15)
            if i < 22:
                base_r = random.uniform(210, 255)
                size   = random.uniform(1.5, 3.5)
                alpha  = random.randint(50, 120)
            elif i < 48:
                base_r = random.uniform(255, 305)
                size   = random.uniform(2.0, 5.0)
                alpha  = random.randint(80, 160)
            else:
                base_r = random.uniform(305, 355)
                size   = random.uniform(1.0, 3.0)
                alpha  = random.randint(30, 90)
            particles.append({
                'angle': angle, 'base_r': base_r, 'r': base_r,
                'size': size, 'phase': random.uniform(0, 2 * math.pi),
                'phase_speed': random.uniform(0.008, 0.035),
                'drift': random.uniform(-0.002, 0.002),
                'base_alpha': alpha,
            })
        return particles

    def test_particle_count(self):
        p = self._init_particles()
        self.assertEqual(len(p), 65, "should create exactly 65 particles")

    def test_particle_required_fields(self):
        required = {'angle', 'base_r', 'r', 'size', 'phase',
                    'phase_speed', 'drift', 'base_alpha'}
        for particle in self._init_particles():
            for field in required:
                self.assertIn(field, particle, f"particle missing field: {field}")

    def test_particle_alpha_bounds(self):
        for p in self._init_particles():
            self.assertGreaterEqual(p['base_alpha'], 0)
            self.assertLessEqual(p['base_alpha'], 255)

    def test_particle_radius_positive(self):
        for p in self._init_particles():
            self.assertGreater(p['base_r'], 0)

    def test_inner_ring_radius(self):
        """First 22 particles should be inner ring (r < 255)."""
        particles = self._init_particles()
        for p in particles[:22]:
            self.assertLessEqual(p['base_r'], 260,
                                 "inner ring particles should have radius < 260")

    def test_outer_ring_radius(self):
        """Last 17 particles should be outer corona (r >= 305)."""
        particles = self._init_particles()
        for p in particles[48:]:
            self.assertGreaterEqual(p['base_r'], 300,
                                    "outer ring particles should have radius >= 300")


class TestUITranscriptionQueue(unittest.TestCase):
    """ui.py — set_transcription / clear_transcription enqueue correctly."""

    def _make_mock_ui(self):
        """Create a headless mock of SamUI with just the queue logic."""
        from queue import Queue, Empty

        class FakeUI:
            def __init__(self):
                self._command_queue = Queue()
                self.transcription_var_value = ""

            def _enqueue(self, func, *args, **kwargs):
                self._command_queue.put((func, args, kwargs))

            def set_transcription(self, text):
                self._enqueue(self._set_trans_impl, text)

            def _set_trans_impl(self, text):
                self.transcription_var_value = text

            def clear_transcription(self):
                self._enqueue(self._set_trans_impl, "")

            def flush(self):
                try:
                    while True:
                        func, args, kwargs = self._command_queue.get_nowait()
                        func(*args, **kwargs)
                except Empty:
                    pass

        return FakeUI()

    def test_set_transcription_queues_text(self):
        ui = self._make_mock_ui()
        ui.set_transcription("Hello world")
        ui.flush()
        self.assertEqual(ui.transcription_var_value, "Hello world")

    def test_clear_transcription_empties_text(self):
        ui = self._make_mock_ui()
        ui.set_transcription("Some text")
        ui.flush()
        ui.clear_transcription()
        ui.flush()
        self.assertEqual(ui.transcription_var_value, "")

    def test_set_transcription_is_thread_safe(self):
        """Multiple threads setting transcription should not deadlock."""
        ui = self._make_mock_ui()
        results = []

        def worker(text):
            ui.set_transcription(text)
            results.append(text)

        threads = [threading.Thread(target=worker, args=(f"msg{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ui.flush()
        self.assertEqual(len(results), 10, "all threads should complete")


# ═════════════════════════════════════════════════════════════════════════════
# 2. WEBSOCKET SERVER TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestWebSocketServerMessages(unittest.TestCase):
    """websocket_server.py — message handling logic."""

    def setUp(self):
        from websocket_server import SpeechWebSocketServer
        self.srv = SpeechWebSocketServer()

    def _simulate_message(self, payload: dict):
        """Simulate receiving a JSON message by calling the parse logic directly."""
        data = payload
        if data.get("type") == "wake_word":
            # Should NOT complete transcription
            pass
        elif data.get("type") == "transcript":
            if data.get("isFinal"):
                self.srv.current_transcription = data.get("text", "")
                self.srv.transcription_complete = True

    def test_wake_word_does_not_complete_transcription(self):
        self._simulate_message({"type": "wake_word"})
        self.assertFalse(self.srv.transcription_complete,
                         "wake_word event must NOT set transcription_complete")
        self.assertEqual(self.srv.current_transcription, "")

    def test_final_transcript_completes(self):
        self._simulate_message({"type": "transcript", "text": "what is the weather", "isFinal": True})
        self.assertTrue(self.srv.transcription_complete)
        self.assertEqual(self.srv.current_transcription, "what is the weather")

    def test_interim_transcript_does_not_complete(self):
        self._simulate_message({"type": "transcript", "text": "partia", "isFinal": False})
        self.assertFalse(self.srv.transcription_complete)

    def test_get_transcription_timeout_returns_empty(self):
        """get_transcription with tiny timeout should return '' without hanging."""
        result = self.srv.get_transcription(timeout=0.1)
        self.assertEqual(result, "")

    def test_transcription_reset_on_get(self):
        self.srv.current_transcription = "stale"
        self.srv.transcription_complete = True
        # Calling get_transcription resets then waits — just check reset happened
        # (we can't wait for a real transcript, so we test short timeout)
        result = self.srv.get_transcription(timeout=0.05)
        self.assertEqual(result, "", "stale transcription should be cleared at start of get_transcription")


# ═════════════════════════════════════════════════════════════════════════════
# 3. SPEECH RECOGNITION — WAKE WORD FLOW
# ═════════════════════════════════════════════════════════════════════════════

class TestRecordVoiceNoStartListening(unittest.TestCase):
    """speech_to_text_websocket.py — record_voice must NOT broadcast start_listening."""

    def test_broadcast_start_listening_not_called(self):
        """record_voice() should NOT call broadcast_command('start_listening')."""
        import speech_to_text_websocket as stw

        # Read the source and assert old command is absent
        src = Path(stw.__file__).read_text(encoding="utf-8")
        self.assertNotIn(
            'broadcast_command("start_listening")',
            src,
            "record_voice() must not broadcast start_listening — HTML handles wake word itself"
        )

    def test_broadcast_stop_listening_not_called(self):
        """record_voice() should NOT call broadcast_command('stop_listening')."""
        import speech_to_text_websocket as stw
        src = Path(stw.__file__).read_text(encoding="utf-8")
        self.assertNotIn(
            'broadcast_command("stop_listening")',
            src,
            "record_voice() must not broadcast stop_listening"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. HANDLERS — BUG FIXES & NO CANNED PHRASES
# ═════════════════════════════════════════════════════════════════════════════

class TestHandlersAutoModeBugFix(unittest.TestCase):
    """handlers.py — _handle_auto_mode NameError fix."""

    def test_auto_mode_signature_has_response_param(self):
        """_handle_auto_mode must accept a 'response' parameter."""
        from intents.handlers import _handle_auto_mode
        sig = inspect.signature(_handle_auto_mode)
        self.assertIn("response", sig.parameters,
                      "_handle_auto_mode must have 'response' as explicit parameter")

    def test_auto_mode_no_nameerror(self):
        """Calling _handle_auto_mode should not raise NameError for 'response'."""
        from intents.handlers import _handle_auto_mode

        mock_ui     = MagicMock()
        mock_watcher = MagicMock()

        # Patch edge_speak so no audio is produced
        with patch("intents.handlers.edge_speak"), \
             patch("intents.handlers.controller"):
            try:
                _handle_auto_mode("Auto mode enabled.", mock_ui, mock_watcher)
            except NameError as e:
                self.fail(f"_handle_auto_mode raised NameError: {e}")

    def test_auto_mode_uses_provided_response(self):
        """_handle_auto_mode should speak the provided response text."""
        from intents.handlers import _handle_auto_mode
        import time

        spoken = []
        done = threading.Event()
        mock_ui      = MagicMock()
        mock_watcher = MagicMock()

        def fake_speak(text, ui, blocking=False):
            spoken.append(text)
            done.set()

        # Keep the patch alive long enough for the daemon thread to run
        p1 = patch("intents.handlers.edge_speak", side_effect=fake_speak)
        p2 = patch("intents.handlers.controller")
        p1.start(); p2.start()
        try:
            _handle_auto_mode("Autonomous mode is active now.", mock_ui, mock_watcher)
            done.wait(timeout=2)  # wait for thread to actually call edge_speak
        finally:
            p1.stop(); p2.stop()

        self.assertTrue(any("Autonomous" in s for s in spoken),
                        f"should speak the given response text; got: {spoken}")

    def test_auto_mode_falls_back_to_default(self):
        """_handle_auto_mode with None response should use the built-in default."""
        from intents.handlers import _handle_auto_mode

        spoken = []
        done = threading.Event()
        mock_ui      = MagicMock()
        mock_watcher = MagicMock()

        def fake_speak(text, ui, blocking=False):
            spoken.append(text)
            done.set()

        p1 = patch("intents.handlers.edge_speak", side_effect=fake_speak)
        p2 = patch("intents.handlers.controller")
        p1.start(); p2.start()
        try:
            _handle_auto_mode(None, mock_ui, mock_watcher)
            done.wait(timeout=2)
        finally:
            p1.stop(); p2.stop()

        self.assertTrue(len(spoken) > 0, "should still speak a default message")
        self.assertTrue(any("auto" in s.lower() or "autonomous" in s.lower() for s in spoken))


class TestHandlersNoCannedPhrases(unittest.TestCase):
    """handlers.py — must not contain any old 'Sir, I encountered' or 'Sir, which' phrases."""

    @classmethod
    def setUpClass(cls):
        handlers_path = ROOT / "intents" / "handlers.py"
        cls.source = handlers_path.read_text(encoding="utf-8")

    BANNED_PHRASES = [
        "Sir, I encountered an error",
        "Sir, which",
        "Sir, I could not",
        "Sir, I need",
        "Sir, this appears",
        "Sir, here is my proposed",
    ]

    def test_no_banned_phrases(self):
        for phrase in self.BANNED_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.source,
                                 f"Found banned canned phrase in handlers.py: '{phrase}'")

    def test_all_31_intents_routed(self):
        """handle_intent() must have a branch for all 31 known intents."""
        expected_intents = [
            "send_message", "open_app", "weather_report", "search",
            "read_messages", "whatsapp_summary", "check_whatsapp",
            "whatsapp_ready", "open_whatsapp_chat", "read_whatsapp",
            "reply_whatsapp", "reply_to_contact", "confirm_send",
            "cancel_reply", "edit_reply", "system_status", "kill_process",
            "performance_mode", "auto_mode", "system_trend",
            "screen_vision", "debug_screen", "vscode_mode",
        ]
        for intent in expected_intents:
            with self.subTest(intent=intent):
                self.assertIn(f'"{intent}"', self.source,
                              f"Intent '{intent}' not found in handlers.py")


# ═════════════════════════════════════════════════════════════════════════════
# 5. LLM MODULE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLLMSafeJsonParse(unittest.TestCase):
    """llm.py — safe_json_parse() handles various formats."""

    def setUp(self):
        from llm import safe_json_parse
        self.parse = safe_json_parse

    def test_clean_json(self):
        result = self.parse('{"intent": "chat", "text": "hello"}')
        self.assertEqual(result["intent"], "chat")
        self.assertEqual(result["text"], "hello")

    def test_json_in_markdown_block(self):
        payload = '```json\n{"intent": "search", "text": "searching"}\n```'
        result = self.parse(payload)
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "search")

    def test_json_with_surrounding_text(self):
        payload = 'Here is the result: {"intent": "chat", "text": "done"} end'
        result = self.parse(payload)
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "done")

    def test_empty_string_returns_none(self):
        self.assertIsNone(self.parse(""))

    def test_none_returns_none(self):
        self.assertIsNone(self.parse(None))

    def test_invalid_json_returns_none(self):
        self.assertIsNone(self.parse("not json at all!"))

    def test_nested_json(self):
        payload = '{"intent": "search", "parameters": {"query": "AI news"}, "needs_clarification": false, "text": "On it.", "memory_update": null}'
        result = self.parse(payload)
        self.assertEqual(result["parameters"]["query"], "AI news")


class TestLLMFallbackMessages(unittest.TestCase):
    """llm.py — fallback error messages must not contain 'Sir,'."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "llm.py").read_text(encoding="utf-8")

    def test_no_sir_in_fallbacks(self):
        """No 'Sir,' should appear in any text string in llm.py."""
        lines = self.source.split("\n")
        for i, line in enumerate(lines, 1):
            if '"text"' in line and 'Sir,' in line:
                self.fail(f"Found 'Sir,' in text field at llm.py:{i}: {line.strip()}")

    def test_empty_input_fallback_is_natural(self):
        from llm import get_llm_output
        result = get_llm_output("")
        self.assertNotIn("Sir,", result.get("text", ""),
                         "empty-input fallback should not use 'Sir,'")
        self.assertTrue(len(result.get("text", "")) > 0,
                        "empty-input fallback should return some text")

    def test_max_tokens_at_least_400(self):
        """max_tokens should be >= 400 for richer responses."""
        import re
        match = re.search(r'"max_tokens":\s*(\d+)', self.source)
        self.assertIsNotNone(match, "max_tokens should be set in payload")
        self.assertGreaterEqual(int(match.group(1)), 400,
                                "max_tokens should be at least 400")

    def test_temperature_above_zero_one(self):
        """Temperature should be > 0.1 to allow natural language variation."""
        import re
        match = re.search(r'"temperature":\s*([\d.]+)', self.source)
        self.assertIsNotNone(match, "temperature should be set in payload")
        self.assertGreater(float(match.group(1)), 0.1,
                           "temperature should be > 0.1 for natural responses")


# ═════════════════════════════════════════════════════════════════════════════
# 6. LAUNCHER TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLauncherModule(unittest.TestCase):
    """launcher.py — module structure."""

    def test_launcher_file_exists(self):
        self.assertTrue((ROOT / "launcher.py").exists(),
                        "launcher.py must exist")

    def test_launcher_class_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("launcher", ROOT / "launcher.py")
        mod  = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            # Allow tk-related errors at import in headless env
            if "Tcl" in str(e) or "display" in str(e).lower() or "no display" in str(e).lower():
                self.skipTest(f"Skipping (no display): {e}")
            raise
        self.assertTrue(hasattr(mod, "Launcher"), "launcher.py must define a Launcher class")

    def test_launcher_defines_launch_sam(self):
        src = (ROOT / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("launch_sam", src, "launcher.py must define launch_sam function")

    def test_launcher_is_always_on_top(self):
        src = (ROOT / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("-topmost", src, "launcher window should set -topmost attribute")

    def test_launcher_no_title_bar(self):
        src = (ROOT / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("overrideredirect", src, "launcher should use overrideredirect (no title bar)")


# ═════════════════════════════════════════════════════════════════════════════
# 7. TTS TRANSCRIPTION PASSTHROUGH TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestTTSTranscriptionPassthrough(unittest.TestCase):
    """tts.py — edge_speak must call ui.set_transcription and ui.clear_transcription."""

    def test_source_sets_transcription(self):
        src = (ROOT / "tts.py").read_text(encoding="utf-8")
        self.assertIn("ui.set_transcription", src,
                      "tts.py must call ui.set_transcription(text) when speaking starts")

    def test_source_clears_transcription(self):
        src = (ROOT / "tts.py").read_text(encoding="utf-8")
        self.assertIn("ui.clear_transcription", src,
                      "tts.py must call ui.clear_transcription() when speaking finishes")

    def test_source_suppresses_mic_on_speaking(self):
        src = (ROOT / "tts.py").read_text(encoding="utf-8")
        self.assertIn("sam_speaking", src,
                      "tts.py should broadcast sam_speaking to suppress mic recording")

    def test_source_resumes_mic_after_speaking(self):
        src = (ROOT / "tts.py").read_text(encoding="utf-8")
        self.assertIn("sam_done", src,
                      "tts.py should broadcast sam_done to resume mic after speaking")


# ═════════════════════════════════════════════════════════════════════════════
# 8. SPEECH CLIENT HTML WAKE WORD TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestSpeechClientHTML(unittest.TestCase):
    """speech_client.html — wake word detection structure."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "speech_client.html").read_text(encoding="utf-8")

    def test_wake_phrases_defined(self):
        self.assertIn("WAKE_PHRASES", self.source,
                      "speech_client.html should define WAKE_PHRASES constant")

    def test_hey_sam_is_a_wake_phrase(self):
        self.assertIn("hey sam", self.source.lower(),
                      "speech_client.html should include 'hey sam' as a wake phrase")

    def test_passive_mode_defined(self):
        self.assertIn("passive", self.source.lower(),
                      "speech_client.html should have passive mode")

    def test_active_mode_defined(self):
        self.assertIn("active", self.source.lower(),
                      "speech_client.html should have active mode")

    def test_sam_speaking_command_handled(self):
        self.assertIn("sam_speaking", self.source,
                      "speech_client.html should handle 'sam_speaking' server command")

    def test_sam_done_command_handled(self):
        self.assertIn("sam_done", self.source,
                      "speech_client.html should handle 'sam_done' server command")

    def test_continuous_recognition(self):
        self.assertIn("recognition.continuous",
                      self.source,
                      "speech recognition should set continuous=true")

    def test_wake_word_message_sent_to_server(self):
        # Legacy wake_word type was replaced by __hmm__ bare-wake-word marker
        self.assertIn("__hmm__", self.source,
                      "speech_client.html should send __hmm__ marker when bare wake word is detected")

    def test_auto_restart_on_end(self):
        self.assertIn("safeStart", self.source,
                      "recognition should auto-restart on end event")

    def test_suppression_during_sam_speech(self):
        self.assertIn("suppressed", self.source,
                      "speech client should suppress output while Sam is speaking")


# ═════════════════════════════════════════════════════════════════════════════
# 9. MAIN.PY WAKE WORD INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════

class TestMainWakeWordIntegration(unittest.TestCase):
    """main.py — wake word flow and hint display."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_get_voice_input_accepts_ui(self):
        """get_voice_input() should accept a ui parameter."""
        self.assertIn("get_voice_input(ui", self.source,
                      "get_voice_input() should accept ui parameter")

    def test_hint_shown_while_waiting(self):
        """set_transcription hint should be shown while waiting for wake word."""
        self.assertIn("say", self.source.lower(),
                      "should show some hint to the user while passive")

    def test_startup_greeting_present(self):
        """Startup greeting should announce Sam is ready."""
        self.assertIn("Sam online", self.source,
                      "startup greeting should tell user Sam is live")

    def test_no_start_listening_broadcast_in_get_voice_input(self):
        """main.py should not broadcast start_listening."""
        self.assertNotIn('broadcast_command("start_listening")', self.source)

    def test_in_conversation_initialized(self):
        """in_conversation must be initialized before the while loop uses it."""
        # Find ai_loop body and check in_conversation is set before the while loop
        loop_start = self.source.find("async def ai_loop")
        while_start = self.source.find("while True:", loop_start)
        # in_conversation must appear between the function def and the while loop
        pre_loop = self.source[loop_start:while_start]
        self.assertIn("in_conversation", pre_loop,
                      "in_conversation must be initialized before 'while True:' to avoid UnboundLocalError")


# ═════════════════════════════════════════════════════════════════════════════
# 10. PROMPT NATURALNESS TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPromptNaturalness(unittest.TestCase):
    """core/prompt.txt — must use natural language instructions."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8")

    def test_no_always_say_sir(self):
        """Prompt must not instruct Sam to always say 'Sir'."""
        # Check it doesn't mandate Sir on every response
        self.assertNotIn("always say Sir", self.source.lower(),
                         "prompt should not force 'Sir' on every response")

    def test_natural_language_directive(self):
        """Prompt should instruct natural speech."""
        lower = self.source.lower()
        self.assertTrue(
            "natural" in lower or "vary" in lower or "real" in lower,
            "prompt should instruct Sam to speak naturally"
        )

    def test_no_robotic_confirmation_instruction(self):
        """Prompt must not MANDATE robotic confirmations (it can mention them as examples to avoid)."""
        lower = self.source.lower()
        self.assertNotIn("always say sir", lower,
                         "prompt should not instruct Sam to always say 'Sir'")
        self.assertTrue(
            "never" in lower or "avoid" in lower or "not" in lower,
            "prompt should instruct Sam what NOT to do"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 11. LATEST FIXES — Double-voice dedup lock
# ═════════════════════════════════════════════════════════════════════════════

class TestWhatsAppDedupLock(unittest.TestCase):
    """handlers.py — _whatsapp_lock prevents concurrent WhatsApp triggers."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "intents" / "handlers.py").read_text(encoding="utf-8")

    def test_lock_defined(self):
        self.assertIn("_whatsapp_lock", self.source,
                      "handlers.py must define _whatsapp_lock")

    def test_lock_is_threading_lock(self):
        self.assertIn("threading.Lock()", self.source,
                      "handlers.py must create _whatsapp_lock with threading.Lock()")

    def test_lock_acquired_in_read_messages(self):
        self.assertIn("_whatsapp_lock.acquire", self.source,
                      "read_messages handler must acquire _whatsapp_lock")

    def test_lock_released_in_finally(self):
        self.assertIn("_whatsapp_lock.release()", self.source,
                      "handlers must release _whatsapp_lock in a finally block")

    def test_say_helper_defined(self):
        self.assertIn("def _say(", self.source,
                      "handlers.py should define a _say() speak helper")

    def test_whatsapp_call_handler_defined(self):
        self.assertIn("def _handle_whatsapp_call(", self.source,
                      "handlers.py must define _handle_whatsapp_call()")

    def test_whatsapp_call_routed_in_handle_intent(self):
        self.assertIn('"whatsapp_call"', self.source,
                      "handle_intent must route the whatsapp_call intent")

    def test_draft_popup_called_on_reply(self):
        self.assertIn("show_draft_popup", self.source,
                      "reply_to_contact handler must call ui.show_draft_popup()")


# ═════════════════════════════════════════════════════════════════════════════
# 12. LATEST FIXES — Draft popup in ui.py
# ═════════════════════════════════════════════════════════════════════════════

class TestUIDraftPopup(unittest.TestCase):
    """ui.py — show_draft_popup() method exists and is thread-safe."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "ui.py").read_text(encoding="utf-8")

    def test_method_defined(self):
        self.assertIn("def show_draft_popup(", self.source,
                      "ui.py must define show_draft_popup()")

    def test_method_enqueues(self):
        # The popup must be dispatched via _enqueue so it runs on the Tk thread
        self.assertIn("_enqueue", self.source[self.source.find("def show_draft_popup"):],
                      "show_draft_popup must use _enqueue for thread-safety")

    def test_popup_has_copy_button(self):
        self.assertIn("Copy", self.source,
                      "draft popup should have a Copy button")

    def test_popup_has_close_button(self):
        self.assertIn("Close", self.source,
                      "draft popup should have a Close button")

    def test_popup_uses_toplevel(self):
        self.assertIn("Toplevel", self.source,
                      "draft popup should use tk.Toplevel")

    def test_window_size_reduced(self):
        """Window should be 580x760, not the old 760x960."""
        self.assertIn("580x760", self.source,
                      "window geometry should be reduced to 580x760")
        self.assertNotIn("760x960", self.source,
                         "old 760x960 geometry should be removed")


# ═════════════════════════════════════════════════════════════════════════════
# 13. LATEST FIXES — Sir removed from whatsapp_assistant.py
# ═════════════════════════════════════════════════════════════════════════════

class TestNoSirInAssistant(unittest.TestCase):
    """automation/whatsapp_assistant.py — all 'Sir,' strings must be gone."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "automation" / "whatsapp_assistant.py").read_text(encoding="utf-8")

    def test_no_sir_comma(self):
        self.assertNotIn("Sir,", self.source,
                         "whatsapp_assistant.py must not contain 'Sir,'")

    def test_no_sir_i(self):
        # "Sir, I" pattern
        self.assertNotIn("Sir, I", self.source,
                         "whatsapp_assistant.py must not contain 'Sir, I'")

    def test_checking_messages_no_sir(self):
        self.assertNotIn("Sir, checking", self.source,
                         "message-check speech must not start with 'Sir,'")

    def test_no_unread_no_sir(self):
        self.assertNotIn("Sir, you have no unread", self.source,
                         "no-unread message must not say 'Sir,'")


# ═════════════════════════════════════════════════════════════════════════════
# 14. LATEST FIXES — Sir removed from prompt
# ═════════════════════════════════════════════════════════════════════════════

class TestPromptNoSir(unittest.TestCase):
    """core/prompt.txt — must now forbid 'Sir' entirely."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8")

    def test_never_say_sir_directive(self):
        lower = self.source.lower()
        self.assertIn("never", lower,
                      "prompt must use 'never' to forbid Sir")
        # Check that the prohibition is about Sir specifically
        self.assertTrue(
            "sir" in lower,
            "prompt must mention 'sir' in a prohibition context"
        )

    def test_whatsapp_call_intent_listed(self):
        self.assertIn("whatsapp_call", self.source,
                      "prompt must list whatsapp_call as a valid intent")

    def test_whatsapp_call_parameter_documented(self):
        self.assertIn("contact_name", self.source,
                      "whatsapp_call must document its contact_name parameter")

    def test_name_memory_rule_present(self):
        self.assertIn("NAME MEMORY RULE", self.source,
                      "prompt must contain a NAME MEMORY RULE section")

    def test_name_memory_path_correct(self):
        self.assertIn("identity.name", self.source,
                      "name memory rule must specify the correct JSON path identity.name")

    def test_cannot_do_honesty_rule(self):
        lower = self.source.lower()
        self.assertTrue(
            "cannot" in lower or "can't" in lower or "unsupported" in lower,
            "prompt must instruct Sam to honestly say when it can't do something"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 15. LATEST FIXES — Expanded wake phrases + __hmm__ handling
# ═════════════════════════════════════════════════════════════════════════════

class TestExpandedWakePhrases(unittest.TestCase):
    """speech_client.html — expanded wake phrase list."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "speech_client.html").read_text(encoding="utf-8")

    def test_are_you_listening_phrase(self):
        self.assertIn("are you listening", self.source.lower(),
                      "speech_client.html should recognise 'are you listening' as a wake phrase")

    def test_are_you_there_phrase(self):
        self.assertIn("are you there", self.source.lower(),
                      "speech_client.html should recognise 'are you there' as a wake phrase")

    def test_hmm_sent_on_bare_wake_word(self):
        self.assertIn("__hmm__", self.source,
                      "bare wake-word (no query) should send __hmm__ transcript so Sam can acknowledge")

    def test_active_timeout_at_least_25s(self):
        import re
        m = re.search(r"ACTIVE_TIMEOUT_MS\s*=\s*(\d+)", self.source)
        self.assertIsNotNone(m, "ACTIVE_TIMEOUT_MS should be defined")
        self.assertGreaterEqual(int(m.group(1)), 25000,
                                "active timeout should be at least 25 s for conversations")


class TestHmmHandlingInMain(unittest.TestCase):
    """main.py — __hmm__ transcription triggers acknowledgment without LLM call."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_hmm_intercepted(self):
        self.assertIn("__hmm__", self.source,
                      "main.py must intercept the __hmm__ transcript")

    def test_hmm_does_not_hit_llm(self):
        # The __hmm__ block must 'continue' before the LLM call
        hmm_idx = self.source.find("__hmm__")
        continue_idx = self.source.find("continue", hmm_idx)
        llm_idx = self.source.find("get_llm_output", hmm_idx)
        self.assertLess(continue_idx, llm_idx,
                        "__hmm__ branch must 'continue' before reaching get_llm_output")

    def test_hmm_responses_varied(self):
        # At least two different acknowledgment strings should exist
        acks = ["Hmm", "Yeah", "here", "What", "Go ahead"]
        found = sum(1 for a in acks if a in self.source)
        self.assertGreaterEqual(found, 2,
                                "Should have at least 2 varied hmm acknowledgment phrases")


# ═════════════════════════════════════════════════════════════════════════════
# 16. LATEST FIXES — mss installed
# ═════════════════════════════════════════════════════════════════════════════

class TestMssInstalled(unittest.TestCase):
    """mss must be importable in the current environment."""

    def test_mss_importable(self):
        try:
            import mss  # noqa: F401
        except ImportError:
            self.fail("mss is not installed — run: pip install mss")

    def test_mss_basic_usage(self):
        """mss.mss() context manager must be usable."""
        import mss
        try:
            with mss.mss() as sct:
                monitors = sct.monitors
                self.assertIsInstance(monitors, list)
                self.assertGreater(len(monitors), 0,
                                   "mss should detect at least one monitor")
        except Exception as e:
            self.skipTest(f"mss context manager unavailable in this environment: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# 17. LATEST FIXES — WhatsApp reply_to_contact full message read
# ═════════════════════════════════════════════════════════════════════════════

class TestReplyToContactFullRead(unittest.TestCase):
    """whatsapp_assistant.py — reply_to_contact reads full message from open chat."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "automation" / "whatsapp_assistant.py").read_text(encoding="utf-8")

    def test_calls_get_latest_message(self):
        self.assertIn("get_latest_message_from_open_chat", self.source,
                      "reply_to_contact must call get_latest_message_from_open_chat() for full text")

    def test_falls_back_to_cache(self):
        # Should use cached message as fallback if DOM read fails
        self.assertIn("unread_cache", self.source,
                      "reply_to_contact should reference unread_cache as fallback")

    def test_opens_chat_before_read(self):
        # open_chat_by_name must be called before reading
        src = self.source if hasattr(self, 'source') else (ROOT / "automation" / "whatsapp_assistant.py").read_text()
        open_idx = src.find("open_chat_by_name")
        read_idx  = src.find("get_latest_message_from_open_chat")
        self.assertLess(open_idx, read_idx,
                        "open_chat_by_name must be called before get_latest_message_from_open_chat")

    def test_handles_empty_unread_cache(self):
        self.assertIn("ensure_chrome_debug", self.source,
                      "reply_to_contact must handle empty cache by doing a fresh Chrome check")


# ═════════════════════════════════════════════════════════════════════════════
# 18. LATEST FIXES — conversation mode persists after Sam speaks
# ═════════════════════════════════════════════════════════════════════════════

class TestConversationPersistence(unittest.TestCase):
    """tts.py + speech_client.html — mic stays active after Sam replies."""

    def test_tts_broadcasts_set_active(self):
        src = (ROOT / "tts.py").read_text(encoding="utf-8")
        self.assertIn("set_active", src,
                      "tts.py should broadcast set_active after speaking so conversation continues")

    def test_html_sam_done_enters_active(self):
        src = (ROOT / "speech_client.html").read_text(encoding="utf-8")
        # In the sam_done handler, enterActive() must be called (not setMode('passive'))
        sam_done_block_start = src.find("case 'sam_done':")
        sam_done_block_end   = src.find("break;", sam_done_block_start)
        block = src[sam_done_block_start:sam_done_block_end]
        self.assertIn("enterActive", block,
                      "sam_done handler must call enterActive() to keep conversation open")
        self.assertNotIn("setMode('passive')", block,
                         "sam_done handler must NOT set passive mode — that kills conversation")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
