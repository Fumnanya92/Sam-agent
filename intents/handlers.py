"""
Intent handler implementations
All intent-specific logic is centralized here
"""
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from conversation_state import controller, State, PendingAction
from tts import edge_speak
from log.logger import get_logger

logger = get_logger("INTENTS")

# Prevent concurrent WhatsApp operations that cause the double-voice bug
_whatsapp_lock = threading.Lock()


def _say(text, ui):
    """Thread-safe speak helper used by action handlers."""
    ui.write_log(f"AI: {text}")
    controller.set_state(State.SPEAKING)
    edge_speak(text, ui, blocking=True)
    controller.set_state(State.IDLE)


def _auto_skill(description: str, temp_memory) -> str | None:
    """Search antigravity skills for the best match and activate it.
    Returns the activated skill name, or None if no match.
    Logs the skill name to the UI output if available.
    """
    try:
        from skills.antigravity_bridge import auto_activate_for_task
        return auto_activate_for_task(description, temp_memory)
    except Exception:
        return None


def handle_intent(intent, parameters, response, ui, temp_memory, **kwargs):
    """
    Route intent to appropriate handler
    
    Args:
        intent: The detected intent
        parameters: Parameters extracted from user input
        response: LLM response text
        ui: UI instance
        temp_memory: Temporary memory instance
        **kwargs: Additional dependencies (whatsapp_engine, whatsapp_assistant, watcher)
    """
    
    # Debug logging
    logger.debug(f"handle_intent called: intent='{intent}', has_response={response is not None}, response_len={len(response) if response else 0}")
    
    # Import actions lazily to avoid circular imports
    from actions.send_message import send_message
    from actions.open_app import open_app
    from actions.weather_report import weather_action
    from actions.web_search import web_search
    
    if intent == "send_message":
        _handle_send_message(parameters, response, ui, temp_memory)
    
    elif intent == "open_app":
        _handle_open_app(parameters, response, ui, temp_memory)
    
    elif intent == "weather_report":
        _handle_weather_report(parameters, response, ui, temp_memory)
    
    elif intent == "search":
        _handle_search(parameters, response, ui, temp_memory)
    
    elif intent == "read_messages":
        _handle_read_messages(ui, kwargs.get('whatsapp_assistant'))
    
    elif intent in ["whatsapp_summary", "check_whatsapp"]:
        _handle_whatsapp_summary(ui, kwargs.get('whatsapp_assistant'))
    
    elif intent == "whatsapp_ready":
        _handle_whatsapp_ready(ui, kwargs.get('whatsapp_assistant'))
    
    elif intent == "open_whatsapp_chat":
        _handle_open_whatsapp_chat(parameters, ui, kwargs.get('whatsapp_assistant'))
    
    elif intent == "read_whatsapp":
        _handle_read_whatsapp(ui, kwargs.get('whatsapp_assistant'))
    
    elif intent == "reply_whatsapp":
        _handle_reply_whatsapp(ui, kwargs.get('whatsapp_engine'))
    
    elif intent == "reply_to_contact":
        _handle_reply_to_contact(parameters, ui, kwargs.get('whatsapp_assistant'), kwargs.get('whatsapp_engine'))
    
    elif intent == "confirm_send":
        _handle_confirm_send(ui, kwargs.get('whatsapp_engine'))
    
    elif intent == "cancel_reply":
        _handle_cancel_reply(ui, kwargs.get('whatsapp_engine'))
    
    elif intent == "edit_reply":
        _handle_edit_reply(parameters, ui, kwargs.get('whatsapp_engine'))
    
    elif intent == "get_time":
        _handle_get_time(ui)

    elif intent == "list_processes":
        _handle_list_processes(ui)

    elif intent == "system_status":
        _handle_system_status(ui)
    
    elif intent == "kill_process":
        _handle_kill_process(parameters, ui)
    
    elif intent == "performance_mode":
        _handle_performance_mode(ui)
    
    elif intent == "auto_mode":
        _handle_auto_mode(response, ui, kwargs.get('watcher'))
    
    elif intent == "system_trend":
        _handle_system_trend(ui, kwargs.get('watcher'))
    
    elif intent == "screen_vision":
        _handle_screen_vision(ui)
    
    elif intent == "debug_screen":
        _handle_debug_screen(ui)
    
    elif intent == "vscode_mode":
        _handle_vscode_mode(ui)

    elif intent == "whatsapp_call":
        _handle_whatsapp_call(parameters, ui, kwargs.get('whatsapp_assistant'))

    # ---- NEW INTENTS ----
    elif intent == "capabilities":
        _handle_capabilities(response, ui)

    elif intent == "set_alarm":
        _handle_set_alarm(parameters, response, ui)

    elif intent == "set_reminder":
        _handle_set_reminder(parameters, response, ui, kwargs.get('reminder_engine'))

    elif intent == "list_reminders":
        _handle_list_reminders(ui, kwargs.get('reminder_engine'))

    elif intent == "cancel_reminder":
        _handle_cancel_reminder(parameters, response, ui, kwargs.get('reminder_engine'))

    elif intent == "read_clipboard":
        _handle_read_clipboard(ui)

    elif intent == "create_note":
        _handle_create_note(parameters, response, ui, temp_memory=temp_memory)

    elif intent in ("housekeeping", "organise_downloads", "organize_downloads",
                    "organize_files", "clean_temp", "archive_screenshots",
                    "housekeeping_report"):
        _handle_housekeeping(intent, ui)

    elif intent == "find_file":
        _handle_find_file(parameters, ui)

    elif intent == "open_file":
        _handle_open_file(parameters, ui)

    elif intent == "log_entry":
        _handle_log_entry(parameters, response, ui)

    elif intent == "read_email":
        _handle_read_email(ui)

    elif intent in ("media_play", "media_pause", "media_play_pause"):
        _handle_media_play_pause(parameters, ui)

    elif intent == "media_next":
        _handle_media_next(ui)

    elif intent == "media_prev":
        _handle_media_prev(ui)

    elif intent == "media_volume_up":
        _handle_media_volume_up(ui)

    elif intent == "media_volume_down":
        _handle_media_volume_down(ui)

    elif intent == "media_mute":
        _handle_media_mute(ui)

    elif intent == "set_speed":
        _handle_set_speed(parameters, response, ui)

    elif intent == "aircraft_radar":
        _handle_aircraft_radar(parameters, ui)

    elif intent == "export_conversation":
        _handle_export_conversation(ui, temp_memory)

    elif intent == "add_to_whitelist":
        _handle_add_to_whitelist(parameters, response, ui)

    elif intent == "organize_files":
        _handle_organize_files(response, ui)

    elif intent == "prepare_workspace":
        _handle_prepare_workspace(response, ui)

    elif intent == "open_project":
        _handle_open_project(parameters, ui)

    elif intent == "start_dictation":
        _handle_start_dictation(ui)

    elif intent == "list_skills":
        _handle_list_skills(ui)

    elif intent in ("switch_to_cloud", "use_cloud", "cloud_model"):
        _handle_switch_model("cloud", ui)

    elif intent in ("switch_to_local", "use_local", "local_model"):
        _handle_switch_model("local", ui)

    # ── Terminal execution ────────────────────────────────────────────────
    elif intent in ("run_tests", "run_test"):
        _handle_run_tests(ui, kwargs.get("terminal_runner"))

    elif intent in ("start_dev_server", "start_server", "run_app"):
        _handle_start_dev_server(ui, kwargs.get("terminal_runner"))

    elif intent in ("install_dependencies", "install_deps", "run_install"):
        _handle_install_dependencies(ui, kwargs.get("terminal_runner"))

    elif intent in ("run_command", "execute_command"):
        _handle_run_command(parameters, ui, kwargs.get("terminal_runner"))

    elif intent in ("confirm_terminal", "confirm_command", "run_it"):
        _handle_confirm_terminal(ui, kwargs.get("terminal_runner"))

    elif intent in ("cancel_command", "cancel_terminal"):
        _handle_cancel_command(ui, kwargs.get("terminal_runner"))

    # ── Google Workspace ───────────────────────────────────────────────────
    elif intent in ("calendar_today", "my_schedule", "check_calendar"):
        _handle_calendar_today(ui)

    elif intent == "next_meeting":
        _handle_next_meeting(ui)

    elif intent in ("send_email_workspace", "compose_email", "email_contact"):
        _handle_send_email_workspace(parameters, ui)

    elif intent == "save_test_credentials":
        _handle_save_test_credentials(parameters, ui)

    elif intent in ("stop_test", "cancel_test"):
        _handle_stop_test(ui)

    # ── Mark capabilities (lifted from Mark-XXX-main) ─────────────────────────

    elif intent == "file_manage":
        _handle_file_manage(parameters, ui)

    elif intent == "computer_settings":
        _handle_computer_settings(parameters, ui)

    elif intent == "browser_control":
        _handle_browser_control(parameters, ui)

    elif intent == "quick_command":
        _handle_quick_command(parameters, ui)

    elif intent == "computer_control":
        _handle_computer_control(parameters, ui)

    elif intent == "desktop_control":
        _handle_desktop_control(parameters, ui)

    elif intent in ("play_youtube", "youtube_summary", "youtube_trending"):
        action_map = {
            "play_youtube":    "play",
            "youtube_summary": "summarize",
            "youtube_trending": "trending",
        }
        p = dict(parameters or {})
        p.setdefault("action", action_map[intent])
        _handle_youtube_video(p, ui)

    elif intent == "find_flights":
        _handle_find_flights(parameters, ui)

    elif intent == "build_project":
        _handle_build_project(parameters, ui, temp_memory)

    elif intent == "code_helper":
        _handle_code_helper(parameters, ui, temp_memory)

    elif intent == "agent_task":
        _handle_agent_task(parameters, response, ui, temp_memory)

    elif intent == "send_notification":
        _handle_send_notification(parameters, response, ui)

    elif intent == "invoke_skill":
        _handle_invoke_skill(parameters, response, ui, temp_memory)

    # ── Confirmation gate — user says yes/no after Sam asks to proceed ────────
    elif intent in ("confirm_action", "confirm_yes", "yes", "proceed", "go_ahead", "apply_it", "do_it"):
        _handle_confirm_action(ui)

    elif intent in ("cancel_action", "cancel_no", "no", "stop_it", "dont_do_it"):
        _handle_cancel_action(ui)

    # ── Mute / Wake ───────────────────────────────────────────────────────────
    elif intent in ("silence_sam", "shut_up", "be_quiet", "stop_talking", "mute"):
        _handle_silence_sam(ui)

    elif intent in ("wake_sam", "you_can_talk", "unmute"):
        _handle_wake_sam(ui)

    # ── Meeting notes ─────────────────────────────────────────────────────────
    elif intent in ("meeting_notes_start", "take_notes", "start_notes"):
        _handle_meeting_notes_start(ui)

    elif intent in ("meeting_notes_stop", "stop_notes", "end_meeting"):
        _handle_meeting_notes_stop(ui)

    # ── Learning system ───────────────────────────────────────────────────────
    elif intent == "learn_from_youtube":
        _handle_learn_from_youtube(parameters, ui)

    elif intent in ("learn_this", "remember_this", "save_knowledge"):
        _handle_learn_this(parameters, response, ui)

    # ── Daily report ──────────────────────────────────────────────────────────
    elif intent in ("daily_report", "what_did_you_do", "session_report"):
        _handle_daily_report(ui)

    elif intent == "guide_task":
        _handle_guide_task(parameters, response, ui, temp_memory)

    elif intent == "create_goal":
        _handle_create_goal(parameters, response, ui)

    elif intent == "list_goals":
        _handle_list_goals(ui)

    elif intent == "update_goal":
        _handle_update_goal(parameters, response, ui)

    elif intent == "run_workflow":
        _handle_run_workflow(parameters, response, ui)

    elif intent == "list_workflows":
        _handle_list_workflows(ui)

    elif intent == "send_to_channel":
        _handle_send_to_channel(parameters, response, ui)

    elif intent == "personality_feedback":
        _handle_personality_feedback(parameters, response, ui)

    else:
        # Check skills registry before falling back to generic chat
        from skills.loader import skill_loader
        if skill_loader.has(intent):
            _handle_skill(intent, parameters, ui, kwargs)
            return

        # Default chat response — MUST run in a thread, never block the asyncio event loop
        logger.debug(f"Default chat handler triggered. response='{response}'")
        if response:
            logger.info(f"Speaking chat response: {response[:100]}...")
            print(f"🤖 Sam: {response}")
            ui.write_log(f"AI: {response}")
            # Set SPEAKING *before* spawning thread so get_voice_input waits correctly
            controller.set_state(State.SPEAKING)
            def _chat_action(text=response):
                try:
                    edge_speak(text, ui, blocking=True)
                except Exception as e:
                    logger.error(f"Chat TTS failed: {e}")
                finally:
                    controller.set_state(State.IDLE)
            threading.Thread(target=_chat_action, daemon=True).start()
        else:
            logger.warning("Default handler reached but response is empty/None")
            controller.set_state(State.IDLE)


