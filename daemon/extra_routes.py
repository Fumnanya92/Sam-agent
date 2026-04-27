"""
daemon/extra_routes.py — remaining stub/functional routes the React dashboard needs.

Covers:
  Authority aliases  — /api/authority/approvals, /api/authority/status,
                       /api/authority/audit/stats, /api/authority/approvals/{id}/{action}
  Sites              — /api/sites/projects (CRUD + start/stop/file ops)
  Awareness          — /api/awareness/status, suggestions, captures, insights, report
  Content            — /api/content (pipeline alias)
  Channels status    — /api/channels/status
  Roles              — /api/roles
  System             — /api/system/autostart, restart
  Sidecars           — /api/sidecars (CRUD + enroll + config)
  User profile       — /api/user-profile (GET/POST/clear)
  Auth               — /api/auth/google/*
  Calendar           — /api/calendar
  Documents          — /api/documents/{id}/download
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from vault.schema import DB_PATH

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


async def _db():
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    return conn


def _row(r: aiosqlite.Row) -> dict:
    return dict(r)


# ══════════════════════════════════════════════════════
#  AUTHORITY — path aliases the frontend actually calls
# ══════════════════════════════════════════════════════

@router.get("/api/authority/status")
async def authority_status():
    return {
        "enabled": True,
        "default_level": 2,
        "pending_count": 0,
        "governed_categories": ["file_write", "code_exec", "network", "system"],
    }


@router.get("/api/authority/approvals")
async def list_approvals(status: str = "", limit: int = 50):
    """Alias for /api/authority/pending — returns a plain array."""
    try:
        from authority.approval import ApprovalManager
        mgr = ApprovalManager(DB_PATH)
        items = await mgr.get_pending() if status == "pending" else await mgr.get_all(limit=limit)
        return [vars(a) for a in items]
    except Exception:
        return []


@router.post("/api/authority/approvals/{request_id}/{action}")
async def decide_approval(request_id: str, action: str):
    try:
        from authority.approval import ApprovalManager
        mgr = ApprovalManager(DB_PATH)
        if action == "approve":
            await mgr.approve(request_id, "user")
        elif action in ("deny", "reject"):
            await mgr.deny(request_id, "user")
        return {"ok": True, "id": request_id, "action": action}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/authority/audit/stats")
async def authority_audit_stats():
    """Alias for /api/authority/stats."""
    try:
        from authority.audit import AuditTrail
        trail = AuditTrail(DB_PATH)
        return await trail.get_stats()
    except Exception:
        return {"total": 0, "allowed": 0, "denied": 0, "approvalRequired": 0, "byCategory": {}}


# ══════════════════════════════════════════════════════
#  SITES — project management
# ══════════════════════════════════════════════════════

async def _ensure_sites_table(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS site_projects (
            id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            name            TEXT NOT NULL,
            path            TEXT NOT NULL DEFAULT '',
            framework       TEXT NOT NULL DEFAULT 'static',
            dev_port        INTEGER,
            dev_server_pid  INTEGER,
            status          TEXT NOT NULL DEFAULT 'stopped',
            git_branch      TEXT,
            git_dirty       INTEGER NOT NULL DEFAULT 0,
            github_url      TEXT,
            created_at      INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000),
            last_opened_at  INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000)
        )
    """)
    await db.commit()


def _project_row(r: aiosqlite.Row) -> dict:
    d = dict(r)
    return {
        "id": d["id"],
        "name": d["name"],
        "path": d["path"],
        "framework": d["framework"],
        "devPort": d.get("dev_port"),
        "devServerPid": d.get("dev_server_pid"),
        "status": d["status"],
        "gitBranch": d.get("git_branch"),
        "gitDirty": bool(d.get("git_dirty", 0)),
        "githubUrl": d.get("github_url"),
        "createdAt": d.get("created_at", 0),
        "lastOpenedAt": d.get("last_opened_at", 0),
    }


