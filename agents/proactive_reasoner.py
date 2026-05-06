"""
agents/proactive_reasoner.py — Sam's inner voice.

Runs every 5 minutes. Dumps context to local LLM (Ollama).
Prompt: "Is there anything Sam should say or do right now? Reply null or JSON action."
Non-null responses are gated through the Authority engine or spoken directly.

Replaces the hardcoded suggestion loops in presence_engine.py.

Usage:
    from agents.proactive_reasoner import proactive_reasoner
    proactive_reasoner.start(ui=ui, speak=edge_speak_fn)
    proactive_reasoner.stop()
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from typing import Callable

logger = logging.getLogger("sam.proactive_reasoner")

_INTERVAL_SECS = 300   # 5 minutes
_MAX_CONTEXT_LEN = 3000


class ProactiveReasoner:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._ui = None
        self._speak: Callable | None = None
        self._last_suggestion_ts: float = 0.0

    def start(self, ui=None, speak: Callable | None = None):
        if self._running:
            return
        self._ui = ui
        self._speak = speak
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ProactiveReasoner"
        )
        self._thread.start()
        logger.info("[ProactiveReasoner] Started")

    def stop(self):
        self._running = False

    # ── Main loop ────────────────────────────────────────────────────────────

    def _loop(self):
        # First run after a short warm-up delay
        time.sleep(60)
        while self._running:
            try:
                self._reason()
            except Exception as e:
                logger.warning(f"[ProactiveReasoner] Reason error: {e}")
            time.sleep(_INTERVAL_SECS)

    def _reason(self):
        context = self._build_context()
        prompt = f"""You are Sam's inner reasoning process.

Current context:
{context}

Is there anything Sam should mention or do RIGHT NOW that would genuinely help the user?
Examples: remind them of a deadline, flag a failing test, suggest a break, mention an upcoming meeting.

Reply with ONLY one of:
1. The word: null
2. A JSON object: {{"action": "speak", "message": "<what Sam should say, max 2 sentences>"}}

Rules:
- Only suggest if something is genuinely important or time-sensitive.
- Don't repeat a suggestion made in the last 30 minutes.
- Don't suggest if the user is in a meeting or Sam is muted.
- Keep messages natural and brief.
"""
        try:
            from llm.manager import get_manager
            mgr = get_manager()
            raw = mgr.complete_sync(prompt, system="You are Sam's internal reasoning engine. Output only 'null' or valid JSON.", model_tier="local")
            raw = raw.strip()

            if not raw or raw.lower() == "null":
                return

            # Strip markdown fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).replace("```", "").strip()

            data = json.loads(raw)
            action  = data.get("action", "")
            message = data.get("message", "").strip()

            if not message:
                return

            if action == "speak":
                self._deliver(message)
        except json.JSONDecodeError:
            pass  # LLM returned non-JSON — ignore
        except Exception as e:
            logger.warning(f"[ProactiveReasoner] LLM call failed: {e}")

    # ── Context builder ──────────────────────────────────────────────────────

    def _build_context(self) -> str:
        lines: list[str] = []
        lines.append(f"Time: {datetime.now().strftime('%A %d %B %Y %H:%M')}")

        # Presence snapshot
        try:
            from main import presence_engine
            snap = presence_engine.get_state_snapshot()
            lines.append(f"User mode: {snap.get('mode', 'unknown')}")
            lines.append(f"Active app: {snap.get('active_app', '')}")
            active_proj = snap.get("active_project", "")
            if active_proj:
                lines.append(f"Active project: {active_proj}")
        except Exception:
            pass

        # Goals
        try:
            from memory.memory_manager import load_memory
            mem = load_memory()
            goals = mem.get("goals", {})
            long_term = goals.get("long_term_goal", {}).get("value", "")
            blockers  = goals.get("current_blockers", {}).get("value", [])
            if long_term:
                lines.append(f"Long-term goal: {long_term}")
            if blockers:
                lines.append(f"Blockers: {blockers}")
        except Exception:
            pass

        # Recent session log (last 5 actions)
        try:
            from system.session_logger import session_logger
            log = session_logger.get_log()[-5:]
            if log:
                entries = "; ".join(f"{e.get('intent','?')}: {e.get('summary','')[:40]}" for e in log)
                lines.append(f"Recent actions: {entries}")
        except Exception:
            pass

        # Recent bus events (last 3)
        try:
            from system.event_bus import bus
            pass  # bus doesn't buffer; would need a listener — skip for now
        except Exception:
            pass

        # Running background tasks
        try:
            from system.task_queue import task_queue
            summary = task_queue.summary()
            if summary != "No background tasks.":
                lines.append(f"Background tasks: {summary}")
        except Exception:
            pass

        # Project index summary
        try:
            from system.project_index import project_index
            lines.append(f"Projects: {project_index.summary()}")
        except Exception:
            pass

        return "\n".join(lines)[:_MAX_CONTEXT_LEN]

    # ── Delivery ─────────────────────────────────────────────────────────────

    def _deliver(self, message: str):
        # Respect meeting mode and mute
        try:
            from conversation_state import controller
            if controller.is_muted() or controller.get_mode() == "meeting":
                from system.notifier import notify
                notify("Sam", message[:120])
                return
        except Exception:
            pass

        # Gate through Authority engine if available
        try:
            from agents.authority import authority_engine
            if not authority_engine.allows("proactive_suggestion"):
                logger.debug("[ProactiveReasoner] Authority blocked suggestion")
                return
        except Exception:
            pass

        self._last_suggestion_ts = time.time()
        logger.info(f"[ProactiveReasoner] Queuing suggestion: {message[:80]}")

        # Enqueue so the ai_loop delivers this between responses, never mid-sentence
        try:
            from system.notification_queue import notification_queue
            notification_queue.enqueue(message, source="proactive", priority=2)
        except Exception:
            pass

        if self._ui:
            try:
                self._ui.append_output(f"[sam] {message}", "info")
            except Exception:
                pass


# Singleton
proactive_reasoner = ProactiveReasoner()
