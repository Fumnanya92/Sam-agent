"""
Approval Manager — Lifecycle of approval requests persisted in SQLite.
Ported from Jarvis src/authority/approval.ts
"""

from __future__ import annotations
import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

import aiosqlite

from vault.schema import DB_PATH

ApprovalStatus = Literal["pending", "approved", "denied", "expired", "executed"]
ApprovalUrgency = Literal["urgent", "normal"]


@dataclass
class ApprovalRequest:
    id: str
    agent_id: str
    agent_name: str
    tool_name: str
    tool_arguments: str      # JSON string
    action_category: str
    urgency: ApprovalUrgency
    reason: str
    context: str
    status: ApprovalStatus
    decided_at: Optional[str]
    decided_by: Optional[str]
    executed_at: Optional[str]
    execution_result: Optional[str]
    created_at: str


def _row_to_request(row: dict) -> ApprovalRequest:
    return ApprovalRequest(**{k: row[k] for k in ApprovalRequest.__dataclass_fields__})


class ApprovalManager:
    async def create_request(
        self,
        *,
        agent_id: str,
        agent_name: str,
        tool_name: str,
        tool_arguments: dict,
        action_category: str,
        urgency: ApprovalUrgency = "normal",
        reason: str,
        context: str = "",
    ) -> ApprovalRequest:
        req_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        tool_args = json.dumps(tool_arguments)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """INSERT INTO approval_requests
                   (id, agent_id, agent_name, tool_name, tool_arguments,
                    action_category, urgency, reason, context, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (req_id, agent_id, agent_name, tool_name, tool_args,
                 action_category, urgency, reason, context, now),
            )
            await db.commit()

        return ApprovalRequest(
            id=req_id, agent_id=agent_id, agent_name=agent_name,
            tool_name=tool_name, tool_arguments=tool_args,
            action_category=action_category, urgency=urgency,
            reason=reason, context=context, status="pending",
            decided_at=None, decided_by=None,
            executed_at=None, execution_result=None, created_at=now,
        )

    async def get(self, request_id: str) -> Optional[ApprovalRequest]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
            row = await cur.fetchone()
        return _row_to_request(dict(row)) if row else None

    async def find_by_prefix(self, prefix: str) -> Optional[ApprovalRequest]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM approval_requests WHERE id LIKE ? AND status = 'pending'",
                (f"{prefix}%",),
            )
            row = await cur.fetchone()
        return _row_to_request(dict(row)) if row else None

    async def approve(self, request_id: str, decided_by: str) -> Optional[ApprovalRequest]:
        now = datetime.utcnow().isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cur = await db.execute(
                "UPDATE approval_requests SET status='approved', decided_at=?, decided_by=? WHERE id=? AND status='pending'",
                (now, decided_by, request_id),
            )
            await db.commit()
            if cur.rowcount == 0:
                return None
        return await self.get(request_id)

    async def deny(self, request_id: str, decided_by: str) -> Optional[ApprovalRequest]:
        now = datetime.utcnow().isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cur = await db.execute(
                "UPDATE approval_requests SET status='denied', decided_at=?, decided_by=? WHERE id=? AND status='pending'",
                (now, decided_by, request_id),
            )
            await db.commit()
            if cur.rowcount == 0:
                return None
        return await self.get(request_id)

    async def mark_executed(self, request_id: str, result: str) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "UPDATE approval_requests SET status='executed', executed_at=?, execution_result=? WHERE id=?",
                (now, result, request_id),
            )
            await db.commit()

    async def get_pending(self) -> list[ApprovalRequest]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM approval_requests WHERE status='pending' ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
        return [_row_to_request(dict(r)) for r in rows]

    async def get_history(
        self,
        *,
        limit: int = 50,
        action: str = "",
        agent_id: str = "",
        status: str = "",
    ) -> list[ApprovalRequest]:
        conditions, values = [], []
        if action:
            conditions.append("action_category = ?"); values.append(action)
        if agent_id:
            conditions.append("agent_id = ?"); values.append(agent_id)
        if status:
            conditions.append("status = ?"); values.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.append(limit)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                f"SELECT * FROM approval_requests {where} ORDER BY created_at DESC LIMIT ?",
                values,
            )
            rows = await cur.fetchall()
        return [_row_to_request(dict(r)) for r in rows]

    async def expire_old(self, max_age_seconds: int = 3600) -> int:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(seconds=max_age_seconds)).isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cur = await db.execute(
                "UPDATE approval_requests SET status='expired' WHERE status='pending' AND created_at < ?",
                (cutoff,),
            )
            await db.commit()
        return cur.rowcount
