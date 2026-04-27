"""
daemon/missing_routes.py — stub routes the React dashboard expects but were missing.

  GET  /api/config              — public config (voice wake engine, etc.)
  GET  /api/config/llm          — LLM provider config
  POST /api/config/llm          — save LLM config
  POST /api/config/llm/test     — test LLM connection
  GET  /api/config/channels     — comms channel config
  POST /api/config/channels     — save channel config
  GET  /api/config/stt          — STT config
  POST /api/config/stt          — save STT config
  GET  /api/config/tts          — TTS config
  POST /api/config/tts          — save TTS config
  POST /api/config/google       — save Google integration config
  GET  /api/health              — system health (memory, uptime, DB)
  GET  /api/agents              — running agent list
  POST /api/agents              — dispatch a new agent task
  GET  /api/agents/tree         — agent hierarchy tree
  GET  /api/agents/specialists  — specialist agent list
  GET  /api/workflows           — workflow list
  POST /api/workflows           — create workflow
  GET  /api/workflows/nodes     — node type catalog
  POST /api/workflows/nl-chat   — NL workflow assistant
  GET  /api/workflows/{id}
  PATCH /api/workflows/{id}
  DELETE /api/workflows/{id}
  POST /api/workflows/{id}/execute
  GET  /api/workflows/{id}/executions
  GET  /api/workflows/{id}/versions
  POST /api/workflows/{id}/versions
  GET  /api/workflows/executions/{exec_id}
"""

from __future__ import annotations

import os
import sys
import time
import json
import psutil
from typing import Any, Optional
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vault.schema import DB_PATH

router = APIRouter()

_START_TIME = time.time()


# ── /api/config ────────────────────────────────────────────────────────────────

@router.get("/api/config")
async def get_public_config():
    """Return public config consumed by the React app on boot."""
    wake_engine = os.getenv("SAM_WAKE_ENGINE", "browser")
    return {
        "voice": {"wake_engine": wake_engine},
        "app_name": "Sam",
        "version": "2.0.0",
        "heartbeat": {
            "interval_minutes": int(os.getenv("SAM_HEARTBEAT_INTERVAL", "5")),
            "active_hours": {"start": 8, "end": 22},
            "aggressiveness": os.getenv("SAM_HEARTBEAT_AGGRESSIVENESS", "moderate"),
        },
    }


