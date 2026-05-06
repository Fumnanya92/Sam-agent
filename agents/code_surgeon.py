"""
agents/code_surgeon.py — End-to-end debug loop.

Pipeline for "X is broken":
  a. Locate   — project_index.find() → project root
  b. Comprehend — read README + manifest, infer stack + dev command
  c. Reproduce  — run dev server, capture stdout/stderr (30 s)
  d. Diagnose   — relevant source files + error → LLM → root cause + patch
  e. Patch      — write diff to disk, surface "say apply" PendingAction
  f. Verify     — rerun dev server after patch; check error disappeared
  g. Report     — voice + dashboard summary

Public entry point:
    from agents.code_surgeon import CodeSurgeon
    surgeon = CodeSurgeon()
    result  = surgeon.debug(description, project_name="", speak=None, ui=None)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger("sam.code_surgeon")

# Max lines of source fed to LLM per relevant file
_MAX_SRC_LINES = 120
# Max files fed to LLM
_MAX_FILES = 6
# Dev server startup wait (seconds)
_SERVER_WAIT = 20
# How long to capture dev server output
_CAPTURE_SECS = 12


# ── Stack-specific helpers ──────────────────────────────────────────────────

_STACK_DEV_CMD: dict[str, list[str]] = {
    "node": ["npm", "run", "dev"],
    "python": ["python", "main.py"],
    "flutter": ["flutter", "run", "--no-pub"],
    "rust": ["cargo", "run"],
    "go": ["go", "run", "."],
    "java": ["mvn", "exec:java"],
    "dotnet": ["dotnet", "run"],
}

_STACK_TEST_CMD: dict[str, list[str]] = {
    "node": ["npm", "test", "--", "--passWithNoTests"],
    "python": ["python", "-m", "pytest", "--tb=short", "-q"],
    "flutter": ["flutter", "test"],
    "rust": ["cargo", "test"],
    "go": ["go", "test", "./..."],
    "java": ["mvn", "test", "-q"],
    "dotnet": ["dotnet", "test"],
}

_ERROR_PATTERNS = [
    re.compile(r"error[:\s]", re.IGNORECASE),
    re.compile(r"exception", re.IGNORECASE),
    re.compile(r"traceback", re.IGNORECASE),
    re.compile(r"failed", re.IGNORECASE),
    re.compile(r"cannot find", re.IGNORECASE),
    re.compile(r"undefined", re.IGNORECASE),
    re.compile(r"null pointer", re.IGNORECASE),
    re.compile(r"segmentation fault", re.IGNORECASE),
]


def _extract_errors(text: str) -> str:
    """Return only lines that look like errors, capped at 60 lines."""
    lines = text.splitlines()
    error_lines = []
    for i, line in enumerate(lines):
        if any(p.search(line) for p in _ERROR_PATTERNS):
            start = max(0, i - 1)
            end = min(len(lines), i + 3)
            error_lines.extend(lines[start:end])
    unique = list(dict.fromkeys(error_lines))  # deduplicate order-preserving
    return "\n".join(unique[:60])


def _run_capture(cmd: list[str], cwd: str, timeout: int = _CAPTURE_SECS) -> str:
    """Run a command and return combined stdout+stderr, truncated."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        return combined.strip()[:8000]
    except subprocess.TimeoutExpired:
        return "(command timed out — server may be running)"
    except FileNotFoundError:
        return f"(command not found: {cmd[0]})"
    except Exception as e:
        return f"(run error: {e})"


def _read_manifest(project_path: Path, stack: str) -> str:
    """Return a short string with the project's name/scripts/dependencies."""
    try:
        if stack == "node":
            pkg = project_path / "package.json"
            if pkg.exists():
                data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
                scripts = data.get("scripts", {})
                deps = list(data.get("dependencies", {}).keys())[:10]
                return f"name={data.get('name')} scripts={list(scripts.keys())} deps={deps}"
        if stack == "python":
            for fname in ("pyproject.toml", "requirements.txt"):
                f = project_path / fname
                if f.exists():
                    return f.read_text(encoding="utf-8", errors="ignore")[:400]
        if stack == "flutter":
            pubspec = project_path / "pubspec.yaml"
            if pubspec.exists():
                return pubspec.read_text(encoding="utf-8", errors="ignore")[:400]
    except Exception:
        pass
    return ""


def _read_readme(project_path: Path) -> str:
    for name in ("README.md", "readme.md", "README.txt"):
        f = project_path / name
        if f.exists():
            try:
                return f.read_text(encoding="utf-8", errors="ignore")[:600]
            except Exception:
                pass
    return ""


