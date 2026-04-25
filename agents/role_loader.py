"""Load agent role definitions from YAML files."""

import yaml
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Role:
    name: str
    description: str = ""
    context: str = ""
    knowledge: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    interaction_style: str = ""
    tools: list = field(default_factory=list)


def load_roles(roles_dir: str = None) -> dict:
    """Load all YAML role files. Returns dict of role_name -> Role."""
    if roles_dir is None:
        # Look in Sam-Agent roles directory first, then fall back to Jarvis
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "roles"),
            r"C:\Users\DELL.COM\Desktop\Darey\Sam-update-Jarvis\roles",
        ]
        roles_dir = next((d for d in candidates if os.path.isdir(d)), None)

    if not roles_dir or not os.path.isdir(roles_dir):
        return _default_roles()

    roles = {}
    for fname in os.listdir(roles_dir):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            path = os.path.join(roles_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    role_name = fname.replace(".yaml", "").replace(".yml", "")
                    roles[role_name] = Role(
                        name=data.get("name", role_name),
                        description=data.get("description", ""),
                        context=data.get("context", ""),
                        knowledge=data.get("knowledge", []),
                        constraints=data.get("constraints", []),
                        interaction_style=data.get("interaction_style", ""),
                        tools=data.get("tools", []),
                    )
            except Exception:
                pass

    if not roles:
        return _default_roles()
    return roles


def _default_roles() -> dict:
    """Minimal built-in roles if no YAML files found."""
    return {
        "personal-assistant": Role(
            name="Personal Assistant",
            description="A helpful personal assistant that handles daily tasks.",
            constraints=["Be concise", "Ask for clarification when needed"],
        ),
        "dev-lead": Role(
            name="Dev Lead",
            description="A senior software engineer focused on code quality and technical decisions.",
            knowledge=["Software architecture", "Code review", "Testing", "Git"],
        ),
        "research-specialist": Role(
            name="Research Specialist",
            description="An analytical researcher who finds and synthesizes information.",
            knowledge=["Web research", "Data analysis", "Report writing"],
        ),
    }
