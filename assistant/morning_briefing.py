from datetime import datetime
from memory.memory_manager import load_memory
import os
import requests

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-3.5-turbo"


def _get_news_headlines(n: int = 3) -> list[str]:
    """Pull top n headlines from SerpAPI Google News. Returns [] on any failure."""
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google_news", "api_key": key, "hl": "en", "gl": "ng"},
            timeout=8,
        )
        results = r.json().get("news_results", [])
        return [item["title"] for item in results[:n] if item.get("title")]
    except Exception:
        return []


def _get_calendar_summary() -> str:
    """Return today's calendar as a spoken string, or '' if gws not set up."""
    try:
        from actions.workspace import get_today_events, format_events_spoken, _is_gws_available
        if not _is_gws_available():
            return ""
        events = get_today_events()
        return format_events_spoken(events)
    except Exception:
        return ""


def generate_morning_briefing() -> str:
    memory = load_memory()

    now = datetime.now()
    time_str = now.strftime("%A, %d %B %Y — %I:%M %p")

    primary_project = memory.get("projects", {}).get("primary_project", {}).get("value", "")
    blockers = memory.get("goals", {}).get("current_blockers", {}).get("value", [])
    long_term = memory.get("goals", {}).get("long_term_goal", {}).get("value", "")

    from llm import get_openai_key
    api_key = get_openai_key()
    if not api_key:
        return "Good morning."

    # Enrich with live data (fail silently — briefing degrades gracefully)
    headlines  = _get_news_headlines(3)
    calendar   = _get_calendar_summary()

    news_block = (
        "\n".join(f"  - {h}" for h in headlines)
        if headlines else "  (no news available)"
    )
    calendar_block = calendar or "  Nothing on the calendar."

    # Pull yesterday's session summary for continuity
    yesterday_block = ""
    try:
        from system.session_logger import session_logger
        from pathlib import Path
        from datetime import timedelta
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = Path(__file__).parent.parent / "reports" / "sessions" / f"{yesterday_str}.json"
        if yesterday_file.exists():
            import json
            with open(yesterday_file, encoding="utf-8") as f:
                entries = json.load(f)
            if entries:
                done = [e for e in entries if e.get("outcome") == "done"]
                yesterday_block = f"Yesterday ({len(done)} tasks done): " + "; ".join(
                    e["summary"][:50] for e in done[-3:]
                )
    except Exception:
        pass

    prompt = f"""You are Sam, a sharp and strategic AI assistant.

Deliver a morning briefing. Be direct, personal, and specific. Max 5 sentences.
Sound natural — like a smart colleague catching you up, not a robot reading a list.

Time: {time_str}
{f"Primary Project: {primary_project}" if primary_project else ""}
{f"Blockers from memory: {blockers}" if blockers else ""}
{f"Long-term goal: {long_term}" if long_term else ""}
{f"Yesterday: {yesterday_block}" if yesterday_block else ""}

Today's calendar:
{calendar_block}

Top news this morning:
{news_block}

Cover: pick up from where we left off (if yesterday data available), one key focus, calendar highlights, one relevant news item if it matters.
Never say "Sir". Vary your language. Be warm and direct.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise strategic AI assistant. Never say Sir."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 220,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        return "Good morning."
    except Exception:
        return "Good morning."
