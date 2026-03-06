"""
skills/loader.py — SkillLoader

Scans the skills/ package for any module that exposes a SKILL_MANIFEST dict.
Each skill is a self-contained plugin:

    SKILL_MANIFEST = {
        "name": "pomodoro",
        "description": "25-min focus timer with break reminders",
        "intents": ["pomodoro", "start_pomodoro"],
        "trigger_phrases": ["start pomodoro", "25 minute timer", "focus timer"],
        "run": <callable(parameters, ui, **ctx) -> str>,
    }

The `run()` callable receives:
  - parameters (dict from LLM)
  - ui            (SamUI instance)
  - presence      (PresenceEngine, optional)
  - reminder_engine (ReminderEngine, optional)
  - Any other context kwarg

It returns a string — what Sam will speak aloud. If it returns None or raises,
Sam falls back to a generic "I couldn't run that skill" response.

Usage in handlers.py:
    from skills.loader import skill_loader
    result = skill_loader.run("pomodoro", parameters, ui, **ctx)
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

_SKILLS_DIR = Path(__file__).parent


class SkillLoader:
    def __init__(self):
        self._registry: dict[str, dict] = {}   # intent → manifest
        self._loaded = False

    def load(self):
        """Scan skills/ and register every module that has SKILL_MANIFEST."""
        if self._loaded:
            return
        self._loaded = True

        package_name = "skills"
        for finder, module_name, _ in pkgutil.iter_modules([str(_SKILLS_DIR)]):
            if module_name in ("loader", "__init__"):
                continue
            try:
                mod = importlib.import_module(f"{package_name}.{module_name}")
                manifest = getattr(mod, "SKILL_MANIFEST", None)
                if not manifest or not isinstance(manifest, dict):
                    continue
                if "run" not in manifest or "intents" not in manifest:
                    continue
                for intent in manifest["intents"]:
                    self._registry[intent] = manifest
            except Exception as e:
                # A broken skill must never crash Sam
                print(f"[SkillLoader] Failed to load skill '{module_name}': {e}")

    def has(self, intent: str) -> bool:
        self.load()
        return intent in self._registry

    def get_trigger_phrases(self) -> list[tuple[str, str]]:
        """Return [(trigger_phrase, intent)] for all skills — for prompt injection."""
        self.load()
        results = []
        for intent, manifest in self._registry.items():
            for phrase in manifest.get("trigger_phrases", []):
                results.append((phrase, intent))
        return results

    def run(self, intent: str, parameters: dict, ui: Any, **ctx) -> str | None:
        """
        Execute the skill mapped to `intent`.
        Returns the spoken response string, or None if no skill matched.
        """
        self.load()
        manifest = self._registry.get(intent)
        if not manifest:
            return None
        try:
            fn: Callable = manifest["run"]
            return fn(parameters, ui, **ctx)
        except Exception as e:
            print(f"[SkillLoader] Skill '{intent}' raised: {e}")
            return f"I ran into a problem with the {manifest.get('name', intent)} skill."

    def list_skills(self) -> list[dict]:
        """Return summary info for all loaded skills (for 'what can you do' responses)."""
        self.load()
        seen = set()
        results = []
        for manifest in self._registry.values():
            name = manifest.get("name", "")
            if name not in seen:
                seen.add(name)
                results.append({
                    "name": name,
                    "description": manifest.get("description", ""),
                })
        return results


# Singleton — imported by handlers.py and llm.py
skill_loader = SkillLoader()
