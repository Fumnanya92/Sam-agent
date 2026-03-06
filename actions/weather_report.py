import webbrowser
from urllib.parse import quote_plus
from tts import edge_speak
from conversation_state import controller, State


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None
):
    """
    Weather report action.
    Opens a Google weather search and gives a short spoken confirmation.
    """

    city = parameters.get("city")
    time = parameters.get("time")
    if not city or not isinstance(city, str):
        msg = "Which city did you want the weather for?"
        _speak_and_log(msg, player)
        return msg

    city = city.strip()

    if not time or not isinstance(time, str):
        time = "today"
    else:
        time = time.strip()

    search_query = f"weather in {city} {time}"
    encoded_query = quote_plus(search_query)
    url = f"https://www.google.com/search?q={encoded_query}"

    try:
        webbrowser.open(url)
    except Exception:
        msg = f"Couldn't open the browser for the weather report."
        _speak_and_log(msg, player)
        return msg

    # Handler already spoke the LLM confirmation — no duplicate speak here
    msg = f"Showing weather for {city}, {time}."

    if session_memory:
        try:
            session_memory.set_last_search(
                query=search_query,
                response=msg
            )
        except Exception:
            pass  

    return msg


def _speak_and_log(message: str, player=None):
    """Helper: log + TTS safely"""
    if player:
        try:
            player.write_log(f"SAM: {message}")
        except Exception:
            pass
    try:
        controller.set_state(State.SPEAKING)
        edge_speak(message, player, blocking=True)
    except Exception:
        pass
    finally:
        try:
            controller.set_state(State.IDLE)
        except Exception:
            pass