def _relevant_source_files(project_path: Path, description: str, stack: str) -> list[Path]:
    """Find source files most likely related to the bug description."""
    keywords = re.findall(r"\w+", description.lower())
    ext_map = {
        "node": [".js", ".ts", ".jsx", ".tsx"],
        "python": [".py"],
        "flutter": [".dart"],
        "rust": [".rs"],
        "go": [".go"],
        "java": [".java"],
        "dotnet": [".cs"],
    }
    exts = ext_map.get(stack, [".py", ".js", ".ts"])

    scored: list[tuple[int, Path]] = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".dart_tool", "build", "dist", ".venv", "venv"}

    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            depth = str(Path(root)).replace(str(project_path), "").count(os.sep)
            if depth > 4:
                dirs.clear()
                continue
            for fname in files:
                if Path(fname).suffix not in exts:
                    continue
                score = sum(1 for kw in keywords if kw in fname.lower())
                # Entry-point files get a bonus
                if fname in ("main.py", "app.py", "index.ts", "index.js", "main.dart", "main.rs"):
                    score += 2
                scored.append((score, Path(root) / fname))
    except (PermissionError, OSError):
        pass

    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:_MAX_FILES]]


def _build_source_block(files: list[Path], project_path: Path) -> str:
    parts = []
    for f in files:
        try:
            rel = f.relative_to(project_path)
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            snippet = "\n".join(lines[:_MAX_SRC_LINES])
            parts.append(f"# {rel}\n{snippet}")
        except Exception:
            pass
    return "\n\n".join(parts)


def _generate_patch_via_llm(
    description: str,
    error_output: str,
    source_block: str,
    stack: str,
    manifest: str,
    readme: str,
) -> dict:
    """Ask LLM to diagnose and produce a JSON patch plan."""
    prompt = f"""You are a senior {stack} debugger.

BUG REPORT: {description}

ERROR OUTPUT:
{error_output or "(no error output captured)"}

MANIFEST:
{manifest or "(unavailable)"}

README:
{readme or "(unavailable)"}

SOURCE CODE:
{source_block or "(unavailable)"}

Respond with ONLY valid JSON:
{{
  "root_cause": "<one sentence>",
  "fix_summary": "<what to change, one sentence>",
  "patches": [
    {{
      "file": "<relative path>",
      "old": "<exact lines to replace — must match source exactly>",
      "new": "<replacement lines>"
    }}
  ],
  "confidence": "high|medium|low"
}}

Rules:
- If you cannot determine the fix, set patches=[] and confidence=low.
- old must be lines that appear verbatim in the source.
- Keep patches minimal — only what's needed to fix the bug.
- Do not add logging, comments, or refactors unrelated to the fix.
"""
    try:
        from llm.manager import get_manager
        mgr = get_manager()
        raw = mgr.complete_sync(prompt, system="You are a precise code debugger. Output only valid JSON.", model_tier="auto")
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
        raw = raw.replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"[CodeSurgeon] LLM patch generation failed: {e}")
        return {"root_cause": "LLM unavailable", "fix_summary": "", "patches": [], "confidence": "low"}


def _apply_patches(patches: list[dict], project_path: Path) -> list[str]:
    """Apply patches to files. Returns list of modified file paths."""
    modified = []
    for patch in patches:
        rel = patch.get("file", "")
        old = patch.get("old", "")
        new = patch.get("new", "")
        if not rel or not old:
            continue
        target = project_path / rel
        if not target.exists():
            logger.warning(f"[CodeSurgeon] Patch target not found: {target}")
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
            if old not in text:
                logger.warning(f"[CodeSurgeon] 'old' text not found in {rel} — skipping patch")
                continue
            patched = text.replace(old, new, 1)
            target.write_text(patched, encoding="utf-8")
            modified.append(str(target))
            logger.info(f"[CodeSurgeon] Patched {rel}")
        except Exception as e:
            logger.error(f"[CodeSurgeon] Failed to patch {rel}: {e}")
    return modified


# ── CodeSurgeon class ───────────────────────────────────────────────────────

