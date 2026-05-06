import sys
import io

# Force stdout/stderr to UTF-8 on Windows — only when run directly (not when imported as module)
if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
import threading
import queue
import time
from difflib import SequenceMatcher

# Load environment variables from .env early so modules that read os.getenv() pick them up
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv not installed — environment variables may be provided by the shell
    pass

# Initialize logging first
from log.logger import get_logger, log_function_entry, log_function_exit, log_error, log_performance, log_state_change
logger = get_logger("MAIN")

# Real-time Web Speech API for speech recognition
from speech_to_text_websocket import (
    record_voice,
    initialize_speech_system,
    run_embedded_window_loop,
)
from llm import get_llm_output, get_ai_response, get_model_tier, set_model_tier, COMPLEX_INTENTS
from actions.terminal import TerminalRunner
from tts import edge_speak, stop_speaking
from ui import SamUI
from conversation_state import controller, State
import sys
from pathlib import Path

from memory.memory_manager import load_memory, update_memory
from memory.temporary_memory import TemporaryMemory
from assistant.morning_briefing import generate_morning_briefing
# generate_daily_plan import removed 2026-05-01 — was unused; daily_planner is
# now a deprecation shim that re-exports through morning_briefing.
from datetime import datetime

# Intent handlers
from intents import handle_intent

# System monitoring
from system.system_watcher import SystemWatcher

# WhatsApp AI automation
from automation.whatsapp_ai_engine import WhatsAppAIEngine
from automation.whatsapp_assistant import WhatsAppAssistant

# Reminder engine
from actions.reminders import ReminderEngine

# Hotkey listener (Ctrl+Alt+S to wake Sam)
from system.hotkey_listener import HotkeyListener

# Notification sounds
from system.sound_fx import play_startup, play_done

# Presence engine — continuous environment awareness
from system.presence_engine import PresenceEngine

interrupt_commands = ["mute", "quit", "exit", "stop"]

# Phrases that will immediately silence Sam and return to passive (wake-word) mode.
# Checked BEFORE the LLM so there is zero latency.
_STOP_PHRASES = [
    "stop listening",
    "stop talking",
    "go quiet",
    "be quiet",
    "pause listening",
    "sam stop",
    "mute yourself",
]

temp_memory = TemporaryMemory()
whatsapp_engine = WhatsAppAIEngine()
whatsapp_assistant = WhatsAppAssistant()

# Initialize system watcher for background monitoring
watcher = SystemWatcher()
watcher.start()

# Initialize presence engine — tracks active window, user mode, stress level
presence_engine = PresenceEngine()
presence_engine.start()

# Kick off background project index scan so open_project / code_helper are fast
try:
    from system.project_index import project_index as _project_index
    _project_index.load()  # loads from disk instantly; rescans in background if stale
except Exception:
    pass

# Initialize background task queue
try:
    from system.task_queue import task_queue as _task_queue  # noqa: F401 — ensures singleton is warm
except Exception:
    pass

# Start event bus watchers
try:
    from system.event_bus import bus as _bus
    from system.watchers.file_watcher import file_watcher as _fw
    from system.watchers.calendar_watcher import calendar_watcher as _cw
    from system.watchers.system_watcher import system_error_watcher as _sw

    def _on_file_changed(event: dict):
        """Auto-run tests when a source file changes in a watched project."""
        try:
            proj = event["data"].get("project", "")
            rel  = event["data"].get("relative", "")
            if not proj:
                return
            from agents.test_runner import TestRunner
            runner = TestRunner()
            result = runner.run(project_path=proj)
            if result.total > 0 and not result.passed:
                from system.task_queue import task_queue
                # Deliver failure via task_queue completion mechanism (respects meeting mode)
                task_queue._deliver_completion(
                    "auto_test",
                    f"Tests failed after editing {rel}: {result.summary()}",
                    is_error=True,
                )
        except Exception:
            pass

    def _on_calendar_soon(event: dict):
        """Mute Sam and send a notification before a meeting."""
        summary = event["data"].get("summary", "Meeting")
        mins    = event["data"].get("minutes_until", 10)
        try:
            from conversation_state import controller
            controller.set_mode("meeting")
            from system.notifier import notify
            notify(f"Meeting in {mins} min", f"{summary} — Sam is now in meeting mode")
        except Exception:
            pass

    _bus.subscribe("file_changed", _on_file_changed)
    _bus.subscribe("calendar_event_soon", _on_calendar_soon)

    _fw.start()
    _cw.start()
    _sw.start()
