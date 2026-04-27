"""
Authority Engine — Central decision maker for tool execution authorization.
Ported from Jarvis src/authority/engine.ts

Decision order:
  1. Temporary grants (parent escalation) → allow
  2. Per-action overrides for this role   → explicit allow/deny
  3. Context rules (time/tool_name)       → allow/deny/require_approval
  4. Numeric level check                  → deny if below required
  5. Governed category check              → require approval if governed
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from authority.constants import AUTHORITY_REQUIREMENTS, describe_level


ActionCategory = str  # one of the keys in AUTHORITY_REQUIREMENTS

Effect = Literal["allow", "deny", "require_approval"]
EmergencyState = Literal["normal", "paused", "killed"]


@dataclass
class PerActionOverride:
    action: ActionCategory
    allowed: bool
    role_id: str = ""          # empty = global
    requires_approval: bool = False


@dataclass
class ContextRule:
    id: str
    action: ActionCategory
    condition: Literal["time_range", "tool_name", "always"]
    params: dict
    effect: Effect
    description: str


@dataclass
class AuthorityConfig:
    default_level: int = 3
    governed_categories: list[ActionCategory] = field(default_factory=list)
    overrides: list[PerActionOverride] = field(default_factory=list)
    context_rules: list[ContextRule] = field(default_factory=list)
    learning_enabled: bool = True
    suggest_threshold: int = 5
    emergency_state: EmergencyState = "normal"


@dataclass
class AuthorityDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    action_category: ActionCategory
    context_rule: str = ""


class AuthorityEngine:
    def __init__(self, config: AuthorityConfig | None = None):
        self.config = config or AuthorityConfig()
        # agent_id -> list of granted ActionCategory strings
        self._temporary_grants: dict[str, list[ActionCategory]] = {}

    def check(
        self,
        *,
        agent_id: str,
        agent_level: int,
        role_id: str,
        tool_name: str,
        action_category: ActionCategory,
    ) -> AuthorityDecision:
        # Emergency kill — deny everything
        if self.config.emergency_state == "killed":
            return AuthorityDecision(False, False, "System is in emergency kill state.", action_category)
        if self.config.emergency_state == "paused":
            return AuthorityDecision(False, False, "System is paused — all actions suspended.", action_category)

        # 1. Temporary grants
        if action_category in self._temporary_grants.get(agent_id, []):
            return AuthorityDecision(True, False, "Temporarily granted by parent agent.", action_category)

        # 2. Per-action overrides
        override = self._find_override(action_category, role_id)
        if override is not None:
            if not override.allowed:
                return AuthorityDecision(False, False, f"Explicitly denied by override for '{role_id or 'global'}'.", action_category)
            if override.requires_approval:
                return AuthorityDecision(True, True, f"Override requires approval for {action_category}.", action_category)
            return AuthorityDecision(True, False, f"Explicitly allowed by override for '{role_id or 'global'}'.", action_category)

        # 3. Context rules
        rule = self._eval_context_rules(action_category, tool_name)
        if rule is not None:
            if rule.effect == "deny":
                return AuthorityDecision(False, False, rule.description, action_category, rule.id)
            if rule.effect == "require_approval":
                return AuthorityDecision(True, True, rule.description, action_category, rule.id)
            if rule.effect == "allow":
                return AuthorityDecision(True, False, rule.description, action_category, rule.id)

        # 4. Numeric level check
        effective = max(agent_level, self.config.default_level)
        required = AUTHORITY_REQUIREMENTS.get(action_category, 5)
        if effective < required:
            return AuthorityDecision(
                False, False,
                f"Level {effective} below required {required} for {action_category}.",
                action_category,
            )

        # 5. Governed category — level ok but needs approval
        if action_category in self.config.governed_categories:
            return AuthorityDecision(True, True, f"{action_category} is governed and requires user approval.", action_category)

        return AuthorityDecision(True, False, f"Level {effective} meets requirement {required}.", action_category)

    # ── Temporary grants ──────────────────────────────────────────────────────

    def grant_temporary(self, agent_id: str, categories: list[ActionCategory]) -> None:
        self._temporary_grants.setdefault(agent_id, [])
        for cat in categories:
            if cat not in self._temporary_grants[agent_id]:
                self._temporary_grants[agent_id].append(cat)

    def revoke_temporary(self, agent_id: str) -> None:
        self._temporary_grants.pop(agent_id, None)

    # ── Config management ─────────────────────────────────────────────────────

    def add_override(self, override: PerActionOverride) -> None:
        self.remove_override(override.action, override.role_id)
        self.config.overrides.append(override)

    def remove_override(self, action: ActionCategory, role_id: str = "") -> None:
        self.config.overrides = [
            o for o in self.config.overrides
            if not (o.action == action and o.role_id == role_id)
        ]

    def add_context_rule(self, rule: ContextRule) -> None:
        self.config.context_rules.append(rule)

    def remove_context_rule(self, rule_id: str) -> None:
        self.config.context_rules = [r for r in self.config.context_rules if r.id != rule_id]

    def set_emergency_state(self, state: EmergencyState) -> None:
        self.config.emergency_state = state

    def describe_rules(self, agent_level: int, role_id: str) -> str:
        effective = max(agent_level, self.config.default_level)
        lines = [
            f"Authority level: {effective}/10 — {describe_level(effective)}",
        ]
        if self.config.governed_categories:
            lines.append("\nActions requiring approval:")
            for cat in self.config.governed_categories:
                lines.append(f"  - {cat}")
        role_overrides = [o for o in self.config.overrides if not o.role_id or o.role_id == role_id]
        if role_overrides:
            lines.append("\nOverrides:")
            for o in role_overrides:
                scope = f"[{o.role_id}]" if o.role_id else "[global]"
                status = ("allowed with approval" if o.requires_approval else "always allowed") if o.allowed else "denied"
                lines.append(f"  - {o.action}: {status} {scope}")
        return "\n".join(lines)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_override(self, action: ActionCategory, role_id: str) -> PerActionOverride | None:
        role_specific = next(
            (o for o in self.config.overrides if o.action == action and o.role_id == role_id),
            None,
        )
        if role_specific:
            return role_specific
        return next(
            (o for o in self.config.overrides if o.action == action and not o.role_id),
            None,
        )

    def _eval_context_rules(self, action: ActionCategory, tool_name: str) -> ContextRule | None:
        for rule in self.config.context_rules:
            if rule.action != action:
                continue
            if rule.condition == "always":
                return rule
            if rule.condition == "time_range":
                hour = datetime.now().hour
                start = rule.params.get("start_hour", 0)
                end = rule.params.get("end_hour", 24)
                if start <= hour < end:
                    return rule
            if rule.condition == "tool_name":
                pattern = rule.params.get("tool_name", "")
                if pattern and (tool_name == pattern or tool_name.startswith(pattern)):
                    return rule
        return None