class CodeSurgeon:
    """End-to-end debug loop: locate → reproduce → diagnose → patch → verify."""

    def debug(
        self,
        description: str,
        project_name: str = "",
        speak: Callable[[str], None] | None = None,
        ui=None,
    ) -> str:
        """
        Run the full debug pipeline.
        Returns a human-readable result string.
        """
        def _say(msg: str):
            logger.info(f"[CodeSurgeon] {msg}")
            if speak:
                speak(msg)
            if ui:
                try:
                    ui.append_output(f"[surgeon] {msg}", "info")
                except Exception:
                    pass

        # ── a. Locate ──────────────────────────────────────────────────
        project_path: Path | None = None
        project_meta: dict = {}

        if project_name:
            try:
                from system.project_index import project_index
                proj = project_index.find(project_name)
                if proj:
                    project_path = Path(proj["path"])
                    project_meta = proj
            except Exception:
                pass

        if not project_path:
            # Try to infer from description
            words = re.findall(r"\w+", description)
            for w in words:
                if len(w) > 4:
                    try:
                        from system.project_index import project_index
                        proj = project_index.find(w)
                        if proj:
                            project_path = Path(proj["path"])
                            project_meta = proj
                            break
                    except Exception:
                        pass

        if not project_path:
            return "I couldn't find the project. Tell me the project name and try again."

        stack = project_meta.get("stack", "unknown")
        _say(f"Found project: {project_path.name} ({stack})")

        # ── b. Comprehend ──────────────────────────────────────────────
        readme = _read_readme(project_path)
        manifest = _read_manifest(project_path, stack)
        relevant_files = _relevant_source_files(project_path, description, stack)

        # ── c. Reproduce ───────────────────────────────────────────────
        _say("Running project to capture errors…")
        dev_cmd = _STACK_DEV_CMD.get(stack)
        raw_output = ""

        # Try tests first (faster + safer than starting a server)
        test_cmd = _STACK_TEST_CMD.get(stack)
        if test_cmd:
            raw_output = _run_capture(test_cmd, str(project_path), timeout=60)

        # If tests gave nothing useful, try a quick build check
        if not raw_output.strip() or "not found" in raw_output:
            if stack == "node":
                raw_output = _run_capture(["npm", "run", "build", "--if-present"], str(project_path), timeout=60)
            elif stack == "python":
                raw_output = _run_capture(["python", "-m", "py_compile"] + [str(f) for f in relevant_files[:3]], str(project_path), timeout=20)
            elif stack == "flutter":
                raw_output = _run_capture(["flutter", "analyze"], str(project_path), timeout=60)

        error_output = _extract_errors(raw_output)
        if not error_output:
            error_output = raw_output[:1000]  # feed raw if no pattern matched

        _say(f"Captured output ({len(raw_output)} chars). Diagnosing…")

        # ── d. Diagnose ────────────────────────────────────────────────
        source_block = _build_source_block(relevant_files, project_path)
        patch_plan = _generate_patch_via_llm(
            description=description,
            error_output=error_output,
            source_block=source_block,
            stack=stack,
            manifest=manifest,
            readme=readme,
        )

        root_cause = patch_plan.get("root_cause", "unknown")
        fix_summary = patch_plan.get("fix_summary", "")
        patches = patch_plan.get("patches", [])
        confidence = patch_plan.get("confidence", "low")

        _say(f"Root cause: {root_cause}")

        if not patches:
            return (
                f"I diagnosed the issue ({root_cause}) but couldn't generate a safe patch "
                f"(confidence: {confidence}). Here's what I found:\n\n{error_output[:400]}"
            )

        # ── e. Patch ───────────────────────────────────────────────────
        # Surface as a PendingAction — don't auto-apply
        patch_summary = "\n".join(
            f"  • {p.get('file')}: {p.get('old','')[:60].strip()!r} → {p.get('new','')[:60].strip()!r}"
            for p in patches
        )
        proposal = (
            f"Root cause: {root_cause}\n"
            f"Fix: {fix_summary}\n\n"
            f"Patches ({len(patches)} file(s)):\n{patch_summary}\n\n"
            f"Say 'apply' to write the changes."
        )

        try:
            from conversation_state import controller, PendingAction

            def _do_apply():
                modified = _apply_patches(patches, project_path)
                if not modified:
                    _say("Patch failed — the source lines didn't match exactly. Check manually.")
                    return
                _say(f"Applied {len(modified)} patch(es). Verifying…")

                # ── f. Verify ──────────────────────────────────────────
                verify_out = ""
                if test_cmd:
                    verify_out = _run_capture(test_cmd, str(project_path), timeout=60)
                verify_errors = _extract_errors(verify_out)

                if verify_errors:
                    _say(f"Tests still show errors after patch. May need manual review:\n{verify_errors[:200]}")
                else:
                    _say("Verification passed — no errors detected after patch.")

            controller.set_pending(PendingAction(
                description=fix_summary or root_cause,
                callback=_do_apply,
            ))
        except Exception as e:
            logger.warning(f"[CodeSurgeon] Could not set PendingAction: {e}")
            # Fall back: just describe the patches without applying
            pass

        return proposal

    def quick_analyze(self, file_path: str, description: str = "") -> str:
        """Lighter variant: analyze a single file without a full project scan."""
        p = Path(file_path)
        if not p.exists():
            return f"File not found: {file_path}"
        try:
            source = p.read_text(encoding="utf-8", errors="ignore")
            ext = p.suffix.lower()
            stack_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                         ".dart": "flutter", ".rs": "rust", ".go": "go", ".java": "java"}
            stack = stack_map.get(ext, "unknown")
            patch_plan = _generate_patch_via_llm(
                description=description or "Analyze for bugs and issues",
                error_output="",
                source_block=source[:8000],
                stack=stack,
                manifest="",
                readme="",
            )
            return (
                f"Root cause: {patch_plan.get('root_cause', 'none found')}\n"
                f"Fix: {patch_plan.get('fix_summary', 'n/a')}\n"
                f"Confidence: {patch_plan.get('confidence', 'low')}"
            )
        except Exception as e:
            return f"Analysis failed: {e}"
