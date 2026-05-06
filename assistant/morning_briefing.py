from datetime import datetime
from memory.memory_manager import load_memory
import os
import requests


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


def _get_yesterday_summary(now: datetime) -> str:
    """Return a short string about yesterday's completed tasks, or '' on any failure."""
    try:
        from pathlib import Path
        from datetime import timedelta
        import json
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = Path(__file__).parent.parent / "reports" / "sessions" / f"{yesterday_str}.json"
        if not yesterday_file.exists():
            return ""
        with open(yesterday_file, encoding="utf-8") as f:
            entries = json.load(f)
        done = [e for e in entries if e.get("outcome") == "done"]
        if not done:
            return ""
        return f"Yesterday ({len(done)} tasks done): " + "; ".join(
            e["summary"][:50] for e in done[-3:]
        )
    except Exception:
        return ""


def _get_project_index_summary() -> str:
    """Return a short summary of indexed projects, or '' on any failure."""
    try:
        from system.project_index import project_index
        return project_index.summary()
    except Exception:
        return ""


def _build_prompt(
    time_str: str,
    primary_project: str,
    blockers: list,
    long_term: str,
    yesterday_block: str,
    calendar_block: str,
    news_block: str,
    projects_block: str,
) -> str:
    lines = [
        "You are Sam, a sharp and strategic AI assistant.",
        "",
        "Deliver a morning briefing. Be direct, personal, and specific. Max 5 sentences.",
        "Sound natural — like a smart colleague catching you up, not a robot reading a list.",
        "",
        f"Time: {time_str}",
    ]
    if primary_project:
        lines.append(f"Primary Project: {primary_project}")
    if blockers:
        lines.append(f"Blockers from memory: {blockers}")
    if long_term:
        lines.append(f"Long-term goal: {long_term}")
    if yesterday_block:
        lines.append(f"Yesterday: {yesterday_block}")
    if projects_block:
        lines.append(f"Indexed projects: {projects_block}")
    lines += [
        "",
        "Today's calendar:",
        calendar_block,
        "",
        "Top news this morning:",
        news_block,
        "",
        "Cover: pick up from where we left off (if yesterday data available), one key focus, "
        "calendar highlights, one relevant news item if it matters.",
        "Never say 'Sir'. Vary your language. Be warm and direct.",
    ]
    return "\n".join(lines)


def generate_morning_briefing() -> str:
    memory = load_memory()
    now = datetime.now()
    time_str = now.strftime("%A, %d %B %Y — %I:%M %p")

    primary_project = memory.get("projects", {}).get("primary_project", {}).get("value", "")
    blockers = memory.get("goals", {}).get("current_blockers", {}).get("value", [])
    long_term = memory.get("goals", {}).get("long_term_goal", {}).get("value", "")

    headlines = _get_news_headlines(3)
    calendar = _get_calendar_summary()
    yesterday_block = _get_yesterday_summary(now)
    projects_block = _get_project_index_summary()

    news_block = (
        "\n".join(f"  - {h}" for h in headlines)
        if headlines else "  (no news available)"
    )
    calendar_block = calendar or "  Nothing on the calendar."

    prompt = _build_prompt(
        time_str=time_str,
        primary_project=primary_project,
        blockers=blockers,
        long_term=long_term,
        yesterday_block=yesterday_block,
        calendar_block=calendar_block,
        news_block=news_block,
        projects_block=projects_block,
    )

    system = "You are a concise strategic AI assistant. Never say Sir. Max 5 sentences."

    try:
        from llm.manager import get_manager
        mgr = get_manager()
        result = mgr.complete_sync(prompt, system=system, model_tier="auto")
        if result and not result.startswith("[LLM error"):
            return result.strip()
    except Exception:
        pass

    return "Good morning."
