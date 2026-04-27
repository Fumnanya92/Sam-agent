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
from assistant.daily_planner import generate_daily_plan
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

    # Hint shown in the transcription area while idle
    if in_conversation:
        ui.set_transcription('Listening…')
    else:
        ui.set_transcription('say "Hey Sam" to activate…')

    logger.debug("[MIC] Calling record_voice() — waiting for speech...")
    text = await asyncio.to_thread(record_voice, in_conversation)
    logger.debug(f"[MIC] record_voice() returned: '{text}'")

    ui.clear_transcription()

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
    """Return typed text immediately if queued, otherwise wait for voice input."""
    try:
        return typed_input_queue.get_nowait()
    except queue.Empty:
        pass
    return await get_voice_input(ui, in_conversation=in_conversation)


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

    # Start reminder engine now that we have a UI reference
    reminder_engine._speak = edge_speak
    reminder_engine._ui = ui
    reminder_engine.start()

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

    ui.write_log(f"SAM: {startup_msg}")
    controller.set_state(State.SPEAKING)
    await asyncio.to_thread(edge_speak, startup_msg, ui, True)
    controller.set_state(State.IDLE)

    # ── Background task: drain & speak presence suggestions every 15 s ──────
    async def _presence_speaker():
        while True:
            await asyncio.sleep(15)
            if controller.is_speaking():
                continue
            try:
                while True:
                    suggestion = presence_engine.suggestions.get_nowait()
                    msg = suggestion.get("message", "")
                    if msg:
                        play_done()
                        ui.write_log(f"Sam: {msg}")
                        controller.set_state(State.SPEAKING)
                        await asyncio.to_thread(edge_speak, msg, ui, True)
                        controller.set_state(State.IDLE)
            except queue.Empty:
                pass

    asyncio.create_task(_presence_speaker())

    while True:
        # Morning briefing check
        current_hour = datetime.now().hour
        current_date = datetime.now().date()
        
        if current_hour == 7 and not briefing_delivered_today:
            try:
                briefing = generate_morning_briefing()
                ui.write_log(f"AI: {briefing}")
                controller.set_state(State.SPEAKING)
                await asyncio.to_thread(edge_speak, briefing, ui, True)
                controller.set_state(State.IDLE)
                briefing_delivered_today = True
            except Exception as e:
                logger.error(f"Morning briefing failed: {e}")
                controller.set_state(State.IDLE)
        
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
            continue

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
            ui = SamUI(BASE_DIR / "face.png", size=(550, 550))
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
    
    # Main thread runs the embedded speech WebView
    logger.info("Step 4: Starting embedded speech window (main thread)")
    try:
        run_embedded_window_loop()
    except Exception as e:
        logger.error(f"Embedded window loop failed: {e}")
    
    logger.info("Main function ending")


if __name__ == "__main__":
    main()
