"""
daemon/api_routes.py — FastAPI REST + WebSocket routes for Sam's daemon.

Routes:
  GET  /health
  GET  /api/tasks
  POST /api/tasks
  PATCH /api/tasks/{id}
  GET  /api/conversations
  POST /api/chat
  GET  /api/settings
  POST /api/settings
  GET  /ws  (WebSocket)
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from daemon.ws_service import manager as ws_manager
from vault.schema import DB_PATH
from authority.engine import AuthorityEngine, AuthorityConfig
from authority.approval import ApprovalManager
from authority.audit import AuditTrail

# Singleton engine — loaded once on startup (config can be updated via API)
_authority_engine = AuthorityEngine(AuthorityConfig())
_approval_manager = ApprovalManager()
_audit_trail = AuditTrail()

logger = logging.getLogger("sam.api_routes")

router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    due_date: Optional[str] = None
    agent: str = ""


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    agent: Optional[str] = None


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class SettingUpdate(BaseModel):
    key: str
    value: str


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_db():
    """Return an open aiosqlite connection. Caller must close."""
    return await aiosqlite.connect(str(DB_PATH))


def _row_to_dict(cursor: aiosqlite.Cursor, row: Any) -> dict:
    """Convert a sqlite3.Row/tuple to a dict using cursor description."""
    if row is None:
        return {}
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Tasks ──────────────────────────────────────────────────────────────────────

@router.get("/api/tasks")
async def list_tasks():
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        tasks = [_row_to_dict(cursor, r) for r in rows]
        return {"tasks": tasks}
    finally:
        await db.close()


@router.post("/api/tasks", status_code=201)
async def create_task(body: TaskCreate):
    db = await _get_db()
    try:
        now = datetime.utcnow().isoformat() + "Z"
        cursor = await db.execute(
            """
            INSERT INTO tasks (title, description, status, priority, due_date, created_at, updated_at, agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (body.title, body.description, body.status, body.priority,
             body.due_date, now, now, body.agent),
        )
        await db.commit()
        task_id = cursor.lastrowid

        # Broadcast to dashboard
        await ws_manager.broadcast("task_event", {
            "action": "created",
            "task_id": task_id,
            "title": body.title,
        })

        return {"id": task_id, "message": "Task created"}
    finally:
        await db.close()


@router.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdate):
    db = await _get_db()
    try:
        # Build SET clause from provided fields only
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = datetime.utcnow().isoformat() + "Z"
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]

        cursor = await db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")

        await ws_manager.broadcast("task_event", {
            "action": "updated",
            "task_id": task_id,
            "changes": body.model_dump(exclude_none=True),
        })

        return {"id": task_id, "message": "Task updated"}
    finally:
        await db.close()


# ── Conversations ──────────────────────────────────────────────────────────────

@router.get("/api/conversations")
async def list_conversations(limit: int = 50):
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        convos = [_row_to_dict(cursor, r) for r in rows]
        return {"conversations": convos}
    finally:
        await db.close()


# ── Chat ───────────────────────────────────────────────────────────────────────

# Module-level chat queue — ai_loop drains this in daemon/main.py
chat_input_queue: asyncio.Queue = asyncio.Queue()


@router.post("/api/chat")
async def post_chat(body: ChatMessage):
    """
    Enqueue a user message for the ai_loop to process.
    Returns a message_id immediately; response arrives via WebSocket.
    """
    message_id = str(uuid.uuid4())
    session_id = body.session_id or "default"

    await chat_input_queue.put({
        "message_id": message_id,
        "session_id": session_id,
        "message": body.message,
    })

    # Persist to conversations table
    db = await _get_db()
    try:
        now = datetime.utcnow().isoformat() + "Z"
        await db.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, "user", body.message, now),
        )
        await db.commit()
    finally:
        await db.close()

    logger.info(f"[CHAT] Queued message {message_id}: {body.message[:60]}")
    return {"message_id": message_id, "status": "queued"}


# ── Settings ───────────────────────────────────────────────────────────────────

@router.get("/api/settings")
async def get_settings():
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT key, value, updated_at FROM settings")
        rows = await cursor.fetchall()
        settings = {r[0]: {"value": r[1], "updated_at": r[2]} for r in rows}
        return {"settings": settings}
    finally:
        await db.close()


