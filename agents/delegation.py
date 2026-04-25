"""Delegate a task to a specific agent role."""


async def delegate_to_agent(task, role, llm) -> str:
    """
    Build a prompt from the role's context + task, execute with LLM.
    Uses local model by default; cloud only if task.requires_cloud.
    """
    system_prompt = build_system_prompt(role)
    user_prompt = f"""Task: {task.task}

Context: {task.context}

Complete this task."""

    tier = "cloud" if task.requires_cloud else "local"
    return await llm.complete(user_prompt, system=system_prompt, model_tier=tier)


def build_system_prompt(role) -> str:
    """Build system prompt from role definition."""
    parts = [f"You are {role.name}."]
    if role.description:
        parts.append(role.description)
    if role.constraints:
        parts.append(f"Constraints: {'; '.join(role.constraints)}")
    if role.knowledge:
        parts.append(f"Domain knowledge: {'; '.join(role.knowledge[:5])}")
    return " ".join(parts)
