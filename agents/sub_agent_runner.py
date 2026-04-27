"""
Sub-agent runner: breaks a complex task into steps and executes them.
Based on Sam's existing agent/executor.py but wired to the role system.
"""

from agents.orchestrator import Orchestrator, AgentTask


class SubAgentRunner:
    MAX_STEPS = 5

    def __init__(self, llm_manager):
        self.orchestrator = Orchestrator(llm_manager)
        self.llm = llm_manager

    async def run(self, goal: str, context: dict = None) -> dict:
        """
        Break goal into steps, execute each with the right agent.
        Returns: {"steps": [...], "result": "...", "success": bool}
        """
        context = context or {}
        steps = await self._plan_steps(goal)
        results = []

        for i, step in enumerate(steps[: self.MAX_STEPS]):
            task = AgentTask(
                task=step,
                context={**context, "step": i + 1, "goal": goal},
            )
            try:
                result = await self.orchestrator.execute(task)
                results.append({"step": step, "result": result, "success": True})
                context["previous_result"] = result
            except Exception as e:
                results.append({"step": step, "error": str(e), "success": False})
                break

        final = (
            results[-1]["result"]
            if results and results[-1].get("success")
            else "Task could not be completed."
        )
        return {
            "steps": results,
            "result": final,
            "success": all(r.get("success") for r in results),
        }

    async def _plan_steps(self, goal: str) -> list:
        """Break goal into max 5 concrete steps using local LLM."""
        prompt = f"""Break this goal into at most 5 concrete steps. One step per line. No numbering or bullets.

Goal: {goal}"""
        response = await self.llm.complete(prompt, model_tier="local")
        steps = [s.strip() for s in response.strip().split("\n") if s.strip()]
        return steps[: self.MAX_STEPS]
