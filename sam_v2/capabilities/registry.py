"""Capability registry for the Sam v2 intent layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Capability:
    intent: str
    description: str
    action_category: str
    requires_write: bool = False


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.intent] = capability

    def get(self, intent: str) -> Capability | None:
        return self._capabilities.get(intent)

    def list_all(self) -> list[Capability]:
        return sorted(self._capabilities.values(), key=lambda item: item.intent)


def build_default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        Capability(
            intent="capabilities",
            description="List currently migrated Sam v2 capabilities.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="awareness_check",
            description="Truthfully report whether a requested capability currently exists.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="propose_upgrade",
            description="Record an approval-gated upgrade proposal for a missing capability.",
            action_category="write_data",
            requires_write=True,
        )
    )
    registry.register(
        Capability(
            intent="chat",
            description="Fallback conversational response when no actionable intent matches.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="plan_request",
            description="Higher-level request that needs planning or clarification before action.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="create_goal",
            description="Create a new goal record in the workflow store.",
            action_category="write_data",
            requires_write=True,
        )
    )
    registry.register(
        Capability(
            intent="create_task",
            description="Create a simple task record in the storage layer.",
            action_category="write_data",
            requires_write=True,
        )
    )
    registry.register(
        Capability(
            intent="list_goals",
            description="List goals from the workflow store.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="list_projects",
            description="List known projects from the project registry.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="project_details",
            description="Find a known project and describe its stored context.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="create_draft",
            description="Create a pipeline draft document.",
            action_category="write_data",
            requires_write=True,
        )
    )
    registry.register(
        Capability(
            intent="list_workflows",
            description="List workflow draft documents.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="push_changes",
            description="Sensitive git push-style action that always requires approval.",
            action_category="execute_command",
            requires_write=True,
        )
    )
    registry.register(
        Capability(
            intent="inspect_repo",
            description="Repo inspection request that needs a project path or registered project name.",
            action_category="read_data",
        )
    )
    registry.register(
        Capability(
            intent="inspect_project_repo",
            description="Inspect a registered project's repository and report safe repo context.",
            action_category="read_data",
        )
    )
    return registry
