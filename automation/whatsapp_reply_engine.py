from llm import get_llm_output
from automation.safety_filter import is_sensitive


def generate_whatsapp_reply(chat_name: str, message_text: str) -> dict:
    """
    Uses OpenAI to generate a balanced professional WhatsApp reply.
    Returns:
        {
            "reply": str,
            "requires_confirmation": bool
        }
    """

    system_prompt = """
You are Sam, a professional but warm executive assistant.

Write short, natural WhatsApp replies.
Tone: respectful, calm, confident.
Do not over-explain.
1–3 sentences maximum.
No emojis unless appropriate.
"""

    user_prompt = f"""
Chat name: {chat_name}
Incoming message: "{message_text}"

Write an appropriate reply.
"""

    result = get_llm_output(user_prompt)

    reply_text = result.get("text") if result else None

    if not reply_text:
        reply_text = "Understood. I will respond shortly."

    requires_confirmation = is_sensitive(message_text) or is_sensitive(reply_text)

    return {
        "reply": reply_text.strip(),
        "requires_confirmation": requires_confirmation
    }
