# memory/memory_manager.py
import asyncio
import json
import logging
import os
from datetime import datetime
from threading import Lock
from typing import Any

MEMORY_PATH = "memory/memory.json"
_lock = Lock()

logger = logging.getLogger("sam.memory_manager")

# ── SQLite persistence helpers (Phase 1 addition) ─────────────────────────────
# These functions extend the existing JSON memory with an SQLite mirror.
# The JSON memory remains the primary store; SQLite adds durability + queryability.

def _get_db_path():
    """Return the DB path from vault config (lazy import to avoid circular deps)."""
    try:
        from vault.schema import DB_PATH
        return DB_PATH
    except Exception:
        from pathlib import Path
        return Path.home() / ".sam" / "sam.db"


def save_to_db(conversation_entry: dict) -> None:
    """
    Write a conversation entry to the SQLite messages table.

    Expected keys in conversation_entry:
        role     (str)  — "user" | "assistant" | "system"
        content  (str)  — message text
        session_id (str, optional)
        metadata (dict, optional)

    Falls back silently if aiosqlite / the DB is unavailable.
    """
    try:
        import aiosqlite  # noqa: F401 — confirm import works
    except ImportError:
        logger.debug("[memory] aiosqlite not available — skipping DB write")
        return

    async def _write():
        db_path = _get_db_path()
        try:
            import aiosqlite as _aio
            async with _aio.connect(str(db_path)) as db:
                now = datetime.utcnow().isoformat() + "Z"
                role = conversation_entry.get("role", "user")
                content = conversation_entry.get("content", "")
                session_id = conversation_entry.get("session_id", "default")
                metadata = json.dumps(conversation_entry.get("metadata") or {})

                # Insert into conversations (top-level session record)
                cursor = await db.execute(
                    "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, now),
                )
                conv_id = cursor.lastrowid

                # Insert into messages (detailed turn record)
                await db.execute(
                    "INSERT INTO messages (conversation_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                    (conv_id, role, content, now, metadata),
                )
                await db.commit()
        except Exception as exc:
            logger.warning(f"[memory] DB write failed: {exc}")

    # Fire-and-forget: run in current event loop if available, else skip
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_write())
        else:
            loop.run_until_complete(_write())
    except RuntimeError:
        # No event loop in this thread (e.g. sync context) — skip DB write
        logger.debug("[memory] No event loop for DB write — skipping")


def load_history_from_db(limit: int = 50) -> list[dict]:
    """
    Read the most recent `limit` messages from SQLite synchronously.

    Returns a list of dicts with keys: id, role, content, timestamp, metadata.
    Returns an empty list if the DB is unavailable or the table doesn't exist.
    """
    try:
        import sqlite3
        db_path = _get_db_path()
        if not db_path.exists():
            return []

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT id, role, content, timestamp, metadata FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            result = []
            for row in reversed(rows):  # chronological order
                entry: dict[str, Any] = dict(row)
                try:
                    entry["metadata"] = json.loads(entry.get("metadata") or "{}")
                except Exception:
                    entry["metadata"] = {}
                result.append(entry)
            return result
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(f"[memory] DB read failed: {exc}")
        return []


def _empty_memory() -> dict:
    """Return an empty memory structure."""
    return {
        "identity": {},
        "preferences": {},
        "relationships": {},
        "emotional_state": {},
        "goals": {},
        "projects": {},
        "tasks": {},
        "automation_preferences": {},
        "daily_state": {
            "last_briefing_date": {}
        }
    }


def load_memory() -> dict:
    """Load memory from disk, return empty if not exists or invalid."""
    if not os.path.exists(MEMORY_PATH):
        return _empty_memory()

    with _lock:
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return _empty_memory()
        except Exception:
            return _empty_memory()


def save_memory(memory: dict) -> None:
    """Save memory to disk safely."""
    if not isinstance(memory, dict):
        return

    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)

    with _lock:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)


def _recursive_update(target: dict, updates: dict) -> bool:
    """Recursively merge updates into target memory. Returns True if changed."""
    changed = False
    now = datetime.utcnow().isoformat() + "Z"

    for key, value in updates.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue

        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:

            entry = value if isinstance(value, dict) and "value" in value else {"value": value}
            if key not in target or target[key] != entry:
                target[key] = entry
                changed = True

    return changed


def update_memory(memory_update: dict) -> dict:
    """Merge LLM memory update into global memory and save."""
    if not isinstance(memory_update, dict):
        return load_memory()

    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)

    return memory
