"""
daemon/vault_routes.py — /api/vault/* endpoints for the React dashboard.

Covers:
  GET  /api/vault/conversations/active   — chat history for a channel session
  GET  /api/vault/conversations          — recent conversation entries
  GET  /api/vault/observations           — environment observations feed
  GET  /api/vault/commitments            — kanban task list
  POST /api/vault/commitments            — create task
  PATCH /api/vault/commitments/{id}      — update task
  DELETE /api/vault/commitments/{id}     — delete task
  GET  /api/vault/entities               — knowledge graph entities
  GET  /api/vault/entities/{id}/facts    — facts for an entity
  GET  /api/vault/entities/{id}/relationships — relationships for an entity
  GET  /api/vault/search                 — search entities + facts (returns MemoryProfile[])
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vault.schema import DB_PATH

router = APIRouter()


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def _get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


def _row(row: aiosqlite.Row) -> dict:
    return dict(row)


async def _ensure_tables(db: aiosqlite.Connection) -> None:
    """Create vault tables that may not exist yet."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS commitments (
            id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            what         TEXT NOT NULL,
            when_due     INTEGER,
            context      TEXT DEFAULT '',
            priority     TEXT NOT NULL DEFAULT 'medium',
            status       TEXT NOT NULL DEFAULT 'pending',
            assigned_to  TEXT DEFAULT 'sam',
            created_from TEXT DEFAULT '',
            created_at   INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000),
            completed_at INTEGER,
            result       TEXT DEFAULT '',
            sort_order   INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            type       TEXT NOT NULL DEFAULT 'system',
            data       TEXT NOT NULL DEFAULT '{}',
            processed  INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000)
        )
    """)
    await db.commit()


# ── Conversations ──────────────────────────────────────────────────────────────

@router.get("/api/vault/conversations/active")
async def get_active_conversation(channel: str = "websocket", limit: int = 100):
    """Return recent messages for the active session of a channel."""
    db = await _get_db()
    try:
        # Return the most recent messages from the conversations table
        # Each row is one turn (role + content).
        async with db.execute(
            """
            SELECT id, session_id, role, content, timestamp, tokens_used
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()

        messages = [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["timestamp"],
                "tool_calls": None,
            }
            for r in reversed(rows)
        ]
        return {"channel": channel, "messages": messages}
    finally:
        await db.close()


@router.get("/api/vault/conversations")
async def list_conversations(limit: int = 50):
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT * FROM conversations ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


# ── Observations ───────────────────────────────────────────────────────────────