@router.get("/api/config/llm")
async def get_llm_config():
    from llm import get_openai_key, OLLAMA_BASE_URL, OLLAMA_MODEL
    return {
        "primary": os.getenv("SAM_LLM_PRIMARY", "openai"),
        "fallback": ["ollama"],
        "anthropic": {
            "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            "has_api_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
        "openai": {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "has_api_key": bool(get_openai_key()),
        },
        "groq": {
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "has_api_key": bool(os.getenv("GROQ_API_KEY")),
        },
        "gemini": {
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            "has_api_key": bool(os.getenv("GEMINI_API_KEY")),
        },
        "ollama": {"base_url": OLLAMA_BASE_URL, "model": OLLAMA_MODEL},
        "openrouter": {
            "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "has_api_key": bool(os.getenv("OPENROUTER_API_KEY")),
        },
    }


class LLMConfigUpdate(BaseModel):
    primary: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None


@router.post("/api/config/llm")
async def save_llm_config(body: LLMConfigUpdate):
    # Persist to api_keys.json
    keys_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    keys: dict = {}
    if keys_path.exists():
        try:
            keys = json.loads(keys_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if body.openai_api_key:
        keys["openai_api_key"] = body.openai_api_key
    if body.anthropic_api_key:
        keys["anthropic_api_key"] = body.anthropic_api_key
    if body.groq_api_key:
        keys["groq_api_key"] = body.groq_api_key
    if body.gemini_api_key:
        keys["gemini_api_key"] = body.gemini_api_key
    keys_path.parent.mkdir(parents=True, exist_ok=True)
    keys_path.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    return {"ok": True}


class LLMTestBody(BaseModel):
    provider: str = "openai"


@router.post("/api/config/llm/test")
async def test_llm_config(body: LLMTestBody):
    try:
        from llm import get_ai_response
        result = get_ai_response("Hello, respond with one word: ready")
        return {"ok": True, "model": body.provider, "response": result.get("text", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/config/channels")
async def get_channels_config():
    return {
        "telegram": {"enabled": bool(os.getenv("TELEGRAM_BOT_TOKEN")), "bot_token": ""},
        "discord": {"enabled": bool(os.getenv("DISCORD_BOT_TOKEN")), "bot_token": ""},
        "whatsapp": {"enabled": False},
    }


class ChannelsUpdate(BaseModel):
    telegram: Optional[dict] = None
    discord: Optional[dict] = None


@router.post("/api/config/channels")
async def save_channels_config(body: ChannelsUpdate):
    return {"ok": True}


@router.get("/api/config/stt")
async def get_stt_config():
    return {
        "engine": os.getenv("SAM_STT_ENGINE", "browser"),
        "language": os.getenv("SAM_STT_LANGUAGE", "en-US"),
        "wake_word": os.getenv("SAM_WAKE_WORD", "hey sam"),
    }


@router.post("/api/config/stt")
async def save_stt_config(body: dict):
    return {"ok": True}


@router.get("/api/config/tts")
async def get_tts_config():
    return {
        "engine": os.getenv("SAM_TTS_ENGINE", "edge"),
        "voice": os.getenv("SAM_TTS_VOICE", "en-US-GuyNeural"),
        "rate": os.getenv("SAM_TTS_RATE", "+0%"),
        "volume": os.getenv("SAM_TTS_VOLUME", "+0%"),
    }


@router.post("/api/config/tts")
async def save_tts_config(body: dict):
    return {"ok": True}


@router.post("/api/config/google")
async def save_google_config(body: dict):
    return {"ok": True}


# ── /api/health ────────────────────────────────────────────────────────────────

@router.get("/api/health")
async def get_health():
    uptime = int(time.time() - _START_TIME)

    # Memory (psutil preferred, fallback to sys)
    try:
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        heap_used = mem.rss
        heap_total = mem.vms if mem.vms > 0 else heap_used * 2
        rss = mem.rss
    except Exception:
        heap_used = heap_total = rss = 0

    # DB size
    db_connected = True
    db_size = 0
    try:
        if DB_PATH.exists():
            db_size = DB_PATH.stat().st_size
    except Exception:
        db_connected = False

    return {
        "uptime": uptime,
        "startedAt": int((_START_TIME) * 1000),
        "services": {
            "llm": "running",
            "tts": "running",
            "stt": "running",
            "websocket": "running",
        },
        "memory": {
            "heapUsed": heap_used,
            "heapTotal": heap_total,
            "rss": rss,
        },
        "database": {
            "connected": db_connected,
            "size": db_size,
        },
    }


# ── /api/agents ────────────────────────────────────────────────────────────────

@router.get("/api/agents")
async def list_agents():
    try:
        from agent.monitor import monitor
        tasks = monitor.get_all_tasks()
        return [
            {
                "id": t.task_id,
                "name": t.name,
                "status": t.status,
                "role": {"name": t.name},
                "output": t.output_lines[-1] if t.output_lines else "",
            }
            for t in tasks
        ]
    except Exception:
        return []


class AgentDispatch(BaseModel):
    task: str
    agent_type: Optional[str] = "general"
    context: Optional[dict] = None


@router.post("/api/agents", status_code=201)
async def dispatch_agent(body: AgentDispatch):
    return {
        "id": f"agent_{int(time.time())}",
        "task": body.task,
        "status": "queued",
        "message": "Agent dispatch queued.",
    }


@router.get("/api/agents/tree")
async def get_agent_tree():
    return {
        "id": "sam",
        "name": "Sam",
        "role": "orchestrator",
        "status": "active",
        "children": [],
    }


@router.get("/api/agents/specialists")
async def list_specialists():
    return {
        "specialists": [
            {"id": "researcher", "name": "Researcher", "status": "available", "specialty": "web search & summarisation"},
            {"id": "coder", "name": "Coder", "status": "available", "specialty": "code writing & review"},
            {"id": "analyst", "name": "Analyst", "status": "available", "specialty": "data analysis"},
        ]
    }


# ── /api/workflows ─────────────────────────────────────────────────────────────

async def _get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


def _row(r: aiosqlite.Row) -> dict:
    return dict(r)


@router.get("/api/workflows")
async def list_workflows():
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT * FROM workflows ORDER BY updated_at DESC"
        ) as cur:
            rows = await cur.fetchall()
        result = []
        for r in rows:
            d = _row(r)
            # Ensure expected fields exist
            d.setdefault("description", "")
            d.setdefault("enabled", d.get("status") == "active")
            d.setdefault("tags", [])
            d.setdefault("current_version", 1)
            d.setdefault("execution_count", d.get("execution_count", 0))
            d.setdefault("last_executed_at", None)
            d.setdefault("last_success_at", None)
            d.setdefault("last_failure_at", None)
            result.append(d)
        return result
    finally:
        await db.close()


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    tags: list = []
    trigger_type: str = "manual"
    trigger_config: dict = {}
    nodes: dict = {}


@router.post("/api/workflows", status_code=201)
async def create_workflow(body: WorkflowCreate):
    import uuid
    db = await _get_db()
    try:
        wf_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        await db.execute(
            """INSERT INTO workflows (id, name, trigger_type, trigger_config, nodes, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (wf_id, body.name, body.trigger_type, json.dumps(body.trigger_config),
             json.dumps(body.nodes), "active" if body.enabled else "inactive"),
        )
        await db.commit()
        return {"id": wf_id, "name": body.name, "status": "active", "created_at": now}
    finally:
        await db.close()


@router.get("/api/workflows/nodes")
async def list_node_catalog():
    return [
        {"type": "trigger", "label": "Trigger", "description": "Starts the workflow"},
        {"type": "action", "label": "Action", "description": "Executes a Sam action"},
        {"type": "condition", "label": "Condition", "description": "Branches based on a condition"},
        {"type": "llm", "label": "LLM Call", "description": "Calls the LLM with a prompt"},
        {"type": "delay", "label": "Delay", "description": "Waits for a duration"},
        {"type": "notify", "label": "Notify", "description": "Sends a notification"},
        {"type": "webhook", "label": "Webhook", "description": "Calls an external URL"},
    ]


class NLChatBody(BaseModel):
    message: str
    context: Optional[dict] = None


@router.post("/api/workflows/nl-chat")
async def workflow_nl_chat(body: NLChatBody):
    return {
        "reply": f"I can help you build that workflow. Could you describe the trigger and actions you want?",
        "suggested_workflow": None,
    }


@router.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    db = await _get_db()
    try:
        async with db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return _row(row)
    finally:
        await db.close()


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[list] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    nodes: Optional[dict] = None


@router.patch("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate):
    db = await _get_db()
    try:
        fields = body.model_dump(exclude_none=True)
        if "enabled" in fields:
            fields["status"] = "active" if fields.pop("enabled") else "inactive"
        if "trigger_config" in fields:
            fields["trigger_config"] = json.dumps(fields["trigger_config"])
        if "nodes" in fields:
            fields["nodes"] = json.dumps(fields["nodes"])
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        fields["updated_at"] = "datetime('now')"
        set_clause = ", ".join(f"{k} = ?" for k in fields if k != "updated_at")
        set_clause += ", updated_at = datetime('now')"
        values = [v for k, v in fields.items() if k != "updated_at"] + [workflow_id]
        await db.execute(f"UPDATE workflows SET {set_clause} WHERE id = ?", values)
        await db.commit()
        async with db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)) as cur:
            row = await cur.fetchone()
        return _row(row) if row else {}
    finally:
        await db.close()


@router.delete("/api/workflows/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str):
    db = await _get_db()
    try:
        await db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        await db.commit()
    finally:
        await db.close()


@router.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str):
    return {"workflow_id": workflow_id, "execution_id": f"exec_{int(time.time())}", "status": "started"}


@router.get("/api/workflows/{workflow_id}/executions")
async def list_executions(workflow_id: str):
    return []


@router.get("/api/workflows/{workflow_id}/versions")
async def list_versions(workflow_id: str):
    return []


@router.post("/api/workflows/{workflow_id}/versions")
async def save_version(workflow_id: str, body: dict):
    return {"workflow_id": workflow_id, "version": 1, "saved_at": int(time.time() * 1000)}


@router.get("/api/workflows/executions/{exec_id}")
async def get_execution(exec_id: str):
    return {"id": exec_id, "status": "completed", "output": {}}
