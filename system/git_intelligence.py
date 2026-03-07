"""
Enhanced git state detection.
Provides file-level changes, dangerous states, large-file alerts, and dependency change detection.
"""
import subprocess
from pathlib import Path
from log.logger import get_logger

logger = get_logger("GIT_INTEL")

# Files whose modification indicates dependencies may need reinstalling
_DEP_FILES = {
    "package.json", "package-lock.json", "yarn.lock",
    "requirements.txt", "requirements-dev.txt",
    "Pipfile", "Pipfile.lock",
    "pyproject.toml", "setup.py", "setup.cfg",
    "pubspec.yaml", "pubspec.lock",
    "Gemfile", "Gemfile.lock",
    "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle",
}

# Files larger than this (bytes) trigger a staged-large-file alert
_LARGE_FILE_THRESHOLD = 500_000  # 500 KB


def _run(args: list[str], cwd: str, timeout: int = 5) -> str:
    """Run a git command and return stdout stripped, or '' on error."""
    try:
        result = subprocess.run(
            args, cwd=cwd,
            capture_output=True, text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_status(cwd: str) -> dict:
    """
    Return a rich dict describing current git state for a repository.

    Keys:
        changed_files   list[str]  — all modified/untracked filenames
        staged_files    list[str]  — staged (index) filenames
        unstaged_files  list[str]  — changed but not staged
        untracked_files list[str]  — new files not yet tracked
        large_staged    list[str]  — staged files over 500 KB ("{name} ({size}KB)")
        dep_changed     list[str]  — dep-file names that are changed/staged
        danger          str|None   — "MERGING" | "REBASING" | "DETACHED_HEAD" | None
        branch          str        — current branch name or ""
        ahead           int        — commits ahead of upstream (0 if unknown)
        cwd             str        — directory that was queried
    """
    result: dict = {
        "changed_files": [],
        "staged_files": [],
        "unstaged_files": [],
        "untracked_files": [],
        "large_staged": [],
        "dep_changed": [],
        "danger": None,
        "branch": "",
        "ahead": 0,
        "cwd": cwd,
    }

    if not cwd or not Path(cwd).exists():
        logger.warning(f"git_intelligence: cwd does not exist: {cwd!r}")
        return result

    try:
        # ── File changes ──────────────────────────────────────────────
        status_out = _run(["git", "status", "--porcelain"], cwd)
        for line in status_out.splitlines():
            if len(line) < 3:
                continue
            index_status  = line[0]   # staged col
            worktree_stat = line[1]   # unstaged col
            filename      = line[3:].strip().split(" -> ")[-1]  # handles renames

            if index_status != " " and index_status != "?":
                result["staged_files"].append(filename)
            if worktree_stat not in (" ", "?"):
                result["unstaged_files"].append(filename)
            if index_status == "?" and worktree_stat == "?":
                result["untracked_files"].append(filename)
            if filename not in result["changed_files"]:
                result["changed_files"].append(filename)

        # ── Danger states ─────────────────────────────────────────────
        git_dir = Path(cwd) / ".git"
        if (git_dir / "MERGE_HEAD").exists():
            result["danger"] = "MERGING"
        elif (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            result["danger"] = "REBASING"
        else:
            branch = _run(["git", "branch", "--show-current"], cwd, timeout=3)
            result["branch"] = branch
            if not branch:
                result["danger"] = "DETACHED_HEAD"

        if not result["branch"]:
            result["branch"] = _run(["git", "branch", "--show-current"], cwd, timeout=3)

        # ── Large staged files ────────────────────────────────────────
        for fname in result["staged_files"]:
            try:
                fpath = Path(cwd) / fname
                if fpath.is_file():
                    size = fpath.stat().st_size
                    if size > _LARGE_FILE_THRESHOLD:
                        result["large_staged"].append(f"{fname} ({size // 1024}KB)")
            except Exception:
                pass

        # ── Dependency file changes ───────────────────────────────────
        all_changed = (
            result["staged_files"]
            + result["unstaged_files"]
            + result["untracked_files"]
        )
        for fname in all_changed:
            if Path(fname).name in _DEP_FILES and fname not in result["dep_changed"]:
                result["dep_changed"].append(Path(fname).name)

        # ── Commits ahead of upstream ─────────────────────────────────
        ahead_str = _run(
            ["git", "rev-list", "--count", "@{u}..HEAD"], cwd, timeout=4
        )
        if ahead_str.isdigit():
            result["ahead"] = int(ahead_str)

    except Exception as e:
        logger.error(f"get_git_status failed: {e}")

    return result


def get_last_commit_message(cwd: str) -> str:
    """Return the subject line of the most recent commit, or ''."""
    return _run(["git", "log", "-1", "--pretty=%s"], cwd, timeout=3)


def get_recent_commits(cwd: str, n: int = 5) -> list[str]:
    """Return the last N commit subject lines."""
    out = _run(["git", "log", f"-{n}", "--oneline"], cwd, timeout=5)
    return [line.strip() for line in out.splitlines() if line.strip()]


def summarise_status(cwd: str) -> str:
    """Return a short spoken summary of the current git state."""
    gs = get_git_status(cwd)
    parts = []

    if gs["danger"] == "MERGING":
        return "Repo is mid-merge — resolve conflicts before doing anything else."
    if gs["danger"] == "REBASING":
        return "Repo is mid-rebase — be careful with commits right now."
    if gs["danger"] == "DETACHED_HEAD":
        parts.append("HEAD is detached — not on any branch.")

    n_staged   = len(gs["staged_files"])
    n_unstaged = len(gs["unstaged_files"])
    n_untracked = len(gs["untracked_files"])

    if n_staged:
        parts.append(f"{n_staged} file{'s' if n_staged != 1 else ''} staged")
    if n_unstaged:
        parts.append(f"{n_unstaged} unstaged")
    if n_untracked:
        parts.append(f"{n_untracked} untracked")

    if not parts:
        return "Clean workspace — nothing to commit."

    branch = gs.get("branch", "")
    prefix = f"On {branch}: " if branch else ""
    return prefix + ", ".join(parts) + "."
