# actions/file_controller.py
# File management — create, delete, move, rename, list, find, organize
# Lifted from Mark-XXX-main (no AI dependency, copied as-is)

import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import send2trash
    _HAVE_SEND2TRASH = True
except ImportError:
    _HAVE_SEND2TRASH = False


# ─── Recent-files registry (disk-backed) ─────────────────────────────────────
# Records files Sam has just written so he can find / run them even after a
# restart. Persisted as a flat JSON list at ``~/.sam/recent_files.json`` with
# a 20-entry cap. All disk I/O is best-effort — failures never crash Sam.
_RECENT_FILES: list[dict] = []
_RECENT_LIMIT = 20
_RECENT_PATH = Path.home() / ".sam" / "recent_files.json"


def _hydrate_recent_files() -> None:
    """Load the registry from disk on first import. Silent on any failure."""
    try:
        if _RECENT_PATH.exists():
            data = json.loads(_RECENT_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                _RECENT_FILES.extend(
                    e for e in data
                    if isinstance(e, dict) and "path" in e
                )
                del _RECENT_FILES[_RECENT_LIMIT:]
    except Exception:
        # Corrupt or unreadable — start clean. Don't crash imports.
        pass


def _persist_recent_files() -> None:
    """Write the current registry to disk. Best-effort, no exceptions raised."""
    try:
        _RECENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RECENT_PATH.write_text(
            json.dumps(_RECENT_FILES, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _register_written(path: Path, action: str) -> None:
    """Record a successful file write so Sam can recall the path later.

    Survives restarts: writes the current list to ``~/.sam/recent_files.json``
    after every update.
    """
    try:
        abs_path = str(path.resolve())
        # Remove duplicate entry if already present so it bubbles to top
        for entry in list(_RECENT_FILES):
            if entry.get("path") == abs_path:
                _RECENT_FILES.remove(entry)
                break
        _RECENT_FILES.insert(0, {
            "path": abs_path,
            "name": path.name,
            "ext":  path.suffix.lower(),
            "action": action,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        del _RECENT_FILES[_RECENT_LIMIT:]
        _persist_recent_files()
    except Exception:
        pass


def get_last_written_file(extension: str | None = None) -> dict | None:
    """Return the most recently written file (optionally filtered by extension)."""
    ext = ("." + extension.lstrip(".").lower()) if extension else None
    for entry in _RECENT_FILES:
        if ext is None or entry.get("ext") == ext:
            return entry
    return None


def list_recent_written(limit: int = 10) -> list[dict]:
    """Return up to ``limit`` recently-written files, newest first."""
    return list(_RECENT_FILES[:max(1, int(limit))])


# Hydrate on import so Sam remembers across restarts.
_hydrate_recent_files()


# ─── Notes & log (consolidated from actions/file_ops.py) ─────────────────────
# Sam's notes/log root. Module-level so test code can monkey-patch DAILY_LOG.
NOTES_DIR = Path.home() / "Documents" / "Sam Notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)
DAILY_LOG = NOTES_DIR / "daily_log.txt"

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


def create_note(title: str, content: str = "", tag: str = "") -> tuple[str, str]:
    """Create a structured note and return (path, announcement).

    Notes are saved to ``~/Documents/Sam Notes/YYYY/MonthName/Category.md``.
    Multiple notes in the same category are appended to the same file with a
    timestamped heading.
    """
    now = datetime.now()
    year_str  = now.strftime("%Y")
    month_str = now.strftime("%B")
    category  = _infer_category(title, content)

    dest_dir = NOTES_DIR / year_str / month_str
    dest_dir.mkdir(parents=True, exist_ok=True)

    path = dest_dir / f"{category}.md"
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

    _register_written(path, "create_note")
    friendly = f"Sam Notes → {year_str} → {month_str} → {category}.md"
    return str(path), f"Saving to {friendly}."


def append_to_log(entry: str) -> str:
    """Append a timestamped entry to the daily log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {entry}\n")
    return str(DAILY_LOG)


def find_files_quick(name: str, search_root: str | None = None,
                     max_results: int = 5) -> list[str]:
    """Lightweight name-substring file search returning a list of absolute paths.

    Distinct from the dispatcher's ``find_files`` which returns a formatted
    user-facing string. Used by handlers that need a programmable list result.
    """
    root = Path(search_root) if search_root else Path.home()
    results: list[str] = []
    try:
        for p in root.rglob(f"*{name}*"):
            if p.is_file():
                results.append(str(p))
            if len(results) >= max_results:
                break
    except PermissionError:
        pass
    return results


def open_path(path: str) -> bool:
    """Open a file or folder using the OS default handler."""
    try:
        import os as _os
        _os.startfile(path)  # Windows: opens with default association
        return True
    except Exception:
        return False


def open_notes_folder() -> bool:
    """Open Sam's notes directory in the OS file manager."""
    return open_path(str(NOTES_DIR))


def _get_desktop() -> Path:
    return Path.home() / "Desktop"


def _get_downloads() -> Path:
    return Path.home() / "Downloads"


def _resolve_path(raw: str) -> Path:
    shortcuts = {
        "desktop":   Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "pictures":  Path.home() / "Pictures",
        "music":     Path.home() / "Music",
        "videos":    Path.home() / "Videos",
        "home":      Path.home(),
    }
    lower = raw.strip().lower()
    if lower in shortcuts:
        return shortcuts[lower]
    return Path(raw).expanduser()


def _format_size(bytes_size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def list_files(path: str = "desktop", show_hidden: bool = False) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"Path not found: {target}"
        if not target.is_dir():
            return f"Not a directory: {target}"
        items = []
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            if item.is_dir():
                items.append(f"[DIR] {item.name}/")
            else:
                size = _format_size(item.stat().st_size)
                items.append(f"[FILE] {item.name} ({size})")
        if not items:
            return f"Directory is empty: {target}"
        return f"Contents of {target.name}/ ({len(items)} items):\n" + "\n".join(items)
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error listing files: {e}"


def create_file(path: str, content: str = "") -> str:
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _register_written(target, "create_file")
        # Include the absolute path in the success message so the LLM
        # (and the user) can refer back to it when asked to run/open it later.
        return f"File created: {target.name} at {target.resolve()}"
    except Exception as e:
        return f"Could not create file: {e}"


def create_folder(path: str) -> str:
    try:
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {target}"
    except Exception as e:
        return f"Could not create folder: {e}"


def delete_file(path: str, confirm: bool = True) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"Not found: {path}"
        if _HAVE_SEND2TRASH:
            send2trash.send2trash(str(target))
            return f"Moved to Recycle Bin: {target.name}"
        if target.is_dir():
            shutil.rmtree(target)
            return f"Folder deleted: {target.name}"
        else:
            target.unlink()
            return f"File deleted: {target.name}"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Could not delete: {e}"


def move_file(source: str, destination: str) -> str:
    try:
        src = Path(source).expanduser()
        dst = _resolve_path(destination)
        if not src.exists():
            return f"Source not found: {source}"
        if dst.is_dir():
            dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved: {src.name} -> {dst.parent.name}/"
    except Exception as e:
        return f"Could not move: {e}"


def copy_file(source: str, destination: str) -> str:
    try:
        src = Path(source).expanduser()
        dst = _resolve_path(destination)
        if not src.exists():
            return f"Source not found: {source}"
        if dst.is_dir():
            dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return f"Copied: {src.name} -> {dst.parent.name}/"
    except Exception as e:
        return f"Could not copy: {e}"


def rename_file(path: str, new_name: str) -> str:
    try:
        target   = Path(path).expanduser()
        new_path = target.parent / new_name
        if not target.exists():
            return f"Not found: {path}"
        if new_path.exists():
            return f"A file named '{new_name}' already exists."
        target.rename(new_path)
        return f"Renamed: {target.name} -> {new_name}"
    except Exception as e:
        return f"Could not rename: {e}"


def read_file(path: str, max_chars: int = 3000) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"File not found: {path}"
        if not target.is_file():
            return f"Not a file: {path}"
        content = target.read_text(encoding="utf-8", errors="ignore")
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... (truncated, {len(content)} total chars)"
        return content
    except Exception as e:
        return f"Could not read file: {e}"


def write_file(path: str, content: str, append: bool = False) -> str:
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        _register_written(target, "append" if append else "write")
        action = "Appended to" if append else "Written to"
        return f"{action}: {target.name} at {target.resolve()}"
    except Exception as e:
        return f"Could not write file: {e}"


def find_files(name: str = "", extension: str = "", path: str = "home",
               max_results: int = 20) -> str:
    try:
        search_path = _resolve_path(path)
        if not search_path.exists():
            return f"Search path not found: {path}"
        results = []
        pattern = f"*{extension}" if extension else "*"
        for item in search_path.rglob(pattern):
            if item.is_file():
                if name and name.lower() not in item.name.lower():
                    continue
                size = _format_size(item.stat().st_size)
                results.append(f"{item.name} ({size}) — {item.parent}")
                if len(results) >= max_results:
                    break
        if not results:
            query = name or extension or "files"
            return f"No {query} found in {search_path.name}/"
        return f"Found {len(results)} file(s):\n" + "\n".join(results)
    except Exception as e:
        return f"Search error: {e}"


def get_largest_files(path: str = "home", count: int = 10) -> str:
    try:
        search_path = _resolve_path(path)
        if not search_path.exists():
            return f"Path not found: {path}"
        files = []
        for item in search_path.rglob("*"):
            if item.is_file():
                try:
                    files.append((item.stat().st_size, item))
                except Exception:
                    continue
        files.sort(reverse=True)
        top = files[:count]
        if not top:
            return "No files found."
        lines = [f"Top {len(top)} largest files in {search_path.name}/:"]
        for size, f in top:
            lines.append(f"  {_format_size(size):>10}  {f.name}  ({f.parent})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def get_disk_usage(path: str = "home") -> str:
    try:
        target = _resolve_path(path)
        usage  = shutil.disk_usage(target)
        total  = _format_size(usage.total)
        used   = _format_size(usage.used)
        free   = _format_size(usage.free)
        pct    = usage.used / usage.total * 100
        return (
            f"Disk usage for {target}:\n"
            f"  Total : {total}\n"
            f"  Used  : {used} ({pct:.1f}%)\n"
            f"  Free  : {free}"
        )
    except Exception as e:
        return f"Could not get disk usage: {e}"


# organize_desktop() removed — delegated to actions/desktop.py (richer implementation)


def get_file_info(path: str) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"Not found: {path}"
        stat = target.stat()
        info = {
            "Name":      target.name,
            "Type":      "Folder" if target.is_dir() else "File",
            "Size":      _format_size(stat.st_size),
            "Location":  str(target.parent),
            "Created":   datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "Modified":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "Extension": target.suffix or "None",
        }
        return "\n".join(f"  {k}: {v}" for k, v in info.items())
    except Exception as e:
        return f"Could not get file info: {e}"


def file_controller(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    action  = (parameters or {}).get("action", "").lower().strip()
    path    = (parameters or {}).get("path", "desktop")
    name    = (parameters or {}).get("name", "")
    content = (parameters or {}).get("content", "")

    def _full_path(p: str, n: str) -> str:
        base = _resolve_path(p)
        return str(base / n) if n else str(base)

    result = "Unknown action."
    try:
        if action == "list":
            result = list_files(path)
        elif action == "create_file":
            result = create_file(_full_path(path, name), content=content)
        elif action == "create_folder":
            result = create_folder(_full_path(path, name))
        elif action == "delete":
            result = delete_file(_full_path(path, name))
        elif action == "move":
            result = move_file(_full_path(path, name), parameters.get("destination", ""))
        elif action == "copy":
            result = copy_file(_full_path(path, name), parameters.get("destination", ""))
        elif action == "rename":
            result = rename_file(_full_path(path, name), parameters.get("new_name", ""))
        elif action == "read":
            result = read_file(_full_path(path, name))
        elif action == "write":
            result = write_file(_full_path(path, name), content=content,
                                append=parameters.get("append", False))
        elif action == "find":
            result = find_files(name=name or parameters.get("name", ""),
                                extension=parameters.get("extension", ""),
                                path=path,
                                max_results=parameters.get("max_results", 20))
        elif action == "largest":
            result = get_largest_files(path=path, count=parameters.get("count", 10))
        elif action == "disk_usage":
            result = get_disk_usage(path)
        elif action == "organize_desktop":
            # Delegate to desktop.py which has the richer implementation
            from actions.desktop import organize_desktop as _organize_desktop
            result = _organize_desktop()
        elif action == "info":
            result = get_file_info(_full_path(path, name))
        elif action in ("recent_files", "recent"):
            limit = int(parameters.get("limit", 10) or 10)
            recent = list_recent_written(limit)
            if not recent:
                result = "No files have been written yet this session."
            else:
                lines = [f"Recent files written this session ({len(recent)}):"]
                for r in recent:
                    lines.append(f"  [{r['action']:<11}] {r['path']}  ({r['ts']})")
                result = "\n".join(lines)
        elif action in ("last_file", "last_written"):
            ext = parameters.get("extension") or None
            entry = get_last_written_file(ext)
            if not entry:
                tail = f" with extension {ext}" if ext else ""
                result = f"No recently written file{tail}."
            else:
                result = (
                    f"Last written file: {entry['name']}\n"
                    f"  path: {entry['path']}\n"
                    f"  ext:  {entry['ext']}\n"
                    f"  action: {entry['action']}\n"
                    f"  at: {entry['ts']}"
                )
        else:
            result = f"Unknown action: '{action}'"
    except Exception as e:
        result = f"File controller error: {e}"

    if player:
        player.write_log(f"[file] {result[:60]}")
    return result