@router.get("/api/vault/observations")
async def list_observations(limit: int = 30):
    db = await _get_db()
    try:
        await _ensure_tables(db)
        async with db.execute(
            "SELECT * FROM observations ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        result = []
        for r in rows:
            d = _row(r)
            try:
                d["data"] = json.loads(d["data"])
            except Exception:
                pass
            result.append(d)
        return result
    finally:
        await db.close()


# ── Commitments ────────────────────────────────────────────────────────────────

class CommitmentCreate(BaseModel):
    what: str
    when_due: Optional[int] = None
    context: Optional[str] = ""
    priority: str = "medium"
    status: str = "pending"
    assigned_to: Optional[str] = "sam"
    created_from: Optional[str] = ""
    sort_order: int = 0


class CommitmentUpdate(BaseModel):
    what: Optional[str] = None
    when_due: Optional[int] = None
    context: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    result: Optional[str] = None
    sort_order: Optional[int] = None
    completed_at: Optional[int] = None


@router.get("/api/vault/commitments")
async def list_commitments(status: str = "", priority: str = "", limit: int = 200):
    db = await _get_db()
    try:
        await _ensure_tables(db)
        filters, params = [], []
        if status:
            filters.append("status = ?")
            params.append(status)
        if priority:
            filters.append("priority = ?")
            params.append(priority)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)
        async with db.execute(
            f"SELECT * FROM commitments {where} ORDER BY sort_order ASC, created_at DESC LIMIT ?",
            params,
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


@router.post("/api/vault/commitments", status_code=201)
async def create_commitment(body: CommitmentCreate):
    db = await _get_db()
    try:
        await _ensure_tables(db)
        now = int(time.time() * 1000)
        await db.execute(
            """
            INSERT INTO commitments
              (what, when_due, context, priority, status, assigned_to, created_from, created_at, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.what, body.when_due, body.context, body.priority,
                body.status, body.assigned_to, body.created_from, now, body.sort_order,
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM commitments ORDER BY rowid DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
        return _row(row)
    finally:
        await db.close()


@router.patch("/api/vault/commitments/{commitment_id}")
async def update_commitment(commitment_id: str, body: CommitmentUpdate):
    db = await _get_db()
    try:
        await _ensure_tables(db)
        fields = body.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        # Auto-set completed_at when status transitions to completed
        if fields.get("status") == "completed" and "completed_at" not in fields:
            fields["completed_at"] = int(time.time() * 1000)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [commitment_id]
        await db.execute(
            f"UPDATE commitments SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM commitments WHERE id = ?", (commitment_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Commitment not found")
        return _row(row)
    finally:
        await db.close()


@router.delete("/api/vault/commitments/{commitment_id}", status_code=204)
async def delete_commitment(commitment_id: str):
    db = await _get_db()
    try:
        await _ensure_tables(db)
        await db.execute("DELETE FROM commitments WHERE id = ?", (commitment_id,))
        await db.commit()
    finally:
        await db.close()


# ── Entities / Knowledge Graph ─────────────────────────────────────────────────

@router.get("/api/vault/entities")
async def list_entities(type: str = "", q: str = "", limit: int = 100):
    db = await _get_db()
    try:
        filters, params = [], []
        if type:
            filters.append("type = ?")
            params.append(type)
        if q:
            filters.append("(name LIKE ? OR description LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)
        async with db.execute(
            f"SELECT * FROM entities {where} ORDER BY name ASC LIMIT ?", params
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


@router.get("/api/vault/entities/{entity_id}/facts")
async def get_entity_facts(entity_id: int):
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT * FROM facts WHERE entity_id = ? ORDER BY created_at DESC",
            (entity_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


@router.get("/api/vault/entities/{entity_id}/relationships")
async def get_entity_relationships(entity_id: int):
    db = await _get_db()
    try:
        async with db.execute(
            """
            SELECT r.*, e.name AS to_name, e.type AS to_type
            FROM relationships r
            JOIN entities e ON e.id = r.to_entity_id
            WHERE r.from_entity_id = ?
            ORDER BY r.strength DESC
            """,
            (entity_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


# ── Search — returns MemoryProfile[] ──────────────────────────────────────────

@router.get("/api/vault/search")
async def search_vault(q: str = "", type: str = "", limit: int = 100):
    db = await _get_db()
    try:
        filters, params = [], []
        if type:
            filters.append("e.type = ?")
            params.append(type)
        if q:
            filters.append("(e.name LIKE ? OR e.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)

        async with db.execute(
            f"SELECT * FROM entities e {where} ORDER BY e.name ASC LIMIT ?", params
        ) as cur:
            entities = await cur.fetchall()

        profiles = []
        for entity in entities:
            eid = entity["id"]

            async with db.execute(
                "SELECT * FROM facts WHERE entity_id = ? ORDER BY created_at DESC",
                (eid,),
            ) as cur:
                facts = [_row(r) for r in await cur.fetchall()]

            async with db.execute(
                """
                SELECT r.*, e2.name AS to_name, e2.type AS to_type
                FROM relationships r
                JOIN entities e2 ON e2.id = r.to_entity_id
                WHERE r.from_entity_id = ?
                """,
                (eid,),
            ) as cur:
                rels = [_row(r) for r in await cur.fetchall()]

            profiles.append({
                "entity": _row(entity),
                "facts": facts,
                "relationships": rels,
            })

        return profiles
    finally:
        await db.close()
