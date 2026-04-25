"""
daemon/main.py — FastAPI + uvicorn daemon for Sam (Phase 1).

Starts the HTTP/WebSocket server on port 3142 and runs Sam's ai_loop()
as a background asyncio task.

Usage:
    python -m daemon.main
    # or via uvicorn directly:
    uvicorn daemon.main:app --host 0.0.0.0 --port 3142
"""

import asyncio
import logging
import sys
import io
from contextlib import asynccontextmanager

# Force UTF-8 output on Windows (mirrors main.py)
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Load .env before anything that reads env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vault.schema import init_db
from daemon.api_routes import router

logger = logging.getLogger("sam.daemon")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ── Background task handles ───────────────────────────────────────────────────

_ai_loop_task: asyncio.Task | None = None
_bridge_task: asyncio.Task | None = None
_channel_manager = None


async def _run_ai_loop_headless() -> None:
    """
    Run Sam's ai_loop in headless (no Tkinter UI) mode suitable for daemon use.

    The real ai_loop requires a SamUI instance for TTS/display.  In daemon mode
    we provide a lightweight stub so the loop can still process chat messages
    that arrive via the REST API and push responses over WebSocket.
    """
    from daemon.ws_service import manager as ws_manager

    class _HeadlessUI:
        """Minimal stub that satisfies the interface expected by ai_loop."""

        def write_log(self, text: str) -> None:
            logger.info(f"[SAM] {text}")

        def set_transcription(self, text: str) -> None:
            pass

        def clear_transcription(self) -> None:
            pass

        def highlight_text_input(self) -> None:
            pass

        def unhighlight_text_input(self) -> None:
            pass

        def set_typed_input_queue(self, q) -> None:
            self._queue = q

        def add_agent_task(self, task_id, name) -> None:
            pass

        def update_agent_task(self, task_id, status, color) -> None:
            pass

        def append_output(self, line, level) -> None:
            logger.info(f"[AGENT] {line}")

    ui = _HeadlessUI()

    # Wire the HTTP chat queue into the typed_input_queue expected by ai_loop
    from daemon.api_routes import chat_input_queue
    import queue as _queue_mod

    # ai_loop expects a stdlib queue.Queue; we bridge from asyncio.Queue
    typed_q: _queue_mod.Queue = _queue_mod.Queue()
    ui.set_typed_input_queue(typed_q)

    async def _bridge_chat_queue():
        """Forward messages from the async HTTP queue to the sync typed queue."""
        while True:
            item = await chat_input_queue.get()
            typed_q.put(item["message"])
            # Broadcast the user message so the dashboard sees it
            await ws_manager.broadcast("chat_message", {
                "role": "user",
                "message_id": item.get("message_id"),
                "content": item["message"],
            })

    global _bridge_task
    _bridge_task = asyncio.create_task(_bridge_chat_queue())

    # Import ai_loop from main.py (non-destructive — main.py is not modified)
    try:
        from main import ai_loop
        logger.info("[daemon] Starting Sam ai_loop (headless)")
        await ai_loop(ui)  # type: ignore[arg-type]
    except ImportError as exc:
        logger.error(f"[daemon] Could not import ai_loop from main.py: {exc}")
        # Keep daemon alive even if ai_loop can't start (e.g. missing deps in test env)
        while True:
            await asyncio.sleep(60)
    except Exception as exc:
        logger.error(f"[daemon] ai_loop crashed: {exc}", exc_info=True)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + start ai_loop. Shutdown: cancel ai_loop and bridge task."""
    global _ai_loop_task, _bridge_task

    # 1. Initialise the SQLite vault
    logger.info("[daemon] Initialising SQLite vault...")
    await init_db()

    # 2. Wire visual tool broadcast callbacks
    from daemon.ws_service import manager as ws_manager
    import actions.tools.screen_view as _sv
    import actions.tools.takeover as _to
    import actions.tools.tutorial as _tut
    import actions.tools.ui_test as _ut
    _sv.set_broadcast(ws_manager.broadcast)
    _to.set_broadcast(ws_manager.broadcast)
    _tut.set_broadcast(ws_manager.broadcast)
    _ut.set_broadcast(ws_manager.broadcast)
    logger.info("[daemon] Visual tool broadcast callbacks wired.")

    # 3. Start comms channels (Telegram, Discord) — skipped if tokens not set
    global _channel_manager
    from comms.manager import ChannelManager
    from daemon.api_routes import chat_input_queue as _cq
    _channel_manager = ChannelManager(_cq)
    asyncio.create_task(_channel_manager.start(), name="sam-channels")

    # 4. Start Sam's ai_loop as a background task
    logger.info("[daemon] Launching Sam ai_loop background task...")
    _ai_loop_task = asyncio.create_task(
        _run_ai_loop_headless(), name="sam-ai-loop"
    )

    logger.info("[daemon] Sam daemon ready on http://0.0.0.0:3142")
    yield  # ← server is running

    # Shutdown
    logger.info("[daemon] Shutting down...")
    if _channel_manager:
        await _channel_manager.stop()
    if _bridge_task and not _bridge_task.done():
        _bridge_task.cancel()
        try:
            await _bridge_task
        except asyncio.CancelledError:
            pass
    if _ai_loop_task and not _ai_loop_task.done():
        _ai_loop_task.cancel()
        try:
            await _ai_loop_task
        except asyncio.CancelledError:
            pass
    logger.info("[daemon] Shutdown complete.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sam Daemon",
    description="Phase 1: FastAPI HTTP/WebSocket daemon for Sam AI assistant",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the local React dashboard (any localhost port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets from React build (must come before router to avoid catch-all conflict)
UI_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "dist")
if os.path.exists(UI_DIST):
    _assets_dir = os.path.join(UI_DIST, "assets")
    if os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

# Mount all routes
app.include_router(router)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "daemon.main:app",
        host="0.0.0.0",
        port=3142,
        reload=False,
        log_level="info",
    )
