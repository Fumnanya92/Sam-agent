"""
system/watchers/file_watcher.py — Watch indexed project directories for file changes.

Polls modification times every 10 seconds. When a file in a watched project changes,
emits a "file_changed" event on the bus.

Usage:
    from system.watchers.file_watcher import file_watcher
    file_watcher.start()       # starts background polling
    file_watcher.stop()
    file_watcher.watch("C:/path/to/project")   # add extra path
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("sam.watchers.file")

_POLL_INTERVAL = 10   # seconds
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".dart_tool", "build", "dist", ".venv", "venv"}
_WATCH_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".dart", ".rs", ".go", ".java", ".cs",
               ".html", ".css", ".json", ".yaml", ".yml", ".toml"}
_MAX_FILES_PER_PROJECT = 500


class FileWatcher:
    def __init__(self):
        self._watched_dirs: set[str] = set()
        self._mtime_cache: dict[str, float] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        # Seed from project index
        self._seed_from_index()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="FileWatcher")
        self._thread.start()
        logger.info(f"[FileWatcher] Started — watching {len(self._watched_dirs)} directories")

    def stop(self):
        self._running = False

    def watch(self, path: str):
        with self._lock:
            self._watched_dirs.add(str(Path(path).resolve()))

    def _seed_from_index(self):
        try:
            from system.project_index import project_index
            for proj in project_index.list_projects():
                p = proj.get("path", "")
                if p and Path(p).exists():
                    with self._lock:
                        self._watched_dirs.add(p)
        except Exception:
            pass

    def _poll_loop(self):
        while self._running:
            try:
                self._scan_all()
            except Exception as e:
                logger.debug(f"[FileWatcher] Poll error: {e}")
            time.sleep(_POLL_INTERVAL)

    def _scan_all(self):
        with self._lock:
            dirs = list(self._watched_dirs)
        for d in dirs:
            self._scan_dir(d)

    def _scan_dir(self, root: str):
        root_path = Path(root)
        if not root_path.exists():
            return
        count = 0
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                if Path(fname).suffix not in _WATCH_EXTS:
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    mtime = os.path.getmtime(full)
                    prev = self._mtime_cache.get(full)
                    if prev is None:
                        self._mtime_cache[full] = mtime
                    elif mtime > prev:
                        self._mtime_cache[full] = mtime
                        self._emit_change(full, root)
                except OSError:
                    pass
                count += 1
                if count >= _MAX_FILES_PER_PROJECT:
                    return

    def _emit_change(self, file_path: str, project_root: str):
        try:
            from system.event_bus import bus
            rel = os.path.relpath(file_path, project_root)
            bus.emit("file_changed", source="file_watcher", data={
                "path": file_path,
                "relative": rel,
                "project": project_root,
            })
            logger.debug(f"[FileWatcher] Changed: {rel}")
        except Exception:
            pass


file_watcher = FileWatcher()