except Exception as _e:
    pass  # watchers are optional; don't crash startup

# Initialize reminder engine (started inside ai_loop after ui is ready)
reminder_engine = ReminderEngine()

# Terminal command execution with approval
terminal_runner = TerminalRunner()

# Initialize global hotkey listener
_hotkey_listener = HotkeyListener(hotkey="ctrl+alt+s")

# Queue for typed text input from the UI text field
typed_input_queue: queue.Queue = queue.Queue()

# use module-level controller from conversation_state

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()

async def get_voice_input(ui: SamUI, in_conversation: bool = False):
    # Wait until Sam is not speaking
    while controller.is_speaking():
        await asyncio.sleep(0.05)

    controller.set_state(State.LISTENING)
    logger.debug(f"[MIC] Entering LISTENING state (in_conversation={in_conversation})")

    # Drive orb to listening state
    if hasattr(ui, "set_voice_state"):
        ui.set_voice_state("listening")

    # Hint shown in the transcription area while idle
    if in_conversation:
        ui.set_transcription('Listening…')
    else:
        ui.set_transcription('say "Hey Sam" to activate…')

    logger.debug("[MIC] Calling record_voice() — waiting for speech...")
    text = await asyncio.to_thread(record_voice, in_conversation)
    logger.debug(f"[MIC] record_voice() returned: '{text}'")

    ui.clear_transcription()
    # Return orb to idle after capture
    if hasattr(ui, "set_voice_state"):
        ui.set_voice_state("idle")

    if text:
        print(f"You: {text}")
        logger.info(f"[MIC] User said: '{text}'")

        # Filter phantom inputs
        PHANTOM_WORDS = {'some', 'some.', 'you', 'the', 'from', 'from some', 'a', 'an', 'and', 'or', 'but'}
        if len(text.strip()) < 3 or text.lower().strip() in PHANTOM_WORDS:
            logger.warning(f"[MIC] Filtered phantom input: '{text}' — ignoring")
            return ""

        # Echo-gate: drop transcript if it matches what Sam just said
        # (happens when speaker output is picked up by the mic)
        last_sam = temp_memory.get_last_ai_response() or ""
        if last_sam:
            t_lower = text.lower().strip()
            s_lower = last_sam.lower().strip()
            # Containment check + fuzzy ratio to catch garbled echoes
            # (e.g. Sam says "1:17", mic captures "117" — exact match fails, ratio catches it)
            ratio = SequenceMatcher(None, t_lower[:len(s_lower)], s_lower).ratio()
            if t_lower in s_lower or s_lower.startswith(t_lower) or (len(t_lower) > 20 and ratio > 0.75):
                logger.warning(f"[MIC] Echo detected (ratio={ratio:.2f}) — dropping: '{text[:60]}'")
                return ""
    else:
        logger.warning("[MIC] record_voice() returned empty — no speech detected or timed out")

    controller.set_state(State.IDLE)
    return text


async def get_any_input(ui: SamUI, in_conversation: bool = False) -> str:
    """Return typed text immediately if queued, otherwise wait for voice input.

    Polls the typed queue every 300 ms while voice input is running so that
    text entered during a voice-wait is never lost.
    """
    try:
        return typed_input_queue.get_nowait()
    except queue.Empty:
        pass

    # Run voice input as a background task so we can interrupt it with typed text
    voice_task = asyncio.create_task(get_voice_input(ui, in_conversation=in_conversation))

    while True:
        done, _ = await asyncio.wait({voice_task}, timeout=0.3)
        if done:
            try:
                return voice_task.result() or ""
            except Exception:
                return ""
        # Check typed queue while the voice thread is still running
        try:
            typed = typed_input_queue.get_nowait()
            voice_task.cancel()
            # Clean up voice state
            controller.set_state(State.IDLE)
            ui.clear_transcription()
            if hasattr(ui, "set_voice_state"):
                ui.set_voice_state("idle")
            return typed
        except queue.Empty:
            pass


def _is_affirmative(text: str) -> bool:
    """Return True if the user's response sounds like a yes/confirmation."""
    t = text.strip().lower()
    return any(w in t for w in [
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
        "go ahead", "do it", "please", "switch", "absolutely",
        "definitely", "go on", "of course", "use it", "use cloud",
        "confirm", "alright", "run it", "execute",
    ])


