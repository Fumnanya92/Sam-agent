"""
Agent orchestrator - decides which specialist handles a task.
Uses local LLM (Ollama) for routing decisions to minimize token cost.
"""

from dataclasses import dataclass, field
from agents.role_loader import load_roles, Role
from agents.delegation import delegate_to_agent
from llm.manager import get_manager


@dataclass
class AgentTask:
    task: str
    context: dict = field(default_factory=dict)
    priority: int = 1  # 1=low, 5=critical
    requires_cloud: bool = False


class Orchestrator:
    def __init__(self, llm_manager=None):
        self.llm = llm_manager or get_manager()
        self.roles = load_roles()  # dict of role_name -> Role

    async def route(self, task: AgentTask) -> str:
        """
        Pick the best specialist role for this task.
        Uses Ollama for routing (cheap, fast).
        Returns role_name string.
        """
        role_names = list(self.roles.keys())
        prompt = f"""You are a task router. Given this task, pick the most suitable specialist.

Task: {task.task}

Available specialists: {', '.join(role_names)}

Reply with ONLY the specialist name, nothing else."""

        # Always use local model for routing
        response = await self.llm.complete(prompt, model_tier="local")
        role_name = response.strip().lower()

        # Validate — fall back to personal-assistant if unknown
        if role_name not in self.roles:
            role_name = "personal-assistant"

        return role_name

    async def execute(self, task: AgentTask) -> str:
        """Route task to best agent and execute."""
        role_name = await self.route(task)
        role = self.roles[role_name]
        return await delegate_to_agent(task, role, self.llm)
