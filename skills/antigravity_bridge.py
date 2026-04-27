"""
skills/antigravity_bridge.py — Antigravity Awesome Skills adapter for Sam

Scans skills/antigravity_skills/skills/ at import time and builds a registry of
all installed skill prompts. Sam can activate any skill by name to augment an
LLM request with specialised context.

Usage (from handlers.py):
    from skills.antigravity_bridge import activate_skill, search_skills, list_skills_brief
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_SKILLS_DIR = Path(__file__).resolve().parent / "antigravity_skills" / "skills"

# ── Registry ─────────────────────────────────────────────────────────────────
# skill_slug → { name, description, tags, content }
SKILL_REGISTRY: dict[str, dict] = {}


def _parse_skill_md(path: Path) -> Optional[dict]:
    """Parse a SKILL.md file and return a dict or None if unreadable."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Extract YAML frontmatter between the first two --- delimiters
    name = path.parent.name   # folder name as default
    description = ""
    tags: list[str] = []

    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        n = re.search(r"^name:\s*['\"]?(.*?)['\"]?\s*$", fm, re.MULTILINE)
        d = re.search(r"^description:\s*['\"]?(.*?)['\"]?\s*$", fm, re.MULTILINE)
        t = re.findall(r"^\s*-\s+(.+)$", re.search(
            r"^tags:(.*?)(?=\n\w|\Z)", fm, re.DOTALL | re.MULTILINE
        ).group(1) if re.search(r"^tags:", fm, re.MULTILINE) else "", re.MULTILINE)
        if n:
            name = n.group(1).strip().strip("'\"")
        if d:
            description = d.group(1).strip().strip("'\"")
        tags = [x.strip() for x in t if x.strip()]

    return {
        "name":        name,
        "slug":        path.parent.name,
        "description": description,
        "tags":        tags,
        "content":     text,   # full SKILL.md content used as system context
    }


def _load_registry():
    """Build SKILL_REGISTRY from the antigravity_skills directory."""
    if not _SKILLS_DIR.exists():
        return
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        parsed = _parse_skill_md(skill_md)
        if parsed:
            SKILL_REGISTRY[parsed["slug"]] = parsed


# ── Public API ────────────────────────────────────────────────────────────────

def activate_skill(slug_or_name: str, temp_memory) -> Optional[str]:
    """
    Activate a skill by slug or partial name match.

    Appends the skill's content to temp_memory["active_skill"] so that the
    next LLM call can include it as additional system context.

    Returns the skill name on success, or None if skill not found.
    """
    key = _resolve(slug_or_name)
    if key is None:
        return None
    skill = SKILL_REGISTRY[key]
    if hasattr(temp_memory, "set"):
        temp_memory.set("active_skill_name", skill["name"])
        temp_memory.set("active_skill_content", skill["content"])
    elif isinstance(temp_memory, dict):
        temp_memory["active_skill_name"] = skill["name"]
        temp_memory["active_skill_content"] = skill["content"]
    return skill["name"]


def deactivate_skill(temp_memory):
    """Remove any active skill from temp_memory."""
    if hasattr(temp_memory, "delete"):
        temp_memory.delete("active_skill_name")
        temp_memory.delete("active_skill_content")
    elif isinstance(temp_memory, dict):
        temp_memory.pop("active_skill_name", None)
        temp_memory.pop("active_skill_content", None)


def search_skills(query: str, max_results: int = 5) -> list[dict]:
    """Return up to max_results skills whose name/description/tags match query."""
    q = query.lower()
    results = []
    for skill in SKILL_REGISTRY.values():
        score = 0
        if q in skill["slug"].lower():
            score += 3
        if q in skill["name"].lower():
            score += 2
        if q in skill["description"].lower():
            score += 1
        if any(q in t.lower() for t in skill["tags"]):
            score += 2
        if score > 0:
            results.append((score, skill))
    results.sort(key=lambda x: -x[0])
    return [r[1] for r in results[:max_results]]


def list_skills_brief(max_items: int = 20) -> list[dict]:
    """Return a brief summary list of all installed skills."""
    out = []
    for skill in list(SKILL_REGISTRY.values())[:max_items]:
        out.append({
            "slug":        skill["slug"],
            "name":        skill["name"],
            "description": skill["description"][:80],
        })
    return out


def _resolve(slug_or_name: str) -> Optional[str]:
    """Return canonical slug for an input string, or None."""
    slug = slug_or_name.lower().strip().replace(" ", "-")
    # Exact match first
    if slug in SKILL_REGISTRY:
        return slug
    # Partial slug match
    for key in SKILL_REGISTRY:
        if slug in key:
            return key
    # Name match
    for key, skill in SKILL_REGISTRY.items():
        if slug in skill["name"].lower():
            return key
    return None


# ── Boot ─────────────────────────────────────────────────────────────────────
_load_registry()


def total_skills() -> int:
    return len(SKILL_REGISTRY)


def auto_activate_for_task(task_description: str, temp_memory) -> Optional[str]:
    """Search skills by task description and auto-activate the best match.

    Returns the activated skill name, or None if no suitable skill found.
    Requires a minimum relevance score to avoid activating irrelevant skills.
    """
    if not task_description or not SKILL_REGISTRY:
        return None
    results = search_skills(task_description, max_results=3)

    # Fallback: if full-string search found nothing, try each significant word.
    # This handles natural-language task descriptions like "help me build a flask api".
    if not results:
        _SKIP = {"a", "an", "the", "to", "in", "for", "with", "and", "or",
                 "my", "me", "this", "that", "is", "it", "of", "do", "at",
                 "i", "be", "on", "by", "as", "up", "how", "let", "get"}
        for word in task_description.lower().split():
            if word in _SKIP or len(word) < 3:
                continue
            word_results = search_skills(word, max_results=3)
            if word_results:
                results = word_results
                break

    if not results:
        return None
    best = results[0]
    # Only activate if there's a meaningful keyword match
    words = set(task_description.lower().split())
    score = 0
    if any(w in best["slug"].lower() for w in words):   score += 3
    if any(w in best["name"].lower() for w in words):   score += 2
    if any(w in best["description"].lower() for w in words): score += 1
    if any(any(w in t.lower() for w in words) for t in best["tags"]): score += 2
    if score < 2:
        return None
    return activate_skill(best["slug"], temp_memory)
