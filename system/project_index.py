"""
system/project_index.py — Project discovery and fuzzy search.

Scans the user's Desktop and Documents for project directories by looking for
known manifest / signature files. Persists the index to memory/project_index.json
so lookups are instant without re-scanning.

Usage:
    from system.project_index import project_index

    # Find a project by approximate name
    match = project_index.find("guest attendance")
    if match:
        print(match["path"], match["stack"])

    # Force a rescan
    project_index.scan()

    # Full list
    for p in project_index.list_projects():
        print(p["name"], p["stack"], p["path"])
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ── Config ─────────────────────────────────────────────────────────────────────

_INDEX_PATH = Path(__file__).resolve().parent.parent / "memory" / "project_index.json"
_SCAN_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Projects",
    Path.home() / "dev",
    Path.home() / "source",
]
_MAX_DEPTH = 4
_RESCAN_INTERVAL_SECS = 30 * 60  # 30 minutes

# Signature files that identify a directory as a project root, mapped to stack name
_SIGNATURES: list[tuple[str, str]] = [
    ("package.json", "node"),
    ("pubspec.yaml", "flutter"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("requirements.txt", "python"),
    ("Cargo.toml", "rust"),
    ("go.mod", "go"),
    ("pom.xml", "java"),
    ("build.gradle", "java"),
    ("*.sln", "dotnet"),
    ("*.csproj", "dotnet"),
    (".git", "git"),  # generic fallback
]


def _detect_stack(project_path: Path) -> str:
    """Return the primary stack for a project directory."""
    for filename, stack in _SIGNATURES:
        if "*" in filename:
            ext = filename.replace("*", "")
            matches = list(project_path.glob(f"*{ext}"))
            if matches:
                return stack
        else:
            if (project_path / filename).exists():
                return stack
    return "unknown"


def _detect_languages(project_path: Path) -> list[str]:
    """Detect programming languages from file extensions (top-level + one level)."""
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".dart": "Dart",
        ".rs": "Rust", ".go": "Go", ".java": "Java", ".cs": "C#",
        ".cpp": "C++", ".c": "C", ".swift": "Swift", ".kt": "Kotlin",
        ".rb": "Ruby", ".php": "PHP", ".html": "HTML", ".css": "CSS",
    }
    counts: dict[str, int] = {}
    try:
        for f in list(project_path.iterdir()) + [
            sub for d in project_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            for sub in d.iterdir()
            if sub.is_file()
        ]:
            if f.is_file():
                lang = ext_map.get(f.suffix.lower())
                if lang:
                    counts[lang] = counts.get(lang, 0) + 1
    except (PermissionError, OSError):
        pass
    return sorted(counts, key=lambda k: -counts[k])[:4]


def _read_readme_summary(project_path: Path) -> str:
    """Return first non-empty paragraph from README.md (or .txt), capped at 200 chars."""
    for name in ("README.md", "readme.md", "README.txt", "README.rst"):
        readme = project_path / name
        if readme.exists():
            try:
                text = readme.read_text(encoding="utf-8", errors="ignore")
                # Strip markdown headers / badges and grab first real paragraph
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines:
                    if not line.startswith(("#", "!", "[", "|", ">")):
                        return line[:200]
            except Exception:
                pass
    return ""


def _read_git_remote(project_path: Path) -> str:
    """Return the origin remote URL from .git/config if present."""
    config = project_path / ".git" / "config"
    if not config.exists():
        return ""
    try:
        text = config.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'url\s*=\s*(.+)', text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _read_project_name(project_path: Path, stack: str) -> str:
    """Try to read the canonical name from the project manifest."""
    try:
        if stack == "node":
            pkg = project_path / "package.json"
            if pkg.exists():
                data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
                return data.get("name") or project_path.name
        if stack == "python":
            for fname in ("pyproject.toml", "setup.py"):
                f = project_path / fname
                if f.exists():
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', text)
                    if m:
                        return m.group(1)
        if stack == "flutter":
            pubspec = project_path / "pubspec.yaml"
            if pubspec.exists():
                text = pubspec.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'^name\s*:\s*(.+)', text, re.MULTILINE)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return project_path.name


def _scan_for_projects(roots: list[Path], max_depth: int) -> list[dict]:
    """Walk roots and collect project metadata dicts."""
    found: list[dict] = []
    seen_paths: set[str] = set()

    sig_files = {s for s, _ in _SIGNATURES if "*" not in s}
    sig_exts = [s.replace("*", "") for s, _ in _SIGNATURES if "*" in s]

    def _has_signature(p: Path) -> bool:
        for sf in sig_files:
            if (p / sf).exists():
                return True
        for ext in sig_exts:
            if list(p.glob(f"*{ext}")):
                return True
        return False

    for root in roots:
        if not root.exists():
            continue
        try:
            for dirpath, dirnames, _ in os.walk(root):
                depth = dirpath.replace(str(root), "").count(os.sep)
                # Prune hidden dirs and node_modules
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build")
                ]
                if depth >= max_depth:
                    dirnames.clear()
                    continue

                p = Path(dirpath)
                if str(p) in seen_paths:
                    continue
                if not _has_signature(p):
                    continue

                seen_paths.add(str(p))
                stack = _detect_stack(p)
                name = _read_project_name(p, stack)
                last_modified = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")

                found.append({
                    "name": name,
                    "folder": p.name,
                    "path": str(p),
                    "stack": stack,
                    "languages": _detect_languages(p),
                    "git_remote": _read_git_remote(p),
                    "readme": _read_readme_summary(p),
                    "last_modified": last_modified,
                    "indexed_at": datetime.now().isoformat(timespec="seconds"),
                })
        except (PermissionError, OSError):
            pass

    return found


def _fuzzy_score(query: str, candidate: str) -> float:
    """Return similarity score 0-1 between query and candidate (case-insensitive)."""
    q = query.lower().replace("-", " ").replace("_", " ")
    c = candidate.lower().replace("-", " ").replace("_", " ")
    if q in c or c in q:
        return 0.9
    return SequenceMatcher(None, q, c).ratio()


# ── ProjectIndex class ─────────────────────────────────────────────────────────

class ProjectIndex:
    def __init__(self):
        self._projects: list[dict] = []
        self._loaded = False
        self._last_scan: float = 0.0
        self._lock = threading.Lock()

    def _load_from_disk(self):
        try:
            if _INDEX_PATH.exists():
                data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
                self._projects = data.get("projects", [])
                self._last_scan = data.get("scanned_at_ts", 0.0)
                return True
        except Exception:
            pass
        return False

    def _save_to_disk(self):
        try:
            _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            _INDEX_PATH.write_text(json.dumps({
                "scanned_at": datetime.now().isoformat(timespec="seconds"),
                "scanned_at_ts": self._last_scan,
                "projects": self._projects,
            }, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[ProjectIndex] Failed to save: {e}")

    def scan(self, force: bool = False) -> int:
        """Scan for projects. Returns number found. Thread-safe."""
        with self._lock:
            now = time.time()
            if not force and self._loaded and (now - self._last_scan) < _RESCAN_INTERVAL_SECS:
                return len(self._projects)
            projects = _scan_for_projects(_SCAN_ROOTS, _MAX_DEPTH)
            self._projects = projects
            self._last_scan = now
            self._loaded = True
            self._save_to_disk()
            return len(projects)

    def load(self):
        """Load from disk if available; schedule a background scan if stale."""
        if self._loaded:
            return
        loaded = self._load_from_disk()
        self._loaded = True
        stale = (time.time() - self._last_scan) > _RESCAN_INTERVAL_SECS
        if not loaded or stale:
            threading.Thread(target=self.scan, kwargs={"force": True}, daemon=True).start()

    def find(self, query: str, threshold: float = 0.4) -> dict | None:
        """Return the best-matching project for a fuzzy name query, or None."""
        self.load()
        if not query:
            return None
        best: dict | None = None
        best_score = 0.0
        for proj in self._projects:
            for field in (proj.get("name", ""), proj.get("folder", "")):
                score = _fuzzy_score(query, field)
                if score > best_score:
                    best_score = score
                    best = proj
        return best if best_score >= threshold else None

    def find_all(self, query: str, threshold: float = 0.35, limit: int = 5) -> list[dict]:
        """Return top matches for a query, sorted by score."""
        self.load()
        scored = []
        for proj in self._projects:
            score = max(
                _fuzzy_score(query, proj.get("name", "")),
                _fuzzy_score(query, proj.get("folder", "")),
            )
            if score >= threshold:
                scored.append((score, proj))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:limit]]

    def list_projects(self) -> list[dict]:
        self.load()
        return list(self._projects)

    def summary(self) -> str:
        """Short human-readable summary for Sam to speak."""
        self.load()
        total = len(self._projects)
        if not total:
            return "No projects indexed yet."
        stacks: dict[str, int] = {}
        for p in self._projects:
            s = p.get("stack", "unknown")
            stacks[s] = stacks.get(s, 0) + 1
        stack_str = ", ".join(f"{v} {k}" for k, v in sorted(stacks.items(), key=lambda x: -x[1]))
        return f"{total} projects indexed: {stack_str}."


# Singleton
project_index = ProjectIndex()
