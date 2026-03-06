"""
File operations for Sam.
Covers: create notes, append to log, find files by name, open files.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime
from log.logger import get_logger

logger = get_logger("FILE_OPS")

# Sam stores notes/logs here by default
NOTES_DIR = Path.home() / "Documents" / "Sam Notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)

DAILY_LOG = NOTES_DIR / "daily_log.txt"

# ---------------------------------------------------------------------------
# Note category inference
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Ideas":    ["idea", "concept", "thought", "notion", "dream", "imagine", "what if"],
    "Tasks":    ["todo", "task", "do this", "must", "need to", "should", "fix", "finish"],
    "Research": ["research", "look into", "investigate", "study", "find out", "explore"],
    "Bugs":     ["bug", "error", "crash", "fail", "broken", "issue", "exception"],
    "Meetings": ["meeting", "call", "sync", "standup", "discuss", "agenda"],
    "Personal": ["personal", "health", "family", "life", "reminder", "feeling"],
}


def _infer_category(title: str, content: str = "") -> str:
    combined = (title + " " + content).lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return cat
    return "Notes"

# ------------------------------------------------------------------ #
# Note creation
# ------------------------------------------------------------------ #

def create_note(title: str, content: str = "", tag: str = "") -> tuple[str, str]:
    """
    Create a structured note and return (path, announcement).

    Notes are saved to:
        ~/Documents/Sam Notes/YYYY/MonthName/Category.md

    Multiple notes in the same category are appended to the same file
    with a timestamped heading, so the folder stays tidy.
    """
    now = datetime.now()
    year_str  = now.strftime("%Y")
    month_str = now.strftime("%B")   # e.g. "March"
    category  = _infer_category(title, content)

    dest_dir = NOTES_DIR / year_str / month_str
    dest_dir.mkdir(parents=True, exist_ok=True)

    path = dest_dir / f"{category}.md"

    # Append entry with a timestamped heading
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    tag_line  = f"\n**Tags:** {tag}" if tag else ""
    entry = (
        f"\n---\n"
        f"## {title}\n"
        f"*{timestamp}*{tag_line}\n\n"
        f"{content}\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)

    # Human-friendly path for Sam to announce
    friendly = f"Sam Notes \u2192 {year_str} \u2192 {month_str} \u2192 {category}.md"
    announcement = f"Saving to {friendly}."

    logger.info(f"Note saved: {path}")
    return str(path), announcement


def append_to_log(entry: str) -> str:
    """Append a timestamped entry to the daily log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {entry}\n")
    return str(DAILY_LOG)


# ------------------------------------------------------------------ #
# File search
# ------------------------------------------------------------------ #

def find_files(name: str, search_root: str | None = None, max_results: int = 5) -> list[str]:
    """
    Search for files whose name matches `name` (case-insensitive substring).
    Searches under search_root (default: user home + Documents).
    """
    root = Path(search_root) if search_root else Path.home()
    results = []
    try:
        for p in root.rglob(f"*{name}*"):
            if p.is_file():
                results.append(str(p))
            if len(results) >= max_results:
                break
    except PermissionError:
        pass
    return results


# ------------------------------------------------------------------ #
# Open file / folder in Explorer / default app
# ------------------------------------------------------------------ #

def open_path(path: str) -> bool:
    """Open a file or folder using the OS default handler."""
    try:
        os.startfile(path)
        return True
    except Exception as e:
        logger.error(f"open_path failed for '{path}': {e}")
        return False


def open_notes_folder() -> bool:
    """Open Sam's notes directory in Windows Explorer."""
    return open_path(str(NOTES_DIR))
