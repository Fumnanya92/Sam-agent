"""
Terminal command execution with approval queue.
Golden rule: Observe → Analyze → Suggest → Wait for approval → Execute
"""
import subprocess
import os
import json
from pathlib import Path
from log.logger import get_logger

logger = get_logger("TERMINAL")


def get_cwd() -> str:
    """Return the active project directory (from last VS Code session) or cwd."""
    try:
        base = Path(__file__).resolve().parent.parent
        session_file = base / "memory" / "session_state.json"
        if session_file.exists():
            data = json.loads(session_file.read_text(encoding="utf-8"))
            cwd = data.get("git_cwd") or data.get("cwd")
            if cwd and Path(cwd).exists():
                return cwd
    except Exception:
        pass
    return os.getcwd()


class TerminalRunner:
    """Queue a shell command and run it only when the user confirms."""

    def __init__(self):
        self._pending: dict | None = None  # {command, cwd, description}

    # ── Public API ────────────────────────────────────────────────────────

    def schedule(self, command: str, cwd: str, description: str) -> None:
        """Queue a command for approval. Overwrites any previous pending command."""
        self._pending = {"command": command, "cwd": cwd, "description": description}
        logger.info(f"Scheduled: {description!r} — `{command}` in {cwd}")

    def get_pending(self) -> dict | None:
        return self._pending

    def has_pending(self) -> bool:
        return self._pending is not None

    def execute(self) -> str:
        """Run the pending command. Returns a spoken-ready result string."""
        if not self._pending:
            return "Nothing pending — say the command first."
        cmd = self._pending["command"]
        cwd = self._pending["cwd"]
        desc = self._pending["description"]
        self._pending = None

        logger.info(f"Executing: `{cmd}` in {cwd}")
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            raw = (proc.stdout + proc.stderr).strip()
            if proc.returncode == 0:
                if raw:
                    # Trim long output — speak first ~400 chars
                    spoken = raw[:400]
                    if len(raw) > 400:
                        spoken += "... (see terminal for full output)"
                    return spoken
                return f"{desc} completed."
            return (
                f"{desc} failed with exit code {proc.returncode}. "
                + (raw[:300] if raw else "No output.")
            )
        except subprocess.TimeoutExpired:
            return f"{desc} timed out after 60 seconds."
        except FileNotFoundError as e:
            return f"Command not found: {e}"
        except Exception as e:
            logger.error(f"Terminal execute failed: {e}")
            return f"Couldn't run {desc}: {e}"

    def cancel(self) -> str:
        """Discard the pending command."""
        if self._pending:
            desc = self._pending["description"]
            self._pending = None
            return f"Cancelled — {desc} won't run."
        return "Nothing to cancel."
