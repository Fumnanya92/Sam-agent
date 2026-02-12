import asyncio
import threading
import time

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
from llm import get_llm_output
from tts import edge_speak, stop_speaking
from ui import SamUI
from conversation_state import controller, State
import sys
from pathlib import Path

from actions.open_app import open_app
from actions.web_search import web_search
from actions.weather_report import weather_action
from actions.send_message import send_message  

from memory.memory_manager import load_memory, update_memory
from memory.temporary_memory import TemporaryMemory

interrupt_commands = ["mute", "quit", "exit", "stop"]

temp_memory = TemporaryMemory()

# use module-level controller from conversation_state

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()

async def get_voice_input():
    # Wait until Sam is not speaking
    while controller.is_speaking():
        await asyncio.sleep(0.05)

    controller.set_state(State.LISTENING)
    text = await asyncio.to_thread(record_voice)
    
    if text:
        print(f"👤 You: {text}")  # Clean console output
        
        # Additional validation to prevent phantom responses
        if len(text.strip()) < 3 or text.lower().strip() in ['some', 'some.', 'you', 'the', 'from', 'from some']:
            logger.debug(f"Filtered phantom input: '{text}'")
            return ""
        
    controller.set_state(State.IDLE)
    return text

async def ai_loop(ui: SamUI):
    while True:
        
        user_text = await get_voice_input()

        if not user_text:
            continue

        if any(cmd in user_text.lower() for cmd in interrupt_commands):
            stop_speaking()
            controller.set_state(State.IDLE)
            temp_memory.reset()
            continue

        ui.write_log(f"You: {user_text}")

        if temp_memory.get_current_question():
            param = temp_memory.get_current_question()
            temp_memory.update_parameters({param: user_text})
            temp_memory.clear_current_question()
            user_text = temp_memory.get_last_user_text()

        temp_memory.set_last_user_text(user_text)

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

        # Set THINKING state just before invoking the LLM
        controller.set_state(State.THINKING)
        try:
            llm_output = await asyncio.to_thread(
                get_llm_output,
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
        memory_update = llm_output.get("memory_update")

        if memory_update and isinstance(memory_update, dict):
            update_memory(memory_update)

        temp_memory.set_last_ai_response(response)

        if intent == "send_message":
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
                # action launched; return to IDLE while it runs
                controller.set_state(State.IDLE)

        elif intent == "open_app":
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
                # action launched; return to IDLE while it runs
                controller.set_state(State.IDLE)

        elif intent == "weather_report":
            if parameters.get("city"):
                threading.Thread(
                    target=weather_action,
                    kwargs={
                        "parameters": parameters,
                        "player": ui,
                        "session_memory": temp_memory
                    },
                    daemon=True
                ).start()
                # action launched; return to IDLE while it runs
                controller.set_state(State.IDLE)

        elif intent == "search":
            if parameters.get("query"):
                threading.Thread(
                    target=web_search,
                    kwargs={
                        "parameters": parameters,
                        "player": ui,
                        "session_memory": temp_memory
                    },
                    daemon=True
                ).start()
                # action launched; return to IDLE while it runs
                controller.set_state(State.IDLE)

        else:
            if response:
                print(f"🤖 Sam: {response}")  # Clean console output
                ui.write_log(f"AI: {response}")
                controller.set_state(State.SPEAKING)
                edge_speak(response, ui, blocking=True)
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
            ui = SamUI(BASE_DIR / "face.png", size=(900, 900))
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
