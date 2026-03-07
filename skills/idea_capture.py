"""
skills/idea_capture.py — Capture a spoken idea and generate a structured dev plan.

Calls the cloud LLM (OpenAI) with a structured prompt, saves a Markdown plan
file to ~/Documents/Sam Notes/Plans/, and speaks a short summary.

Intents: capture_idea, create_feature_plan, plan_feature
Trigger phrases: "plan this feature", "capture this idea", "build a plan for",
                 "I want to build", "create feature plan"
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from log.logger import get_logger

logger = get_logger("IDEA_CAPTURE")

PLANS_DIR = Path.home() / "Documents" / "Sam Notes" / "Plans"


def _slug(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]


def _call_openai(idea: str) -> dict | None:
    """Call OpenAI to generate a structured dev plan. Returns parsed dict or None."""
    try:
        import openai
    except ImportError:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    prompt = (
        f'Generate a concise developer feature plan for: "{idea}"\n'
        "Return JSON only with these keys:\n"
        '{\n'
        '  "feature": "short feature name",\n'
        '  "backend": ["task1", "task2"],\n'
        '  "api": ["endpoint1"],\n'
        '  "ui": ["component1"],\n'
        '  "scope": "small|medium|large",\n'
        '  "summary": "One sentence Sam will speak"\n'
        "}"
    )

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a technical planning assistant. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        logger.error(f"idea_capture OpenAI call failed: {e}")
        return None


def _save_plan(plan: dict, idea: str) -> Path:
    """Write plan as a Markdown file; return the file path."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    feature = plan.get("feature") or idea
    filename = f"{date.today().isoformat()}-{_slug(feature)}.md"
    filepath = PLANS_DIR / filename

    lines = [
        f"# {feature}",
        f"\n> *Captured {date.today().isoformat()}*\n",
        f"**Scope:** {plan.get('scope', 'unknown')}",
        "",
    ]

    backend = plan.get("backend", [])
    if backend:
        lines += ["## Backend", ""] + [f"- {t}" for t in backend] + [""]

    api = plan.get("api", [])
    if api:
        lines += ["## API", ""] + [f"- {e}" for e in api] + [""]

    ui = plan.get("ui", [])
    if ui:
        lines += ["## UI", ""] + [f"- {c}" for c in ui] + [""]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _run(parameters: dict, ui: Any, **ctx) -> str:
    idea = (
        parameters.get("idea")
        or parameters.get("feature")
        or parameters.get("text")
        or ""
    ).strip()

    if not idea:
        return "What feature or idea do you want to plan?"

    if not os.getenv("OPENAI_API_KEY"):
        return (
            f"I'd love to plan '{idea}' but I need an OpenAI API key to generate the plan. "
            "Set OPENAI_API_KEY in your .env file."
        )

    plan = _call_openai(idea)
    if not plan:
        return f"I couldn't generate a plan for '{idea}' right now — check the logs."

    try:
        filepath = _save_plan(plan, idea)
        summary = plan.get("summary", f"Plan created for {idea}.")
        scope = plan.get("scope", "")
        scope_text = f" It looks like a {scope}-scope feature." if scope else ""
        logger.info(f"idea_capture: saved plan to {filepath}")
        return f"{summary}{scope_text} I've saved the plan to your Sam Notes."
    except Exception as e:
        logger.error(f"idea_capture save failed: {e}")
        return f"I generated a plan for '{idea}' but couldn't save it: {e}"


SKILL_MANIFEST = {
    "name": "idea_capture",
    "description": "Capture a spoken feature idea and generate a structured developer plan",
    "intents": [
        "capture_idea",
        "create_feature_plan",
        "plan_feature",
    ],
    "trigger_phrases": [
        "plan this feature",
        "capture this idea",
        "build a plan for",
        "i want to build",
        "create feature plan",
        "plan the feature",
        "make a dev plan",
    ],
    "run": _run,
}
