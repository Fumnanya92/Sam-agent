"""Live test for Sam v2 startup log reset behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Log Reset Live Test ===")
    logs_root = REPO_ROOT / "sam_v2" / "logs"
    runs_dir = logs_root / "runs"
    actions_dir = logs_root / "actions"
    runs_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)

    old_run = runs_dir / "stale-run.jsonl"
    old_action = actions_dir / "stale-action.jsonl"
    old_run.write_text("old\n", encoding="utf-8")
    old_action.write_text("old\n", encoding="utf-8")

    command = [sys.executable, "-m", "sam_v2", "--once", "what can you do", "--json"]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    if completed.returncode != 0:
        print("[FAIL] Log reset live test failed")
        print(f"  - sam_v2 startup failed: {completed.stderr or completed.stdout}")
        return 1

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        print("[FAIL] Log reset live test failed")
        print(f"  - startup output was not JSON: {exc}")
        return 1

    try:
        _assert(payload.get("status") == "success", "startup request did not succeed")
        _assert(not old_run.exists(), "stale run log was not removed")
        _assert(not old_action.exists(), "stale action log was not removed")
        run_logs = list(runs_dir.glob("*.jsonl"))
        action_logs = list(actions_dir.glob("*.jsonl"))
        _assert(len(run_logs) >= 1, "no new run logs were created")
        _assert(len(action_logs) >= 1, "no new action logs were created")
        print("[PASS] Startup clears stale logs and creates fresh log files")
        return 0
    except Exception as exc:
        print("[FAIL] Log reset live test failed")
        print(f"  - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