# ==================== SKILL HANDLERS ====================

def _handle_skill(intent: str, parameters: dict, ui, ctx: dict):
    """Run a registered skill and speak its response."""
    def _action():
        try:
            from skills.loader import skill_loader
            result = skill_loader.run(
                intent, parameters, ui,
                reminder_engine=ctx.get("reminder_engine"),
                watcher=ctx.get("watcher"),
                terminal_runner=ctx.get("terminal_runner"),
            )
            if result:
                _say(result, ui)
            else:
                logger.warning(f"Skill '{intent}' returned no response.")
                controller.set_state(State.IDLE)
        except Exception as e:
            logger.error(f"Skill handler error for '{intent}': {e}")
            _say("I ran into a problem with that skill.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_skills(ui):
    """Tell the user what skills Sam currently has."""
    def _action():
        try:
            from skills.loader import skill_loader
            skills = skill_loader.list_skills()
            if not skills:
                _say("I don't have any skills loaded right now.", ui)
                return
            names = [s["name"].replace("_", " ") for s in skills]
            joined = ", ".join(names[:-1]) + (f", and {names[-1]}" if len(names) > 1 else names[0])
            _say(f"I have {len(skills)} skills ready: {joined}.", ui)
        except Exception as e:
            logger.error(f"List skills error: {e}")
            _say("Couldn't retrieve the skill list.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


# ==================== ACTION INTENTS ====================

def _handle_send_message(parameters, response, ui, temp_memory):
    """Handle send_message intent"""
    from actions.send_message import send_message

    temp_memory.set_pending_intent("send_message")
    temp_memory.update_parameters(parameters)

    def _action():
        if response:
            ui.write_log(f"SAM: {response}")
            controller.set_state(State.SPEAKING)
            edge_speak(response, ui, blocking=True)
        if all(temp_memory.get_parameter(p) for p in ["receiver", "message_text", "platform"]):
            send_message(
                parameters=temp_memory.get_parameters(),
                player=ui,
                session_memory=temp_memory
            )
        controller.set_state(State.IDLE)

    threading.Thread(target=_action, daemon=True).start()


def _handle_open_app(parameters, response, ui, temp_memory):
    """Handle open_app intent"""
    from actions.open_app import open_app
    
    if parameters.get("app_name"):
        threading.Thread(
            target=open_app,
            kwargs={
                "parameters": parameters,
                "response": response,
                "player": ui,
                "session_memory": temp_memory
            },
            daemon=True
        ).start()
        controller.set_state(State.IDLE)


def _handle_weather_report(parameters, response, ui, temp_memory):
    """Handle weather_report intent"""
    from actions.weather_report import weather_action

    def _action():
        if parameters.get("city"):
            if response:
                ui.write_log(f"SAM: {response}")
                controller.set_state(State.SPEAKING)
                edge_speak(response, ui, blocking=True)
            weather_action(
                parameters=parameters,
                player=ui,
                session_memory=temp_memory
            )
        controller.set_state(State.IDLE)

    threading.Thread(target=_action, daemon=True).start()


def _handle_search(parameters, response, ui, temp_memory):
    """Handle search intent"""
    from actions.web_search import web_search

    def _action():
        if parameters.get("query"):
            if response:
                ui.write_log(f"SAM: {response}")
                controller.set_state(State.SPEAKING)
                edge_speak(response, ui, blocking=True)
            web_search(
                parameters=parameters,
                player=ui,
                session_memory=temp_memory
            )
        controller.set_state(State.IDLE)

    threading.Thread(target=_action, daemon=True).start()


def _handle_read_messages(ui, whatsapp_assistant):
    """Handle read_messages intent - uses Chrome DOM via WhatsApp Assistant"""
    def read_action():
        if not _whatsapp_lock.acquire(blocking=False):
            return  # Another WhatsApp operation is already running
        try:
            whatsapp_assistant.summarize_unread(player=ui)
        except Exception as e:
            logger.error(f"Read messages failed: {e}")
            _say("Couldn't reach your messages right now.", ui)
        finally:
            _whatsapp_lock.release()
            controller.set_state(State.IDLE)

    threading.Thread(target=read_action, daemon=True).start()
    controller.set_state(State.IDLE)


# ==================== WHATSAPP INTENTS ====================

def _handle_whatsapp_summary(ui, whatsapp_assistant):
    """Handle whatsapp_summary intent"""
    def whatsapp_summary_action():
        if not _whatsapp_lock.acquire(blocking=False):
            return  # Another WhatsApp operation is already running
        try:
            whatsapp_assistant.summarize_unread(player=ui)
        except Exception as e:
            logger.error(f"WhatsApp summary failed: {e}")
            _say("Something went wrong checking WhatsApp.", ui)
        finally:
            _whatsapp_lock.release()
            controller.set_state(State.IDLE)

    threading.Thread(target=whatsapp_summary_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_whatsapp_ready(ui, whatsapp_assistant):
    """Handle whatsapp_ready intent"""
    def whatsapp_ready_action():
        try:
            whatsapp_assistant.continue_after_setup(player=ui)
        except Exception as e:
            logger.error(f"WhatsApp continue failed: {e}")
            msg = "Had trouble reconnecting to WhatsApp."
            ui.write_log(msg)
            controller.set_state(State.SPEAKING)
            edge_speak(msg, ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=whatsapp_ready_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_open_whatsapp_chat(parameters, ui, whatsapp_assistant):
    """Handle open_whatsapp_chat intent"""
    chat_name = parameters.get("chat_name") or parameters.get("contact_name")
    
    if not chat_name:
        _say("Which chat did you want to open?", ui)
        controller.set_state(State.IDLE)
    else:
        def open_chat_action():
            try:
                whatsapp_assistant.open_chat(chat_name, player=ui)
            except Exception as e:
                logger.error(f"Open WhatsApp chat failed: {e}")
                _say("Couldn't find or open that chat.", ui)
            finally:
                controller.set_state(State.IDLE)

        threading.Thread(target=open_chat_action, daemon=True).start()
        controller.set_state(State.IDLE)


def _handle_read_whatsapp(ui, whatsapp_assistant):
    """Handle read_whatsapp intent"""
    def read_whatsapp_action():
        if not _whatsapp_lock.acquire(blocking=False):
            return
        try:
            whatsapp_assistant.read_current_chat(player=ui)
        except Exception as e:
            logger.error(f"Read WhatsApp failed: {e}")
            _say("Had trouble reading that message.", ui)
        finally:
            _whatsapp_lock.release()
            controller.set_state(State.IDLE)

    threading.Thread(target=read_whatsapp_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_reply_whatsapp(ui, whatsapp_engine):
    """Handle reply_whatsapp intent"""
    def reply_whatsapp_action():
        try:
            whatsapp_engine.handle_reply_flow(player=ui)
        except Exception as e:
            logger.error(f"WhatsApp reply failed: {e}")
            msg = "Couldn't generate a reply right now."
            ui.write_log(msg)
            controller.set_state(State.SPEAKING)
            edge_speak(msg, ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=reply_whatsapp_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_reply_to_contact(parameters, ui, whatsapp_assistant, whatsapp_engine):
    """Handle reply_to_contact intent"""
    contact_name = parameters.get("contact_name")
    
    if not contact_name:
        _say("Who did you want to reply to?", ui)
        controller.set_state(State.IDLE)
    else:
        def reply_to_contact_action():
            if not _whatsapp_lock.acquire(blocking=False):
                return
            try:
                message = whatsapp_assistant.reply_to_contact(contact_name, player=ui)

                if message:
                    from automation.reply_drafter import generate_reply
                    draft = generate_reply(message.get("text", ""), message.get("sender"))

                    if draft and "error" not in draft.lower():
                        whatsapp_engine.reply_controller.set_draft(message.get("sender"), draft)

                        spoken = f"Here's a draft reply to {message.get('sender')}: {draft}. Say 'send it', 'edit', or 'cancel'."
                        _say(spoken, ui)
                        # Also open a copyable popup so Kelvin can see and edit the full text
                        ui.show_draft_popup(draft)
                    else:
                        _say("Couldn't generate a reply for that.", ui)
                else:
                    _say("Couldn't find that message to reply to.", ui)
            except Exception as e:
                logger.error(f"Reply to contact failed: {e}")
                _say("Something went wrong generating that reply.", ui)
            finally:
                _whatsapp_lock.release()
                controller.set_state(State.IDLE)

        threading.Thread(target=reply_to_contact_action, daemon=True).start()
        controller.set_state(State.IDLE)


def _handle_confirm_send(ui, whatsapp_engine):
    """Handle confirm_send intent"""
    def confirm_send_action():
        try:
            whatsapp_engine.confirm_send(player=ui)
        except Exception as e:
            logger.error(f"Confirm send failed: {e}")
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=confirm_send_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_cancel_reply(ui, whatsapp_engine):
    """Handle cancel_reply intent"""
    def cancel_reply_action():
        try:
            whatsapp_engine.cancel_reply(player=ui)
        except Exception as e:
            logger.error(f"Cancel reply failed: {e}")
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=cancel_reply_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_edit_reply(parameters, ui, whatsapp_engine):
    """Handle edit_reply intent"""
    new_text = parameters.get("new_text", "")
    
    def edit_reply_action():
        try:
            whatsapp_engine.edit_reply(new_text, player=ui)
        except Exception as e:
            logger.error(f"Edit reply failed: {e}")
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=edit_reply_action, daemon=True).start()
    controller.set_state(State.IDLE)


# ==================== SYSTEM MONITORING INTENTS ====================

def _handle_get_time(ui):
    """Return the current time and date from the system clock."""
    def time_action():
        try:
            from datetime import datetime
            now = datetime.now()
            time_str = now.strftime("%I:%M %p").lstrip("0")
            day = now.strftime("%A")
            date = now.strftime("%B %d")
            message = f"It's {time_str}, {day} {date}."
            ui.write_log(f"AI: {message}")
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"Get time failed: {e}")
            edge_speak("Couldn't read the system time.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=time_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_list_processes(ui):
    """List currently running user-visible processes."""
    def list_action():
        try:
            import psutil as _psutil
            SKIP = {
                "system idle process", "system", "registry", "smss.exe",
                "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
                "svchost.exe", "dwm.exe", "conhost.exe", "fontdrvhost.exe",
                "winlogon.exe", "spoolsv.exe",
            }
            seen: set[str] = set()
            names = []
            for proc in _psutil.process_iter(['name']):
                try:
                    n = proc.info['name']
                    if n and n.lower() not in SKIP and n.lower() not in seen:
                        seen.add(n.lower())
                        names.append(n)
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    continue
            names.sort(key=str.lower)
            if not names:
                message = "No user processes detected right now."
            else:
                listed = ", ".join(names[:15])
                more = f" — and {len(names) - 15} more" if len(names) > 15 else ""
                message = f"Running: {listed}{more}."
            ui.write_log(f"AI: {message}")
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"List processes failed: {e}")
            edge_speak("Couldn't list running processes.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=list_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_system_status(ui):
    """Handle system_status intent"""
    from system.system_monitor import get_system_report
    
    def system_status_action():
        try:
            report = get_system_report()

            message = (
                f"CPU is at {report['cpu']}%, "
                f"RAM {report['ram']['percent']}% — "
                f"{report['ram']['used_gb']} of {report['ram']['total_gb']} GB used. "
                f"Disk at {report['disk']['percent']}%, "
                f"{report['disk']['used_gb']} of {report['disk']['total_gb']} GB."
            )

            if report["battery"]:
                pct = report['battery']['percent']
                plugged = "plugged in" if report['battery']['plugged'] else "on battery"
                message += f" Battery {pct}%, {plugged}."

            if not report["online"]:
                message += " No internet connection detected."
            else:
                message += " Network is up."

            top_procs = [p for p in report['top_processes'] if p['cpu_percent'] > 0 and p['name']]
            if top_procs:
                message += " Heaviest processes: "
                message += ", ".join(f"{p['name']} at {p['cpu_percent']}%" for p in top_procs[:3]) + "."

            ui.write_log(message)
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"System status failed: {e}")
            ui.write_log("AI: Error checking system status.")
            controller.set_state(State.SPEAKING)
            edge_speak("Something went wrong checking system status.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=system_status_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_kill_process(parameters, ui):
    """Handle kill_process intent"""
    from system.process_control import kill_process_by_name

    process_name = parameters.get("process_name")

    def kill_process_action():
        try:
            if not process_name:
                message = "Which process should I terminate?"
            else:
                # User explicitly requested — bypass the auto-mode whitelist
                killed = kill_process_by_name(process_name, respect_whitelist=False)
                if killed:
                    unique = list(dict.fromkeys(killed))  # deduplicate, preserve order
                    message = f"Terminated {', '.join(unique)}."
                else:
                    message = f"No running process found matching '{process_name}'."

            ui.write_log(message)
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"Kill process failed: {e}")
            edge_speak("Couldn't terminate that process.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=kill_process_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_performance_mode(ui):
    """Handle performance_mode intent"""
    from system.process_control import get_heavy_processes
    
    def performance_mode_action():
        try:
            heavy = get_heavy_processes()
            
            if heavy and heavy[0]['cpu_percent'] > 0:
                message = f"Heaviest is {heavy[0]['name']} at {heavy[0]['cpu_percent']}% CPU."
                if len(heavy) > 1 and heavy[1]['cpu_percent'] > 0:
                    message += f" Next up: {heavy[1]['name']} at {heavy[1]['cpu_percent']}%."
            else:
                message = "System load looks normal right now."
            
            ui.write_log(message)
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"Performance mode failed: {e}")
            edge_speak("Had trouble analyzing performance.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=performance_mode_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_auto_mode(response, ui, watcher):
    """Handle auto_mode intent"""
    def auto_mode_action():
        try:
            watcher.enable_auto_mode()
            message = response or "Autonomous mode is active. I'll manage CPU load and step in if anything spikes."
            
            ui.write_log(message)
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"Auto mode failed: {e}")
            edge_speak("Couldn't enable auto mode.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=auto_mode_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_system_trend(ui, watcher):
    """Handle system_trend intent"""
    def system_trend_action():
        try:
            avg_cpu, avg_ram = watcher.get_average_load()
            
            if avg_cpu == 0 and avg_ram == 0:
                message = "Still collecting data — check back in a moment."
            else:
                message = f"Average CPU is {avg_cpu:.1f}%, RAM at {avg_ram:.1f}% over the monitoring window."
            
            ui.write_log(message)
            controller.set_state(State.SPEAKING)
            edge_speak(message, ui, blocking=True)
        except Exception as e:
            logger.error(f"System trend failed: {e}")
            edge_speak("Couldn't read system trends right now.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=system_trend_action, daemon=True).start()
    controller.set_state(State.IDLE)


# ==================== VISION INTENTS ====================

def _handle_screen_vision(ui):
    """Handle screen_vision intent"""
    def screen_vision_action():
        try:
            from system.screen_vision import analyze_screen
            
            ui.write_log("SAM: Reading the screen...")
            analysis = analyze_screen()
            
            ui.write_log(f"SAM: {analysis}")
            controller.set_state(State.SPEAKING)
            edge_speak(analysis, ui, blocking=True)
        except Exception as e:
            logger.error(f"Screen vision failed: {e}")
            edge_speak("Something went wrong analyzing the screen.", ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=screen_vision_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_debug_screen(ui):
    """Handle debug_screen intent — routes to code_helper(action=screen_debug)."""
    def debug_screen_action():
        try:
            ui.write_log("SAM: Scanning screen for errors...")
            from actions.code_helper import code_helper
            result = code_helper(
                {"action": "screen_debug"},
                player=ui,
                speak=lambda t: _say(t, ui),
            )
            if result:
                _say(result, ui)
        except Exception as e:
            logger.error(f"Debug screen failed: {e}")
            _say("Something went wrong analyzing the screen.", ui)
    threading.Thread(target=debug_screen_action, daemon=True).start()


def _handle_vscode_mode(ui):
    """Handle vscode_mode intent"""
    import os
    from system.vscode_mode import analyze_vscode_screen
    
    def vscode_mode_action():
        try:
            ui.write_log("SAM: Analyzing your code...")

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                msg = "I need an OpenAI API key to look at your code."
                ui.write_log(msg)
                controller.set_state(State.SPEAKING)
                edge_speak(msg, ui, blocking=True)
                controller.set_state(State.IDLE)
                return

            result = analyze_vscode_screen(api_key)

            ui.write_log(f"SAM: {result}")
            controller.set_state(State.SPEAKING)
            edge_speak(result, ui, blocking=True)
        except Exception as e:
            logger.error(f"VSCode mode failed: {e}")
            msg = "Had trouble analyzing your code."
            ui.write_log(msg)
            controller.set_state(State.SPEAKING)
            edge_speak(msg, ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=vscode_mode_action, daemon=True).start()
    controller.set_state(State.IDLE)


def _handle_whatsapp_call(parameters, ui, whatsapp_assistant):
    """Handle whatsapp_call intent - opens the chat and tries to click the voice call button."""
    contact_name = (parameters.get("contact_name") or parameters.get("chat_name") or "").strip()

    if not contact_name:
        _say("Who did you want to call?", ui)
        return

    def call_action():
        if not _whatsapp_lock.acquire(blocking=False):
            _say("I'm busy with something else on WhatsApp right now.", ui)
            return
        try:
            import time as _time
            from automation.chrome_debug import (
                evaluate_js, is_chrome_debug_running, ensure_chrome_debug,
                open_chat_by_name
            )

            if not is_chrome_debug_running():
                if not ensure_chrome_debug():
                    _say("I need Chrome running to call on WhatsApp. Couldn't launch it.", ui)
                    return

            # Open the contact's chat first
            success = open_chat_by_name(contact_name)
            if not success:
                _say(f"Couldn't find {contact_name}'s chat on WhatsApp.", ui)
                return

            _time.sleep(1.5)  # wait for chat to load

            # Try clicking the voice-call button via JS
            result = evaluate_js("""
                (function() {
                    const btn = document.querySelector('[data-icon="voice-call"]');
                    if (btn) { btn.closest('button')?.click() || btn.click(); return 'clicked'; }
                    const aria = document.querySelector('[aria-label="Voice call"]');
                    if (aria) { aria.click(); return 'clicked_aria'; }
                    return 'not_found';
                })()
            """)

            if result in ('clicked', 'clicked_aria'):
                _say(f"Calling {contact_name} on WhatsApp now.", ui)
            else:
                _say(
                    f"I've opened {contact_name}'s chat. "
                    "I can open chats but WhatsApp Web's call button is browser-controlled and can't always be automated — "
                    "tap the call icon there to start the call.",
                    ui
                )
        except Exception as e:
            logger.error(f"WhatsApp call failed: {e}")
            _say(f"Something went wrong trying to call {contact_name}.", ui)
        finally:
            _whatsapp_lock.release()
            controller.set_state(State.IDLE)

    threading.Thread(target=call_action, daemon=True).start()
    controller.set_state(State.IDLE)


# ==================== NEW CAPABILITY INTENTS ====================

def _handle_capabilities(response, ui):
    """Tell the user what Sam can do."""
    msg = (response or (
        "Here's what I can do: system monitoring, WhatsApp read and reply, "
        "web search, weather, open apps, screen vision and code analysis, "
        "reminders, email reading, media control, clipboard read, file notes, "
        "aircraft radar, daily planning, and more. Just ask."
    ))
    _say(msg, ui)


def _handle_set_reminder(parameters, response, ui, reminder_engine):
    """Set a reminder."""
    def _action():
        label       = parameters.get("label") or parameters.get("reminder_text") or "reminder"
        minutes     = int(parameters.get("minutes") or 0)
        hours       = int(parameters.get("hours") or 0)
        seconds     = int(parameters.get("seconds") or 0)
        fire_at_str = parameters.get("fire_at")

        if not reminder_engine:
            _say("Reminder engine isn't running right now.", ui)
            return

        if fire_at_str:
            # Parse absolute time string — try multiple formats.
            target_dt = None
            for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"):
                try:
                    parsed = datetime.strptime(fire_at_str.strip().upper(), fmt)
                    now = datetime.now()
                    target_dt = now.replace(hour=parsed.hour, minute=parsed.minute,
                                            second=0, microsecond=0)
                    break
                except ValueError:
                    continue
            if target_dt is None:
                _say(f"I couldn't parse '{fire_at_str}' as a time. Try '1:17 PM' or '13:17'.", ui)
                controller.set_state(State.IDLE)
                return
            reminder_engine.add(label, fire_at=target_dt)
            _say(response or f"Reminder set for {target_dt.strftime('%I:%M %p').lstrip('0')}.", ui)
        else:
            reminder_engine.add(label, seconds=seconds, minutes=minutes, hours=hours)
            total = hours * 60 + minutes + seconds // 60
            unit = "minute" if total == 1 else "minutes"
            _say(response or f"Reminder set. I'll remind you about '{label}' in {total or 1} {unit}.", ui)

        controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_set_alarm(parameters, response, ui):
    """Set a Windows system alarm (not just a reminder)."""
    def _action():
        from actions.windows_alarm import set_windows_alarm
        
        label       = parameters.get("label") or "alarm"
        fire_at_str = parameters.get("fire_at")

        if not fire_at_str:
            _say("I need a time for the alarm. Try 'set alarm for 2:30 PM'.", ui)
            controller.set_state(State.IDLE)
            return

        # Parse absolute time string
        target_dt = None
        for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"):
            try:
                parsed = datetime.strptime(fire_at_str.strip().upper(), fmt)
                now = datetime.now()
                target_dt = now.replace(hour=parsed.hour, minute=parsed.minute,
                                        second=0, microsecond=0)
                # If time has passed today, schedule for tomorrow
                if target_dt <= now:
                    target_dt = target_dt + timedelta(days=1)
                break
            except ValueError:
                continue

        if target_dt is None:
            _say(f"I couldn't parse '{fire_at_str}' as a time. Try '2:30 PM' or '14:30'.", ui)
            controller.set_state(State.IDLE)
            return

        # Set Windows system alarm
        success, message = set_windows_alarm(target_dt, label)
        
        if success:
            _say(response or f"Alarm set in Windows for {target_dt.strftime('%I:%M %p').lstrip('0')}. {message}", ui)
        else:
            _say(f"Couldn't set Windows alarm: {message}", ui)

        controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_reminders(ui, reminder_engine):
    """List pending reminders."""
    def _action():
        if not reminder_engine:
            _say("Reminder engine isn't available.", ui)
            return
        reminders = reminder_engine.list_reminders()
        if not reminders:
            _say("No active reminders right now.", ui)
        else:
            lines = ", ".join(f"{r['label']} at {r['fire_at']}" for r in reminders)
            _say(f"You have {len(reminders)} reminder{'s' if len(reminders)>1 else ''}: {lines}.", ui)
        controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_cancel_reminder(parameters, response, ui, reminder_engine):
    """Cancel a reminder by label or id."""
    def _action():
        if not reminder_engine:
            _say("Reminder engine isn't available.", ui)
            return
        label = parameters.get("label") or parameters.get("reminder_id") or ""
        for r in reminder_engine.list_reminders():
            if label.lower() in r["label"].lower() or label == r["id"]:
                reminder_engine.cancel(r["id"])
                _say(response or "Reminder cancelled.", ui)
                controller.set_state(State.IDLE)
                return
        _say("Couldn't find that reminder.", ui)
        controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_read_clipboard(ui):
    """Read clipboard content aloud."""
    def _action():
        try:
            from actions.clipboard_ops import read_clipboard
            text = read_clipboard()
            if text:
                preview = text[:300] + ("..." if len(text) > 300 else "")
                _say(f"Clipboard has: {preview}", ui)
            else:
                _say("Clipboard is empty or doesn't contain text.", ui)
        except Exception as e:
            logger.error(f"Clipboard read failed: {e}")
            _say("Couldn't read the clipboard.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_create_note(parameters, response, ui, temp_memory=None):
    """Create a structured note in Sam Notes and announce the path."""
    def _action():
        try:
            from actions.file_ops import create_note
            title   = parameters.get("title") or "Quick Note"
            content = parameters.get("content") or ""
            tag     = parameters.get("tag") or ""

            # If content is empty, store pending intent so the next utterance
            # is used as content (bypassing the LLM) rather than being lost.
            if not content.strip():
                if temp_memory is not None:
                    temp_memory.set_pending_intent("create_note")
                    temp_memory.update_parameters({"title": title, "tag": tag})
                _say("What should I write in the note? Go ahead.", ui)
                controller.set_state(State.IDLE)
                return

            _path, announcement = create_note(title, content, tag)
            _say(announcement, ui)
        except Exception as e:
            logger.error(f"Create note failed: {e}")
            _say("Couldn't create that note.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_open_project(parameters, ui):
    """Find a project folder by name and open it in VS Code."""
    def _action():
        try:
            folder_name = (
                parameters.get("folder_name")
                or parameters.get("project_name")
                or parameters.get("name")
                or ""
            ).strip()

            if not folder_name:
                _say("Which project folder should I open?", ui)
                return

            from pathlib import Path as _Path
            import os as _os

            def _find_dir(root: _Path, name: str, max_depth: int = 5) -> _Path | None:
                """Depth-limited folder search — avoids crawling the entire home tree."""
                if not root.exists():
                    return None
                try:
                    for dirpath, dirnames, _ in _os.walk(root):
                        depth = dirpath.replace(str(root), "").count(_os.sep)
                        if depth >= max_depth:
                            dirnames.clear()   # don't go deeper
                            continue
                        for d in dirnames:
                            if name.lower() in d.lower():
                                return _Path(dirpath) / d
                except PermissionError:
                    pass
                return None

            # Search common locations in priority order (Desktop first for speed)
            search_roots = [
                _Path.home() / "Desktop",
                _Path.home() / "Documents",
                _Path.home() / "Projects",
                _Path.home() / "dev",
                _Path.home(),
            ]
            found = None
            for root in search_roots:
                found = _find_dir(root, folder_name)
                if found:
                    break

            if not found:
                _say(
                    f"I couldn't find a folder called {folder_name}. "
                    "Can you give me the full path?",
                    ui,
                )
                return

            import subprocess as _sp

            def _find_code_exe() -> list:
                """Return the command to launch VS Code, falling back to known install paths."""
                # Common VS Code installation locations on Windows
                candidates = [
                    _Path(r"C:\Program Files\Microsoft VS Code\bin\code.cmd"),
                    _Path(r"C:\Program Files (x86)\Microsoft VS Code\bin\code.cmd"),
                    _Path.home() / r"AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
                    _Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
                    _Path.home() / r"AppData\Local\Programs\Microsoft VS Code\Code.exe",
                ]
                for c in candidates:
                    if c.exists():
                        return [str(c), str(found)]
                # Last resort — hope 'code' is on PATH
                return ["code", str(found)]

            _sp.Popen(_find_code_exe(), shell=False)
            _say(f"Opening {found.name} in VS Code.", ui)
        except Exception as e:
            logger.error(f"Open project failed: {e}")
            _say("Couldn't open that project.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_start_dictation(ui):
    """Open Notepad and enter dictation mode — next voice chunks get typed in."""
    def _action():
        try:
            import subprocess as _sp
            import time as _time
            import ctypes

            _sp.Popen(["notepad.exe"])
            _time.sleep(1.8)  # give Notepad time to open and get focus

            # Bring Notepad to front via ctypes (more reliable than pyautogui)
            user32 = ctypes.windll.user32
            for title_fragment in ("Notepad", "Untitled"):
                hwnd = user32.FindWindowW(None, None)  # start enumeration
                # Walk all top-level windows
                hwnd = user32.GetTopWindow(None)
                while hwnd:
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    if title_fragment.lower() in buf.value.lower() and "notepad" in buf.value.lower():
                        user32.SetForegroundWindow(hwnd)
                        break
                    hwnd = user32.GetWindow(hwnd, 2)  # GW_HWNDNEXT

            from shared_state import set_dictation_mode
            set_dictation_mode(True)

            _say(
                "Notepad is open. Go ahead — I'll type everything you say. "
                "Say 'done dictating' or 'stop' when you're finished.",
                ui,
            )
        except Exception as e:
            logger.error(f"Start dictation failed: {e}")
            _say("Couldn't open Notepad.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_housekeeping(intent: str, ui):
    """Run digital housekeeping actions."""
    def _action():
        try:
            from system.housekeeping import (
                organize_downloads, format_organize_result,
                archive_screenshots, clean_temp_files,
                summarise_report, get_housekeeping_report,
            )

            if intent == "housekeeping_report":
                report = get_housekeeping_report()
                _say(summarise_report(report), ui)

            elif intent in ("organise_downloads", "organize_downloads"):
                moved = organize_downloads()
                _say(format_organize_result(moved), ui)

            elif intent == "archive_screenshots":
                n = archive_screenshots()
                if n:
                    _say(f"Archived {n} screenshot{'s' if n > 1 else ''} to Pictures.", ui)
                else:
                    _say("No screenshots found on the Desktop.", ui)

            elif intent == "clean_temp":
                n, mb = clean_temp_files()
                if n:
                    _say(f"Cleared {n} old temp file{'s' if n > 1 else ''} — freed {mb} MB.", ui)
                else:
                    _say("Temp folder was already clean.", ui)

            else:
                # Generic "housekeeping" — run report and offer
                report = get_housekeeping_report()
                _say(summarise_report(report), ui)

        except Exception as e:
            logger.error(f"Housekeeping failed: {e}")
            _say("Ran into an issue while tidying up.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_find_file(parameters, ui):
    """Search for files by name."""
    def _action():
        try:
            from actions.file_ops import find_files
            name = parameters.get("filename") or parameters.get("query") or ""
            if not name:
                _say("What file are you looking for?", ui)
                return
            results = find_files(name)
            if results:
                listed = ", ".join(results[:3])
                _say(f"Found {len(results)} match{'es' if len(results)>1 else ''}: {listed}.", ui)
            else:
                _say(f"Nothing found matching '{name}'.", ui)
        except Exception as e:
            logger.error(f"Find file failed: {e}")
            _say("File search ran into an issue.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_open_file(parameters, ui):
    """Open a file or folder."""
    def _action():
        import os
        try:
            from actions.file_ops import open_path, find_files
            path = parameters.get("path") or parameters.get("filename") or ""
            if not path:
                _say("Which file did you want to open?", ui)
                return
            if not os.path.exists(path):
                results = find_files(path)
                if results:
                    path = results[0]
                else:
                    _say(f"Couldn't find '{path}'.", ui)
                    return
            open_path(path)
            _say("Opened.", ui)
        except Exception as e:
            logger.error(f"Open file failed: {e}")
            _say("Couldn't open that file.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_log_entry(parameters, response, ui):
    """Append an entry to the daily log."""
    def _action():
        try:
            from actions.file_ops import append_to_log
            entry = parameters.get("entry") or parameters.get("text") or ""
            if not entry:
                _say("What did you want to log?", ui)
                return
            append_to_log(entry)
            _say(response or "Logged.", ui)
        except Exception as e:
            logger.error(f"Log entry failed: {e}")
            _say("Couldn't write to the log.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_read_email(ui):
    """Read unread emails via IMAP."""
    def _action():
        try:
            from actions.email_reader import get_unread_emails
            emails = get_unread_emails(max_count=5)
            if not emails:
                _say("No unread emails.", ui)
                return
            if "error" in emails[0]:
                _say(emails[0]["error"], ui)
                return
            lines = [f"{i+1}. From {e['from']}: {e['subject']}" for i, e in enumerate(emails)]
            summary = f"You have {len(emails)} unread email{'s' if len(emails)>1 else ''}. " + ". ".join(lines[:3])
            _say(summary, ui)
        except Exception as e:
            logger.error(f"Email read failed: {e}")
            _say("Couldn't reach your email right now.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_play_pause(parameters, ui):
    """Play, pause, or play a search query."""
    def _action():
        try:
            from actions.media_control import play_pause, play_query
            query = parameters.get("query") or parameters.get("song") or ""
            msg = play_query(query) if query else play_pause()
            _say(msg, ui)
        except Exception as e:
            logger.error(f"Media play/pause failed: {e}")
            _say("Couldn't control media right now.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_next(ui):
    def _action():
        try:
            from actions.media_control import next_track
            _say(next_track(), ui)
        except Exception as e:
            logger.error(f"Media next failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_prev(ui):
    def _action():
        try:
            from actions.media_control import previous_track
            _say(previous_track(), ui)
        except Exception as e:
            logger.error(f"Media prev failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_volume_up(ui):
    def _action():
        try:
            from actions.media_control import volume_up
            _say(volume_up(), ui)
        except Exception as e:
            logger.error(f"Volume up failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_volume_down(ui):
    def _action():
        try:
            from actions.media_control import volume_down
            _say(volume_down(), ui)
        except Exception as e:
            logger.error(f"Volume down failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_media_mute(ui):
    def _action():
        try:
            from actions.media_control import mute_toggle
            _say(mute_toggle(), ui)
        except Exception as e:
            logger.error(f"Mute failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_set_speed(parameters, response, ui):
    """Change TTS speaking speed."""
    def _action():
        try:
            from tts import set_speed
            level = parameters.get("speed") or parameters.get("level") or "normal"
            msg = set_speed(level)
            _say(response or msg, ui)
        except Exception as e:
            logger.error(f"Set speed failed: {e}")
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_aircraft_radar(parameters, ui):
    """Report live aircraft over a region."""
    def _action():
        try:
            from actions.aircraft_report import describe_flights
            region = parameters.get("region") or parameters.get("location") or "Nigeria"
            msg = describe_flights(region)
            _say(msg, ui)
        except Exception as e:
            logger.error(f"Aircraft radar failed: {e}")
            _say("Couldn't reach the aircraft radar right now.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_export_conversation(ui, temp_memory):
    """Export the session conversation to a text file."""
    def _action():
        try:
            if not temp_memory or not getattr(temp_memory, 'session_log', None):
                _say("Nothing to export yet this session.", ui)
                return
            path = temp_memory.export_session()
            _say(f"Conversation exported and saved.", ui)
        except Exception as e:
            logger.error(f"Export conversation failed: {e}")
            _say("Couldn't export the conversation.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_add_to_whitelist(parameters, response, ui):
    """Add a process to the auto-kill whitelist."""
    def _action():
        try:
            from system.process_control import save_whitelist_entry
            name = parameters.get("process_name") or ""
            if not name:
                _say("Which process should I protect from auto-kill?", ui)
                return
            save_whitelist_entry(name)
            _say(response or f"{name} is now protected — I won't kill it automatically.", ui)
        except Exception as e:
            logger.error(f"Whitelist add failed: {e}")
            _say("Couldn't update the whitelist.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_organize_files(response, ui):
    """Organise ~/Downloads into category subfolders."""
    def _action():
        try:
            from system.housekeeping import organize_downloads, format_organize_result
            ui.write_log("Sam: Organising Downloads...")
            moved = organize_downloads()
            summary = format_organize_result(moved)
            _say(summary, ui)
        except Exception as e:
            logger.error(f"organize_files failed: {e}")
            _say("I ran into a problem organising the Downloads folder.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_prepare_workspace(response, ui):
    """Open the apps that make up the user's learned morning routine."""
    def _action():
        try:
            import subprocess
            from system.pattern_learner import PatternLearner
            learner = PatternLearner()
            routine = learner.morning_routine_apps()
            if not routine:
                _say("I haven't learned your routine yet. Give me a few more days.", ui)
                return

            _LAUNCHERS = {
                "code.exe":     "code",
                "chrome.exe":   "chrome",
                "msedge.exe":   "msedge",
                "whatsapp.exe": "whatsapp",
                "slack.exe":    "slack",
                "firefox.exe":  "firefox",
                "spotify.exe":  "spotify",
            }
            _FRIENDLY = {
                "code.exe": "VS Code", "chrome.exe": "Chrome",
                "msedge.exe": "Edge", "whatsapp.exe": "WhatsApp",
                "slack.exe": "Slack", "firefox.exe": "Firefox",
                "spotify.exe": "Spotify",
            }

            opened = []
            for app in routine[:4]:   # open up to 4 apps
                cmd = _LAUNCHERS.get(app.lower())
                if cmd:
                    try:
                        subprocess.Popen([cmd], shell=True)
                        opened.append(_FRIENDLY.get(app.lower(), app))
                    except Exception:
                        pass

            if opened:
                names = ", ".join(opened)
                _say(f"Opening {names}. Workspace ready.", ui)
            else:
                _say("Couldn't open any apps — check your app paths.", ui)
        except Exception as e:
            logger.error(f"prepare_workspace failed: {e}")
            _say("Ran into a problem preparing the workspace.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_switch_model(tier: str, ui):
    """Switch Sam's LLM between local (Ollama) and cloud (OpenAI)."""
    from llm import set_model_tier
    def _action():
        try:
            msg = set_model_tier(tier)
            _say(msg, ui)
        except Exception as e:
            logger.error(f"switch_model failed: {e}")
            _say("Something went wrong switching models.", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


# ── Terminal execution handlers ───────────────────────────────────────────────

def _handle_run_tests(ui, terminal_runner):
    """Detect test runner and schedule a test run for approval."""
    def _action():
        try:
            from actions.terminal import get_cwd
            from pathlib import Path as _Path
            cwd = get_cwd()
            name = _Path(cwd).name

            if terminal_runner is None:
                _say("Terminal execution isn't set up yet.", ui)
                return

            # Flutter project — unit tests run differently; UI test is a separate skill
            if (_Path(cwd) / "pubspec.yaml").exists():
                _say(
                    f"{name} is a Flutter project. "
                    "Say 'test my app' for UI testing, or 'run flutter test' for unit tests.",
                    ui,
                )
                return

            if (_Path(cwd) / "pytest.ini").exists() or (_Path(cwd) / "pyproject.toml").exists():
                cmd = "python -m pytest"
            elif (_Path(cwd) / "package.json").exists():
                cmd = "npm test"
            else:
                cmd = "python -m pytest"

            terminal_runner.schedule(cmd, cwd, f"{cmd} in {name}")
            _say(f"I'll run `{cmd}` in {name}. Say confirm to go ahead.", ui)
        except Exception as e:
            logger.error(f"run_tests failed: {e}")
            _say("Couldn't set up the test run.", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_start_dev_server(ui, terminal_runner):
    """Detect dev server command and schedule it for approval."""
    def _action():
        try:
            from actions.terminal import get_cwd
            from pathlib import Path as _Path
            import json as _json
            cwd = get_cwd()
            name = _Path(cwd).name

            if terminal_runner is None:
                _say("Terminal execution isn't set up yet.", ui)
                return

            # Try to read dev script from package.json
            pkg = _Path(cwd) / "package.json"
            cmd = "npm run dev"
            if pkg.exists():
                try:
                    scripts = _json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
                    if "dev" in scripts:
                        cmd = "npm run dev"
                    elif "start" in scripts:
                        cmd = "npm start"
                except Exception:
                    pass
            elif (_Path(cwd) / "manage.py").exists():
                cmd = "python manage.py runserver"

            terminal_runner.schedule(cmd, cwd, f"dev server in {name}")
            _say(f"I'll start the server with `{cmd}` in {name}. Say confirm.", ui)
        except Exception as e:
            logger.error(f"start_dev_server failed: {e}")
            _say("Couldn't set up the server start.", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_install_dependencies(ui, terminal_runner):
    """Detect package manager and schedule dependency install."""
    def _action():
        try:
            from actions.terminal import get_cwd
            from pathlib import Path as _Path
            cwd = get_cwd()
            name = _Path(cwd).name

            if terminal_runner is None:
                _say("Terminal execution isn't set up yet.", ui)
                return

            if (_Path(cwd) / "package.json").exists():
                cmd = "npm install"
            elif (_Path(cwd) / "requirements.txt").exists():
                cmd = "pip install -r requirements.txt"
            elif (_Path(cwd) / "Pipfile").exists():
                cmd = "pipenv install"
            elif (_Path(cwd) / "pubspec.yaml").exists():
                cmd = "flutter pub get"
            else:
                cmd = "npm install"

            terminal_runner.schedule(cmd, cwd, f"{cmd} in {name}")
            _say(f"I'll run `{cmd}` in {name}. Say confirm.", ui)
        except Exception as e:
            logger.error(f"install_dependencies failed: {e}")
            _say("Couldn't set up the install.", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_run_command(parameters, ui, terminal_runner):
    """Schedule an arbitrary shell command for approval."""
    def _action():
        try:
            from actions.terminal import get_cwd
            from pathlib import Path as _Path
            cwd = get_cwd()

            if terminal_runner is None:
                _say("Terminal execution isn't set up yet.", ui)
                return

            cmd = (
                parameters.get("command")
                or parameters.get("query")
                or parameters.get("text")
                or ""
            ).strip()
            if not cmd:
                _say("What command should I run?", ui)
                return

            terminal_runner.schedule(cmd, cwd, cmd)
            _say(f"I'll run `{cmd}` in {_Path(cwd).name}. Say confirm to go ahead.", ui)
        except Exception as e:
            logger.error(f"run_command failed: {e}")
            _say("Couldn't schedule that command.", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_confirm_terminal(ui, terminal_runner):
    """Execute the pending terminal command."""
    def _action():
        try:
            if terminal_runner is None or not terminal_runner.has_pending():
                _say("Nothing pending — tell me a command first.", ui)
                return
            pending = terminal_runner.get_pending()
            ui.write_log(f"SAM: Running `{pending['command']}`...")
            result = terminal_runner.execute()
            _say(result, ui)
        except Exception as e:
            logger.error(f"confirm_terminal failed: {e}")
            _say("Something went wrong running that command.", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_cancel_command(ui, terminal_runner):
    """Cancel the pending terminal command."""
    def _action():
        try:
            if terminal_runner is None:
                _say("Nothing to cancel.", ui)
                return
            msg = terminal_runner.cancel()
            _say(msg, ui)
        except Exception as e:
            logger.error(f"cancel_command failed: {e}")
            _say("Couldn't cancel.", ui)
    threading.Thread(target=_action, daemon=True).start()


# ── Google Workspace handlers ─────────────────────────────────────────────────

def _handle_calendar_today(ui):
    """Fetch and speak today's calendar events via gws CLI."""
    def _action():
        try:
            from actions.workspace import get_today_events, format_events_spoken, _is_gws_available
            if not _is_gws_available():
                _say(
                    "Google Workspace isn't set up yet. "
                    "Run: npm install -g @googleworkspace/cli, then gws auth setup", ui
                )
                return
            events = get_today_events()
            msg = format_events_spoken(events)
        except Exception as e:
            logger.error(f"calendar_today failed: {e}")
            msg = f"Couldn't reach the calendar: {e}"
        _say(msg, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_next_meeting(ui):
    """Fetch and speak the next upcoming calendar event."""
    def _action():
        try:
            from actions.workspace import get_next_event, _format_time, _is_gws_available
            if not _is_gws_available():
                _say("Google Workspace isn't set up. Run: npm install -g @googleworkspace/cli", ui)
                return
            event = get_next_event()
            if not event:
                msg = "Nothing coming up in the next 24 hours."
            else:
                start_raw = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
                time_str = _format_time(start_raw)
                summary = event.get("summary", "Untitled event")
                msg = f"Next up: {summary} at {time_str}."
        except Exception as e:
            logger.error(f"next_meeting failed: {e}")
            msg = f"Couldn't get the next meeting: {e}"
        _say(msg, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_send_email_workspace(parameters: dict, ui):
    """Compose and send (or draft) an email via gws CLI."""
    def _action():
        to      = (parameters.get("to") or parameters.get("receiver") or "").strip()
        subject = (parameters.get("subject") or "").strip()
        body    = (parameters.get("body") or parameters.get("message_text") or "").strip()

        if not to:
            _say("Who should I send the email to?", ui)
            return
        if not body:
            _say(f"What should I say in the email to {to}?", ui)
            return

        try:
            from actions.workspace import send_email
            result = send_email(to, subject or f"Message from Sam", body)
        except Exception as e:
            logger.error(f"send_email_workspace failed: {e}")
            result = f"Couldn't send the email: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_stop_test(ui):
    """Cancel any currently running flutter tester."""
    try:
        from skills.flutter_tester import cancel_test
        result = cancel_test()
    except Exception as e:
        result = f"Couldn't stop the test: {e}"
    _say(result, ui)


def _handle_save_test_credentials(parameters: dict, ui):
    """Save test credentials for a Flutter project into memory/test_credentials.json."""
    project  = (parameters.get("project") or parameters.get("app") or "").strip()
    email    = (parameters.get("email") or "").strip()
    password = (parameters.get("password") or "").strip()

    if not project:
        _say("Which project are these credentials for?", ui)
        return
    if not email or not password:
        _say(
            f"I need both an email and a password for {project}. "
            "Say something like: save Sam's credentials for Estate — email is test@example.com, password is secret123.",
            ui,
        )
        return

    try:
        from skills.flutter_tester import save_credentials
        save_credentials(project, email, password)
        _say(f"Saved. I'll use {email} when testing {project}.", ui)
    except Exception as e:
        logger.error(f"save_test_credentials failed: {e}")
        _say(f"Couldn't save the credentials: {e}", ui)


# ── Mark capabilities — lifted from Mark-XXX-main ─────────────────────────────

def _handle_file_manage(parameters: dict, ui):
    """File management: create, delete, move, copy, rename, read, write, find, list."""
    def _action():
        try:
            from actions.file_controller import file_controller
            result = file_controller(parameters, player=ui)
        except Exception as e:
            logger.error(f"file_manage failed: {e}")
            result = f"File operation failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_computer_settings(parameters: dict, ui):
    """System-level settings: volume, brightness, dark mode, WiFi, window management."""
    def _action():
        try:
            from actions.computer_settings import computer_settings
            result = computer_settings(parameters, player=ui)
        except Exception as e:
            logger.error(f"computer_settings failed: {e}")
            result = f"Settings action failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_browser_control(parameters: dict, ui):
    """Playwright browser automation: navigate, search, click, type, scroll."""
    def _action():
        try:
            from actions.browser_control import browser_control
            result = browser_control(parameters, player=ui)
        except Exception as e:
            logger.error(f"browser_control failed: {e}")
            result = f"Browser action failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_quick_command(parameters: dict, ui):
    """Auto-run safe natural-language terminal queries without confirmation."""
    def _action():
        try:
            from actions.cmd_control import cmd_control
            result = cmd_control(parameters, player=ui)
        except Exception as e:
            logger.error(f"quick_command failed: {e}")
            result = f"Command failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_computer_control(parameters: dict, ui):
    """GUI automation: mouse clicks, drags, typing, hotkeys, AI screen element finder."""
    def _action():
        try:
            from actions.computer_control import computer_control
            result = computer_control(parameters, player=ui)
        except Exception as e:
            logger.error(f"computer_control failed: {e}")
            result = f"Control action failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_desktop_control(parameters: dict, ui):
    """Desktop management: wallpaper, organize by type/date, clean, list, stats."""
    def _action():
        try:
            from actions.desktop import desktop_control
            result = desktop_control(parameters, player=ui)
        except Exception as e:
            logger.error(f"desktop_control failed: {e}")
            result = f"Desktop action failed: {e}"
        _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_youtube_video(parameters: dict, ui):
    """YouTube: play, summarize transcript, get info, trending videos."""
    def _action():
        try:
            from actions.youtube_video import youtube_video
            result = youtube_video(parameters, player=ui, speak=lambda t: _say(t, ui))
        except Exception as e:
            logger.error(f"youtube_video failed: {e}")
            result = f"YouTube action failed: {e}"
        if result:
            _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_find_flights(parameters: dict, ui):
    """Search Google Flights and speak results."""
    def _action():
        try:
            from actions.flight_finder import flight_finder
            result = flight_finder(parameters, player=ui, speak=lambda t: _say(t, ui))
        except Exception as e:
            logger.error(f"find_flights failed: {e}")
            result = f"Flight search failed: {e}"
        if result:
            _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_build_project(parameters: dict, ui, temp_memory=None):
    """AI dev agent: plan, write, run, and auto-fix a full project."""
    def _action():
        from agent.monitor import monitor
        from system.notifier import notify_task_done, notify_task_error
        desc = (parameters or {}).get("description", "project")[:60]
        # Auto-activate a matching antigravity skill and prime the LLM
        _tm = temp_memory if isinstance(temp_memory, dict) else {}
        skill_name = _auto_skill(desc, _tm)
        if skill_name and _tm.get("active_skill_content"):
            try:
                from llm import prime_skill_context
                prime_skill_context(_tm["active_skill_content"], skill_name)
                ui.append_output(f"[skill] activated: {skill_name}", "info")
            except Exception:
                pass
        task_id = monitor.register_task("build_project", desc)
        ui.add_agent_task(task_id, f"build: {desc[:24]}")
        ui.append_output(f"[build_project] {desc}", "info")
        try:
            from actions.dev_agent import dev_agent
            result = dev_agent(parameters, player=ui, speak=lambda t: _say(t, ui))
            monitor.update_task(task_id, "done")
            ui.update_agent_task(task_id, "done")
            notify_task_done("build_project", desc)
        except Exception as e:
            logger.error(f"build_project failed: {e}")
            monitor.update_task(task_id, "error", str(e))
            ui.update_agent_task(task_id, "error")
            notify_task_error("build_project", str(e))
            result = f"Build failed: {e}"
        if result:
            _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_code_helper(parameters: dict, ui, temp_memory=None):
    """AI code assistant: write, edit, explain, run, build, optimize, screen debug."""
    def _action():
        from agent.monitor import monitor
        from system.notifier import notify_task_done, notify_task_error
        action = (parameters or {}).get("action", "code")
        desc   = (parameters or {}).get("description", action)[:50]
        # Auto-activate a matching antigravity skill and prime the LLM
        _tm = temp_memory if isinstance(temp_memory, dict) else {}
        skill_name = _auto_skill(f"{action} {desc}", _tm)
        if skill_name and _tm.get("active_skill_content"):
            try:
                from llm import prime_skill_context
                prime_skill_context(_tm["active_skill_content"], skill_name)
                ui.append_output(f"[skill] activated: {skill_name}", "info")
            except Exception:
                pass
        task_id = monitor.register_task("code_helper", desc)
        ui.add_agent_task(task_id, f"code: {desc[:24]}")
        ui.append_output(f"[code_helper] {action}: {desc}", "info")
        try:
            from actions.code_helper import code_helper
            result = code_helper(parameters, player=ui, speak=lambda t: _say(t, ui))
            monitor.update_task(task_id, "done")
            ui.update_agent_task(task_id, "done")
            notify_task_done("code_helper", result[:80] if result else "")
        except Exception as e:
            logger.error(f"code_helper failed: {e}")
            monitor.update_task(task_id, "error", str(e))
            ui.update_agent_task(task_id, "error")
            notify_task_error("code_helper", str(e))
            result = f"Code helper failed: {e}"
        if result:
            _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_agent_task(parameters: dict, response: str, ui, temp_memory=None):
    """Multi-step autonomous task: AI planner + executor loop."""
    def _action():
        from agent.monitor import monitor
        from system.notifier import notify_task_done, notify_task_error
        goal = (parameters or {}).get("goal", "").strip() or response or ""
        if not goal:
            _say("What would you like me to do?", ui)
            return
        # Auto-activate a matching antigravity skill and prime the LLM
        _tm = temp_memory if isinstance(temp_memory, dict) else {}
        skill_name = _auto_skill(goal, _tm)
        if skill_name and _tm.get("active_skill_content"):
            try:
                from llm import prime_skill_context
                prime_skill_context(_tm["active_skill_content"], skill_name)
                ui.append_output(f"[skill] activated: {skill_name}", "info")
            except Exception:
                pass
        task_id = monitor.register_task("agent_task", goal[:60])
        ui.add_agent_task(task_id, "agent_task")
        ui.append_output(f"[agent_task] {goal}", "info")
        try:
            from agent.executor import AgentExecutor
            executor = AgentExecutor()
            result   = executor.execute(goal, speak=lambda t: _say(t, ui))
            monitor.update_task(task_id, "done")
            ui.update_agent_task(task_id, "done")
            notify_task_done("agent_task", result[:80] if result else "")
        except Exception as e:
            logger.error(f"agent_task failed: {e}")
            monitor.update_task(task_id, "error", str(e))
            ui.update_agent_task(task_id, "error")
            notify_task_error("agent_task", str(e))
            result = f"Task execution failed: {e}"
        if result:
            _say(result, ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_send_notification(parameters: dict, response: str, ui):
    """Send a Windows toast notification on Sam's behalf."""
    def _action():
        from system.notifier import notify
        title = (parameters or {}).get("title", "Sam")
        body  = (parameters or {}).get("body", response or "")
        notify(title, body)
        _say(f"Notification sent: {title}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_invoke_skill(parameters: dict, response: str, ui, temp_memory):
    """Activate an antigravity skill for the current session."""
    def _action():
        try:
            from skills.antigravity_bridge import activate_skill, search_skills, total_skills
            skill_name = (parameters or {}).get("skill_name", "").strip()
            if not skill_name:
                # No name given — list options
                count = total_skills()
                _say(f"I have {count} skills available. Which one would you like? Try saying 'use the architecture skill' or 'activate debugging mode'.", ui)
                return
            activated = activate_skill(skill_name, temp_memory)
            if activated:
                _say(f"Activating {activated} mode. I'll think through this with that lens.", ui)
                ui.append_output(f"[skill] Activated: {activated}", "ok")
            else:
                # Search for close matches
                matches = search_skills(skill_name, max_results=3)
                if matches:
                    names = ", ".join(m["name"] for m in matches)
                    _say(f"I couldn't find '{skill_name}' exactly. Did you mean one of these? {names}", ui)
                else:
                    _say(f"No skill matching '{skill_name}' found. I have over a thousand skills — try a different keyword.", ui)
        except Exception as e:
            logger.error(f"invoke_skill failed: {e}")
            _say("Something went wrong loading that skill.", ui)
    threading.Thread(target=_action, daemon=True).start()


# ==================== PENDING ACTION CONFIRMATION ====================

def _handle_confirm_action(ui):
    """User said 'yes' or 'proceed' — execute the stored pending action."""
    pending = controller.get_pending()
    if pending is None:
        # No pending action — treat as generic yes
        controller.set_state(State.IDLE)
        return
    controller.clear_pending()

    def _action(cb=pending.callback, desc=pending.description):
        try:
            ui.write_log(f"AI: Proceeding — {desc}")
            cb()
        except Exception as e:
            logger.error(f"Pending action callback failed: {e}")
            _say(f"Something went wrong: {e}", ui)
        finally:
            controller.set_state(State.IDLE)
    threading.Thread(target=_action, daemon=True).start()


def _handle_cancel_action(ui):
    """User said 'no' or 'cancel' — discard the stored pending action."""
    pending = controller.get_pending()
    if pending:
        controller.clear_pending()
        def _action():
            _say("Alright, cancelled.", ui)
        threading.Thread(target=_action, daemon=True).start()
    else:
        controller.set_state(State.IDLE)


# ==================== MUTE / WAKE ====================

def _handle_silence_sam(ui):
    """Mute Sam's voice — he listens but won't speak."""
    def _action():
        controller.set_muted(True)
        # Flush any pending buffer
        controller.clear_pending()
        from tts import stop_speaking
        stop_speaking()
        ui.write_log("AI: [muted — say 'hey Sam' to wake me]")
    threading.Thread(target=_action, daemon=True).start()


def _handle_wake_sam(ui):
    """Unmute Sam — he can speak again."""
    def _action():
        controller.set_muted(False)
        _say("I'm here.", ui)
    threading.Thread(target=_action, daemon=True).start()


# ==================== MEETING NOTES ====================

def _handle_meeting_notes_start(ui):
    """Enter meeting mode — Sam silences himself but listens and can take notes."""
    import os
    from pathlib import Path
    notes_dir = Path("notes")
    notes_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    notes_file = notes_dir / f"meeting-{today}.md"

    def _action():
        controller.set_mode("meeting")
        from system.notifier import notify
        notify("Sam", f"Meeting mode on. Notes → {notes_file}")
        ui.write_log(f"AI: Meeting mode on. I'm listening silently. Notes → {notes_file}")
        ui.append_output(f"[meeting] Notes file: {notes_file}", "info")
    threading.Thread(target=_action, daemon=True).start()


def _handle_meeting_notes_stop(ui):
    """Exit meeting mode — Sam speaks again."""
    def _action():
        controller.set_mode("normal")
        _say("Meeting mode off. I can talk again.", ui)
    threading.Thread(target=_action, daemon=True).start()


# ==================== LEARNING SYSTEM ====================

def _handle_learn_from_youtube(parameters: dict, ui):
    """Extract knowledge from a YouTube video transcript and store in memory."""
    def _action():
        from agent.monitor import monitor
        url = (parameters or {}).get("url", "").strip()
        if not url:
            _say("What YouTube URL should I learn from?", ui)
            return
        task_id = monitor.register_task("learn_youtube", url[:50])
        ui.add_agent_task(task_id, "learn_youtube")
        ui.append_output(f"[learning] Fetching transcript: {url}", "info")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import re
            # Extract video ID from URL
            vid_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
            if not vid_match:
                _say("I couldn't parse that YouTube URL.", ui)
                monitor.update_task(task_id, "error", "bad URL")
                return
            video_id = vid_match.group(1)
            # New instance-based API (jdepoix/youtube-transcript-api)
            fetched = YouTubeTranscriptApi().fetch(video_id)
            transcript_text = " ".join(s.text for s in fetched)
            if len(transcript_text) > 6000:
                transcript_text = transcript_text[:6000]
            # Ask LLM to extract knowledge
            from agent.llm_bridge import agent_llm_call
            extraction = agent_llm_call(
                system_prompt="Extract key knowledge, concepts, and insights from this transcript. Format as a concise markdown summary with topic headings and bullet points. Max 400 words.",
                user_prompt=transcript_text,
                require_json=False
            )
            if not extraction:
                extraction = transcript_text[:500]
            # Save to memory
            from memory.memory_manager import update_memory
            topic = f"youtube_{video_id}"
            update_memory({"knowledge": {topic: extraction}})
            monitor.update_task(task_id, "done")
            ui.append_output(f"[learning] Saved knowledge under '{topic}'", "ok")
            _say(f"Done. I've extracted and saved the key knowledge from that video.", ui)
        except Exception as e:
            logger.error(f"learn_from_youtube failed: {e}")
            monitor.update_task(task_id, "error", str(e))
            _say(f"Couldn't get the transcript. {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_learn_this(parameters: dict, response: str, ui):
    """Manually teach Sam a piece of knowledge."""
    def _action():
        knowledge = (parameters or {}).get("knowledge", "").strip() or response or ""
        topic     = (parameters or {}).get("topic", "").strip()
        if not knowledge:
            _say("What should I learn? Say 'Sam, learn this:' followed by what you want me to know.", ui)
            return
        if not topic:
            # Auto-extract a topic from the first few words
            topic = "_".join(knowledge.split()[:4]).lower().replace(",", "").replace(".", "")
        try:
            from memory.memory_manager import update_memory
            update_memory({"knowledge": {topic: knowledge}})
            ui.append_output(f"[learning] Saved: '{topic}' → {knowledge[:80]}", "ok")
            _say(f"Got it. Saved under '{topic.replace('_', ' ')}'.", ui)
        except Exception as e:
            logger.error(f"learn_this failed: {e}")
            _say("Couldn't save that to memory.", ui)
    threading.Thread(target=_action, daemon=True).start()


# ==================== DAILY REPORT ====================

def _handle_daily_report(ui):
    """Generate and save today's session report."""
    def _action():
        try:
            from system.session_logger import session_logger
            from system.report_writer import write_daily_report
            log = session_logger.get_today_log()
            if not log:
                _say("Nothing logged yet today. I'll have more to report after we've done some work.", ui)
                return
            path = write_daily_report(log)
            ui.append_output(f"[report] Saved → {path}", "ok")
            _say(f"Daily report saved. You can find it at {path}. Want me to read the summary?", ui)
        except Exception as e:
            logger.error(f"daily_report failed: {e}")
            _say(f"Couldn't generate the report: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# GUIDED TASK (CO-PILOT)
# ══════════════════════════════════════════════════════════════════════════════

def _handle_guide_task(parameters: dict, response: str, ui, temp_memory):
    """
    Initial guide_task trigger.
    Generates a step plan, stores it, and offers to guide or do autonomously.
    Subsequent turns handled by _handle_guided_step_turn via main.py bypass.
    """
    def _action():
        try:
            task = (parameters or {}).get("task", "").strip()
            if not task:
                _say("What task would you like me to guide you through?", ui)
                return

            _say("Give me a second to plan that out.", ui)

            from actions.guided_task import generate_task_steps
            import json as _json

            steps = generate_task_steps(task)
            if not steps:
                _say("I couldn't build a plan for that. Can you describe it differently?", ui)
                return

            total = len(steps)
            temp_memory.update_parameters({
                "task_description": task,
                "steps": _json.dumps(steps),
                "total_steps": total,
                "current_step": 0,
                "failed_attempts": 0,
                "processing": False,
            })
            temp_memory.set_pending_intent("guided_task")

            _say(
                f"I've got a {total}-step plan ready for {task}. "
                f"Step 1: {steps[0]}. "
                f"Tell me when you're done with each step and I'll give you the next one. "
                f"Or say 'sam do it' and I'll take over.",
                ui,
            )

        except Exception as e:
            logger.error(f"guide_task failed: {e}")
            _say("Couldn't set up the guided session — check the API connection.", ui)
        finally:
            controller.set_state(State.IDLE)

    threading.Thread(target=_action, daemon=True).start()


def _handle_guided_step_turn(user_text: str, ui, temp_memory):
    """
    Called from main.py on every voice turn while pending_intent == 'guided_task'.

    Philosophy: TRUST FIRST.
      - User says "done" / "ok" / "yeah" -> advance immediately. No vision quiz.
      - User says "can you check" -> do vision verify once, silently.
      - User says "do it" / "sam take over" -> autonomous screen click.
      - Unclear input -> remind user of current step.

    Processing guard prevents parallel threads racing on temp_memory.
    """
    _ABORT_WORDS = {
        "stop", "cancel", "abort", "quit", "exit",
        "never mind", "forget it", "stop guiding",
        "stop the guide", "end guide", "stop co-pilot",
    }
    _TRUST_SIGNALS = {
        "done", "next", "ok", "okay", "yeah", "yes", "yep",
        "i did it", "i've done it", "did it", "finished", "complete", "completed",
        "move on", "proceed", "continue", "advance", "ready", "got it",
        "skip", "checked", "its done", "it's done", "done that", "that's done",
        "all good", "all done",
    }
    _VERIFY_SIGNALS = {
        "check", "verify", "confirm", "can you check", "look at my screen",
        "see my screen", "what do you see", "does it look right", "take a look",
        "check my screen", "are you sure", "make sure",
    }
    _DO_IT_PHRASES = {
        "you do it", "sam do it", "do it yourself", "handle it", "take over",
        "you handle it", "do it for me", "you do this", "take control",
        "click it", "you click", "click for me", "do the click",
        "can you click", "please click", "click that", "click the button",
    }

    def _action():
        import json as _json

        u_lower = user_text.strip().lower()

        # ── ABORT always wins — runs BEFORE processing guard so "stop"
        # is never silently swallowed while another step is mid-flight.
        if any(w in u_lower for w in _ABORT_WORDS):
            temp_memory.reset()
            _say("Guided session stopped. Back to normal.", ui)
            return

        params = temp_memory.get_parameters()

        # Processing guard - prevent parallel threads
        if params.get("processing"):
            return
        temp_memory.update_parameters({"processing": True})

        try:
            steps            = _json.loads(params.get("steps", "[]"))
            current_step     = int(params.get("current_step", 0))
            total_steps      = int(params.get("total_steps", len(steps)))
            task_description = params.get("task_description", "the task")

            # Guard: stale/cleared session
            if not steps or current_step >= total_steps:
                temp_memory.reset()
                _say("That guided session already finished.", ui)
                return

            is_trust  = any(s in u_lower for s in _TRUST_SIGNALS)
            is_verify = any(s in u_lower for s in _VERIFY_SIGNALS)
            is_do_it  = any(p in u_lower for p in _DO_IT_PHRASES)

            # 2. Autonomous takeover
            if is_do_it:
                _say("On it.", ui)
                from actions.computer_control import computer_control as _cc
                result = _cc(
                    {"action": "screen_click", "description": steps[current_step]},
                    player=ui,
                )
                if "NOT_FOUND" in str(result).upper():
                    _say(
                        "I couldn't find that element on screen. "
                        "Try it yourself and say done when ready.", ui
                    )
                else:
                    _advance_step(current_step, total_steps, steps,
                                  task_description, temp_memory, ui,
                                  prefix="Done. ")
                return

            # 3. TRUST FIRST - advance immediately on natural completion signal
            if is_trust and not is_verify:
                _advance_step(current_step, total_steps, steps,
                              task_description, temp_memory, ui)
                return

            # 4. Vision verify - only when user explicitly asks
            if is_verify:
                from system.screen_vision import capture_screen_base64
                from actions.guided_task import verify_step_completion

                image_b64 = capture_screen_base64()
                is_done, feedback = verify_step_completion(
                    step_text=steps[current_step],
                    step_num=current_step + 1,
                    total_steps=total_steps,
                    image_b64=image_b64,
                )
                if is_done:
                    _advance_step(current_step, total_steps, steps,
                                  task_description, temp_memory, ui,
                                  prefix="Looks good, confirmed. ")
                else:
                    hint = (feedback[:80].strip() + ".") if feedback else ""
                    _say(
                        f"Not quite yet. {hint} "
                        f"Step {current_step + 1}: {steps[current_step]}. "
                        f"Say done when you're ready to move on.", ui
                    )
                return

            # 5. Unclear input - remind user
            _say(
                f"We're on step {current_step + 1} of {total_steps}: "
                f"{steps[current_step]}. "
                f"Say 'do it' and I'll handle it, say done when you've finished, "
                f"or say stop to exit.",
                ui,
            )

        except Exception as e:
            logger.error(f"_handle_guided_step_turn failed: {e}", exc_info=True)
            _say("Something went wrong. Say stop to exit or done to continue.", ui)
        finally:
            temp_memory.update_parameters({"processing": False})
            controller.set_state(State.IDLE)

    threading.Thread(target=_action, daemon=True).start()


def _advance_step(
    current_step: int,
    total_steps: int,
    steps: list,
    task_description: str,
    temp_memory,
    ui,
    prefix: str = "",
):
    """Advance to the next guided step, or declare completion."""
    new_step = current_step + 1
    if new_step >= total_steps:
        temp_memory.reset()
        _say(
            f"{prefix}That's all {total_steps} steps done. "
            f"{task_description} is complete. Great work!", ui
        )
    else:
        temp_memory.update_parameters({
            "current_step": new_step,
            "failed_attempts": 0,
            "processing": False,
        })
        _say(
            f"{prefix}Step {new_step + 1} of {total_steps}: {steps[new_step]}. "
            f"Say 'do it' and I'll handle it, or do it yourself and say done.", ui
        )


# ── Goals ─────────────────────────────────────────────────────────────────────

def _handle_create_goal(parameters: dict, response: str, ui):
    """Create a new tracked goal in the SQLite vault."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        title = (parameters or {}).get("title", "").strip() or response or ""
        if not title:
            _say("What's the goal you'd like to track?", ui)
            return
        level = (parameters or {}).get("level", "task")
        time_horizon = (parameters or {}).get("time_horizon", "weekly")
        deadline = (parameters or {}).get("deadline")
        try:
            tracker = GoalTracker()
            goal_id = asyncio.run(tracker.create_goal(
                title=title,
                level=level,
                time_horizon=time_horizon,
                deadline=deadline,
            ))
            _say(f"Goal set: {title}. I'll track it as a {time_horizon} {level}.", ui)
            ui.append_output(f"[goal created] id={goal_id} title={title}", "info")
        except Exception as e:
            logger.error(f"create_goal failed: {e}")
            _say(f"Couldn't create the goal: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_goals(ui):
    """List active goals with health scores."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        try:
            tracker = GoalTracker()
            goals = asyncio.run(tracker.list_goals(status="active"))
            if not goals:
                _say("No active goals right now. Say 'set a goal' to add one.", ui)
                return
            lines = []
            for g in goals:
                health = g.get("health", "unknown")
                score = g.get("score", 0.0)
                title = g.get("title", "Untitled")
                lines.append(f"• {title} — {int(float(score) * 100)}% ({health})")
            summary = "\n".join(lines)
            _say(f"Here are your active goals:\n{summary}", ui)
            ui.append_output(summary, "info")
        except Exception as e:
            logger.error(f"list_goals failed: {e}")
            _say(f"Couldn't load goals: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_update_goal(parameters: dict, response: str, ui):
    """Update a goal's progress score."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        title = (parameters or {}).get("title", "").strip()
        raw_score = (parameters or {}).get("score")
        note = (parameters or {}).get("note", "")
        if raw_score is None:
            _say("What's the current progress? Give me a number from 0 to 100.", ui)
            return
        try:
            score = float(raw_score)
            if score > 1.0:
                score = score / 100.0
            score = max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            _say("I need a number for the progress, like 60 or 0.6.", ui)
            return
        try:
            tracker = GoalTracker()
            goals = asyncio.run(tracker.list_goals(status="active"))
            match = next((g for g in goals if title.lower() in g.get("title", "").lower()), None) if title else (goals[0] if goals else None)
            if not match:
                _say(f"Couldn't find an active goal{f' matching {title!r}' if title else ''}.", ui)
                return
            asyncio.run(tracker.update_score(match["id"], score, note))
            _say(f"Updated '{match['title']}' to {int(score * 100)}% complete.", ui)
        except Exception as e:
            logger.error(f"update_goal failed: {e}")
            _say(f"Couldn't update the goal: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


# ── Workflows ─────────────────────────────────────────────────────────────────

def _handle_run_workflow(parameters: dict, response: str, ui):
    """Run a named workflow from the vault."""
    def _action():
        import asyncio
        from workflows.engine import WorkflowEngine
        name = (parameters or {}).get("name", "").strip() or response or ""
        if not name:
            _say("Which workflow should I run? Say the name.", ui)
            return
        try:
            engine = WorkflowEngine()
            workflows = asyncio.run(engine.list_workflows())
            match = next((w for w in workflows if name.lower() in w.get("name", "").lower()), None)
            if not match:
                available = ", ".join(w.get("name", "") for w in workflows) or "none configured"
                _say(f"No workflow matching '{name}'. Available: {available}.", ui)
                return
            _say(f"Running workflow: {match['name']}.", ui)
            run = asyncio.run(engine.run_workflow(match["id"]))
            if run.status == "completed":
                _say(f"Workflow '{match['name']}' completed.", ui)
            else:
                _say(f"Workflow '{match['name']}' ended with status: {run.status}.", ui)
            ui.append_output(f"[workflow] {match['name']}: {run.status} — {run.error or 'ok'}", "info")
        except Exception as e:
            logger.error(f"run_workflow failed: {e}")
            _say(f"Workflow failed: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_workflows(ui):
    """List all configured workflows."""
    def _action():
        import asyncio
        from workflows.engine import WorkflowEngine
        try:
            engine = WorkflowEngine()
            workflows = asyncio.run(engine.list_workflows())
            if not workflows:
                _say("No workflows configured yet. You can create them in the dashboard.", ui)
                return
            names = "\n".join(f"• {w.get('name', 'Unnamed')}" for w in workflows)
            _say(f"Here are your workflows:\n{names}", ui)
        except Exception as e:
            logger.error(f"list_workflows failed: {e}")
            _say(f"Couldn't load workflows: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


# ── Comms channels ────────────────────────────────────────────────────────────

def _handle_send_to_channel(parameters: dict, response: str, ui):
    """Send a message to Discord or Telegram."""
    def _action():
        import asyncio
        import os
        channel = (parameters or {}).get("channel", "").lower().strip()
        message = (parameters or {}).get("message", "").strip() or response or ""
        if not message:
            _say("What message should I send?", ui)
            return
        if not channel:
            _say("Which channel — Discord or Telegram?", ui)
            return

        if channel == "telegram":
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if not token or not chat_id:
                _say("Telegram isn't configured yet. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your environment.", ui)
                return
            try:
                from comms.channels.telegram import TelegramAdapter
                adapter = TelegramAdapter(token=token)
                asyncio.run(adapter.send_message(chat_id, message))
                _say("Sent to Telegram.", ui)
            except Exception as e:
                logger.error(f"telegram send failed: {e}")
                _say(f"Telegram send failed: {e}", ui)

        elif channel == "discord":
            token = os.getenv("DISCORD_BOT_TOKEN", "")
            channel_id = os.getenv("DISCORD_CHANNEL_ID", "")
            if not token or not channel_id:
                _say("Discord isn't configured yet. Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID in your environment.", ui)
                return
            try:
                from comms.channels.discord import DiscordAdapter
                adapter = DiscordAdapter(token=token)
                asyncio.run(adapter.send_message(channel_id, message))
                _say("Sent to Discord.", ui)
            except Exception as e:
                logger.error(f"discord send failed: {e}")
                _say(f"Discord send failed: {e}", ui)

        else:
            _say(f"I don't know the channel '{channel}'. I support Discord and Telegram.", ui)

    threading.Thread(target=_action, daemon=True).start()


# ── Personality ───────────────────────────────────────────────────────────────

def _handle_personality_feedback(parameters: dict, response: str, ui):
    """Record user style feedback into the personality learner."""
    def _action():
        import asyncio
        from personality.model import PersonalityLearner
        feedback = (parameters or {}).get("feedback", "").strip() or response or ""
        signal = (parameters or {}).get("signal", "negative")
        topic = feedback[:80] if feedback else "style"
        try:
            learner = PersonalityLearner()
            asyncio.run(learner.record_feedback(positive=(signal == "positive")))
            if signal == "positive":
                _say("Good to know, I'll keep doing that.", ui)
            else:
                _say("Got it, I'll adjust.", ui)
        except Exception as e:
            logger.error(f"personality_feedback failed: {e}")
            _say("Noted.", ui)
    threading.Thread(target=_action, daemon=True).start()

