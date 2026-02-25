# automation/whatsapp_controller.py

from automation.chrome_debug import (
    get_unread_messages,
    get_all_chat_names,
    find_best_chat_match,
    open_chat_by_name,
)
from automation.whatsapp_dom import get_latest_message_from_open_chat
from llm import get_llm_output
from tts import edge_speak
from conversation_state import controller, State


class WhatsAppController:
    def __init__(self, player=None):
        self.player = player
        self.pending_reply = None
        self.pending_chat = None

    # -------------------------------------------------
    # STEP 1: List unread chats
    # -------------------------------------------------
    def list_unread(self):
        unread = get_unread_messages()

        if not unread:
            self._speak("Sir, you have no unread messages.")
            return []

        count = len(unread)
        names = [u["name"] for u in unread]

        summary = f"Sir, you have {count} chats with unread messages."
        self._speak(summary)

        for name in names[:5]:
            self._speak(f"{name} has unread messages.")

        return names

    # -------------------------------------------------
    # STEP 2: Open specific chat
    # -------------------------------------------------
    def open_chat(self, query_name: str):
        chat_list = get_all_chat_names()

        match, suggestions = find_best_chat_match(query_name, chat_list)

        if not match:
            self._speak("Sir, I found multiple similar names.")
            for s in suggestions[:3]:
                self._speak(s[0])
            return False

        opened = open_chat_by_name(match)

        if not opened:
            self._speak("Sir, I could not open that chat.")
            return False

        self.pending_chat = match
        return True

    # -------------------------------------------------
    # STEP 3: Read latest message
    # -------------------------------------------------
    def read_latest(self):
        msg = get_latest_message_from_open_chat()

        if not msg or not msg.get("text"):
            self._speak("Sir, I could not read the latest message.")
            return None

        text = msg["text"]
        sender = msg.get("sender")

        if sender:
            spoken = f"Sir, {sender} says: {text}"
        else:
            spoken = f"Sir, the message says: {text}"

        self._speak(spoken)
        return text

    # -------------------------------------------------
    # STEP 4: Generate reply (OpenAI)
    # -------------------------------------------------
    def generate_reply(self, incoming_text):
        prompt = f"""
You are a formal assistant replying on behalf of your user.

Message received:
"{incoming_text}"

Generate a concise, respectful reply.
"""

        result = get_llm_output(prompt)

        reply_text = result.get("text")

        if not reply_text:
            self._speak("Sir, I could not generate a reply.")
            return None

        self.pending_reply = reply_text

        self._speak(f"My suggested reply is: {reply_text}")
        self._speak("Shall I send this, Sir?")

        return reply_text

    # -------------------------------------------------
    # STEP 5: Handle confirmation
    # -------------------------------------------------
    def handle_confirmation(self, user_response: str):
        if not self.pending_reply:
            return False

        response = user_response.lower()

        if response in ["yes", "send it", "send", "go ahead"]:
            self._send_reply()
            return True

        if response in ["no", "cancel"]:
            self._speak("Understood, Sir. Message not sent.")
            self.pending_reply = None
            return True

        # Otherwise treat as refinement instruction
        refined = self._refine_reply(user_response)
        return refined

    # -------------------------------------------------
    # INTERNAL: Refine reply
    # -------------------------------------------------
    def _refine_reply(self, instruction):
        prompt = f"""
Original reply:
"{self.pending_reply}"

User instruction:
"{instruction}"

Rewrite accordingly.
"""

        result = get_llm_output(prompt)
        new_reply = result.get("text")

        if new_reply:
            self.pending_reply = new_reply
            self._speak(f"Updated reply: {new_reply}")
            self._speak("Shall I send this, Sir?")
            return True

        return False

    # -------------------------------------------------
    # INTERNAL: Send reply via DOM
    # -------------------------------------------------
    def _send_reply(self):
        from automation.whatsapp_dom import send_message_in_open_chat

        sent = send_message_in_open_chat(self.pending_reply)

        if sent:
            self._speak("Message sent, Sir.")
        else:
            self._speak("Sir, I failed to send the message.")

        self.pending_reply = None

    # -------------------------------------------------
    # SPEAK HELPER
    # -------------------------------------------------
    def _speak(self, text):
        if self.player:
            self.player.write_log(text)

        controller.set_state(State.SPEAKING)
        edge_speak(text, self.player, blocking=True)
        controller.set_state(State.IDLE)
