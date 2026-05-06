"""
assistant/daily_planner.py — DEPRECATED re-export shim.

The "daily plan" and "morning briefing" features were two parallel briefing
producers that both pulled from the same memory keys (primary_project,
blockers, long_term_goal). The merge consolidates them under
``assistant/morning_briefing.generate_morning_briefing`` as the single
canonical briefing producer.

If you genuinely need the older "3 concrete actions" framing, ask Sam:
he can run morning_briefing's prompt with that emphasis via the LLM. Don't
add another producer here.

Strip-down phase (2026-05-01): scheduled for full removal once any external
imports are migrated. ``generate_daily_plan`` now delegates to
``generate_morning_briefing`` so any caller still gets a useful response.
"""
from assistant.morning_briefing import generate_morning_briefing


def generate_daily_plan() -> str:
    """Deprecated. Delegates to generate_morning_briefing for one canonical briefing."""
    return generate_morning_briefing()


__all__ = ["generate_daily_plan"]
