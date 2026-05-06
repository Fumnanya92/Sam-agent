"""
Agent orchestrator - decides which specialist handles a task.
Uses local LLM (Ollama) for routing decisions to minimize token cost.
Escalation: if the chosen specialist fails, hierarchy.py picks the next role up.
"""

from dataclasses import dataclass, field
from agents.role_loader import load_roles, Role
from agents.delegation import delegate_to_agent
from agents.hierarchy import get_escalation_path, can_handle
from llm.manager import get_manager
import logging

logger = logging.getLogger("sam.orchestrator")

_MAX_ESCALATIONS = 2  # try original + up to 2 escalation levels


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
        Prefers a role whose can_handle() matches; falls back to LLM routing.
        Returns role_name string.
        """
        # Quick capability-match from hierarchy before spending an LLM call
        for role_name in self.roles:
            if can_handle(role_name, task.task):
                return role_name

        role_names = list(self.roles.keys())
        prompt = f"""You are a task router. Given this task, pick the most suitable specialist.

Task: {task.task}

Available specialists: {', '.join(role_names)}

Reply with ONLY the specialist name, nothing else."""

        response = await self.llm.complete(prompt, model_tier="local")
        role_name = response.strip().lower()

        if role_name not in self.roles:
            role_name = "personal-assistant"

        return role_name

    async def execute(self, task: AgentTask) -> str:
        """Route task to best agent; escalate up the hierarchy on failure."""
        role_name = await self.route(task)
        attempt_chain = [role_name] + get_escalation_path(role_name)

        last_error = None
        for attempt_role in attempt_chain[:1 + _MAX_ESCALATIONS]:
            role = self.roles.get(attempt_role)
            if role is None:
                continue
            try:
                result = await delegate_to_agent(task, role, self.llm)
                if attempt_role != role_name:
                    logger.info(f"[Orchestrator] Escalated '{task.task[:40]}' from {role_name} → {attempt_role}")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[Orchestrator] {attempt_role} failed: {e} — escalating")

        raise RuntimeError(f"All escalation attempts failed for task: {task.task[:60]}") from last_error
