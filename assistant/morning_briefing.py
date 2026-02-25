from datetime import datetime
from memory.memory_manager import load_memory
import os
import requests

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-3.5-turbo"


def generate_morning_briefing() -> str:
    memory = load_memory()

    now = datetime.now()
    time_str = now.strftime("%A, %d %B %Y — %I:%M %p")

    primary_project = memory.get("projects", {}).get("primary_project", {}).get("value", "No primary project set.")
    blockers = memory.get("goals", {}).get("current_blockers", {}).get("value", [])
    long_term = memory.get("goals", {}).get("long_term_goal", {}).get("value", "")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Good morning, Sir."

    prompt = f"""
You are Sam, a formal strategic AI assistant.

Deliver a concise morning briefing.

Time: {time_str}
Primary Project: {primary_project}
Blockers: {blockers}
Long Term Goal: {long_term}

Maximum 5 sentences.
Be sharp. Be strategic. Be formal.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a formal AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 180
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        return "Good morning, Sir."
    except:
        return "Good morning, Sir."
