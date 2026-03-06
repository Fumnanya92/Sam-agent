"""
housekeeping.py — Downloads organizer and temp file cleaner.

Safe actions (no destructive operations without explicit call):
  - organize_downloads()  : move files into category subfolders
  - preview_downloads()   : return what would move without moving
  - download_count()      : count of non-partial files in Downloads
  - clear_stale_temps()   : remove partial/Chrome downloads older than 1 hour
"""
import shutil
from datetime import datetime
from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"

# Map of subfolder name → file extensions that belong there
CATEGORY_MAP: dict[str, set] = {
    "Images":     {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
                  ".ico", ".tiff", ".heic"},
    "Documents":  {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
                  ".txt", ".md", ".csv", ".odt", ".rtf", ".epub"},
    "Installers": {".exe", ".msi", ".msix", ".pkg", ".dmg", ".deb", ".rpm",
                  ".appx"},
    "Archives":   {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                  ".tar.gz"},
    "Audio":      {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Videos":     {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv"},
}

# Extensions treated as partial / incomplete — always skipped
_PARTIALS = {".crdownload", ".tmp", ".part", ".download"}


def _categorise(ext: str) -> str:
    """Return the folder name for a given file extension."""
    ext = ext.lower()
    for cat, exts in CATEGORY_MAP.items():
        if ext in exts:
            return cat
    return "Other"


def _iter_downloads():
    """Yield Path objects for complete files in ~/Downloads (top-level only)."""
    try:
        for p in DOWNLOADS.iterdir():
            if p.is_file() and p.suffix.lower() not in _PARTIALS:
                yield p
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_count() -> int:
    """Return number of complete (non-partial) files currently in Downloads."""
    return sum(1 for _ in _iter_downloads())


def preview_downloads() -> dict[str, list[str]]:
    """Return {category: [filenames]} showing what organize_downloads would do."""
    result: dict[str, list[str]] = {}
    for p in _iter_downloads():
        cat = _categorise(p.suffix)
        result.setdefault(cat, []).append(p.name)
    return result


def organize_downloads() -> dict[str, int]:
    """
    Move files from ~/Downloads into category subfolders.

    Returns {category: count_moved}.
    Skips files already inside a subfolder.
    Never overwrites existing files (appends _1, _2 … on collision).
    """
    moved: dict[str, int] = {}
    for p in list(_iter_downloads()):
        cat = _categorise(p.suffix)
        dest_dir = DOWNLOADS / cat
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / p.name

        # Resolve name collisions
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{p.stem}_{counter}{p.suffix}"
            counter += 1

        try:
            shutil.move(str(p), str(dest))
            moved[cat] = moved.get(cat, 0) + 1
        except Exception:
            pass

    return moved


def clear_stale_temps() -> int:
    """
    Remove .crdownload / .tmp / .part files older than 1 hour from Downloads.
    Returns count of files removed.
    """
    removed = 0
    cutoff = datetime.now().timestamp() - 3600
    try:
        for p in DOWNLOADS.iterdir():
            if p.is_file() and p.suffix.lower() in _PARTIALS:
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
                        removed += 1
                except Exception:
                    pass
    except Exception:
        pass
    return removed


def format_organize_result(moved: dict[str, int]) -> str:
    """Turn the moved-dict into a human-readable summary line."""
    if not moved:
        return "Downloads folder was already organised."
    total = sum(moved.values())
    parts = [f"{v} to {k}" for k, v in sorted(moved.items())]
    return f"Moved {total} file{'s' if total != 1 else ''}: {', '.join(parts)}."


# ---------------------------------------------------------------------------
# Screenshot archiver
# ---------------------------------------------------------------------------

import re as _re
import os as _os
from datetime import timedelta

_SCREENSHOT_PATTERNS = [
    _re.compile(r"screenshot", _re.IGNORECASE),
    _re.compile(r"screen.?shot", _re.IGNORECASE),
    _re.compile(r"snip", _re.IGNORECASE),
    _re.compile(r"capture", _re.IGNORECASE),
]
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


def _is_screenshot(name: str) -> bool:
    return any(pat.search(name) for pat in _SCREENSHOT_PATTERNS)


def archive_screenshots(dry_run: bool = False) -> int:
    """
    Move screenshot files from the Desktop to
    ~/Pictures/Screenshots/YYYY-MM/.

    Returns number of files moved (or that would be moved if dry_run=True).
    """
    desktop = Path.home() / "Desktop"
    month_folder = Path.home() / "Pictures" / "Screenshots" / datetime.now().strftime("%Y-%m")
    count = 0
    if not desktop.exists():
        return 0
    try:
        for src in desktop.iterdir():
            if not src.is_file():
                continue
            if src.suffix.lower() not in _IMAGE_EXTS:
                continue
            if not _is_screenshot(src.name):
                continue
            if not dry_run:
                month_folder.mkdir(parents=True, exist_ok=True)
                dest = month_folder / src.name
                c = 1
                while dest.exists():
                    dest = month_folder / f"{src.stem}_{c}{src.suffix}"
                    c += 1
                shutil.move(str(src), str(dest))
            count += 1
    except Exception:
        pass
    return count


# ---------------------------------------------------------------------------
# Temp file cleaner
# ---------------------------------------------------------------------------

def clean_temp_files(older_than_days: int = 7, dry_run: bool = False) -> tuple[int, float]:
    """
    Delete plain files in %TEMP% older than `older_than_days` days.

    Returns (n_deleted, mb_freed).
    Never removes directories.
    """
    temp_dir = Path(_os.environ.get("TEMP", "C:/Windows/Temp"))
    cutoff = datetime.now() - timedelta(days=older_than_days)
    deleted, freed = 0, 0
    if not temp_dir.exists():
        return 0, 0.0
    try:
        for p in temp_dir.iterdir():
            if not p.is_file():
                continue
            try:
                if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                    size = p.stat().st_size
                    if not dry_run:
                        p.unlink(missing_ok=True)
                    deleted += 1
                    freed += size
            except Exception:
                continue
    except PermissionError:
        pass
    return deleted, round(freed / (1024 * 1024), 1)


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

def get_housekeeping_report() -> dict:
    """
    Return a preview of all pending housekeeping actions without doing anything.
    """
    n_del, mb = clean_temp_files(dry_run=True)
    return {
        "downloads_preview": preview_downloads(),        # {cat: [filenames]}
        "screenshot_count": archive_screenshots(dry_run=True),
        "temp_files_count": n_del,
        "temp_mb": mb,
    }


def summarise_report(report: dict | None = None) -> str:
    """
    Natural-language summary of pending housekeeping work.
    If report is None, runs get_housekeeping_report() first.
    """
    if report is None:
        report = get_housekeeping_report()

    parts = []

    total_dl = sum(len(v) for v in report.get("downloads_preview", {}).values())
    if total_dl:
        parts.append(f"{total_dl} file{'s' if total_dl > 1 else ''} in Downloads to sort")

    n_ss = report.get("screenshot_count", 0)
    if n_ss:
        parts.append(f"{n_ss} screenshot{'s' if n_ss > 1 else ''} on the Desktop to archive")

    mb = report.get("temp_mb", 0)
    if mb > 10:
        parts.append(f"{mb:.0f} MB of old temp files to clear")

    if not parts:
        return "Everything looks tidy — nothing to organise right now."
    return "I found " + ", and ".join(parts) + ". Want me to take care of it?"
