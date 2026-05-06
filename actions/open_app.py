import time
import pyautogui
from tts import edge_speak
from conversation_state import controller, State

# Map of spoken app names → Sam UI routes.
# If the user asks to "open" one of these, Sam navigates within its own UI
# rather than launching a Windows application.
_UI_ROUTES: dict[str, str] = {
    "dashboard": "dashboard",
    "sam dashboard": "dashboard",
    "home": "dashboard",
    "chat": "chat",
    "conversation": "chat",
    "history": "chat",
    "tasks": "tasks",
    "task": "tasks",
    "goals": "goals",
    "goal": "goals",
    "pipeline": "pipeline",
    "memory": "memory",
    "calendar": "calendar",
    "workflows": "workflows",
    "workflow": "workflows",
    "authority": "authority",
    "command": "command",
    "settings": "settings",
    "agents": "office",
    "office": "office",
    "capabilities": "capabilities",
    "skills": "skills",
    "knowledge": "knowledge",
}


def open_app(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None
) -> bool:
    """
    Opens an application using Windows search.
    If the app name matches a Sam UI page, navigates there instead.

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
        msg = "Which application did you want me to open?"
        if player:
            player.write_log(msg)
        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)
        return False

    # Check if this is a Sam UI page navigation request
    route = _UI_ROUTES.get(app_name.lower())
    if route is None:
        # Try partial match (e.g. "sam's dashboard" → "dashboard")
        for key, val in _UI_ROUTES.items():
            if key in app_name.lower():
                route = val
                break

    if route is not None:
        # Broadcast to any already-open browser tabs
        try:
            from tts import broadcast_to_web
            broadcast_to_web("navigate", {"route": route})
        except Exception:
            pass
        # Always open / focus the browser at the React UI so the user actually sees it
        try:
            import webbrowser
            webbrowser.open(f"http://localhost:3142/{route}")
        except Exception:
            pass
        msg = response or f"Opening the {route} page."
        if player:
            player.write_log(f"AI: {msg}")
        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)
        return True

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
        msg = f"I wasn't able to open {app_name}."
        if player:
            player.write_log(f"{msg} ({e})")
        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)
        return False
