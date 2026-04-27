# agent/utils.py
# Shared utilities for agent layer and action modules.
# Import from here instead of re-defining in each file.

import re
import subprocess
import platform
from datetime import datetime
from pathlib import Path


# ── Code cleaning ─────────────────────────────────────────────────────────────

def clean_code(text: str) -> str:
    """Strip markdown code fences from AI-generated code output."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ── Error detection ───────────────────────────────────────────────────────────

_ERROR_SIGNALS = [
    "error", "exception", "traceback", "syntaxerror",
    "nameerror", "typeerror", "importerror", "stderr", "failed", "crash",
]


def has_error(output: str) -> bool:
    """Return True if subprocess output looks like an error."""
    if "timed out" in output.lower():
        return False
    return any(s in output.lower() for s in _ERROR_SIGNALS)


# ── Desktop text file save ────────────────────────────────────────────────────

def save_to_desktop_text(content: str, filename_prefix: str) -> str:
    """
    Save text content to a timestamped file on the Desktop and open it.

    Returns the full path of the saved file.
    """
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe     = re.sub(r"[^\w\-]", "_", filename_prefix)
    filename = f"{safe}_{ts}.txt"
    desktop  = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    filepath = desktop / filename

    filepath.write_text(content, encoding="utf-8")
    print(f"[utils] Saved: {filepath}")

    system  = platform.system()
    open_fn = {
        "Windows": lambda p: subprocess.Popen(["notepad.exe", str(p)]),
        "Darwin":  lambda p: subprocess.Popen(["open", "-t", str(p)]),
        "Linux":   lambda p: subprocess.Popen(["xdg-open", str(p)]),
    }
    opener = open_fn.get(system)
    if opener:
        try:
            opener(filepath)
        except Exception as e:
            print(f"[utils] Could not open file: {e}")

    return str(filepath)
