"""
Goal Tracker — OKR-style hierarchical goals with 0.0-1.0 scoring.
Ported from Jarvis src/goals/service.ts + types.ts

Goal levels: objective → key_result → milestone → task → daily_action
Scoring: 0.0-1.0 (0.7+ = on track, <0.4 = critical)

Usage:
    from goals.tracker import GoalTracker
    tracker = GoalTracker()
    goal_id = await tracker.create_goal(title="Ship v2.0", level="objective")
    await tracker.update_score(goal_id, 0.6, "Halfway through milestones")
"""

from __future__ import annotations
import json
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

import aiosqlite

from vault.schema import DB_PATH

logger = logging.getLogger("sam.goals")

GoalLevel = Literal["objective", "key_result", "milestone", "task", "daily_action"]
GoalStatus = Literal["draft", "active", "paused", "completed", "failed", "killed"]
GoalHealth = Literal["on_track", "at_risk", "behind", "critical"]
TimeHorizon = Literal["life", "yearly", "quarterly", "monthly", "weekly", "daily"]


def _score_to_health(score: float) -> GoalHealth:
    if score >= 0.7:
        return "on_track"
    if score >= 0.5:
        return "at_risk"
    if score >= 0.3:
        return "behind"
    return "critical"


class GoalTracker:
    # ── Create ────────────────────────────────────────────────────────────────

    async def create_goal(
        self,
        *,
        title: str,
        description: str = "",
        level: GoalLevel = "task",
        time_horizon: TimeHorizon = "weekly",
        success_criteria: str = "",
        parent_id: Optional[str] = None,
        deadline: Optional[str] = None,
        tags: list[str] | None = None,
    ) -> str:
        goal_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                """INSERT INTO goals
                   (id, parent_id, level, title, description, success_criteria,
                    time_horizon, score, status, health, deadline, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 'active', 'on_track', ?, ?, ?, ?)""",
                (goal_id, parent_id, level, title, description, success_criteria,
                 time_horizon, deadline, json.dumps(tags or []), now, now),
            )
            await db.commit()
        logger.info(f"[Goals] Created {level} goal '{title}' ({goal_id})")
        return goal_id

    # ── Score update ──────────────────────────────────────────────────────────

    async def update_score(self, goal_id: str, score: float, note: str = "") -> None:
        score = max(0.0, min(1.0, score))
        health = _score_to_health(score)
        now = datetime.utcnow().isoformat() + "Z"
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "UPDATE goals SET score=?, health=?, updated_at=? WHERE id=?",
                (score, health, now, goal_id),
            )
            # Log progress entry in documents table as JSON note
            await db.execute(
                """INSERT INTO documents (title, content, type, source, created_at)
                   VALUES (?, ?, 'goal_progress', ?, ?)""",
                (f"Goal progress: {goal_id}", json.dumps({"goal_id": goal_id, "score": score, "note": note}), "goal_tracker", now),
            )
            await db.commit()
        logger.info(f"[Goals] {goal_id} score → {score:.2f} ({health}) — {note}")

    # ── Status ────────────────────────────────────────────────────────────────

    async def complete_goal(self, goal_id: str) -> None:
        await self._set_status(goal_id, "completed", score=1.0)

    async def pause_goal(self, goal_id: str) -> None:
        await self._set_status(goal_id, "paused")

    async def kill_goal(self, goal_id: str) -> None:
        await self._set_status(goal_id, "killed")

    async def _set_status(self, goal_id: str, status: GoalStatus, score: Optional[float] = None) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        if score is not None:
            async with aiosqlite.connect(str(DB_PATH)) as db:
                await db.execute(
                    "UPDATE goals SET status=?, score=?, health=?, updated_at=? WHERE id=?",
                    (status, score, _score_to_health(score), now, goal_id),
                )
                await db.commit()
        else:
            async with aiosqlite.connect(str(DB_PATH)) as db:
                await db.execute(
                    "UPDATE goals SET status=?, updated_at=? WHERE id=?",
                    (status, now, goal_id),
                )
                await db.commit()

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_goals(
        self,
        *,
        status: str = "",
        level: str = "",
        parent_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        conditions, values = [], []
        if status:
            conditions.append("status = ?"); values.append(status)
        if level:
            conditions.append("level = ?"); values.append(level)
        if parent_id is not None:
            conditions.append("parent_id = ?"); values.append(parent_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.append(limit)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                f"SELECT * FROM goals {where} ORDER BY score ASC LIMIT ?", values
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_goal(self, goal_id: str) -> Optional[dict]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
            row = await cur.fetchone()
        return dict(row) if row else None

    # ── Daily check-in ────────────────────────────────────────────────────────

    async def morning_check_in(self, llm_manager=None) -> str:
        """Generate a morning briefing for active goals."""
        goals = await self.list_goals(status="active", limit=10)
        if not goals:
            return "No active goals. A good day to set some new objectives!"

        lines = ["Good morning. Here are your active goals:\n"]
        for g in goals:
            health_emoji = {"on_track": "✅", "at_risk": "⚠️", "behind": "🔶", "critical": "🔴"}.get(g.get("health", "on_track"), "•")
            lines.append(f"{health_emoji} [{g['level']}] {g['title']} — score: {g.get('score', 0):.0%}")

        at_risk = [g for g in goals if g.get("health") in ("at_risk", "behind", "critical")]
        if at_risk:
            lines.append(f"\n{len(at_risk)} goal(s) need attention today.")

        return "\n".join(lines)

    async def evening_review(self) -> str:
        """Summarize goal progress for evening review."""
        goals = await self.list_goals(status="active", limit=10)
        if not goals:
            return "No active goals to review."

        completed_today = [g for g in goals if g.get("score", 0) >= 1.0]
        lines = [f"Evening review — {len(goals)} active goal(s):"]
        for g in goals:
            lines.append(f"  {g['title']}: {g.get('score', 0):.0%}")
        if completed_today:
            lines.append(f"\n{len(completed_today)} goal(s) reached 100% today. Well done.")
        return "\n".join(lines)

    # ── DB migration helper ───────────────────────────────────────────────────

    async def ensure_schema(self) -> None:
        """Add goal columns that may not exist in older schema."""
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cols = {row[1] for row in await (await db.execute("PRAGMA table_info(goals)")).fetchall()}
            extras = {
                "id": "TEXT",
                "parent_id": "TEXT",
                "level": "TEXT DEFAULT 'task'",
                "success_criteria": "TEXT DEFAULT ''",
                "time_horizon": "TEXT DEFAULT 'weekly'",
                "score": "REAL DEFAULT 0.0",
                "health": "TEXT DEFAULT 'on_track'",
                "tags": "TEXT DEFAULT '[]'",
            }
            for col, col_type in extras.items():
                if col not in cols:
                    try:
                        await db.execute(f"ALTER TABLE goals ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass
            await db.commit()
