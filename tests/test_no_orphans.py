"""
CI gate: every intent in core/capabilities.REGISTRY must be routable.

Checks:
  1. Every canonical intent in INTENT_MAP is present in _DISPATCH_TABLE
     OR is handled by skills.loader (skill: handler prefix).
  2. No intent in INTENT_MAP maps to a handler name that doesn't exist in
     intents.handlers (for non-skill handlers).
  3. The registry has no duplicate intent strings across capabilities.
"""

import pytest


def test_no_duplicate_intents_in_registry():
    from core.capabilities import REGISTRY
    seen = {}
    for cap in REGISTRY:
        for intent in cap.intents:
            assert intent not in seen, (
                f"Duplicate intent '{intent}' in '{cap.name}' and '{seen[intent]}'"
            )
            seen[intent] = cap.name


def test_all_registry_intents_routable():
    from core.capabilities import REGISTRY, INTENT_MAP
    from intents.handlers import _DISPATCH_TABLE

    skill_caps = {cap.name for cap in REGISTRY if cap.handler.startswith("skill:")}
    unroutable = []

    for intent, cap in INTENT_MAP.items():
        if cap.handler.startswith("skill:"):
            # Skill routing is dynamic — skip static check
            continue
        if intent not in _DISPATCH_TABLE:
            unroutable.append((intent, cap.name))

    assert not unroutable, (
        f"Intents not in _DISPATCH_TABLE:\n"
        + "\n".join(f"  {i!r}  (from capability '{c}')" for i, c in unroutable)
    )


def test_all_non_skill_handlers_exist():
    from core.capabilities import REGISTRY
    import intents.handlers as _h

    missing = []
    for cap in REGISTRY:
        if not cap.handler or cap.handler.startswith("skill:"):
            continue
        if not hasattr(_h, cap.handler):
            missing.append((cap.name, cap.handler))

    assert not missing, (
        "Capabilities reference handler functions that don't exist in intents/handlers.py:\n"
        + "\n".join(f"  capability '{n}' → {h!r}" for n, h in missing)
    )
