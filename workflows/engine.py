"""
Workflow Engine — trigger-based automation with node execution.
Ported from Jarvis src/workflows/engine.ts + executor.ts

Supports:
  - Manual triggers (run on demand)
  - Cron triggers (scheduled via asyncio)
  - Sequential + parallel node execution
  - HTTP, Python-code, LLM, notify node types
  - Retry with exponential backoff

Usage:
    from workflows.engine import WorkflowEngine
    engine = WorkflowEngine(llm_manager)
    await engine.run_workflow(workflow_id)
"""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal, Optional

import aiosqlite

from vault.schema import DB_PATH

logger = logging.getLogger("sam.workflows")

ExecutionStatus = Literal["running", "completed", "failed", "cancelled"]
StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]


@dataclass
class NodeResult:
    node_id: str
    node_type: str
    status: StepStatus
    output: Any = None
    error: str = ""
    duration_ms: int = 0


@dataclass
class WorkflowRun:
    id: str
    workflow_id: str
    status: ExecutionStatus
    steps: list[NodeResult] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


class WorkflowEngine:
    def __init__(self, llm_manager=None) -> None:
        self._llm = llm_manager
        self._node_handlers: dict[str, Callable] = {}
        self._register_builtin_nodes()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run_workflow(self, workflow_id: str, trigger_data: dict | None = None) -> WorkflowRun:
        """Load a workflow from DB and execute it."""
        definition = await self._load_definition(workflow_id)
        if not definition:
            raise ValueError(f"Workflow {workflow_id} not found.")

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status="running",
            variables=trigger_data or {},
            started_at=datetime.utcnow().isoformat() + "Z",
        )

        settings = definition.get("settings", {})
        parallelism = settings.get("parallelism", "sequential")
        nodes: list[dict] = definition.get("nodes", [])
        # Filter out trigger nodes — they fired already
        action_nodes = [n for n in nodes if not n.get("type", "").startswith("trigger.")]

        try:
            if parallelism == "parallel":
                results = await asyncio.gather(
                    *[self._execute_node(n, run.variables) for n in action_nodes],
                    return_exceptions=True,
                )
                for r in results:
                    if isinstance(r, Exception):
                        run.steps.append(NodeResult("?", "?", "failed", error=str(r)))
                    else:
                        run.steps.append(r)
            else:
                for node in action_nodes:
                    result = await self._execute_node(node, run.variables)
                    run.steps.append(result)
                    if result.output is not None:
                        run.variables[f"node_{node['id']}_output"] = result.output
                    if result.status == "failed" and settings.get("onError", "stop") == "stop":
                        run.status = "failed"
                        run.error = result.error
                        break

            if run.status != "failed":
                run.status = "completed"
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error(f"[Workflow] Run {run.id} failed: {e}")

        run.completed_at = datetime.utcnow().isoformat() + "Z"
        await self._persist_run(run)
        return run

    async def run_manual(self, workflow_id: str, inputs: dict | None = None) -> WorkflowRun:
        return await self.run_workflow(workflow_id, trigger_data=inputs)

    async def list_workflows(self) -> list[dict]:
        """Return all workflows from the vault."""
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, name, description, trigger_type, execution_count FROM workflows ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    def register_node(self, node_type: str, handler: Callable) -> None:
        """Register a custom node handler: async fn(config, variables) -> Any."""
        self._node_handlers[node_type] = handler

    # ── Node execution ────────────────────────────────────────────────────────

    async def _execute_node(self, node: dict, variables: dict) -> NodeResult:
        node_id = node.get("id", "?")
        node_type = node.get("type", "unknown")
        config = node.get("config", {})
        retry_policy = node.get("retryPolicy", {"maxRetries": 1, "delayMs": 1000, "backoff": "fixed"})
        max_retries = retry_policy.get("maxRetries", 1)
        delay_ms = retry_policy.get("delayMs", 1000)
        backoff = retry_policy.get("backoff", "fixed")

        handler = self._node_handlers.get(node_type)
        if not handler:
            return NodeResult(node_id, node_type, "skipped", error=f"No handler for {node_type}")

        t0 = asyncio.get_event_loop().time()
        last_error = ""
        for attempt in range(max_retries):
            try:
                output = await handler(config, variables)
                duration = int((asyncio.get_event_loop().time() - t0) * 1000)
                return NodeResult(node_id, node_type, "completed", output=output, duration_ms=duration)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Workflow] Node {node_id} attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep_s = (delay_ms / 1000) * (2 ** attempt if backoff == "exponential" else 1)
                    await asyncio.sleep(sleep_s)

        duration = int((asyncio.get_event_loop().time() - t0) * 1000)
        return NodeResult(node_id, node_type, "failed", error=last_error, duration_ms=duration)

    # ── Built-in node types ───────────────────────────────────────────────────

    def _register_builtin_nodes(self) -> None:
        self._node_handlers.update({
            "action.http_request": self._node_http,
            "action.run_python": self._node_python,
            "action.llm_prompt": self._node_llm,
            "action.notify": self._node_notify,
            "action.log": self._node_log,
            "logic.condition": self._node_condition,
        })

    async def _node_http(self, config: dict, variables: dict) -> dict:
        import aiohttp
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body", None)
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=body) as resp:
                return {"status": resp.status, "body": await resp.text()}

    async def _node_python(self, config: dict, variables: dict) -> Any:
        code = config.get("code", "")
        local_vars = {"variables": variables, "result": None}
        exec(code, {}, local_vars)  # noqa: S102
        return local_vars.get("result")

    async def _node_llm(self, config: dict, variables: dict) -> str:
        if not self._llm:
            return "LLM not configured."
        prompt = config.get("prompt", "")
        tier = config.get("model_tier", "local")
        return await self._llm.complete(prompt, model_tier=tier)

    async def _node_notify(self, config: dict, variables: dict) -> str:
        msg = config.get("message", "Workflow notification")
        logger.info(f"[Workflow notify] {msg}")
        return f"Notified: {msg}"

    async def _node_log(self, config: dict, variables: dict) -> str:
        msg = config.get("message", "")
        logger.info(f"[Workflow log] {msg}")
        return msg

    async def _node_condition(self, config: dict, variables: dict) -> bool:
        expr = config.get("expression", "True")
        return bool(eval(expr, {}, variables))  # noqa: S307

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _load_definition(self, workflow_id: str) -> dict | None:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT nodes FROM workflows WHERE id = ?", (workflow_id,))
            row = await cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row["nodes"])
        except Exception:
            return None

    async def _persist_run(self, run: WorkflowRun) -> None:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "UPDATE workflows SET execution_count = execution_count + 1 WHERE id = ?",
                (run.workflow_id,),
            )
            await db.commit()
