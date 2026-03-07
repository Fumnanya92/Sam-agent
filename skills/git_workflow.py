"""
Git workflow skill — full git operations with terminal_runner approval.
Intents: git_commit, git_branch, git_diff_summary, git_status_full
"""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any

from log.logger import get_logger

logger = get_logger("GIT_WORKFLOW")


def _run(args: list[str], cwd: str, timeout: int = 8) -> str:
    try:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=timeout
        ).stdout.strip()
    except Exception:
        return ""


def _get_cwd() -> str:
    from actions.terminal import get_cwd
    return get_cwd()


# ── Commit ────────────────────────────────────────────────────────────────────

def _infer_message(diff_stat: str, cwd: str) -> str:
    """Reuse commit_writer heuristic to generate a commit message."""
    try:
        from skills.commit_writer import _infer_commit_message
        return _infer_commit_message(diff_stat, cwd)
    except Exception:
        return "chore: update files"


def _handle_commit(parameters: dict, ui: Any, ctx: dict) -> str:
    terminal_runner = ctx.get("terminal_runner")
    if terminal_runner is None:
        return "Terminal execution isn't available — can't commit."

    cwd = _get_cwd()
    if not cwd:
        return "I can't find your project directory."

    from system.git_intelligence import get_git_status
    gs = get_git_status(cwd)

    if not gs.get("changed_files"):
        return "Nothing to commit — workspace is clean."

    # Get diff stat to build message
    diff_stat = _run(["git", "diff", "--stat", "HEAD"], cwd) or _run(["git", "status", "--short"], cwd)
    msg = _infer_message(diff_stat, cwd)

    staged = gs.get("staged_files", [])
    unstaged = gs.get("unstaged_files", [])
    total = len(gs["changed_files"])

    # Build git command: stage everything then commit
    # Use double quotes carefully for Windows
    safe_msg = msg.replace('"', "'")
    git_cmd = f'git add -A && git commit -m "{safe_msg}"'
    terminal_runner.schedule(git_cmd, cwd, f"git commit: {safe_msg}")

    detail = f"{total} file{'s' if total != 1 else ''} changed"
    return (
        f"Ready to commit {detail}. Message: '{safe_msg}'. "
        f"Say confirm to run, or cancel to skip."
    )


# ── Branch ────────────────────────────────────────────────────────────────────

def _handle_branch(parameters: dict, ui: Any, ctx: dict) -> str:
    terminal_runner = ctx.get("terminal_runner")
    if terminal_runner is None:
        return "Terminal execution isn't available — can't create a branch."

    branch_name = (
        parameters.get("branch_name")
        or parameters.get("name")
        or parameters.get("text")
        or ""
    ).strip()

    if not branch_name:
        return "What should I name the branch?"

    # Sanitise: spaces → dashes, lowercase
    branch_name = branch_name.lower().replace(" ", "-")

    cwd = _get_cwd()
    terminal_runner.schedule(
        f"git checkout -b {branch_name}",
        cwd,
        f"create branch {branch_name}",
    )
    return f"I'll create branch `{branch_name}`. Say confirm to go ahead."


# ── Diff summary ──────────────────────────────────────────────────────────────

def _handle_diff(ui: Any, ctx: dict) -> str:
    cwd = _get_cwd()
    if not cwd:
        return "I can't find your project directory."

    stat = _run(["git", "diff", "--stat", "HEAD"], cwd)
    log  = _run(["git", "log", "--oneline", "-5"], cwd)

    parts = []
    if stat:
        # Count lines changed
        last = stat.splitlines()[-1] if stat.splitlines() else ""
        parts.append(f"Changes: {last}") if last else None

    if log:
        commits = log.splitlines()
        parts.append(f"Last {len(commits)} commit{'s' if len(commits) != 1 else ''}: {commits[0]}")

    if not parts:
        return "Nothing to show — workspace looks clean."

    return " | ".join(parts) + "."


# ── Status full ───────────────────────────────────────────────────────────────

def _handle_status(ui: Any, ctx: dict) -> str:
    from system.git_intelligence import summarise_status
    cwd = _get_cwd()
    if not cwd:
        return "I can't find your project directory."
    return summarise_status(cwd)


# ── Skill router ──────────────────────────────────────────────────────────────

def _run_skill(parameters: dict, ui: Any, **ctx) -> str:
    intent = parameters.get("_intent", "git_commit")

    if intent in ("git_commit", "commit_changes", "commit_my_changes"):
        return _handle_commit(parameters, ui, ctx)
    if intent in ("git_branch", "create_branch"):
        return _handle_branch(parameters, ui, ctx)
    if intent in ("git_diff_summary", "show_diff"):
        return _handle_diff(ui, ctx)
    if intent in ("git_status_full", "full_status"):
        return _handle_status(ui, ctx)

    return "Unknown git workflow intent."


SKILL_MANIFEST = {
    "name": "git_workflow",
    "description": "Full git workflow — commit with message, create branches, see diff summaries",
    "intents": [
        "git_commit", "commit_changes", "commit_my_changes",
        "git_branch", "create_branch",
        "git_diff_summary", "show_diff",
        "git_status_full", "full_status",
    ],
    "trigger_phrases": [
        "commit my changes", "commit this", "git commit",
        "create branch", "new branch", "switch to new branch",
        "what changed", "show diff", "git diff",
        "full git status", "what's staged",
    ],
    "run": _run_skill,
}
