"""
Agent hierarchy: CEO -> COS -> Specialist.
Handles escalation when a specialist can't complete a task.
"""

HIERARCHY = {
    "ceo-founder": [],  # top level
    "chief-of-staff": ["ceo-founder"],
    "dev-lead": ["chief-of-staff"],
    "personal-assistant": ["chief-of-staff"],
    "executive-assistant": ["chief-of-staff"],
    "marketing-director": ["chief-of-staff"],
    "system-admin": ["dev-lead"],
    "research-specialist": ["chief-of-staff"],
    "activity-observer": [],
}


def get_escalation_path(role_name: str) -> list:
    """Returns list of roles to escalate to, in order."""
    return HIERARCHY.get(role_name, ["personal-assistant"])


def can_handle(role_name: str, task_type: str) -> bool:
    """Check if a role can handle a task type."""
    role_capabilities = {
        "dev-lead": ["code", "debug", "build", "deploy", "git", "test"],
        "research-specialist": ["research", "search", "analyze", "find"],
        "marketing-director": ["write", "content", "email", "post", "blog"],
        "system-admin": ["system", "server", "config", "install", "process"],
        "personal-assistant": ["schedule", "remind", "calendar", "note"],
        "executive-assistant": ["meeting", "email", "document", "plan"],
    }
    caps = role_capabilities.get(role_name, [])
    return any(cap in task_type.lower() for cap in caps)
