"""
system/task_queue.py — Async background task queue.

Wraps agent/monitor.py with:
  - A bounded concurrent worker pool (default: 4 workers)
  - Submit long-running callables without blocking the voice loop
  - Completion callbacks: TTS result + Windows notification (meeting-mode aware)
  - Cancellation support

Usage:
    from system.task_queue import task_queue

    # Submit a job
    job_id = task_queue.submit(
        name="debug_app",
        description="Fix the login button",
        fn=lambda: surgeon.debug("login button broken", project_name="guest app"),
        on_done=lambda result: speak(result),
    )

    # Cancel a job
    task_queue.cancel(job_id)

    # Get all jobs
    task_queue.list_jobs()
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("sam.task_queue")

_MAX_WORKERS = 4
_RESULT_PREVIEW_LEN = 120


@dataclass
class QueuedJob:
    job_id: str
    name: str
    description: str
    status: str = "pending"   # pending | running | done | error | cancelled
    result: Any = None
    error: str = ""
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    future: Optional[Future] = field(default=None, repr=False, compare=False)
    monitor_task_id: Optional[str] = None

    @property
    def elapsed(self) -> str:
        if self.started_at is None:
            return "queued"
        end = self.finished_at or time.time()
        secs = int(end - self.started_at)
        return f"{secs}s" if secs < 60 else f"{secs // 60}m {secs % 60}s"

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "elapsed": self.elapsed,
            "result_preview": str(self.result or "")[:_RESULT_PREVIEW_LEN],
            "error": self.error,
        }


class TaskQueue:
    """Thread-safe background task queue backed by ThreadPoolExecutor."""

    def __init__(self, max_workers: int = _MAX_WORKERS):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sam-task")
        self._jobs: dict[str, QueuedJob] = {}
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    def submit(
        self,
        name: str,
        description: str,
        fn: Callable[[], Any],
        on_done: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        ui=None,
    ) -> str:
        """
        Submit a callable to run in the background.
        Returns job_id.

        on_done(result_str) is called on the caller's behalf when the job finishes.
        on_error(error_str) is called if the job raises.
        """
        job_id = str(uuid.uuid4())[:8]

        # Register with AgentMonitor so the UI Tasks panel lights up
        monitor_task_id: Optional[str] = None
        try:
            from agent.monitor import monitor
            monitor_task_id = monitor.register_task(name, description)
            if ui:
                ui.add_agent_task(monitor_task_id, f"{name}: {description[:24]}")
        except Exception:
            pass

        job = QueuedJob(
            job_id=job_id,
            name=name,
            description=description,
            status="pending",
            monitor_task_id=monitor_task_id,
        )

        with self._lock:
            self._jobs[job_id] = job

        future = self._executor.submit(
            self._run_job, job, fn, on_done, on_error, ui
        )
        with self._lock:
            job.future = future

        logger.info(f"[TaskQueue] Submitted job {job_id}: {name} — {description[:60]}")
        return job_id

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending (not yet running) job. Returns True if cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.future and job.future.cancel():
            job.status = "cancelled"
            self._monitor_update(job, "cancelled")
            logger.info(f"[TaskQueue] Cancelled job {job_id}")
            return True
        return False

    def list_jobs(self, status_filter: str = "") -> list[dict]:
        """Return job summaries, optionally filtered by status."""
        with self._lock:
            jobs = list(self._jobs.values())
        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]
        return [j.to_dict() for j in jobs]

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == "running")

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == "pending")

    def summary(self) -> str:
        """Short human-readable summary for Sam to speak."""
        with self._lock:
            jobs = list(self._jobs.values())
        running = [j for j in jobs if j.status == "running"]
        pending = [j for j in jobs if j.status == "pending"]
        done    = [j for j in jobs if j.status == "done"]
        if not jobs:
            return "No background tasks."
        parts = []
        if running:
            parts.append(f"{len(running)} running: {', '.join(j.name for j in running[:3])}")
        if pending:
            parts.append(f"{len(pending)} queued")
        if done:
            parts.append(f"{len(done)} done")
        return "Background tasks — " + "; ".join(parts) + "."

    # ── Internal ────────────────────────────────────────────────────────────

    def _run_job(
        self,
        job: QueuedJob,
        fn: Callable[[], Any],
        on_done: Callable[[str], None] | None,
        on_error: Callable[[str], None] | None,
        ui,
    ):
        job.status = "running"
        job.started_at = time.time()
        self._monitor_update(job, "running")

        try:
            result = fn()
            job.result = result
            job.status = "done"
            job.finished_at = time.time()
            self._monitor_update(job, "done", str(result or "")[:_RESULT_PREVIEW_LEN])

            result_str = str(result or "Done.").strip()
            logger.info(f"[TaskQueue] Job {job.job_id} done in {job.elapsed}: {result_str[:80]}")

            if ui:
                try:
                    ui.update_agent_task(job.monitor_task_id, "done")
                except Exception:
                    pass

            # Deliver result: respect meeting mode
            if on_done:
                try:
                    on_done(result_str)
                except Exception as e:
                    logger.warning(f"[TaskQueue] on_done callback failed: {e}")
            else:
                self._deliver_completion(job.name, result_str)

        except Exception as exc:
            job.error = str(exc)
            job.status = "error"
            job.finished_at = time.time()
            self._monitor_update(job, "error", str(exc))
            logger.error(f"[TaskQueue] Job {job.job_id} error: {exc}")

            if ui:
                try:
                    ui.update_agent_task(job.monitor_task_id, "error")
                except Exception:
                    pass

            error_str = f"{job.name} failed: {exc}"
            if on_error:
                try:
                    on_error(error_str)
                except Exception as e:
                    logger.warning(f"[TaskQueue] on_error callback failed: {e}")
            else:
                self._deliver_completion(job.name, error_str, is_error=True)

    def _deliver_completion(self, name: str, message: str, is_error: bool = False):
        """Queue task result for conversational delivery, respecting meeting/mute state."""
        try:
            from conversation_state import controller
            if controller.is_muted() or controller.get_mode() == "meeting":
                from system.notifier import notify
                title = f"Sam — {name} {'failed' if is_error else 'done'}"
                notify(title, message[:120])
                return
        except Exception:
            pass
        # Enqueue so the ai_loop delivers this between responses, never mid-sentence
        try:
            from system.notification_queue import notification_queue
            notification_queue.enqueue(message[:200], source="task", priority=5)
        except Exception as e:
            logger.warning(f"[TaskQueue] TTS delivery failed: {e}")

    def _monitor_update(self, job: QueuedJob, status: str, output_line: str = ""):
        if job.monitor_task_id:
            try:
                from agent.monitor import monitor
                monitor.update_task(job.monitor_task_id, status, output_line or None)
            except Exception:
                pass


# ── Singleton ───────────────────────────────────────────────────────────────
task_queue = TaskQueue()
