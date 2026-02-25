from datetime import datetime
from memory.memory_manager import load_memory
import os
import requests

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-3.5-turbo"


def generate_daily_plan() -> str:
    memory = load_memory()

    primary_project = memory.get("projects", {}).get("primary_project", {}).get("value", "")
    blockers = memory.get("goals", {}).get("current_blockers", {}).get("value", [])
    long_term = memory.get("goals", {}).get("long_term_goal", {}).get("value", "")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Sir, daily planning unavailable."

    today = datetime.now().strftime("%A")

    prompt = f"""
You are Sam, a strategic execution assistant for a solo tech founder.

Context:
- The user has already shipped a Flutter estate visitor management app.
- It is live on App Store and Play Store.
- The user personally visits the estate to ensure adoption.
- Current blockers: money and time.
- Long-term goal: build a profitable tech company with subscription-based apps.

Today is {today}.

Primary Project:
{primary_project}

Blockers:
{blockers}

Long-Term Goal:
{long_term}

Create a DAILY EXECUTION PLAN that is directly relevant to THIS project.

Rules:
- Give exactly 3 concrete actions for TODAY.
- Focus on adoption, revenue, leverage, or system automation.
- No generic corporate language.
- No team meetings (he is mostly solo).
- Tasks must be realistic for one person.
- End with one sharp strategic reminder sentence.
- Maximum 6 sentences total.
- Formal tone. Address him as Sir.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a formal strategic assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 220
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        return "Sir, I could not generate today's plan."
    except:
        return "Sir, planning system unavailable."
