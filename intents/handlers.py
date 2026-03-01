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
    print(f"🤖 Sam: {text}")
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

    else:
        # Default chat response
        logger.debug(f"Default chat handler triggered. response='{response}'")
        if response:
            logger.info(f"Speaking chat response: {response[:100]}...")
            print(f"🤖 Sam: {response}")
            ui.write_log(f"AI: {response}")
            controller.set_state(State.SPEAKING)
            edge_speak(response, ui, blocking=True)
            controller.set_state(State.IDLE)
        else:
            logger.warning("Default handler reached but response is empty/None")


# ==================== ACTION INTENTS ====================

def _handle_send_message(parameters, response, ui, temp_memory):
    """Handle send_message intent"""
    from actions.send_message import send_message
    
    # Speak LLM response as confirmation first
    if response:
        ui.write_log(f"SAM: {response}")
        controller.set_state(State.SPEAKING)
        edge_speak(response, ui, blocking=True)
        controller.set_state(State.IDLE)
    
    temp_memory.set_pending_intent("send_message")
    temp_memory.update_parameters(parameters)

    if all(temp_memory.get_parameter(p) for p in ["receiver", "message_text", "platform"]):
        threading.Thread(
            target=send_message,
            kwargs={
                "parameters": temp_memory.get_parameters(),
                "player": ui,
                "session_memory": temp_memory
            },
            daemon=True
        ).start()
        controller.set_state(State.IDLE)


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
    
    if parameters.get("city"):
        # Speak LLM response before opening browser
        if response:
            ui.write_log(f"SAM: {response}")
            controller.set_state(State.SPEAKING)
            edge_speak(response, ui, blocking=True)
            controller.set_state(State.IDLE)
        threading.Thread(
            target=weather_action,
            kwargs={
                "parameters": parameters,
                "player": ui,
                "session_memory": temp_memory
            },
            daemon=True
        ).start()
        controller.set_state(State.IDLE)


def _handle_search(parameters, response, ui, temp_memory):
    """Handle search intent"""
    from actions.web_search import web_search
    
    if parameters.get("query"):
        # Speak LLM response before searching
        if response:
            ui.write_log(f"SAM: {response}")
            controller.set_state(State.SPEAKING)
            edge_speak(response, ui, blocking=True)
            controller.set_state(State.IDLE)
        threading.Thread(
            target=web_search,
            kwargs={
                "parameters": parameters,
                "player": ui,
                "session_memory": temp_memory
            },
            daemon=True
        ).start()
        controller.set_state(State.IDLE)


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
                killed = kill_process_by_name(process_name)
                if killed:
                    message = f"Terminated {', '.join(killed)}."
                else:
                    message = f"No running process found named {process_name}."
            
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
