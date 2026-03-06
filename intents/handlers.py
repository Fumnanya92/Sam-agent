"""
Intent handler implementations
All intent-specific logic is centralized here
"""
import threading
from conversation_state import controller, State
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
    """Handle debug_screen intent"""
    import os
    from system.screen_vision import analyze_screen_for_errors
    
    def debug_screen_action():
        try:
            ui.write_log("SAM: Scanning screen for errors...")

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                msg = "I need an OpenAI API key to analyze the screen."
                ui.write_log(msg)
                controller.set_state(State.SPEAKING)
                edge_speak(msg, ui, blocking=True)
                controller.set_state(State.IDLE)
                return

            result = analyze_screen_for_errors(api_key)

            ui.write_log(f"SAM: {result}")
            controller.set_state(State.SPEAKING)
            edge_speak(result, ui, blocking=True)
        except Exception as e:
            logger.error(f"Debug screen failed: {e}")
            msg = "Something went wrong analyzing the screen."
            ui.write_log(msg)
            controller.set_state(State.SPEAKING)
            edge_speak(msg, ui, blocking=True)
        finally:
            controller.set_state(State.IDLE)
    
    threading.Thread(target=debug_screen_action, daemon=True).start()
    controller.set_state(State.IDLE)


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
        label   = parameters.get("label") or parameters.get("reminder_text") or "reminder"
        minutes = int(parameters.get("minutes") or 0)
        hours   = int(parameters.get("hours") or 0)
        seconds = int(parameters.get("seconds") or 0)
        if not reminder_engine:
            _say("Reminder engine isn't running right now.", ui)
            return
        reminder_engine.add(label, seconds=seconds, minutes=minutes, hours=hours)
        total = hours * 60 + minutes + seconds // 60
        unit = "minute" if total == 1 else "minutes"
        _say(response or f"Reminder set. I'll remind you about '{label}' in {total or 1} {unit}.", ui)
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