@router.post("/api/settings")
async def update_setting(body: SettingUpdate):
    db = await _get_db()
    try:
        now = datetime.utcnow().isoformat() + "Z"
        await db.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (body.key, body.value, now),
        )
        await db.commit()
        return {"key": body.key, "message": "Setting saved"}
    finally:
        await db.close()


# ── Goals routes ───────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    description: str = ""
    level: str = "task"
    time_horizon: str = "weekly"
    success_criteria: str = ""
    parent_id: Optional[str] = None
    deadline: Optional[str] = None
    tags: list = []

class GoalScoreUpdate(BaseModel):
    score: float
    note: str = ""


@router.get("/api/goals")
async def list_goals(status: str = "", level: str = "", limit: int = 50):
    from goals.tracker import GoalTracker
    return {"goals": await GoalTracker().list_goals(status=status, level=level, limit=limit)}

@router.post("/api/goals", status_code=201)
async def create_goal(body: GoalCreate):
    from goals.tracker import GoalTracker
    goal_id = await GoalTracker().create_goal(**body.model_dump())
    return {"id": goal_id}

@router.patch("/api/goals/{goal_id}/score")
async def update_goal_score(goal_id: str, body: GoalScoreUpdate):
    from goals.tracker import GoalTracker
    await GoalTracker().update_score(goal_id, body.score, body.note)
    return {"id": goal_id, "score": body.score}

@router.post("/api/goals/{goal_id}/complete")
async def complete_goal(goal_id: str):
    from goals.tracker import GoalTracker
    await GoalTracker().complete_goal(goal_id)
    return {"id": goal_id, "status": "completed"}


# ── Pipeline routes ─────────────────────────────────────────────────────────────

class DraftCreate(BaseModel):
    title: str
    body: str
    content_type: str = "post"
    tags: list = []


@router.get("/api/pipeline")
async def list_pipeline(stage: str = "", limit: int = 50):
    from pipeline.engine import PipelineEngine
    return {"docs": await PipelineEngine().list_docs(stage=stage, limit=limit)}

@router.post("/api/pipeline", status_code=201)
async def create_draft(body: DraftCreate):
    from pipeline.engine import PipelineEngine
    doc_id = await PipelineEngine().create_draft(**body.model_dump())
    return {"id": doc_id}

@router.post("/api/pipeline/{doc_id}/review")
async def submit_review(doc_id: str):
    from pipeline.engine import PipelineEngine
    await PipelineEngine().submit_for_review(doc_id)
    return {"id": doc_id, "stage": "review"}

@router.post("/api/pipeline/{doc_id}/approve")
async def approve_doc(doc_id: str):
    from pipeline.engine import PipelineEngine
    await PipelineEngine().approve(doc_id)
    return {"id": doc_id, "stage": "approved"}

@router.post("/api/pipeline/{doc_id}/publish")
async def publish_doc(doc_id: str, channel: str = "log"):
    from pipeline.engine import PipelineEngine
    result = await PipelineEngine().publish(doc_id, channel=channel)
    return {"id": doc_id, "result": result}


# ── Workflow routes ─────────────────────────────────────────────────────────────

class WorkflowRun(BaseModel):
    inputs: dict = {}


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, body: WorkflowRun):
    from workflows.engine import WorkflowEngine
    engine = WorkflowEngine()
    run = await engine.run_manual(workflow_id, inputs=body.inputs)
    return {"run_id": run.id, "status": run.status, "steps": len(run.steps), "error": run.error}


# ── Authority / Approval routes ────────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decided_by: str = "user"


@router.get("/api/authority/config")
async def get_authority_config():
    return _authority_engine.config.__dict__


@router.get("/api/authority/pending")
async def get_pending_approvals():
    items = await _approval_manager.get_pending()
    return {"approvals": [vars(a) for a in items]}


@router.post("/api/authority/approve/{request_id}")
async def approve_request(request_id: str, body: ApprovalDecision):
    req = await _approval_manager.approve(request_id, body.decided_by)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found or not pending")
    await ws_manager.broadcast("task_event", {"action": "approval_decided", "id": request_id, "status": "approved"})
    return vars(req)


