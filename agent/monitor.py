"""
agent/monitor.py — Global agent task tracker

All long-running tasks (agent_task, build_project, code_helper, browser_control, etc.)
register here. The UI subscribes to get live status updates.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class AgentTask:
    task_id: str
    name: str
    description: str
    status: str          # 'running' | 'done' | 'error' | 'cancelled'
    output_lines: list = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def elapsed(self) -> str:
        end = self.end_time or time.time()
        secs = int(end - self.start_time)
        return f"{secs}s" if secs < 60 else f"{secs // 60}m {secs % 60}s"


class AgentMonitor:
    """Singleton that tracks every spawned agent/task and notifies listeners."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._tasks: List[AgentTask] = []
                cls._instance._callbacks: List[Callable] = []
                cls._instance._tasks_lock = threading.Lock()
        return cls._instance

    # ── Registration ────────────────────────────────────────────────────────

    def register_task(self, name: str, description: str = "") -> str:
        """Register a new task and return its task_id."""
        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(task_id=task_id, name=name, description=description, status="running")
        with self._tasks_lock:
            self._tasks.append(task)
        self._notify(task)
        return task_id

    def update_task(self, task_id: str, status: str, output_line: str = None):
        """Update task status; optionally append a line of output."""
        with self._tasks_lock:
            task = self._find(task_id)
            if task is None:
                return
            task.status = status
            if status in ("done", "error", "cancelled"):
                task.end_time = time.time()
            if output_line:
                task.output_lines.append(output_line)
        self._notify(task)

    def append_output(self, task_id: str, line: str):
        """Append a line of output without changing status."""
        with self._tasks_lock:
            task = self._find(task_id)
            if task is None:
                return
            task.output_lines.append(line)
        self._notify(task)

    # ── Query ────────────────────────────────────────────────────────────────

    def get_tasks(self) -> List[AgentTask]:
        with self._tasks_lock:
            return list(self._tasks)

    def get_running(self) -> List[AgentTask]:
        with self._tasks_lock:
            return [t for t in self._tasks if t.status == "running"]

    def _find(self, task_id: str) -> Optional[AgentTask]:
        """Must be called with _tasks_lock held."""
        for t in self._tasks:
            if t.task_id == task_id:
                return t
        return None

    # ── Subscription ────────────────────────────────────────────────────────

    def subscribe(self, callback: Callable[[AgentTask], None]):
        """Subscribe to task update events. Callback runs on a background thread."""
        self._callbacks.append(callback)

    def _notify(self, task: AgentTask):
        for cb in list(self._callbacks):
            try:
                cb(task)
            except Exception:
                pass


# Module-level singleton — import this everywhere
monitor = AgentMonitor()