@router.get("/api/sites/projects")
async def list_projects():
    db = await _db()
    try:
        await _ensure_sites_table(db)
        async with db.execute("SELECT * FROM site_projects ORDER BY last_opened_at DESC") as cur:
            rows = await cur.fetchall()
        return [_project_row(r) for r in rows]
    finally:
        await db.close()


class ProjectCreate(BaseModel):
    name: str
    path: str = ""
    framework: str = "static"
    githubUrl: Optional[str] = None


@router.post("/api/sites/projects", status_code=201)
async def create_project(body: ProjectCreate):
    db = await _db()
    try:
        await _ensure_sites_table(db)
        pid = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        await db.execute(
            "INSERT INTO site_projects (id, name, path, framework, github_url, created_at, last_opened_at) VALUES (?,?,?,?,?,?,?)",
            (pid, body.name, body.path, body.framework, body.githubUrl, now, now),
        )
        await db.commit()
        async with db.execute("SELECT * FROM site_projects WHERE id = ?", (pid,)) as cur:
            row = await cur.fetchone()
        return _project_row(row)
    finally:
        await db.close()


@router.get("/api/sites/projects/{project_id}")
async def get_project(project_id: str):
    db = await _db()
    try:
        await _ensure_sites_table(db)
        async with db.execute("SELECT * FROM site_projects WHERE id = ?", (project_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        return _project_row(row)
    finally:
        await db.close()


@router.delete("/api/sites/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    db = await _db()
    try:
        await _ensure_sites_table(db)
        await db.execute("DELETE FROM site_projects WHERE id = ?", (project_id,))
        await db.commit()
    finally:
        await db.close()


@router.post("/api/sites/projects/{project_id}/start")
async def start_project(project_id: str):
    db = await _db()
    try:
        await _ensure_sites_table(db)
        await db.execute("UPDATE site_projects SET status='running' WHERE id=?", (project_id,))
        await db.commit()
        async with db.execute("SELECT * FROM site_projects WHERE id=?", (project_id,)) as cur:
            row = await cur.fetchone()
        return _project_row(row) if row else {}
    finally:
        await db.close()


@router.post("/api/sites/projects/{project_id}/stop")
async def stop_project(project_id: str):
    db = await _db()
    try:
        await _ensure_sites_table(db)
        await db.execute("UPDATE site_projects SET status='stopped', dev_server_pid=NULL WHERE id=?", (project_id,))
        await db.commit()
        async with db.execute("SELECT * FROM site_projects WHERE id=?", (project_id,)) as cur:
            row = await cur.fetchone()
        return _project_row(row) if row else {}
    finally:
        await db.close()


@router.get("/api/sites/projects/{project_id}/files")
async def list_project_files(project_id: str, path: str = ""):
    return []


@router.get("/api/sites/projects/{project_id}/file")
async def get_project_file(project_id: str, path: str = ""):
    return {"path": path, "content": ""}


@router.post("/api/sites/projects/{project_id}/file")
async def save_project_file(project_id: str, body: dict):
    return {"ok": True}


# Git stubs
@router.get("/api/sites/projects/{project_id}/git/branches")
async def git_branches(project_id: str):
    return [{"name": "main", "current": True}]


@router.get("/api/sites/projects/{project_id}/git/log")
async def git_log(project_id: str, limit: int = 30):
    return []


@router.post("/api/sites/projects/{project_id}/git/branch")
async def git_create_branch(project_id: str, body: dict):
    return {"ok": True}


@router.post("/api/sites/projects/{project_id}/git/merge")
async def git_merge(project_id: str, body: dict):
    return {"success": True, "conflicts": []}


@router.get("/api/sites/projects/{project_id}/github/status")
async def github_status(project_id: str):
    return {"connected": False, "ahead": 0, "behind": 0, "branch": "main"}


@router.post("/api/sites/projects/{project_id}/github/repo")
async def github_create_repo(project_id: str, body: dict):
    return {"ok": True, "url": ""}


@router.post("/api/sites/projects/{project_id}/github/push")
async def github_push(project_id: str, body: dict):
    return {"ok": True}


@router.get("/api/sites/github/token")
async def github_token_status():
    return {"connected": bool(os.getenv("GITHUB_TOKEN")), "username": ""}


@router.post("/api/sites/github/token")
async def save_github_token(body: dict):
    return {"ok": True, "username": ""}


@router.delete("/api/sites/github/token")
async def delete_github_token():
    return {"ok": True}


@router.get("/api/sites/github/repos")
async def list_github_repos():
    return []


# ══════════════════════════════════════════════════════
#  AWARENESS
# ══════════════════════════════════════════════════════

@router.get("/api/awareness/status")
async def awareness_status():
    return {
        "status": "idle",
        "enabled": False,
        "liveContext": {
            "currentApp": None,
            "currentWindow": None,
            "currentSession": None,
            "recentApps": [],
            "capturesLastHour": 0,
            "suggestionsToday": 0,
            "isRunning": False,
        },
    }


@router.get("/api/awareness/suggestions")
async def list_suggestions(limit: int = 10):
    return []


@router.post("/api/awareness/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    return {"ok": True}


@router.post("/api/awareness/suggestions/{suggestion_id}/act")
async def act_suggestion(suggestion_id: str):
    return {"ok": True}


@router.get("/api/awareness/captures")
async def list_captures(limit: int = 20):
    return []


@router.post("/api/awareness/captures")
async def create_capture(body: dict):
    return {"id": str(uuid.uuid4())[:8], "ok": True}


@router.delete("/api/awareness/captures/{capture_id}", status_code=204)
async def delete_capture(capture_id: str):
    pass


@router.get("/api/awareness/insights")
async def list_insights():
    return []


@router.get("/api/awareness/report")
async def awareness_report(date: str = ""):
    today = date or time.strftime("%Y-%m-%d")
    return {
        "date": today,
        "totalActiveMinutes": 0,
        "appBreakdown": [],
        "sessionCount": 0,
        "sessions": [],
        "focusScore": 0,
        "contextSwitches": 0,
        "longestFocusMinutes": 0,
        "suggestions": {"total": 0, "actedOn": 0},
        "aiTakeaways": [],
    }


@router.get("/api/awareness/report/weekly")
async def awareness_weekly_report():
    return {"weeks": []}


# ══════════════════════════════════════════════════════
#  CONTENT  (pipeline page alias with richer shape)
# ══════════════════════════════════════════════════════

@router.get("/api/content")
async def list_content(stage: str = "", limit: int = 50):
    db = await _db()
    try:
        filters, params = [], []
        if stage:
            filters.append("stage = ?")
            params.append(stage)
        where = "WHERE " + " AND ".join(filters) if filters else ""
        params.append(limit)
        async with db.execute(
            f"SELECT * FROM documents {where} ORDER BY created_at DESC LIMIT ?", params
        ) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


@router.post("/api/content", status_code=201)
async def create_content(body: dict):
    return {"id": str(uuid.uuid4())[:8], **body}


@router.get("/api/content/{content_id}")
async def get_content(content_id: str):
    raise HTTPException(status_code=404, detail="Not found")


@router.patch("/api/content/{content_id}")
async def update_content(content_id: str, body: dict):
    return {"id": content_id, **body}


@router.delete("/api/content/{content_id}", status_code=204)
async def delete_content(content_id: str):
    pass


@router.post("/api/content/{content_id}/advance")
async def advance_content(content_id: str):
    return {"id": content_id, "stage": "review"}


@router.post("/api/content/{content_id}/regress")
async def regress_content(content_id: str):
    return {"id": content_id, "stage": "draft"}


@router.get("/api/content/{content_id}/attachments")
async def list_attachments(content_id: str):
    return []


@router.delete("/api/content/{content_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(content_id: str, attachment_id: str):
    pass


@router.get("/api/content/{content_id}/notes")
async def list_notes(content_id: str):
    return []


# ══════════════════════════════════════════════════════
#  CHANNELS STATUS
# ══════════════════════════════════════════════════════

@router.get("/api/channels/status")
async def channels_status():
    return {
        "channels": {
            "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "discord": bool(os.getenv("DISCORD_BOT_TOKEN")),
            "whatsapp": False,
            "websocket": True,
        },
        "stt": os.getenv("SAM_STT_ENGINE", "browser"),
    }


# ══════════════════════════════════════════════════════
#  ROLES
# ══════════════════════════════════════════════════════

@router.get("/api/roles")
async def get_roles():
    return {
        "active_role": "default",
        "role": {
            "id": "default",
            "name": "Default",
            "authority_level": 2,
            "tools": ["web_search", "file_read", "code_exec"],
            "sub_roles": [],
        },
    }


# ══════════════════════════════════════════════════════
#  SYSTEM — autostart / service management
# ══════════════════════════════════════════════════════

@router.get("/api/system/autostart")
async def autostart_status():
    return {
        "platform": sys.platform,
        "manager": "task_scheduler" if sys.platform == "win32" else "systemd",
        "installed": False,
        "keepalive_supported": True,
        "restart_supported": True,
    }


@router.post("/api/system/autostart")
async def configure_autostart(body: dict):
    return {"ok": True}


@router.post("/api/system/autostart/restart")
async def restart_service():
    return {"ok": True, "message": "Restart signal sent."}


# ══════════════════════════════════════════════════════
#  SIDECARS
# ══════════════════════════════════════════════════════

async def _ensure_sidecars_table(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sidecars (
            id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            name       TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'offline',
            host       TEXT NOT NULL DEFAULT 'localhost',
            port       INTEGER NOT NULL DEFAULT 9000,
            config     TEXT NOT NULL DEFAULT '{}',
            enrolled_at INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000)
        )
    """)
    await db.commit()


@router.get("/api/sidecars")
async def list_sidecars():
    db = await _db()
    try:
        await _ensure_sidecars_table(db)
        async with db.execute("SELECT * FROM sidecars ORDER BY enrolled_at DESC") as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]
    finally:
        await db.close()


@router.post("/api/sidecars/enroll", status_code=201)
async def enroll_sidecar(body: dict):
    db = await _db()
    try:
        await _ensure_sidecars_table(db)
        sid = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        await db.execute(
            "INSERT INTO sidecars (id, name, host, port, enrolled_at) VALUES (?,?,?,?,?)",
            (sid, body.get("name", "sidecar"), body.get("host", "localhost"), body.get("port", 9000), now),
        )
        await db.commit()
        return {"id": sid, "status": "enrolled"}
    finally:
        await db.close()


@router.get("/api/sidecars/{sidecar_id}")
async def get_sidecar(sidecar_id: str):
    db = await _db()
    try:
        await _ensure_sidecars_table(db)
        async with db.execute("SELECT * FROM sidecars WHERE id=?", (sidecar_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sidecar not found")
        return _row(row)
    finally:
        await db.close()


@router.delete("/api/sidecars/{sidecar_id}", status_code=204)
async def delete_sidecar(sidecar_id: str):
    db = await _db()
    try:
        await _ensure_sidecars_table(db)
        await db.execute("DELETE FROM sidecars WHERE id=?", (sidecar_id,))
        await db.commit()
    finally:
        await db.close()


@router.get("/api/sidecars/{sidecar_id}/config")
async def get_sidecar_config(sidecar_id: str):
    return {"sidecar_id": sidecar_id, "config": {}}


@router.post("/api/sidecars/{sidecar_id}/config")
async def save_sidecar_config(sidecar_id: str, body: dict):
    return {"ok": True}


# ══════════════════════════════════════════════════════
#  USER PROFILE
# ══════════════════════════════════════════════════════

_PROFILE_QUESTIONS = [
    {"id": "name", "step": 1, "step_title": "Identity", "label": "Your name", "prompt": "What should Sam call you?", "description": "Sam will use this name when addressing you.", "placeholder": "e.g. Alex"},
    {"id": "role", "step": 2, "step_title": "Role", "label": "Your role", "prompt": "What do you do?", "description": "Helps Sam tailor responses to your domain.", "placeholder": "e.g. Software engineer"},
    {"id": "goals", "step": 3, "step_title": "Goals", "label": "Current goals", "prompt": "What are you working towards?", "description": "Sam will keep these in mind.", "placeholder": "e.g. Launch my SaaS product", "multiline": True},
    {"id": "preferences", "step": 4, "step_title": "Style", "label": "Communication style", "prompt": "How should Sam communicate?", "description": "Brief and direct, or detailed and thorough?", "placeholder": "e.g. Brief and direct, no fluff"},
]

async def _ensure_profile_table(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id          INTEGER PRIMARY KEY DEFAULT 1,
            answers     TEXT NOT NULL DEFAULT '{}',
            created_at  INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000),
            updated_at  INTEGER NOT NULL DEFAULT (unixepoch('now') * 1000),
            completed_at INTEGER
        )
    """)
    await db.commit()


@router.get("/api/user-profile")
async def get_user_profile():
    db = await _db()
    try:
        await _ensure_profile_table(db)
        async with db.execute("SELECT * FROM user_profile WHERE id=1") as cur:
            row = await cur.fetchone()
        profile = None
        answered_count = 0
        if row:
            d = _row(row)
            answers = json.loads(d.get("answers", "{}"))
            answered_count = len([v for v in answers.values() if v])
            profile = {
                "version": 1,
                "answers": answers,
                "created_at": d.get("created_at", 0),
                "updated_at": d.get("updated_at", 0),
                "completed_at": d.get("completed_at"),
            }
        return {
            "questions": _PROFILE_QUESTIONS,
            "profile": profile,
            "answered_count": answered_count,
            "total_questions": len(_PROFILE_QUESTIONS),
            "has_profile": profile is not None,
        }
    finally:
        await db.close()


class ProfileUpdate(BaseModel):
    answers: dict


@router.post("/api/user-profile")
async def save_user_profile(body: ProfileUpdate):
    db = await _db()
    try:
        await _ensure_profile_table(db)
        now = int(time.time() * 1000)
        answered = len([v for v in body.answers.values() if v])
        completed = now if answered >= len(_PROFILE_QUESTIONS) else None
        await db.execute(
            """INSERT INTO user_profile (id, answers, created_at, updated_at, completed_at)
               VALUES (1, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET answers=excluded.answers, updated_at=excluded.updated_at, completed_at=excluded.completed_at""",
            (json.dumps(body.answers), now, now, completed),
        )
        await db.commit()
        return {"message": "Profile saved."}
    finally:
        await db.close()


@router.post("/api/user-profile/clear")
async def clear_user_profile():
    db = await _db()
    try:
        await _ensure_profile_table(db)
        await db.execute("DELETE FROM user_profile WHERE id=1")
        await db.commit()
        return {"message": "Profile cleared."}
    finally:
        await db.close()


# ══════════════════════════════════════════════════════
#  AUTH — Google OAuth stub
# ══════════════════════════════════════════════════════

@router.get("/api/auth/google/init")
async def google_auth_init():
    return {"auth_url": ""}


@router.get("/api/auth/google/status")
async def google_auth_status():
    return {"connected": False, "email": None, "scopes": []}


@router.post("/api/auth/google/disconnect")
async def google_disconnect():
    return {"ok": True}


# ══════════════════════════════════════════════════════
#  CALENDAR
# ══════════════════════════════════════════════════════

@router.get("/api/calendar")
async def list_calendar(start: str = "", end: str = ""):
    return []


@router.post("/api/calendar", status_code=201)
async def create_event(body: dict):
    return {"id": str(uuid.uuid4())[:8], **body}


# ══════════════════════════════════════════════════════
#  DOCUMENTS — download
# ══════════════════════════════════════════════════════

@router.get("/api/documents/{doc_id}/download")
async def download_document(doc_id: str):
    raise HTTPException(status_code=404, detail="Document not found")
