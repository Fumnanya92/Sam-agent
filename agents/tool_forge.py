"""
agents/tool_forge.py — Sam writes its own action handlers.

When Sam receives an intent with no matching Capability:
  1. Recognise the gap (registry miss).
  2. Ask the LLM to draft actions/<intent>.py + a test.
  3. Run the generated test.
  4. Present diff in UI — "I built a new tool. Say 'apply it' to load it."
  5. On approval: register Capability, hot-reload module, re-run original intent.

Self-healing variant: when a known handler throws an unhandled exception the same
flow triggers — diagnose, patch, present, apply.

Gated by config/forge.json: { "enabled": false, "auto_apply": false }.

Usage:
    from agents.tool_forge import tool_forge
    result = tool_forge.attempt(intent, parameters, ui=ui, speak=speak_fn)
    # returns True if a new action was built AND approved (or auto-applied)
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import subprocess
import sys
import textwrap
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("sam.tool_forge")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "forge.json"
_ACTIONS_DIR = Path(__file__).parent.parent / "actions"
_TESTS_DIR   = Path(__file__).parent.parent / "tests" / "forge"

_FORGE_LOCK = threading.Lock()  # only one forge at a time


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "auto_apply": False}


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class ForgeResult:
    intent: str
    success: bool = False
    module_path: str = ""
    test_path: str = ""
    test_passed: bool = False
    applied: bool = False
    error: str = ""
    diff: str = ""


# ── Main class ────────────────────────────────────────────────────────────────

class ToolForge:
    def __init__(self):
        self._pending_forge: dict[str, ForgeResult] = {}  # intent → ForgeResult awaiting apply

    # ── Public API ────────────────────────────────────────────────────────────

    def is_enabled(self) -> bool:
        return _load_config().get("enabled", False)

    def attempt(
        self,
        intent: str,
        parameters: dict | None,
        ui=None,
        speak: Callable | None = None,
    ) -> bool:
        """Try to forge a new action for *intent*. Returns True if applied."""
        if not self.is_enabled():
            logger.debug("[ToolForge] disabled — skipping")
            return False

        cfg = _load_config()
        blocked = cfg.get("blocked_intents", [])
        if intent in blocked:
            logger.info(f"[ToolForge] Intent '{intent}' is blocked")
            return False

        prefixes = cfg.get("allowed_intent_prefixes", [])
        if prefixes and not any(intent.startswith(p) for p in prefixes):
            logger.debug(f"[ToolForge] Intent '{intent}' not in allowed prefixes")
            return False

        if not _FORGE_LOCK.acquire(blocking=False):
            logger.debug("[ToolForge] Another forge in progress — skipping")
            return False

        try:
            return self._forge(intent, parameters or {}, cfg, ui, speak)
        finally:
            _FORGE_LOCK.release()

    def apply_pending(self, intent: str, ui=None, speak: Callable | None = None) -> bool:
        """Called when user says 'apply it' — hot-reload the pending module."""
        result = self._pending_forge.pop(intent, None)
        if result is None:
            return False
        return self._apply(result, ui, speak)

    def has_pending(self, intent: str) -> bool:
        return intent in self._pending_forge

    def heal(
        self,
        intent: str,
        module_name: str,
        error: str,
        ui=None,
        speak: Callable | None = None,
    ) -> bool:
        """Self-healing: a live handler threw — diagnose and patch it."""
        if not self.is_enabled():
            return False
        if not _FORGE_LOCK.acquire(blocking=False):
            return False
        try:
            return self._heal(intent, module_name, error, ui, speak)
        finally:
            _FORGE_LOCK.release()

    # ── Forge pipeline ────────────────────────────────────────────────────────

    def _forge(self, intent: str, parameters: dict, cfg: dict, ui, speak) -> bool:
        self._status(ui, f"[tool_forge] No handler for '{intent}' — drafting one…")

        # 1. Generate action module
        module_src, test_src = self._generate(intent, parameters)
        if not module_src:
            self._status(ui, "[tool_forge] LLM failed to draft code — skipping")
            return False

        # 2. Write to disk (temp location until applied)
        slug = re.sub(r"[^a-z0-9_]", "_", intent.lower())
        action_path = _ACTIONS_DIR / f"forged_{slug}.py"
        test_path   = _TESTS_DIR   / f"test_forged_{slug}.py"
        _TESTS_DIR.mkdir(parents=True, exist_ok=True)

        action_path.write_text(module_src, encoding="utf-8")
        test_path.write_text(test_src,   encoding="utf-8")

        result = ForgeResult(
            intent=intent,
            module_path=str(action_path),
            test_path=str(test_path),
            diff=module_src,
        )

        # 3. Run the test
        passed, test_out = self._run_test(str(test_path))
        result.test_passed = passed

        if not passed:
            self._status(ui, f"[tool_forge] Generated test failed:\n{test_out[:300]}")
            # Attempt one LLM fix
            fixed_src = self._fix_code(module_src, test_out)
            if fixed_src:
                action_path.write_text(fixed_src, encoding="utf-8")
                result.diff = fixed_src
                passed, test_out = self._run_test(str(test_path))
                result.test_passed = passed

        if not passed:
            self._status(ui, "[tool_forge] Could not produce a passing test — saved but not registering")
            result.success = False
            self._present(result, ui, speak)
            return False

        result.success = True

        # 4. Auto-apply or ask
        if cfg.get("auto_apply", False):
            return self._apply(result, ui, speak)

        # Store as pending and present to user
        self._pending_forge[intent] = result
        self._present(result, ui, speak)
        return False  # not yet applied

    # ── Self-healing ──────────────────────────────────────────────────────────

    def _heal(self, intent: str, module_name: str, error: str, ui, speak) -> bool:
        self._status(ui, f"[tool_forge] Handler '{module_name}' threw — diagnosing…")

        # Read current source
        try:
            mod_path = Path(sys.modules[module_name].__file__)
            src = mod_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[ToolForge] Can't read module '{module_name}': {e}")
            return False

        patched = self._patch_code(src, error)
        if not patched:
            return False

        result = ForgeResult(
            intent=intent,
            module_path=str(mod_path),
            test_path="",
            diff=self._unified_diff(src, patched),
            success=True,
        )

        # Write and ask
        cfg = _load_config()
        if cfg.get("auto_apply", False):
            mod_path.write_text(patched, encoding="utf-8")
            self._hot_reload(module_name)
            self._status(ui, f"[tool_forge] Patched and reloaded '{module_name}'")
            return True

        # Store patched source in diff field for apply step
        result.diff = patched
        self._pending_forge[intent] = result
        self._present(result, ui, speak, healing=True)
        return False

    # ── LLM calls ─────────────────────────────────────────────────────────────

    def _generate(self, intent: str, parameters: dict) -> tuple[str, str]:
        """Ask LLM to generate action module + pytest test. Returns (module_src, test_src)."""
        param_str = json.dumps(parameters, indent=2) if parameters else "{}"
        prompt = f"""You are generating a new Python action module for the Sam voice AI agent.

