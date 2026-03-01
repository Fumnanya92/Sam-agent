from automation.chrome_debug import (
    get_unread_messages,
    get_all_chat_names,
    find_best_chat_match,
    open_chat_by_name,
    is_chrome_debug_running,
    ensure_chrome_debug,
    get_whatsapp_tab,
)
from automation.whatsapp_dom import get_latest_message_from_open_chat
from tts import edge_speak
from conversation_state import controller, State
import time


class WhatsAppAssistant:
    def __init__(self):
        self.unread_cache = []
        self.current_chat = None

    # ---------------------------------------------------------
    # STEP 1 — SUMMARY OF UNREAD
    # ---------------------------------------------------------

    def summarize_unread(self, player=None):
        """Check WhatsApp messages with Chrome auto-launch and QR code handling"""
        
        # Step 1: Check if Chrome is running with remote debugging
        if not is_chrome_debug_running():
            self._speak("I need to launch Chrome to access WhatsApp Web.", player)
            
            # Launch Chrome with remote debugging
            if not ensure_chrome_debug():
                self._speak("Failed to launch Chrome. Please ensure Chrome is installed.", player)
                return
            
            self._speak("Chrome is up. Scan the QR code on WhatsApp Web if prompted, then tell me when you're ready.", player)
            return  # Return and wait for user to confirm setup is complete

        # Step 2: Check if WhatsApp tab exists and is working
        whatsapp_tab = get_whatsapp_tab()
        if not whatsapp_tab:
            self._speak("Can't find the WhatsApp Web tab. Open https://web.whatsapp.com and scan the QR code if needed.", player)
            return

        # Step 3: Try to get unread messages
        self._speak("Checking your WhatsApp messages...", player)
        
        try:
            unread = get_unread_messages()
            self.unread_cache = unread or []
        except Exception as e:
            self._speak("Had an issue accessing WhatsApp Web. Make sure you're logged in and try again.", player)
            return

        # Step 4: Report results with message content
        if not self.unread_cache:
            msg = "No unread messages."
            self._speak(msg, player)
            return

        count = len(self.unread_cache)

        if count == 1:
            item = self.unread_cache[0]
            name = item.get("name")
            message = item.get("message", "")
            self._speak(f"1 unread message from {name}: {message}", player)
        elif count <= 5:
            self._speak(f"You have {count} unread messages:", player)
            for i, item in enumerate(self.unread_cache[:3]):
                name = item.get("name")
                message = item.get("message", "")
                self._speak(f"{i+1}. {name} says: {message}", player)
            
            if count > 3:
                remaining = count - 3
                self._speak(f"And {remaining} more. Want me to reply to any of these?", player)
        else:
            self._speak(f"You have {count} unread messages. Here are the most recent:", player)
            for i, item in enumerate(self.unread_cache[:3]):
                name = item.get("name")
                message = item.get("message", "")
                self._speak(f"{i+1}. {name} says: {message}", player)
            
            remaining = count - 3
            self._speak(f"And {remaining} more. Say 'reply to [name]' or 'read more' to continue.", player)

    def continue_after_setup(self, player=None):
        """Continue checking messages after QR code scan is complete"""
        self._speak("Let me check your messages now...", player)
        
        # Wait a moment for WhatsApp Web to load completely
        time.sleep(2)
        
        # Now proceed with the normal message checking
        self.summarize_unread(player)

    def reply_to_contact(self, contact_name: str, player=None):
        """Find a specific contact's chat, open it, read the full latest message, and prepare reply."""
        # First check if we have cached unread; if not, do a fresh check
        if not self.unread_cache:
            # Try to get unread messages directly
            from automation.chrome_debug import get_unread_messages, is_chrome_debug_running, ensure_chrome_debug
            if not is_chrome_debug_running():
                if not ensure_chrome_debug():
                    self._speak("I need Chrome running to access WhatsApp.", player)
                    return None
            unread = get_unread_messages()
            self.unread_cache = unread or []

        # Find the contact in unread messages (fuzzy match)
        target_message = None
        for item in self.unread_cache:
            if contact_name.lower() in item.get("name", "").lower():
                target_message = item
                break

        if not target_message:
            # Try to open the chat directly by name even without a cached unread entry
            from automation.chrome_debug import open_chat_by_name, find_best_chat_match, get_all_chat_names
            chat_list = get_all_chat_names()
            best_match, _ = find_best_chat_match(contact_name, chat_list)
            if best_match:
                target_message = {"name": best_match, "message": ""}
            else:
                self._speak(f"Couldn't find a message or chat from {contact_name}.", player)
                return None

        name = target_message.get("name")

        # Open the chat
        success = open_chat_by_name(name)
        if not success:
            self._speak(f"Couldn't open the chat with {name}.", player)
            return None

        self.current_chat = name

        # Wait for chat to load then read the full latest message
        time.sleep(1.0)
        full_msg = get_latest_message_from_open_chat()
        message_text = full_msg.get("text", "") if full_msg else target_message.get("message", "")
        sender_dir = full_msg.get("direction", "incoming") if full_msg else "incoming"

        if message_text:
            if sender_dir == "outgoing":
                self._speak(f"The last message in {name}'s chat was sent by you: {message_text}", player)
            else:
                self._speak(f"{name}'s latest message: {message_text}", player)
        else:
            self._speak(f"Opened {name}'s chat. The last message appears to be media content.", player)

        # Return message info for AI reply generation
        return {
            "sender": name,
            "text": message_text or target_message.get("message", ""),
            "direction": sender_dir,
            "type": "text"
        }

    # ---------------------------------------------------------
    # STEP 2 — OPEN CHAT BY NAME (FUZZY)
    # ---------------------------------------------------------

    def open_chat(self, query: str, player=None):
        chat_list = get_all_chat_names()
        best_match, matches = find_best_chat_match(query, chat_list)

        if best_match:
            success = open_chat_by_name(best_match)
            if success:
                self.current_chat = best_match
                msg = f"Opening {best_match}."
                self._speak(msg, player)
                return True

        # If unclear, suggest closest
        if matches:
            options = [chat_list[m[2]] for m in matches[:3]]
            msg = (
                "I found a few similar names. Did you mean: "
                + ", ".join(options)
                + "?"
            )
            self._speak(msg, player)
            return False

        self._speak("Couldn't find that chat.", player)
        return False

    # ---------------------------------------------------------
    # STEP 3 — READ LATEST MESSAGE FROM OPEN CHAT
    # ---------------------------------------------------------

    def read_current_chat(self, player=None):
        message = get_latest_message_from_open_chat()

        if not message:
            self._speak("Couldn't read that message.", player)
            return None

        sender = message.get("sender")
        text = message.get("text")
        direction = message.get("direction")

        if direction == "outgoing":
            msg = "The last message in this chat was sent by you."
        else:
            if text:
                msg = f"{sender} says: {text}"
            else:
                msg = f"The last message from {sender} was media content."

        self._speak(msg, player)
        return message

    # ---------------------------------------------------------
    # STEP 4 — READ ALL UNREAD ONE BY ONE
    # ---------------------------------------------------------

    def read_all_unread(self, player=None):
        unread = get_unread_messages()
        if not unread:
            self._speak("Sir, there are no unread chats.", player)
            return

        for item in unread:
            name = item.get("name")
            opened = open_chat_by_name(name)
            if opened:
                self.current_chat = name
                message = get_latest_message_from_open_chat()
                if message and message.get("text"):
                    msg = f"{name} says: {message['text']}"
                else:
                    msg = f"{name} sent a media message."
                self._speak(msg, player)

    # ---------------------------------------------------------
    # INTERNAL SPEAK WRAPPER
    # ---------------------------------------------------------

    def _speak(self, text, player=None):
        # Print to console
        print(f"🤖 Sam: {text}")
        
        if player:
            player.write_log(text)

        controller.set_state(State.SPEAKING)
        edge_speak(text, player, blocking=True)
        controller.set_state(State.IDLE)
