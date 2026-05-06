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
import json
import pkgutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_SKILLS_DIR = Path(__file__).parent
_STATE_PATH = _SKILLS_DIR.parent / "memory" / "skill_state.json"


def _load_state() -> dict:
    try:
        if _STATE_PATH.exists():
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict):
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[SkillLoader] Failed to save skill state: {e}")


class SkillLoader:
    def __init__(self):
        self._registry: dict[str, dict] = {}   # intent → manifest
        self._loaded = False
        self._state: dict = _load_state()       # name → {"enabled": bool, "last_activated": iso|""}

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
                # Ensure state entry exists for this skill
                name = manifest.get("name", module_name)
                if name not in self._state:
                    self._state[name] = {"enabled": True, "last_activated": ""}
            except Exception as e:
                # A broken skill must never crash Sam
                print(f"[SkillLoader] Failed to load skill '{module_name}': {e}")

    def _is_enabled(self, name: str) -> bool:
        return self._state.get(name, {}).get("enabled", True)

    def has(self, intent: str) -> bool:
        self.load()
        manifest = self._registry.get(intent)
        if not manifest:
            return False
        return self._is_enabled(manifest.get("name", ""))

    def toggle(self, name: str) -> bool:
        """Toggle a skill on/off by name. Returns the new enabled state."""
        self.load()
        current = self._state.get(name, {}).get("enabled", True)
        new_state = not current
        if name not in self._state:
            self._state[name] = {"enabled": new_state, "last_activated": ""}
        else:
            self._state[name]["enabled"] = new_state
        _save_state(self._state)
        return new_state

    def set_enabled(self, name: str, enabled: bool):
        """Explicitly enable or disable a skill by name."""
        self.load()
        if name not in self._state:
            self._state[name] = {"enabled": enabled, "last_activated": ""}
        else:
            self._state[name]["enabled"] = enabled
        _save_state(self._state)

    def _record_activation(self, name: str):
        if name not in self._state:
            self._state[name] = {"enabled": True, "last_activated": ""}
        self._state[name]["last_activated"] = datetime.now().isoformat(timespec="seconds")
        _save_state(self._state)

    def get_trigger_phrases(self) -> list[tuple[str, str]]:
        """Return [(trigger_phrase, intent)] for enabled skills — for prompt injection."""
        self.load()
        results = []
        for intent, manifest in self._registry.items():
            if not self._is_enabled(manifest.get("name", "")):
                continue
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
        name = manifest.get("name", intent)
        if not self._is_enabled(name):
            return None
        try:
            fn: Callable = manifest["run"]
            result = fn(parameters, ui, **ctx)
            self._record_activation(name)
            return result
        except Exception as e:
            print(f"[SkillLoader] Skill '{intent}' raised: {e}")
            return f"I ran into a problem with the {name} skill."

    def list_skills(self) -> list[dict]:
        """Return full info for all loaded skills (for the dashboard)."""
        self.load()
        seen: dict[str, dict] = {}
        for manifest in self._registry.values():
            name = manifest.get("name", "")
            if name not in seen:
                state = self._state.get(name, {})
                seen[name] = {
                    "name": name,
                    "description": manifest.get("description", ""),
                    "intents": manifest.get("intents", []),
                    "trigger_phrases": manifest.get("trigger_phrases", []),
                    "enabled": state.get("enabled", True),
                    "last_activated": state.get("last_activated", ""),
                }
        return list(seen.values())

    def prompt_skills_section(self) -> str:
        """Generate the SKILLS section for the system prompt — only enabled skills."""
        self.load()
        seen: set[str] = set()
        lines = ["SKILLS (built-in capabilities):"]
        for manifest in self._registry.values():
            name = manifest.get("name", "")
            if name in seen or not self._is_enabled(name):
                continue
            seen.add(name)
            phrases = manifest.get("trigger_phrases", [])
            intents = manifest.get("intents", [])
            desc = manifest.get("description", "")
            if phrases:
                trigger = f'If user says "{phrases[0]}"'
                if len(phrases) > 1:
                    trigger += f' (or "{phrases[1]}")'
            else:
                trigger = f"If user invokes {name}"
            primary_intent = intents[0] if intents else name
            lines.append(f"- {trigger} -> intent: {primary_intent}  [{desc}]")
        return "\n".join(lines)


# Singleton — imported by handlers.py and llm.py
skill_loader = SkillLoader()