Intent name: {intent}
Parameters provided: {param_str}

Write TWO things:

1. A Python module `actions/forged_{intent}.py` that:
   - Has a top-level function `run(parameters: dict, ui=None, speak=None) -> str`
   - Implements the intent in a simple, safe way
   - Returns a short result string
   - Handles exceptions gracefully
   - Has no external dependencies beyond the Python standard library (unless essential)

2. A pytest test file that:
   - Imports `run` from the module
   - Has at least one test that calls `run({{}})` and asserts the return is a non-empty string
   - Does NOT require real services (mock if needed)

Reply with ONLY valid JSON in this exact shape:
{{
  "module": "<full Python source for the action module>",
  "test": "<full Python source for the test file>"
}}
"""
        try:
            from llm.manager import get_manager
            mgr = get_manager()
            raw = mgr.complete_sync(
                prompt,
                system="Output only valid JSON. No markdown fences.",
                model_tier="local",
            )
            raw = raw.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).replace("```", "").strip()
            data = json.loads(raw)
            return data.get("module", ""), data.get("test", "")
        except Exception as e:
            logger.warning(f"[ToolForge] Generate LLM call failed: {e}")
            return "", ""

    def _fix_code(self, src: str, test_output: str) -> str:
        """Ask LLM to fix failing code given test output."""
        prompt = f"""This Python action module has a failing test.

Current source:
```python
{src[:2000]}
```

Test failure output:
```
{test_output[:1000]}
```

Return ONLY the corrected Python source for the module. No JSON, no markdown fences.
"""
        try:
            from llm.manager import get_manager
            raw = get_manager().complete_sync(prompt, model_tier="local")
            raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE).replace("```", "").strip()
            return raw if raw else ""
        except Exception:
            return ""

    def _patch_code(self, src: str, error: str) -> str:
        """Ask LLM to patch existing source given an error message."""
        prompt = f"""This Python module has an error at runtime.

Error:
```
{error[:800]}
```

Source:
```python
{src[:2500]}
```