async def ai_loop(ui: SamUI):
    briefing_delivered_today = False
    in_conversation = False  # True after first exchange; keeps mic active without re-saying "Hey Sam"

    # Wire the typed input queue into the UI so the text field can push text here
    ui.set_typed_input_queue(typed_input_queue)

    # Track which complex intents we've already suggested the cloud model for (once-per-session)
    _complex_intents_suggested: set = set()

    # Cloud model confirmation state
    _awaiting_cloud_confirm: bool = False     # True while waiting for user yes/no
    _cloud_confirm_user_text: str | None = None  # original request being held
    _replay_user_text: str | None = None     # set to replay a request without new voice input

    # Start reminder engine — it now enqueues to notification_queue instead of speaking
    reminder_engine._speak = None   # disabled; notification_queue handles delivery
    reminder_engine._ui = ui
    reminder_engine.start()

    # Start proactive reasoner — it now enqueues to notification_queue instead of speaking
    try:
        from agents.proactive_reasoner import proactive_reasoner as _pr
        _pr.start(ui=ui, speak=None)   # speak=None; notification_queue handles delivery
    except Exception as _e:
        logger.warning(f"ProactiveReasoner failed to start: {_e}")

    # Start global hotkey — pressing Ctrl+Alt+S sets Sam to active listening
    def _hotkey_wake():
        try:
            from websocket_server import speech_server as _srv
            if _srv:
                _srv.broadcast_command("set_active")
            logger.info("Hotkey wake triggered")
        except Exception:
            pass
    _hotkey_listener.add_callback(_hotkey_wake)
    _hotkey_listener.start()

    # Startup greeting — context-aware by time of day, active project, and last session
    await asyncio.sleep(2)  # brief pause for UI to settle
    play_startup()

    hour = datetime.now().hour
    _boot_mem = load_memory()
    _name = (
        _boot_mem.get("identity", {})
        .get("name", {})
        .get("value", "")
    )

    if 5 <= hour < 12:
        _salutation = "Good morning"
    elif 12 <= hour < 17:
        _salutation = "Good afternoon"
    elif 17 <= hour < 21:
        _salutation = "Good evening"
    else:
        _salutation = "Still up"

    _greeting = f"{_salutation}, {_name}." if _name else f"{_salutation}."

    # Build context-aware continuation from last session
    from memory.session_state import load_last_session, is_session_recent
    _last = load_last_session()

    if _last and is_session_recent(_last, max_hours=20):
        _proj     = _last.get("git_project", "")
        _branch   = _last.get("git_branch", "")
        _mins     = _last.get("session_duration_minutes", 0)
        _commits  = _last.get("commit_count", 0)
        _failures = _last.get("build_failures", 0)
        _late     = _last.get("ended_late", False)
        _pending  = _last.get("uncommitted_count", 0)

        if _late and 5 <= hour < 12:
            _greeting += " You were up late last night."

        if _proj:
            _context = f" Last session was in {_proj}"
            if _branch and _branch not in ("main", "master"):
                _context += f" on {_branch}"
            _context += "."
            if _pending:
                _context += f" {_pending} uncommitted change{'s' if _pending != 1 else ''} waiting."
            elif _commits:
                _context += f" {_commits} commit{'s' if _commits != 1 else ''} landed."
            if _failures >= 2:
                _context += f" There were {_failures} debug cycles."
            startup_msg = f"{_greeting}{_context} Say 'Hey Sam' when you need me."
        else:
            startup_msg = f"{_greeting} Say 'Hey Sam' whenever you need me."
    else:
        # No recent session — fall back to project from memory
        _project = (
            _boot_mem.get("projects", {})
            .get("primary_project", {})
            .get("value", "")
            or _boot_mem.get("goals", {})
            .get("primary_project", {})
            .get("value", "")
        )
        if _project:
            startup_msg = f"{_greeting} We're working on {_project}. Say 'Hey Sam' when you need me."
        else:
            startup_msg = f"{_greeting} Say 'Hey Sam' whenever you need me."

    # Always log the boot greeting so it's visible in chat history.
    ui.write_log(f"SAM: {startup_msg}")

    # Conversation gate: if the user has already started talking to Sam
    # while the boot was settling (LISTENING / THINKING / SPEAKING), do NOT
    # speak the greeting on top of them. The text is still logged above so
    # they can see it scroll past — we just keep the audio channel free.
    # Also respect mute and meeting/silent modes.
    _boot_state = controller.get_state()
    _boot_mode  = getattr(controller, "_mode", "normal")
    _boot_muted = getattr(controller, "_muted", False)
    if _boot_state == State.IDLE and not _boot_muted and _boot_mode == "normal":
        controller.set_state(State.SPEAKING)
        await asyncio.to_thread(edge_speak, startup_msg, ui, True)
        controller.set_state(State.IDLE)
    else:
        logger.info(
            "Boot greeting suppressed (state=%s muted=%s mode=%s) — text-only.",
            _boot_state.name, _boot_muted, _boot_mode,
        )

    # ── Background task: move presence suggestions into the notification queue ──
    async def _presence_collector():
        """Drain presence engine suggestions into the notification queue every 15s.
        The notification_queue drainer (below) handles actual speech delivery."""
        while True:
            await asyncio.sleep(15)
            try:
                from system.notification_queue import notification_queue as _nq
                while True:
                    suggestion = presence_engine.suggestions.get_nowait()
                    msg = suggestion.get("message", "")
                    if msg:
                        _nq.enqueue(msg, source="presence", priority=1)
            except queue.Empty:
                pass

    asyncio.create_task(_presence_collector())

    # ── Background task: deliver queued notifications when Sam is idle ──────────
    async def _notification_drainer():
        """
        Speak pending notifications only when Sam is idle (not mid-response).
        Checks every 6 seconds.  Waits an extra 1.5 s after Sam stops speaking
        to avoid clashing with the tail of a TTS response.
        """
        from system.notification_queue import notification_queue as _nq
        from shared_state import is_sam_speaking as _speaking_flag

        while True:
            await asyncio.sleep(6)

            if not _nq.has_pending():
                continue

            # Skip if Sam is busy — speaking, thinking, or actively listening to the user
            _busy_states = (State.THINKING, State.LISTENING, State.SPEAKING)
            if _speaking_flag.is_set() or controller.get_state() in _busy_states:
                continue

            # Brief settling delay so a just-finished response fully clears
            await asyncio.sleep(1.5)

            # Re-check after the settling delay
            if _speaking_flag.is_set() or controller.get_state() in _busy_states:
                continue

            if not _nq.has_pending():
                continue

            items = _nq.drain()
            if not items:
                continue

            msg = _nq.format_for_speech(items)
            if not msg:
                continue

            play_done()
            ui.write_log(f"AI: {msg}")
            # Push to React dashboard so it appears in chat history
            try:
                from tts import broadcast_to_web
                broadcast_to_web("notification", {"source": "assistant_message", "text": msg})
            except Exception:
                pass
            controller.set_state(State.SPEAKING)
            try:
                await asyncio.to_thread(edge_speak, msg, ui, True)
            except Exception as _drain_err:
                logger.error(f"[NotificationDrainer] TTS failed: {_drain_err}")
            finally:
                controller.set_state(State.IDLE)

    asyncio.create_task(_notification_drainer())

    while True:
        # Morning briefing check
        current_hour = datetime.now().hour
        current_date = datetime.now().date()
        
        if current_hour == 7 and not briefing_delivered_today:
            try:
                briefing = generate_morning_briefing()
                briefing_delivered_today = True
                # Enqueue — delivered conversationally between responses
                from system.notification_queue import notification_queue as _nq
                _nq.enqueue(briefing, source="briefing", priority=8)
                ui.write_log(f"[Briefing queued] {briefing[:80]}...")
            except Exception as e:
                logger.error(f"Morning briefing failed: {e}")
        
        # Reset briefing flag at midnight (hour 0)
        if current_hour == 0:
            briefing_delivered_today = False

        # Replay confirmation-accepted requests without fresh voice input
        if _replay_user_text:
            user_text = _replay_user_text
            _replay_user_text = None
        else:
            user_text = await get_any_input(ui, in_conversation=in_conversation)

        if not user_text:
            # Timed out — if we were in a conversation, drop back to passive
            in_conversation = False
            continue

        # Intercept yes/no when Sam is waiting for cloud-model confirmation
        if _awaiting_cloud_confirm:
            _awaiting_cloud_confirm = False
            ui.unhighlight_text_input()
            if _is_affirmative(user_text):
                msg = set_model_tier("cloud")
                ui.write_log(f"AI: {msg}")
                controller.set_state(State.SPEAKING)
                await asyncio.to_thread(edge_speak, msg, ui, True)
                controller.set_state(State.IDLE)
                # Replay the original request now on cloud
                _replay_user_text = _cloud_confirm_user_text
                _cloud_confirm_user_text = None
            else:
                controller.set_state(State.SPEAKING)
                await asyncio.to_thread(edge_speak, "Alright, sticking with local.", ui, True)
                controller.set_state(State.IDLE)
                # Re-process original request on local tier instead of dropping it
                _replay_user_text = _cloud_confirm_user_text
                _cloud_confirm_user_text = None
            continue

        # ── Terminal-pending intercept — bypass LLM for confirm/cancel ──────
        # If terminal_runner has a command queued, grab yes/no before the LLM
        # sees it (the LLM has no awareness of pending state).
        if terminal_runner.has_pending():
            _t_lower = user_text.strip().lower()
            _CANCEL_WORDS = {"cancel", "never mind", "nevermind", "stop", "abort", "no", "nope", "don't"}
            if _is_affirmative(user_text):
                result = terminal_runner.execute()
                ui.write_log(f"Sam: {result}")
                controller.set_state(State.SPEAKING)
                await asyncio.to_thread(edge_speak, result, ui, True)
                controller.set_state(State.IDLE)
                continue
            elif any(w in _t_lower for w in _CANCEL_WORDS):
                result = terminal_runner.cancel()
                ui.write_log(f"Sam: {result}")
                controller.set_state(State.SPEAKING)
                await asyncio.to_thread(edge_speak, result, ui, True)
                controller.set_state(State.IDLE)
                continue

        # Wake-word-only acknowledgment — respond with a short "hmm" without hitting the LLM
        if user_text.strip() == "__hmm__":
            import random
            ack = random.choice(["Hmm?", "Yeah?", "I'm here.", "What's up?", "Go ahead."])
            ui.write_log(f"AI: {ack}")
            controller.set_state(State.SPEAKING)
            await asyncio.to_thread(edge_speak, ack, ui, True)
            controller.set_state(State.IDLE)
            in_conversation = True
            continue

        # Guided-session abort: let handler speak cancel message BEFORE interrupt block
        # silences Sam. Only applies when in a guided session AND user says an abort word.
        _GUIDED_ABORT_WORDS = {"stop", "cancel", "abort", "quit", "exit", "never mind", "forget it"}
        if (temp_memory.pending_intent == "guided_task"
                and any(w in user_text.lower() for w in _GUIDED_ABORT_WORDS)):
            from intents.handlers import _handle_guided_step_turn
            _handle_guided_step_turn(user_text, ui, temp_memory)
            continue

        if any(cmd in user_text.lower() for cmd in interrupt_commands):
            stop_speaking()
            # Force the speech client back to passive (wake-word) mode
            try:
                from websocket_server import speech_server as _srv
                if _srv:
                    _srv.broadcast_command("set_passive")
            except Exception:
                pass
            controller.set_state(State.IDLE)
            temp_memory.reset()
            in_conversation = False
            # Exit dictation mode too if we were in it
            try:
                from shared_state import set_dictation_mode
                set_dictation_mode(False)
            except Exception:
                pass
            continue

        # Explicit stop-listening phrases — bypass LLM entirely
        _u_lower = user_text.lower()
        if any(phrase in _u_lower for phrase in _STOP_PHRASES):
            stop_speaking()
            try:
                from websocket_server import speech_server as _srv
                if _srv:
                    _srv.broadcast_command("set_passive")
            except Exception:
                pass
            try:
                from shared_state import set_dictation_mode
                set_dictation_mode(False)
            except Exception:
                pass
            controller.set_state(State.IDLE)
            in_conversation = False
            continue

        # Dictation mode — type the spoken text into the foreground window
        try:
            from shared_state import get_dictation_mode, set_dictation_mode
            if get_dictation_mode():
                _exit_words = {"done", "done dictating", "stop dictating", "finish",
                               "that's it", "that's all", "end dictation", "stop"}
                if any(w in _u_lower for w in _exit_words):
                    set_dictation_mode(False)
                    ui.write_log("SAM: Dictation ended.")
                    controller.set_state(State.SPEAKING)
                    await asyncio.to_thread(edge_speak, "Dictation ended.", ui, True)
                    controller.set_state(State.IDLE)
                    in_conversation = False
                else:
                    # Focus Notepad, then paste via clipboard (handles all Unicode)
                    import time as _t
                    _clean = user_text.replace("'", "\u2019")
                    try:
                        import ctypes as _ct
                        import pyautogui as _pag

                        # Focus Notepad via ctypes — reliable on Windows
                        _user32 = _ct.windll.user32
                        _hwnd = _user32.GetTopWindow(None)
                        while _hwnd:
                            _buf = _ct.create_unicode_buffer(512)
                            _user32.GetWindowTextW(_hwnd, _buf, 512)
                            if "notepad" in _buf.value.lower():
                                _user32.ShowWindow(_hwnd, 9)   # SW_RESTORE
                                _user32.SetForegroundWindow(_hwnd)
                                _t.sleep(0.2)
                                break
                            _hwnd = _user32.GetWindow(_hwnd, 2)  # GW_HWNDNEXT

                        # Set clipboard using win32clipboard via ctypes (no PowerShell)
                        import subprocess as _clip_proc
                        _clip_proc.run(
                            "clip",
                            input=(_clean + "\r\n").encode("utf-16-le"),
                            shell=True,
                            check=False,
                        )
                        _t.sleep(0.15)
                        _pag.hotkey("ctrl", "v")
                    except Exception as _de:
                        logger.warning(f"Dictation type failed: {_de}")
                    ui.write_log(f"[Dictation] {user_text}")
                    in_conversation = True
                continue
        except Exception:
            pass

        ui.write_log(f"You: {user_text}")

        if temp_memory.get_current_question():
            param = temp_memory.get_current_question()
            temp_memory.update_parameters({param: user_text})
            temp_memory.clear_current_question()
            user_text = temp_memory.get_last_user_text()

        temp_memory.set_last_user_text(user_text)
        in_conversation = True  # Sam has spoken at least once; keep conversation active

        # Pending create_note — user is supplying content; bypass LLM entirely
        if temp_memory.pending_intent == "create_note":
            _stored = temp_memory.get_parameters()
            temp_memory.reset()
            from intents.handlers import _handle_create_note
            _handle_create_note(
                {"title": _stored.get("title", "Quick Note"),
                 "content": user_text,
                 "tag": _stored.get("tag", "")},
                response=None,
                ui=ui,
            )
            continue

        # Pending guided_task — user responding to a co-pilot step; bypass LLM
        if temp_memory.pending_intent == "guided_task":
            from intents.handlers import _handle_guided_step_turn
            _handle_guided_step_turn(user_text, ui, temp_memory)
            continue

        long_term_memory = load_memory()

        def minimal_memory_for_prompt(memory: dict) -> dict:
            result = {}

            identity = memory.get("identity", {})
            preferences = memory.get("preferences", {})
            relationships = memory.get("relationships", {})
            emotional_state = memory.get("emotional_state", {})

            if "name" in identity:
                result["user_name"] = identity["name"].get("value")

            for k in ["favorite_color", "favorite_food", "favorite_music"]:
                if k in preferences:
                    val = preferences[k].get("value")
                    if isinstance(val, dict) and "value" in val:
                        val = val["value"]
                    result[k] = val

            for rel, info in relationships.items():
                if isinstance(info, dict) and "name" in info and "value" in info["name"]:
                    result[f"{rel}_name"] = info["name"]["value"]

            for event, info in emotional_state.items():
                if "value" in info:
                    result[f"emotion_{event}"] = info["value"]

            return {k: v for k, v in result.items() if v}

        memory_for_prompt = minimal_memory_for_prompt(long_term_memory)

        history_lines = temp_memory.get_history_for_prompt()
        recent_history = "\n".join(history_lines.split("\n")[-5:])
        if recent_history:
            memory_for_prompt["recent_conversation"] = recent_history

        if temp_memory.has_pending_intent():
            memory_for_prompt["_pending_intent"] = temp_memory.pending_intent
            memory_for_prompt["_collected_params"] = str(temp_memory.get_parameters())

        # Inject live presence context so the LLM can calibrate tone
        memory_for_prompt["presence"] = presence_engine.get_state_snapshot()

        # Inject last written code file so "run it" / "show me the game" can resolve it
        try:
            if hasattr(temp_memory, "get_last_code_file") and temp_memory.get_last_code_file():
                memory_for_prompt["last_code_file"] = temp_memory.get_last_code_file()
        except Exception:
            pass

        # Inject flutter test state so the LLM knows when a UI test is running
        try:
            from skills.flutter_tester import _test_state as _fts
            if _fts["running"]:
                memory_for_prompt["flutter_test_running"] = (
                    f"Sam is currently running a UI test (step {_fts['step']}/25) "
                    f"on {_fts['project']} at {_fts['app_url']}. "
                    f"Task: {_fts['task']}"
                )
        except Exception:
            pass

        # Set THINKING state just before invoking the LLM
        controller.set_state(State.THINKING)
        if hasattr(ui, "set_voice_state"):
            ui.set_voice_state("thinking")

        # Prime skill context if an antigravity skill was recently activated
        try:
            from llm import prime_skill_context
            skill_content = temp_memory.get("active_skill_content") if hasattr(temp_memory, "get") else None
            skill_name    = temp_memory.get("active_skill_name")    if hasattr(temp_memory, "get") else None
            if skill_content:
                prime_skill_context(skill_content, skill_name)
                # Clear so it's only used once
                if hasattr(temp_memory, "delete"):
                    temp_memory.delete("active_skill_content")
                    temp_memory.delete("active_skill_name")
        except Exception:
            pass

        try:
            llm_output = await asyncio.to_thread(
                get_ai_response,
                user_text=user_text,
                memory_block=memory_for_prompt
            )
        except Exception as e:
            ui.write_log(f"AI ERROR: {e}")
            controller.set_state(State.IDLE)
            if hasattr(ui, "set_voice_state"):
                ui.set_voice_state("idle")
            continue

        # Orb returns to idle; tts.py drives it to "speaking" via start_speaking()
        if hasattr(ui, "set_voice_state"):
            ui.set_voice_state("idle")

        intent = llm_output.get("intent", "chat")
        parameters = llm_output.get("parameters", {})
        response = llm_output.get("text")
        needs_clarification = llm_output.get("needs_clarification", False)
        memory_update = llm_output.get("memory_update")

        # Debug: Log what we got from LLM
        logger.debug(f"LLM output: intent='{intent}', response={repr(response)}, params={parameters}")

        # Highlight text field if Sam needs clarification (prompts typed input)
        if needs_clarification:
            ui.highlight_text_input()

        # For complex tasks on local tier: ask the user before proceeding
        if (get_model_tier() == "local"
                and intent in COMPLEX_INTENTS
                and intent not in _complex_intents_suggested):
            _complex_intents_suggested.add(intent)
            _cloud_confirm_user_text = user_text
            _awaiting_cloud_confirm = True
            # Redirect to a simple yes/no question — don't execute the intent yet
            intent = "chat"
            response = "This might do better on the cloud model — want me to switch?"
            ui.highlight_text_input()

        if memory_update and isinstance(memory_update, dict):
            update_memory(memory_update)

        temp_memory.set_last_ai_response(response)

        # Broadcast Sam's response text to the React UI over WebSocket (no-op if daemon not wired)
        try:
            from tts import broadcast_to_web
            broadcast_to_web("chat_message", {"role": "assistant", "content": response or ""})
        except Exception:
            pass

        # Log detected intent for debugging
        logger.info(f"Intent detected: '{intent}' | Response: '{response[:50] if response else 'None'}...'")

        # Log action to session logger (used for daily report)
        try:
            from system.session_logger import session_logger
            session_logger.log_action(intent, response[:120] if response else intent, "pending")
        except Exception:
            pass

        # Route to intent handler with error handling
        try:
            handle_intent(
                intent=intent,
                parameters=parameters,
                response=response,
                ui=ui,
                temp_memory=temp_memory,
                whatsapp_engine=whatsapp_engine,
                whatsapp_assistant=whatsapp_assistant,
                watcher=watcher,
                reminder_engine=reminder_engine,
                terminal_runner=terminal_runner,
            )
        except Exception as e:
            logger.error(f"Intent handler error: {e}", exc_info=True)
            ui.write_log(f"AI ERROR: {e}")
            controller.set_state(State.IDLE)

        # loop continues; get_voice_input handles waiting for SPEAKING

