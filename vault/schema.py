"""
vault/schema.py — SQLite schema for Sam's persistent vault.

Creates all tables in ~/.sam/sam.db using aiosqlite.
Run directly: python vault/schema.py
"""

import asyncio
import os
from pathlib import Path

try:
    import aiosqlite
except ImportError:
    raise ImportError(
        "aiosqlite is required: pip install aiosqlite"
    )

# Default DB path; can be overridden via SAM_DB_PATH env var
_DEFAULT_DB = Path.home() / ".sam" / "sam.db"
DB_PATH = Path(os.environ.get("SAM_DB_PATH", str(_DEFAULT_DB)))


CREATE_STATEMENTS = [
    # Conversations — top-level session containers
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT    NOT NULL,
        role        TEXT    NOT NULL,
        content     TEXT    NOT NULL,
        timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
        tokens_used INTEGER DEFAULT 0
    )
    """,

    # Messages — individual turns within a conversation
    """
    CREATE TABLE IF NOT EXISTS messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
        metadata        TEXT DEFAULT '{}'
    )
    """,

    # Tasks — to-do items managed by Sam
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT DEFAULT '',
        status      TEXT NOT NULL DEFAULT 'pending',
        priority    TEXT NOT NULL DEFAULT 'medium',
        due_date    TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
        agent       TEXT DEFAULT ''
    )
    """,

    # Goals — longer-horizon objectives with measurable metrics
    """
    CREATE TABLE IF NOT EXISTS goals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT DEFAULT '',
        status      TEXT NOT NULL DEFAULT 'active',
        metric      TEXT DEFAULT '',
        target      REAL DEFAULT 0,
        current     REAL DEFAULT 0,
        due_date    TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Entities — people, places, tools, concepts Sam knows about
    """
    CREATE TABLE IF NOT EXISTS entities (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        type        TEXT NOT NULL DEFAULT 'unknown',
        description TEXT DEFAULT '',
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Facts — individual facts attached to an entity
    """
    CREATE TABLE IF NOT EXISTS facts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id   INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
        fact        TEXT NOT NULL,
        confidence  REAL NOT NULL DEFAULT 1.0,
        source      TEXT DEFAULT '',
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Relationships — directed edges between entities
    """
    CREATE TABLE IF NOT EXISTS relationships (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        from_entity_id    INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
        to_entity_id      INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL DEFAULT 'related',
        strength          REAL NOT NULL DEFAULT 1.0,
        created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Workflows — automation triggers and node graphs
    """
    CREATE TABLE IF NOT EXISTS workflows (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        trigger_type   TEXT NOT NULL DEFAULT 'manual',
        trigger_config TEXT NOT NULL DEFAULT '{}',
        nodes          TEXT NOT NULL DEFAULT '[]',
        status         TEXT NOT NULL DEFAULT 'active',
        created_at     TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Settings — key/value store for Sam config at runtime
    """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Audit log — authority engine decision history
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id                 TEXT PRIMARY KEY,
        agent_id           TEXT NOT NULL DEFAULT 'sam',
        agent_name         TEXT NOT NULL DEFAULT 'Sam',
        tool_name          TEXT NOT NULL DEFAULT '',
        action_category    TEXT NOT NULL DEFAULT '',
        authority_decision TEXT NOT NULL DEFAULT 'allowed',
        approval_id        TEXT,
        executed           INTEGER NOT NULL DEFAULT 0,
        execution_time_ms  INTEGER,
        created_at         TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Approval requests — pending/decided gate requests
    """
    CREATE TABLE IF NOT EXISTS approval_requests (
        id               TEXT PRIMARY KEY,
        agent_id         TEXT NOT NULL,
        agent_name       TEXT NOT NULL,
        tool_name        TEXT NOT NULL,
        tool_arguments   TEXT NOT NULL DEFAULT '{}',
        action_category  TEXT NOT NULL,
        urgency          TEXT NOT NULL DEFAULT 'normal',
        reason           TEXT NOT NULL DEFAULT '',
        context          TEXT NOT NULL DEFAULT '',
        status           TEXT NOT NULL DEFAULT 'pending',
        decided_at       TEXT,
        decided_by       TEXT,
        executed_at      TEXT,
        execution_result TEXT,
        created_at       TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Documents — text chunks with optional embedding for RAG
    """
    CREATE TABLE IF NOT EXISTS documents (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        title      TEXT NOT NULL,
        content    TEXT NOT NULL,
        type       TEXT NOT NULL DEFAULT 'text',
        source     TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        embedding  BLOB
    )
    """,
]

# Indexes for common queries
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)",
    "CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_agent ON approval_requests(agent_id)",
]


async def init_db(db_path: Path | None = None) -> Path:
    """
    Create the ~/.sam/sam.db (or custom path) and initialise all tables.
    Returns the resolved DB path.
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(path)) as db:
        # Enable WAL mode for better concurrent read performance
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        for stmt in CREATE_STATEMENTS:
            await db.execute(stmt)

        for stmt in INDEX_STATEMENTS:
            await db.execute(stmt)

        await db.commit()

    print(f"[vault] Database ready at: {path}")
    return path


if __name__ == "__main__":
    asyncio.run(init_db())