Return ONLY the corrected Python source. No JSON, no markdown fences.
"""
        try:
            from llm.manager import get_manager
            raw = get_manager().complete_sync(prompt, model_tier="local")
            raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE).replace("```", "").strip()
            return raw if raw else ""
        except Exception:
            return ""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_test(self, test_path: str) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_path, "-x", "-q", "--tb=short"],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path(__file__).parent.parent),
            )
            passed = result.returncode == 0
            return passed, (result.stdout + result.stderr)[:800]
        except Exception as e:
            return False, str(e)

    def _apply(self, result: ForgeResult, ui, speak) -> bool:
        """Register the capability and hot-reload."""
        try:
            # Determine module name from path
            action_path = Path(result.module_path)
            mod_name = f"actions.{action_path.stem}"

            # If patching existing module, write patched source
            if result.diff and not result.test_passed and result.success:
                action_path.write_text(result.diff, encoding="utf-8")

            # Hot-reload
            self._hot_reload(mod_name)

            # Register capability
            self._register_capability(result.intent, mod_name, action_path)

            result.applied = True
            msg = f"New tool for '{result.intent}' is loaded and ready."
            self._status(ui, f"[tool_forge] {msg}")
            if speak:
                try:
                    speak(msg, ui, blocking=False)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.warning(f"[ToolForge] Apply failed: {e}")
            return False

    def _hot_reload(self, module_name: str):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)

    def _register_capability(self, intent: str, mod_name: str, action_path: Path):
        try:
            from core.capabilities import REGISTRY, Capability
            if not any(c.name == intent for c in REGISTRY):
                REGISTRY.append(Capability(
                    name=intent,
                    description=f"Auto-forged handler for '{intent}'",
                    intents=[intent],
                    handler=f"_handle_{intent}",
                    status="wip",
                    tags=["forged"],
                ))
                logger.info(f"[ToolForge] Registered capability '{intent}'")
        except Exception as e:
            logger.warning(f"[ToolForge] Capability registration failed: {e}")

        # Wire into dispatch table in handlers.py
        try:
            from intents import handlers as _h
            if not hasattr(_h, f"_handle_{intent}"):
                def _forged_handler(params, resp, ui, temp_memory, **kw):
                    try:
                        mod = importlib.import_module(mod_name)
                        result = mod.run(params or {}, ui=ui, speak=None)
                        if ui:
                            ui.append_output(f"[{intent}] {result}", "info")
                    except Exception as e:
                        if ui:
                            ui.append_output(f"[{intent}] error: {e}", "error")
                setattr(_h, f"_handle_{intent}", _forged_handler)
                # Add to dispatch table
                if hasattr(_h, "_DISPATCH_TABLE") and isinstance(_h._DISPATCH_TABLE, dict):
                    _h._DISPATCH_TABLE[intent] = _forged_handler
        except Exception as e:
            logger.warning(f"[ToolForge] Handler injection failed: {e}")

    def _present(self, result: ForgeResult, ui, speak, healing: bool = False):
        verb = "patched" if healing else "built"
        if result.success:
            msg = (
                f"I {verb} a new tool for '{result.intent}'. "
                f"{'Tests passed. ' if result.test_passed else ''}"
                f"Say 'apply it' to load it."
            )
        else:
            msg = f"I tried to forge '{result.intent}' but couldn't produce passing tests. Saved to {result.module_path} for review."

        self._status(ui, f"[tool_forge] {msg}")
        if speak:
            try:
                speak(msg, ui, blocking=False)
            except Exception:
                pass

        # Show abbreviated diff in UI
        if ui and result.diff:
            preview = result.diff[:600]
            try:
                ui.append_output(f"[tool_forge preview]\n{preview}", "code")
            except Exception:
                pass

        # Register a PendingAction so "apply it" / "confirm_action" triggers the apply
        if result.success:
            try:
                from conversation_state import controller, PendingAction
                forge_result = result

                def _do_apply():
                    self.apply_pending(forge_result.intent, ui=ui, speak=speak)

                controller.set_pending(PendingAction(
                    description=f"Apply forged tool for '{result.intent}'",
                    callback=_do_apply,
                ))
            except Exception as e:
                logger.debug(f"[ToolForge] Could not set PendingAction: {e}")

    @staticmethod
    def _unified_diff(old: str, new: str) -> str:
        import difflib
        lines = list(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="original",
            tofile="patched",
            n=3,
        ))
        return "".join(lines[:60])

    @staticmethod
    def _status(ui, msg: str):
        logger.info(msg)
        if ui:
            try:
                ui.append_output(msg, "info")
            except Exception:
                pass


# Singleton
tool_forge = ToolForge()
