"""Structured logger for Sam v2 live tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


LOG_DIR = Path("sam_v2/logs/tests")
LOG_DIR.mkdir(parents=True, exist_ok=True)


class TestRunLogger:
    def __init__(self, test_name: str):
        self.run_id = str(uuid4())
        self.test_name = test_name
        self.log_file = LOG_DIR / f"{test_name}_{self.run_id}.jsonl"
        self.event("started", {"test_name": test_name})

    def event(self, status: str, data: dict | None = None) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": self.run_id,
            "test_name": self.test_name,
            "status": status,
            "data": data or {},
        }
        with open(self.log_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def pass_step(self, step: str, data: dict | None = None) -> None:
        self.event("pass", {"step": step, **(data or {})})

    def fail_step(self, step: str, error: str) -> None:
        self.event("fail", {"step": step, "error": error})

    def complete(self, success: bool, failures: list[str]) -> None:
        self.event(
            "completed",
            {
                "success": success,
                "failure_count": len(failures),
                "failures": failures,
            },
        )
