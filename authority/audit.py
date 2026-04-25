"""
Audit Trail — Logs every tool execution decision to SQLite.
Ported from Jarvis src/authority/audit.ts
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

import aiosqlite

from vault.schema import DB_PATH

AuthorityDecisionType = Literal["allowed", "denied", "approval_required"]


@dataclass
class AuditEntry:
    id: str
    agent_id: str
    agent_name: str
    tool_name: str
    action_category: str
    authority_decision: AuthorityDecisionType
    approval_id: Optional[str]
    executed: bool
    execution_time_ms: Optional[int]
    created_at: str


def _row_to_entry(row: dict) -> AuditEntry:
    return AuditEntry(
        id=row["id"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        tool_name=row["tool_name"],
        action_category=row["action_category"],
        authority_decision=row["authority_decision"],
        approval_id=row.get("approval_id"),
        executed=bool(row["executed"]),
        execution_time_ms=row.get("execution_time_ms"),
        created_at=row["created_at"],
    )


class AuditTrail:
    async def log(
        self,
        *,
        agent_id: str,
        agent_name: str,
        tool_name: str,
        action_category: str,
        authority_decision: AuthorityDecisionType,
        approval_id: Optional[str] = None,
        executed: bool = False,
        execution_time_ms: Optional[int] = None,
    ) -> AuditEntry:
        entry_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                """INSERT INTO audit_log
                   (id, agent_id, agent_name, tool_name, action_category,
                    authority_decision, approval_id, executed, execution_time_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, agent_id, agent_name, tool_name, action_category,
                 authority_decision, approval_id, 1 if executed else 0,
                 execution_time_ms, now),
            )
            await db.commit()

        return AuditEntry(
            id=entry_id, agent_id=agent_id, agent_name=agent_name,
            tool_name=tool_name, action_category=action_category,
            authority_decision=authority_decision, approval_id=approval_id,
            executed=executed, execution_time_ms=execution_time_ms, created_at=now,
        )

    async def query(
        self,
        *,
        agent_id: str = "",
        action: str = "",
        tool: str = "",
        decision: str = "",
        since: str = "",
        limit: int = 100,
    ) -> list[AuditEntry]:
        conditions, values = [], []
        if agent_id:
            conditions.append("agent_id = ?"); values.append(agent_id)
        if action:
            conditions.append("action_category = ?"); values.append(action)
        if tool:
            conditions.append("tool_name = ?"); values.append(tool)
        if decision:
            conditions.append("authority_decision = ?"); values.append(decision)
        if since:
            conditions.append("created_at >= ?"); values.append(since)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.append(limit)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT ?",
                values,
            )
            rows = await cur.fetchall()
        return [_row_to_entry(dict(r)) for r in rows]

    async def get_stats(self, since: str = "") -> dict:
        where = f"WHERE created_at >= '{since}'" if since else ""

        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row

            cur = await db.execute(
                f"SELECT authority_decision, COUNT(*) as count FROM audit_log {where} GROUP BY authority_decision"
            )
            totals = await cur.fetchall()

            cur2 = await db.execute(
                f"SELECT action_category, COUNT(*) as count FROM audit_log {where} GROUP BY action_category"
            )
            categories = await cur2.fetchall()

        stats = {"total": 0, "allowed": 0, "denied": 0, "approval_required": 0, "by_category": {}}
        for row in totals:
            stats["total"] += row["count"]
            key = row["authority_decision"]
            if key in stats:
                stats[key] = row["count"]
        for row in categories:
            stats["by_category"][row["action_category"]] = row["count"]
        return stats
