"""
skills/commit_writer.py — Auto-generate a conventional commit message.

Reads `git diff --staged` from the last known repo.
Returns a properly formatted commit message Sam can speak and copy.

Trigger phrases:
  "write commit message"  /  "generate commit"  /  "what should I commit"  /
  "commit message"  /  "help me commit"
"""

from __future__ import annotations
import os
import subprocess
from typing import Any


def _run(parameters: dict, ui: Any, **ctx) -> str:
    try:
        cwd = _find_repo_cwd()
        if not cwd:
            return (
                "I couldn't find your git repository. "
                "Make sure you're in a project and have staged some changes."
            )

        diff = subprocess.run(
            ["git", "diff", "--staged", "--stat"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        if not diff:
            # Nothing staged — check what's unstaged
            unstaged = subprocess.run(
                ["git", "status", "--short"],
                cwd=cwd, capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if unstaged:
                return (
                    "Nothing is staged yet. "
                    "Run `git add` on your changes first, then ask me again."
                )
            return "Working tree is clean — nothing to commit."

        # Build a conventional commit from the diff stat
        message = _infer_commit_message(diff, cwd)

        # Copy to clipboard silently
        try:
            import subprocess as sp
            sp.run(["clip"], input=message.encode("utf-8"), check=False)
        except Exception:
            pass

        return (
            f"Here's a commit message: {message}. "
            "I've copied it to your clipboard."
        )

    except Exception as e:
        return f"Couldn't generate a commit message: {e}"


def _find_repo_cwd() -> str:
    """Return the CWD of the last known git repo."""
    try:
        from memory.session_state import load_last_session
        session = load_last_session()
        cwd = (session or {}).get("git_cwd", "")
        if cwd and os.path.exists(os.path.join(cwd, ".git")):
            return cwd
    except Exception:
        pass
    # Fallback: current directory
    cwd = os.getcwd()
    return cwd if os.path.exists(os.path.join(cwd, ".git")) else ""


def _infer_commit_message(diff_stat: str, cwd: str) -> str:
    """
    Build a conventional commit message from diff stat.
    Uses simple heuristics — no LLM call to keep it instant and offline.
    """
    lines = [l.strip() for l in diff_stat.splitlines() if l.strip()]

    # Extract changed file names
    changed: list[str] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 2:
            fname = parts[0].strip()
            if fname:
                changed.append(fname.split("/")[-1])  # basename only

    summary_line = lines[-1] if lines else ""  # e.g. "3 files changed, 42 insertions(+)"

    # Infer type from filenames
    commit_type = "feat"
    all_names = " ".join(changed).lower()
    if any(w in all_names for w in ("test", "spec")):
        commit_type = "test"
    elif any(w in all_names for w in ("fix", "bug", "patch", "hotfix")):
        commit_type = "fix"
    elif any(w in all_names for w in ("readme", "doc", "changelog")):
        commit_type = "docs"
    elif any(w in all_names for w in ("style", ".css", ".scss")):
        commit_type = "style"
    elif any(w in all_names for w in ("refactor", "cleanup", "clean")):
        commit_type = "refactor"
    elif any(w in all_names for w in ("config", ".json", ".env", ".yaml", ".yml")):
        commit_type = "chore"

    # Scope from most common file root
    scope = ""
    if changed:
        scope_candidate = changed[0].replace(".py", "").replace(".js", "").replace(".ts", "")
        if len(scope_candidate) < 20:
            scope = scope_candidate

    # Description
    if len(changed) == 1:
        desc = f"update {changed[0]}"
    elif len(changed) <= 3:
        desc = f"update {', '.join(changed[:2])}"
    else:
        desc = f"update {len(changed)} files"

    if scope:
        return f"{commit_type}({scope}): {desc}"
    return f"{commit_type}: {desc}"


SKILL_MANIFEST = {
    "name": "commit_writer",
    "description": "Auto-generate a conventional commit message from staged changes",
    "intents": ["commit_writer", "write_commit", "commit_message", "generate_commit"],
    "trigger_phrases": [
        "write commit message",
        "generate commit message",
        "commit message",
        "what should I commit",
        "help me write a commit",
        "create commit",
        "suggest a commit",
    ],
    "run": _run,
}
