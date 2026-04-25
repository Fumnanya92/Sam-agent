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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from daemon.ws_service import manager as ws_manager
from vault.schema import DB_PATH

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
