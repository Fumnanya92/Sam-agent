import time
import pyautogui
from tts import edge_speak
from conversation_state import controller, State


def open_app(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None
) -> bool:
    """
    Opens an application using Windows search.

    parameters:
        - app_name (str)

    Memory behavior:
        - Uses ONLY session memory
        - No long-term memory writes
    """

    app_name = (parameters or {}).get("app_name", "").strip()

    if not app_name and session_memory:
        app_name = session_memory.open_app or ""

    if not app_name:
        msg = "Sir, I couldn't determine which application to open."
        if player:
            player.write_log(msg)
        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)
        return False

    if response:
        if player:
            player.write_log(response)
        controller.set_state(State.SPEAKING)
        edge_speak(response, player, blocking=True)
        controller.set_state(State.IDLE)

    try:
        pyautogui.PAUSE = 0.1


        pyautogui.press("win")
        time.sleep(0.3)

        pyautogui.write(app_name, interval=0.03)
        time.sleep(0.2)

        pyautogui.press("enter")
        time.sleep(0.6)

        if session_memory:
            session_memory.set_open_app(app_name)

        return True

    except Exception as e:
        msg = f"Sir, I failed to open {app_name}."
        if player:
            player.write_log(f"{msg} ({e})")
        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)
        return False
