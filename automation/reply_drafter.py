import os
import requests
import json

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"


def generate_reply(message_text: str, sender: str = None) -> str:
    """
    Generate AI reply draft for a WhatsApp message.
    """

    api_key = os.getenv("OPENAI_API_KEY")
    
    # Fallback: try loading from config if env var not set
    if not api_key:
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "api_keys.json")
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("openai_api_key")
        except:
            pass
    
    if not api_key:
        return "Sir, I cannot generate a reply because the OpenAI key is missing."

    system_prompt = """
You are Sam, a formal and strategic AI assistant.
Generate short, intelligent WhatsApp replies.
Keep it natural.
Do not over-explain.
Be human but composed.
    """

    user_prompt = f"""
Incoming message:
From: {sender or "Unknown"}
Message: {message_text}

Generate a concise reply.
    """

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 120
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[ERROR] Reply generation failed: {e}")
        return "Sir, I encountered an error while drafting the reply."
