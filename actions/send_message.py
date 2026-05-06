import time
from log.logger import get_logger

logger = get_logger("SEND_MESSAGE")

# Score threshold — above this the match is treated as unambiguous
_EXACT_THRESHOLD = 88


def send_message(parameters: dict, response: str | None = None, player=None, session_memory=None) -> bool:
    """
    Send a WhatsApp message to a contact via Chrome debug automation.
    Resolves the contact FIRST, announces the real matched name so the user
    can catch a wrong match before the message goes out.
    Fuzzy matches (score < _EXACT_THRESHOLD) trigger a PendingAction confirmation.
    """
    recipient = (
        (parameters or {}).get("receiver")      # LLM extracts as "receiver"
        or (parameters or {}).get("recipient")
        or (parameters or {}).get("contact")
        or (parameters or {}).get("name")
        or (parameters or {}).get("to")
        or ""
    ).strip()

    message = (
        (parameters or {}).get("message_text")  # LLM extracts as "message_text"
        or (parameters or {}).get("message")
        or (parameters or {}).get("text")
        or (parameters or {}).get("content")
        or ""
    ).strip()

    if not recipient:
        _say("Who should I send the message to?", player)
        return False

    if not message:
        _say(f"What would you like to say to {recipient}?", player)
        return False

    try:
        from automation.chrome_debug import (
            launch_chrome_debug,
            get_all_chat_names,
            find_best_chat_match,
            open_chat_by_name,
        )
        from automation.whatsapp_dom import send_message_in_open_chat

        if not launch_chrome_debug():
            _say("Chrome with WhatsApp Web isn't running. Please open WhatsApp Web first.", player)
            return False

        chat_list = get_all_chat_names()
        if not chat_list:
            _say("I couldn't find any WhatsApp chats. Make sure WhatsApp Web is open.", player)
            return False

        match, suggestions = find_best_chat_match(recipient, chat_list)
        if not match:
            if suggestions:
                names = ", ".join(s[0] for s in suggestions[:3])
                _say(f"I couldn't find {recipient}. Did you mean: {names}?", player)
            else:
                _say(f"I couldn't find a contact named {recipient}.", player)
            return False

        # Resolve the match score so we know if this was exact or fuzzy.
        # Strip emojis and punctuation for a clean name comparison — so
        # "Sugar" → "Sugar❤️" is treated as exact, not fuzzy.
        import re as _re
        _clean = lambda s: _re.sub(r'[^\w\s]', '', s, flags=_re.UNICODE).strip().lower()
        clean_query = _clean(recipient)
        clean_match = _clean(match)
        # Exact if: clean names are equal, OR query is a clean prefix of match name
        is_exact = (
            clean_match == clean_query
            or clean_match.startswith(clean_query + " ")
            or clean_match.startswith(clean_query)
        )
        if not is_exact:
            from rapidfuzz import fuzz as _fuzz
            score = _fuzz.WRatio(recipient.lower(), match.lower())
            is_exact = score >= _EXACT_THRESHOLD

        def _do_send():
            opened = open_chat_by_name(match)
            if not opened:
                _say(f"I found {match} but couldn't open the chat.", player)
                return False
            time.sleep(1.0)
            sent = send_message_in_open_chat(message)
            if sent:
                _say(f"Message sent to {match}.", player)
                logger.info(f"[send_message] Sent to {match}: {message[:80]}")
                return True
            else:
                _say(f"I opened the chat but couldn't send the message to {match}.", player)
                return False

        if is_exact:
            # High-confidence match — announce resolved name and send
            _say(f"Sending to {match}.", player)
            return _do_send()
        else:
            # Fuzzy match — confirm before sending so user can catch wrong contacts
            try:
                from conversation_state import controller, PendingAction
                controller.set_pending(PendingAction(
                    intent="send_message",
                    parameters=parameters,
                    description=f"Send to {match}: {message[:60]}",
                    callback=_do_send,
                ))
                _say(f"I found {match} — is that who you meant? Say yes to send.", player)
                return True
            except Exception:
                # Fallback: no pending system available, just announce and send
                _say(f"Sending to {match}.", player)
                return _do_send()

    except Exception as e:
        logger.error(f"[send_message] Failed: {e}")
        _say(f"Something went wrong trying to send the message: {e}", player)
        return False


def _say(text: str, player=None):
    if player:
        player.write_log(f"SAM: {text}")
    try:
        from tts import edge_speak
        edge_speak(text, player, blocking=True)
    except Exception:
        pass