def start_ui_in_thread():
    """Start the Tk UI in a background thread with proper setup."""
    import tkinter as tk
    from queue import Queue
    
    logger.info("Starting UI thread setup")
    ui_ready = threading.Event()
    ui_queue = Queue()
    
    def _ui_thread():
        logger.info("UI thread starting - creating SamUI")
        try:
            # Create a new Tk root for this thread
            ui = SamUI()
            logger.info("SamUI created successfully")
            
            # Pass the UI object back to main thread
            ui_queue.put(ui)
            ui_ready.set()
            logger.info("UI object passed to main thread")
            
            # Keep the UI alive  
            logger.info("Starting UI mainloop")
            ui.root.mainloop()
        except Exception as e:
            logger.error(f"UI thread failed: {e}")
            ui_ready.set()  # Ensure main thread doesn't hang
    
    # Start UI thread as non-daemon so it keeps the process alive
    ui_thread = threading.Thread(target=_ui_thread, daemon=False, name="SamUIThread")
    ui_thread.start()
    logger.info("UI thread started")
    
    # Wait for UI to be ready and get the UI object
    logger.info("Waiting for UI to be ready...")
    if not ui_ready.wait(timeout=10):
        logger.error("UI thread failed to start within timeout")
        return None, None
    
    try:
        ui = ui_queue.get(timeout=1)
        logger.info("UI object retrieved successfully")
        # Wire shell activity feed so every subprocess Sam runs appears in the output panel
        try:
            from system.shell_broadcast import set_ui_sink
            set_ui_sink(ui)
        except Exception:
            pass
        return ui, ui_thread
    except:
        logger.error("Failed to get UI object from queue")
        return None, None


