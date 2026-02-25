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
            self._speak("Sir, I need to launch Chrome to access WhatsApp Web.", player)
            
            # Launch Chrome with remote debugging
            if not ensure_chrome_debug():
                self._speak("Sir, I failed to launch Chrome. Please ensure Chrome is installed.", player)
                return
            
            self._speak("Sir, Chrome has been launched. Please scan the QR code on the WhatsApp Web page if prompted, then tell me when you're ready.", player)
            return  # Return and wait for user to confirm setup is complete

        # Step 2: Check if WhatsApp tab exists and is working
        whatsapp_tab = get_whatsapp_tab()
        if not whatsapp_tab:
            self._speak("Sir, I cannot find the WhatsApp Web tab. Please open https://web.whatsapp.com and scan the QR code if needed.", player)
            return

        # Step 3: Try to get unread messages
        self._speak("Sir, checking your WhatsApp messages...", player)
        
        try:
            unread = get_unread_messages()
            self.unread_cache = unread or []
        except Exception as e:
            self._speak("Sir, I encountered an issue accessing WhatsApp Web. Please ensure you're logged in and try again.", player)
            return

        # Step 4: Report results with message content
        if not self.unread_cache:
            msg = "Sir, you have no unread messages."
            self._speak(msg, player)
            return

        count = len(self.unread_cache)

        if count == 1:
            # Read the single message content
            item = self.unread_cache[0]
            name = item.get("name")
            message = item.get("message", "")
            self._speak(f"Sir, you have 1 unread message from {name}: {message}", player)
        elif count <= 5:
            # Read first few messages with content
            self._speak(f"Sir, you have {count} unread messages:", player)
            for i, item in enumerate(self.unread_cache[:3]):  # Limit to first 3 to avoid too much speech
                name = item.get("name")
                message = item.get("message", "")
                self._speak(f"{i+1}. {name} says: {message}", player)
            
            if count > 3:
                remaining = count - 3
                self._speak(f"And {remaining} more messages. Would you like me to reply to any of these?", player)
        else:
            # For many messages, read the first few
            self._speak(f"Sir, you have {count} unread messages. Here are the most recent:", player)
            for i, item in enumerate(self.unread_cache[:3]):
                name = item.get("name")
                message = item.get("message", "")
                self._speak(f"{i+1}. {name} says: {message}", player)
            
            remaining = count - 3
            self._speak(f"And {remaining} more. Say 'reply to [name]' or 'read more' to continue.", player)

    def continue_after_setup(self, player=None):
        """Continue checking messages after QR code scan is complete"""
        self._speak("Sir, let me check your messages now...", player)
        
        # Wait a moment for WhatsApp Web to load completely
        time.sleep(2)
        
        # Now proceed with the normal message checking
        self.summarize_unread(player)

    def reply_to_contact(self, contact_name: str, player=None):
        """Find a specific contact from unread messages and prepare for reply"""
        if not self.unread_cache:
            self._speak("Sir, there are no unread messages to reply to.", player)
            return None
        
        # Find the contact in unread messages
        target_message = None
        for item in self.unread_cache:
            if contact_name.lower() in item.get("name", "").lower():
                target_message = item
                break
        
        if not target_message:
            self._speak(f"Sir, I could not find an unread message from {contact_name}.", player)
            return None
        
        # Open the chat and return the message info for AI drafting
        name = target_message.get("name")
        message = target_message.get("message", "")
        
        # Open the chat first
        success = open_chat_by_name(name)
        if not success:
            self._speak(f"Sir, I could not open the chat with {name}.", player)
            return None
        
        self.current_chat = name
        
        # Return the message info for AI reply generation
        return {
            "sender": name,
            "text": message,
            "direction": "incoming",
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
                msg = f"Opening {best_match}, Sir."
                self._speak(msg, player)
                return True

        # If unclear, suggest closest
        if matches:
            options = [chat_list[m[2]] for m in matches[:3]]
            msg = (
                "Sir, I found multiple similar names. Did you mean: "
                + ", ".join(options)
                + "?"
            )
            self._speak(msg, player)
            return False

        self._speak("Sir, I could not find that chat.", player)
        return False

    # ---------------------------------------------------------
    # STEP 3 — READ LATEST MESSAGE FROM OPEN CHAT
    # ---------------------------------------------------------

    def read_current_chat(self, player=None):
        message = get_latest_message_from_open_chat()

        if not message:
            self._speak("Sir, I could not read the message.", player)
            return None

        sender = message.get("sender")
        text = message.get("text")
        direction = message.get("direction")

        if direction == "outgoing":
            msg = "Sir, the last message in this chat was sent by you."
        else:
            if text:
                msg = f"Sir, {sender} says: {text}"
            else:
                msg = f"Sir, the last message from {sender} was media content."

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