@router.post("/api/authority/deny/{request_id}")
async def deny_request(request_id: str, body: ApprovalDecision):
    req = await _approval_manager.deny(request_id, body.decided_by)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found or not pending")
    await ws_manager.broadcast("task_event", {"action": "approval_decided", "id": request_id, "status": "denied"})
    return vars(req)


@router.get("/api/authority/audit")
async def get_audit_log(limit: int = 100, decision: str = ""):
    entries = await _audit_trail.query(decision=decision, limit=limit)
    return {"entries": [vars(e) for e in entries]}


@router.get("/api/authority/stats")
async def get_audit_stats():
    return await _audit_trail.get_stats()


# ── Skills ────────────────────────────────────────────────────────────────────

@router.get("/api/skills")
async def list_skills():
    """List all loaded skills (name + description)."""
    from skills.loader import skill_loader
    skill_loader.load()
    return {"skills": skill_loader.list_skills()}


@router.get("/api/skills/triggers")
async def list_skill_triggers():
    """Return all trigger phrases with their mapped intent — for client-side autocomplete."""
    from skills.loader import skill_loader
    skill_loader.load()
    triggers = [{"phrase": p, "intent": i} for p, i in skill_loader.get_trigger_phrases()]
    return {"triggers": triggers}


# ── Personality ────────────────────────────────────────────────────────────────

class FeedbackBody(BaseModel):
    positive: bool


class StyleBody(BaseModel):
    style: str  # concise | balanced | detailed | technical


@router.get("/api/personality")
async def get_personality():
    from personality.model import get_learner
    return await get_learner().get_profile()


@router.post("/api/personality/feedback")
async def post_personality_feedback(body: FeedbackBody):
    from personality.model import get_learner
    await get_learner().record_feedback(body.positive)
    return {"status": "recorded"}


@router.post("/api/personality/style")
async def set_personality_style(body: StyleBody):
    valid = {"concise", "balanced", "detailed", "technical"}
    if body.style not in valid:
        raise HTTPException(status_code=400, detail=f"style must be one of {valid}")
    from personality.model import get_learner
    await get_learner().set_style(body.style)  # type: ignore[arg-type]
    return {"style": body.style}


# ── LLM streaming + stats ─────────────────────────────────────────────────────

@router.get("/api/chat/stream")
async def stream_chat(message: str, session_id: str = "default", system: str = ""):
    """
    Stream a chat response via Server-Sent Events.
    Client receives: data: {"chunk": "..."}\n\n
    Finishes with:  data: [DONE]\n\n
    Personality style instruction is automatically injected into the system prompt.
    """
    from llm.manager import get_manager
    from personality.model import get_learner

    learner = get_learner()
    style_hint = await learner.get_style_instruction()
    effective_system = " ".join(filter(None, [system, style_hint])) or None

    async def generate():
        full_response: list[str] = []
        try:
            async for chunk in get_manager().stream(
                message,
                system=effective_system,
                model_tier="auto",
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as exc:
            logger.error(f"[SSE] stream error: {exc}")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            # Record interaction for personality adaptation (fire-and-forget)
            asyncio.create_task(
                learner.record_interaction(message, sum(len(c) for c in full_response))
            )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/api/llm/stats")
async def get_llm_stats():
    """Return token usage + cost totals for the current daemon session."""
    from llm.manager import session_stats
    return session_stats()


# ── React SPA static file serving ─────────────────────────────────────────────

UI_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "dist")


@router.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(UI_DIST, "index.html"))


@router.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith(("api/", "ws", "health")):
        raise HTTPException(status_code=404, detail="Not found")
    file_path = os.path.join(UI_DIST, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(UI_DIST, "index.html"))


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial connection acknowledgement
        await ws.send_text(json.dumps({
            "type": "system_status",
            "payload": {"status": "connected", "version": "2.0.0"},
        }))

        # Keep the connection alive; messages from client are logged/ignored for now
        while True:
            data = await ws.receive_text()
            logger.debug(f"[WS] Received from client: {data[:120]}")
    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected (WebSocketDisconnect)")
    except Exception as exc:
        logger.warning(f"[WS] Unexpected error: {exc}")
    finally:
        await ws_manager.disconnect(ws)