def main():
    logger.info("=== SAM STARTING ===\n")
    
    logger.info("Step 1: Initializing speech system")
    initialize_speech_system()
    
    logger.info("Step 2: Starting UI thread")
    ui, ui_thread = start_ui_in_thread()

    if ui is None:
        logger.error("Failed to start UI - exiting")
        return

    # Wire AgentMonitor → UI panel so all agent tasks appear as live task cards
    try:
        from agent.monitor import monitor as _monitor
        def _on_agent_update(task):
            try:
                if task.status == "running" and len(task.output_lines) == 0:
                    ui.add_agent_task(task.task_id, task.name[:28])
                elif task.status in ("done", "error", "cancelled"):
                    color = "green" if task.status == "done" else "red"
                    ui.update_agent_task(task.task_id, task.status, color)
                if task.output_lines:
                    ui.append_output(task.output_lines[-1], "info")
            except Exception:
                pass
        _monitor.subscribe(_on_agent_update)
        logger.info("AgentMonitor subscribed to UI panel")
    except Exception as e:
        logger.warning(f"AgentMonitor wiring failed: {e}")

    logger.info("Step 3: Starting AI thread")
    def runner():
        logger.info("AI thread starting")
        try:
            asyncio.run(ai_loop(ui))
        except Exception as e:
            logger.error(f"AI loop failed: {e}")
    
    ai_thread = threading.Thread(target=runner, daemon=True, name="SamAIThread")
    ai_thread.start()
    logger.info("AI thread started")
    
    # Start FastAPI daemon in background so the React UI (port 3142) gets all features.
    # SAM_EMBEDDED=1 tells daemon/main.py to skip its own headless ai_loop — ours is already running.
    import os as _os
    _os.environ["SAM_EMBEDDED"] = "1"

    def _start_daemon():
        try:
            import uvicorn as _uv
            _uv.run(
                "daemon.main:app",
                host="0.0.0.0",
                port=3142,
                reload=False,
                log_level="warning",
            )
        except Exception as _de:
            logger.error(f"FastAPI daemon failed to start: {_de}")

    _daemon_thread = threading.Thread(target=_start_daemon, daemon=True, name="SamDaemonThread")
    _daemon_thread.start()
    logger.info("Step 4: FastAPI daemon started in background (port 3142)")

    # Main thread runs the embedded speech WebView
    logger.info("Step 5: Starting embedded speech window (main thread)")
    try:
        run_embedded_window_loop()
    except Exception as e:
        logger.error(f"Embedded window loop failed: {e}")
    
    logger.info("Main function ending")


if __name__ == "__main__":
    main()
