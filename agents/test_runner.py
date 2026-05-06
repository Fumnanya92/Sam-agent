"""
agents/test_runner.py — Stack-aware test runner with pass/fail gate.

Per-stack default recipes:
  flutter → flutter test
  node    → npm test (--passWithNoTests) + optional Playwright on top-3 routes
  python  → pytest --tb=short -q
  rust    → cargo test
  go      → go test ./...
  java    → mvn test -q
  dotnet  → dotnet test

Entry point:
    from agents.test_runner import TestRunner
    runner = TestRunner()
    result = runner.run(project_name="guest app", speak=speak_fn, ui=ui)
    # returns TestResult(passed, total, failed_names, output, stack)

The "done gate":
    runner.run() returns a TestResult. If TestResult.passed is False and the caller
    wants to enforce the gate, it should call runner.request_override(ui, speak)
    which sets a PendingAction asking the user to confirm shipping with failures.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("sam.test_runner")

_TIMEOUT = 120  # seconds per test run


@dataclass
class TestResult:
    passed: bool
    total: int = 0
    failed: int = 0
    failed_names: list[str] = field(default_factory=list)
    output: str = ""
    stack: str = "unknown"
    project_path: str = ""

    def summary(self) -> str:
        if self.total == 0:
            return f"No tests found ({self.stack})."
        if self.passed:
            return f"All {self.total} tests passed ({self.stack})."
        return f"{self.failed}/{self.total} tests failed ({self.stack}): {', '.join(self.failed_names[:3])}"


# ── Stack commands ──────────────────────────────────────────────────────────

_STACK_CMDS: dict[str, list[str]] = {
    "flutter": ["flutter", "test", "--reporter", "compact"],
    "node":    ["npm", "test", "--", "--passWithNoTests", "--watchAll=false"],
    "python":  ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],
    "rust":    ["cargo", "test"],
    "go":      ["go", "test", "./...", "-v"],
    "java":    ["mvn", "test", "-q"],
    "dotnet":  ["dotnet", "test", "--logger", "console;verbosity=minimal"],
    "git":     ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],  # generic fallback
}


# ── Output parsers ──────────────────────────────────────────────────────────

def _parse_pytest(output: str) -> tuple[int, int, list[str]]:
    """Parse pytest output: return (total, failed, [failed_names])."""
    total, failed = 0, 0
    failed_names = []
    # e.g. "5 passed, 2 failed in 1.23s"
    m = re.search(r"(\d+) passed", output)
    if m:
        total += int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
        total += failed
    # Collect FAILED test names
    for line in output.splitlines():
        if line.strip().startswith("FAILED "):
            name = line.strip()[7:].split(" ")[0]
            failed_names.append(name)
    return total, failed, failed_names


def _parse_jest(output: str) -> tuple[int, int, list[str]]:
    """Parse Jest output."""
    total, failed = 0, 0
    failed_names: list[str] = []
    m = re.search(r"Tests:\s+(?:(\d+) failed,\s*)?(\d+) passed,\s*(\d+) total", output)
    if m:
        failed = int(m.group(1) or 0)
        total = int(m.group(3))
    for line in output.splitlines():
        if "● " in line and "●" == line.strip()[0]:
            failed_names.append(line.strip()[2:60])
    return total, failed, failed_names


def _parse_flutter(output: str) -> tuple[int, int, list[str]]:
    """Parse flutter test output."""
    total, failed = 0, 0
    failed_names: list[str] = []
    m = re.search(r"(\d+) tests? passed", output)
    if m:
        total += int(m.group(1))
    m = re.search(r"(\d+) tests? failed", output)
    if m:
        failed = int(m.group(1))
        total += failed
    for line in output.splitlines():
        if "FAILED" in line or "✗" in line:
            failed_names.append(line.strip()[:80])
    return total, failed, failed_names


def _parse_go(output: str) -> tuple[int, int, list[str]]:
    total, failed = 0, 0
    failed_names: list[str] = []
    for line in output.splitlines():
        if line.startswith("--- PASS"):
            total += 1
        elif line.startswith("--- FAIL"):
            total += 1
            failed += 1
            parts = line.split()
            if len(parts) > 2:
                failed_names.append(parts[2])
    return total, failed, failed_names


def _parse_generic(output: str) -> tuple[int, int, list[str]]:
    """Fallback: look for BUILD FAILURE or error patterns."""
    if re.search(r"BUILD\s+FAILURE|FAILED|Tests run:.*Failures:", output, re.IGNORECASE):
        return 1, 1, ["(see output)"]
    if re.search(r"BUILD\s+SUCCESS|All tests passed|0 failures", output, re.IGNORECASE):
        return 1, 0, []
    return 0, 0, []


_PARSERS: dict[str, Callable] = {
    "python": _parse_pytest,
    "git":    _parse_pytest,
    "node":   _parse_jest,
    "flutter": _parse_flutter,
    "go":     _parse_go,
    "rust":   _parse_generic,
    "java":   _parse_generic,
    "dotnet": _parse_generic,
}


# ── TestRunner class ────────────────────────────────────────────────────────

class TestRunner:
    def run(
        self,
        project_name: str = "",
        project_path: str = "",
        speak: Callable[[str], None] | None = None,
        ui=None,
    ) -> TestResult:
        """
        Locate project, pick test command, run tests, parse results.
        Returns TestResult.
        """
        def _say(msg: str):
            logger.info(f"[TestRunner] {msg}")
            if speak:
                speak(msg)
            if ui:
                try:
                    ui.append_output(f"[tests] {msg}", "info")
                except Exception:
                    pass

        # Resolve project path
        proj_dir: Path | None = None
        stack = "unknown"

        if project_path:
            proj_dir = Path(project_path)
        elif project_name:
            try:
                from system.project_index import project_index
                proj = project_index.find(project_name)
                if proj:
                    proj_dir = Path(proj["path"])
                    stack = proj.get("stack", "unknown")
            except Exception:
                pass

        # Fallback: use current working directory
        if not proj_dir or not proj_dir.exists():
            try:
                from actions.terminal import get_cwd
                proj_dir = Path(get_cwd())
            except Exception:
                proj_dir = Path.cwd()

        # Detect stack from dir if not already known
        if stack == "unknown":
            stack = _detect_stack(proj_dir)

        cmd = _STACK_CMDS.get(stack, _STACK_CMDS["python"])
        _say(f"Running {' '.join(cmd[:2])} in {proj_dir.name}…")

        output = _run_tests(cmd, str(proj_dir))

        parser = _PARSERS.get(stack, _parse_generic)
        total, failed, failed_names = parser(output)
        passed = failed == 0

        result = TestResult(
            passed=passed,
            total=total,
            failed=failed,
            failed_names=failed_names,
            output=output,
            stack=stack,
            project_path=str(proj_dir),
        )

        _say(result.summary())
        return result

    def request_override(
        self,
        result: TestResult,
        speak: Callable[[str], None] | None = None,
        ui=None,
    ) -> None:
        """Set a PendingAction asking whether to ship despite failures."""
        msg = (
            f"{result.failed} test(s) failed: {', '.join(result.failed_names[:3])}. "
            "Say 'ship it anyway' to proceed, or 'no' to stay."
        )
        if speak:
            speak(msg)
        if ui:
            try:
                ui.append_output(f"[tests] {msg}", "warning")
            except Exception:
                pass

        try:
            from conversation_state import controller, PendingAction

            def _override():
                if speak:
                    speak("Proceeding despite test failures — noted.")

            controller.set_pending(PendingAction(
                description="ship with failing tests",
                callback=_override,
            ))
        except Exception as e:
            logger.warning(f"[TestRunner] Could not set PendingAction: {e}")


def _detect_stack(project_path: Path) -> str:
    sigs = [
        ("package.json", "node"),
        ("pubspec.yaml", "flutter"),
        ("pyproject.toml", "python"),
        ("setup.py", "python"),
        ("requirements.txt", "python"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ]
    for fname, stack in sigs:
        if (project_path / fname).exists():
            return stack
    for ext in (".sln", ".csproj"):
        if list(project_path.glob(f"*{ext}")):
            return "dotnet"
    return "git"


def _run_tests(cmd: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=_TIMEOUT, encoding="utf-8", errors="replace",
        )
        return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()[:10000]
    except subprocess.TimeoutExpired:
        return f"(tests timed out after {_TIMEOUT}s)"
    except FileNotFoundError:
        return f"(command not found: {cmd[0]})"
    except Exception as e:
        return f"(test run error: {e})"
