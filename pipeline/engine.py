"""
Content Pipeline Engine — Draft → Review → Publish flow.
Ported from Jarvis src/pipeline concept.

Stages: draft → review → approved → published | rejected
Content types: post, email, blog, thread, report

Usage:
    from pipeline.engine import PipelineEngine
    engine = PipelineEngine(llm_manager)
    doc_id = await engine.create_draft(title="Q1 Update", content_type="email", body="...")
    await engine.submit_for_review(doc_id)
    await engine.approve(doc_id)
    result = await engine.publish(doc_id)
"""

from __future__ import annotations
import json
import uuid
import logging
from datetime import datetime
from typing import Literal, Optional

import aiosqlite

from vault.schema import DB_PATH

logger = logging.getLogger("sam.pipeline")

ContentStage = Literal["draft", "review", "approved", "published", "rejected", "archived"]
ContentType = Literal["post", "email", "blog", "thread", "report", "script"]


class PipelineEngine:
    def __init__(self, llm_manager=None) -> None:
        self._llm = llm_manager

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_draft(
        self,
        *,
        title: str,
        body: str,
        content_type: ContentType = "post",
        tags: list[str] | None = None,
    ) -> str:
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        meta = json.dumps({
            "stage": "draft",
            "content_type": content_type,
            "tags": tags or [],
            "history": [{"stage": "draft", "at": now}],
        })
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "INSERT INTO documents (title, content, type, source, created_at, embedding) VALUES (?, ?, 'pipeline', ?, ?, NULL)",
                (title, json.dumps({"body": body, "meta": meta}), doc_id, now),
            )
            await db.commit()
        logger.info(f"[Pipeline] Draft '{title}' created ({doc_id})")
        return doc_id

    # ── Stage transitions ──────────────────────────────────────────────────────

    async def submit_for_review(self, doc_id: str) -> None:
        await self._transition(doc_id, "review")

    async def approve(self, doc_id: str) -> None:
        await self._transition(doc_id, "approved")

    async def reject(self, doc_id: str, reason: str = "") -> None:
        await self._transition(doc_id, "rejected", note=reason)

    async def publish(self, doc_id: str, channel: str = "log") -> str:
        doc = await self.get_doc(doc_id)
        if not doc:
            return f"Document {doc_id} not found."
        meta = json.loads(doc.get("meta", "{}"))
        if meta.get("stage") != "approved":
            return f"Cannot publish: document is in stage '{meta.get('stage')}', must be 'approved'."

        body = doc.get("body", "")

        # Dispatch to channel
        result = await self._dispatch(channel, doc.get("title", ""), body)
        await self._transition(doc_id, "published", note=f"channel:{channel}")
        logger.info(f"[Pipeline] {doc_id} published to {channel}")
        return result

    async def improve_with_llm(self, doc_id: str, instruction: str = "Improve this content") -> str:
        if not self._llm:
            return "LLM not configured."
        doc = await self.get_doc(doc_id)
        if not doc:
            return "Document not found."
        body = doc.get("body", "")
        improved = await self._llm.complete(
            f"{instruction}:\n\n{body}",
            system="You are a professional content editor. Return only the improved content, no commentary.",
            model_tier="cloud",
        )
        await self._update_body(doc_id, improved)
        return improved

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_docs(self, stage: str = "", limit: int = 50) -> list[dict]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM documents WHERE type = 'pipeline' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
        docs = []
        for row in rows:
            d = dict(row)
            try:
                payload = json.loads(d.get("content", "{}"))
                meta = json.loads(payload.get("meta", "{}"))
                d["body"] = payload.get("body", "")
                d["stage"] = meta.get("stage", "draft")
                d["content_type"] = meta.get("content_type", "post")
                d["tags"] = meta.get("tags", [])
            except Exception:
                d["stage"] = "unknown"
            if not stage or d.get("stage") == stage:
                docs.append(d)
        return docs

    async def get_doc(self, doc_id: str) -> Optional[dict]:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM documents WHERE source = ? AND type = 'pipeline'", (doc_id,)
            )
            row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            payload = json.loads(d.get("content", "{}"))
            meta = json.loads(payload.get("meta", "{}"))
            d["body"] = payload.get("body", "")
            d["stage"] = meta.get("stage", "draft")
            d["meta"] = payload.get("meta", "{}")
        except Exception:
            pass
        return d

    # ── Private ───────────────────────────────────────────────────────────────

    async def _transition(self, doc_id: str, stage: ContentStage, note: str = "") -> None:
        doc = await self.get_doc(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found.")
        try:
            payload = json.loads(doc.get("content", "{}"))  # type: ignore
            meta = json.loads(payload.get("meta", "{}"))
        except Exception:
            payload, meta = {}, {}

        now = datetime.utcnow().isoformat() + "Z"
        meta["stage"] = stage
        history = meta.get("history", [])
        history.append({"stage": stage, "at": now, "note": note})
        meta["history"] = history
        payload["meta"] = json.dumps(meta)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "UPDATE documents SET content = ? WHERE source = ? AND type = 'pipeline'",
                (json.dumps(payload), doc_id),
            )
            await db.commit()
        logger.info(f"[Pipeline] {doc_id} → {stage}")

    async def _update_body(self, doc_id: str, body: str) -> None:
        doc = await self.get_doc(doc_id)
        if not doc:
            return
        try:
            payload = json.loads(doc.get("content", "{}"))  # type: ignore
        except Exception:
            payload = {}
        payload["body"] = body
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "UPDATE documents SET content = ? WHERE source = ? AND type = 'pipeline'",
                (json.dumps(payload), doc_id),
            )
            await db.commit()

    async def _dispatch(self, channel: str, title: str, body: str) -> str:
        if channel == "log":
            logger.info(f"[Pipeline publish] {title}: {body[:120]}")
            return f"Published to log: {title}"
        if channel == "twitter":
            return f"[Twitter stub] Would tweet: {body[:280]}"
        if channel == "email":
            return f"[Email stub] Would send email: {title}"
        return f"Published to {channel}: {title}"
