"""
skills/flutter_tester.py — Intelligent Flutter app testing via playwright-cli.

HOW IT WORKS:
  1. Dynamically finds the running Flutter web app (scans dart.exe processes → ports → content check).
  2. Opens a headed browser via 'playwright-cli open --headed' (user can watch it work).
  3. Takes a snapshot after each step to get accessibility-tree element refs.
  4. GPT-4o reads the snapshot + task description and decides the next playwright-cli command.
  5. Executes that command via subprocess, loops until done/error/limit.
  6. Logs failures (errors + screenshots) to ~/Documents/Sam Notes/TestLogs/.
  7. Speaks a pass/fail summary.

CLI vs MCP:
  Uses @playwright/cli (npm install -g @playwright/cli) — token-efficient, no Python playwright.
  'playwright-cli open' is blocking; we Popen it in the background, then run other commands.

URL DISCOVERY order:
  1. User-supplied port/url in the command
  2. memory/flutter_state.json (previously saved)
  3. Scan dart.exe process ports (Flutter dev server) and verify Flutter content
  4. Scan common Flutter dev ports
  5. Ask the user
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from log.logger import get_logger

logger = get_logger("FLUTTER_TESTER")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT               = Path(__file__).resolve().parent.parent
_CONFIG_PATH        = _ROOT / "config" / "api_keys.json"
_SESSION_FILE       = _ROOT / "memory" / "session_state.json"
_FLUTTER_STATE_FILE = _ROOT / "memory" / "flutter_state.json"
_CREDENTIALS_FILE   = _ROOT / "memory" / "test_credentials.json"
_TEST_LOGS_DIR      = Path.home() / "Documents" / "Sam Notes" / "TestLogs"
_SNAP_DIR           = _ROOT / "debug" / "playwright_snaps"
_PLAYWRIGHT_SESSION = "sam-flutter"
_MAX_STEPS          = 25

# ── Shared test state (readable by ai_loop + cancellable from voice) ─────────
_test_state: dict = {
    "running":      False,
    "cancel_event": threading.Event(),
    "step":         0,
    "task":         "",
    "app_url":      "",
    "project":      "",
}


def cancel_test() -> str:
    """Signal the currently running test to stop.  Called by stop_test intent."""
    if _test_state["running"]:
        _test_state["cancel_event"].set()
        return "Stopping the test — I'll wrap up after the current step."
    return "No test is running right now."


# Common Flutter dev-server ports (last-resort scan)
_FLUTTER_COMMON_PORTS = [5000, 8080, 8000, 3000, 4040, 9000, 9999, 7357,
                          44316, 44317, 44318, 44319, 44320, 44321]
_CONFIG_PATH        = _ROOT / "config" / "api_keys.json"
_SESSION_FILE       = _ROOT / "memory" / "session_state.json"
_FLUTTER_STATE_FILE = _ROOT / "memory" / "flutter_state.json"
_CREDENTIALS_FILE   = _ROOT / "memory" / "test_credentials.json"


# ══════════════════════════════════════════════════════════════════════════════
# playwright-cli runners
# ══════════════════════════════════════════════════════════════════════════════

def _cli_bin() -> str | None:
    """Return the playwright-cli command if available on PATH."""
    # On Windows npm installs a .cmd wrapper; try both forms
    candidates = (
        ["playwright-cli.cmd", "playwright-cli"]
        if sys.platform == "win32"
        else ["playwright-cli"]
    )
    for candidate in candidates:
        try:
            res = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True, timeout=8,
                shell=(sys.platform == "win32"),
            )
            if res.returncode == 0:
                # Use the .cmd form on Windows for subprocess reliability
                return candidate
        except Exception:
            pass


def _ensure_cli() -> str | None:
    """Return cli bin path, auto-installing if needed."""
    cli = _cli_bin()
    if cli:
        return cli
    logger.info("playwright-cli not found — installing…")
    try:
        res = subprocess.run(
            ["npm", "install", "-g", "@playwright/cli@latest"],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode == 0:
            # Also install skills for this workspace
            subprocess.run(["playwright-cli", "install", "--skills"],
                           capture_output=True, timeout=15)
            return _cli_bin()
        logger.error(f"npm install failed: {res.stderr[:300]}")
    except Exception as e:
        logger.error(f"playwright-cli install error: {e}")
    return None


def _run_cmd(cli: str, args: list[str],
             session: str = _PLAYWRIGHT_SESSION,
             timeout: int = 30) -> tuple[bool, str]:
    """Run: playwright-cli -s=<session> <args>  →  (ok, output)"""
    cmd = [cli, f"-s={session}"] + [str(a) for a in args]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=(sys.platform == "win32"),
        )
        out = (res.stdout + "\n" + res.stderr).strip()
        return res.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    except Exception as e:
        return False, str(e)


def _session_alive(cli: str, session: str = _PLAYWRIGHT_SESSION) -> bool:
    """Return True if a playwright-cli session already has a live browser page."""
    ok, out = _run_cmd(cli, ["snapshot"], session=session, timeout=8)
    return ok and "Page URL" in out


def _open_browser(cli: str, url: str,
                  session: str = _PLAYWRIGHT_SESSION) -> "subprocess.Popen | None":
    """
    Reuse an existing session if one is alive (navigates via goto — no new window).
    Otherwise opens a new Chrome window using the user's installed Chrome.
    Returns Popen handle (new window) or None (reused existing).
    """
    if _session_alive(cli, session):
        logger.info(f"Reusing existing session '{session}' — goto {url}")
        _run_cmd(cli, ["goto", url], session=session, timeout=15)
        return None   # no new process
    return subprocess.Popen(
        [cli, f"-s={session}", "open", url, "--headed", "--channel=chrome"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        shell=(sys.platform == "win32"),
    )


def _close_browser(cli: str, proc: "subprocess.Popen | None",
                   session: str = _PLAYWRIGHT_SESSION) -> None:
    """Close browser. If proc is None the user's Chrome was reused — leave it open."""
    if proc is None:
        # We navigated inside the user's existing Chrome — don't close their window
        return
    _run_cmd(cli, ["close"], session=session, timeout=10)
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.terminate()


def _get_snapshot(cli: str,
                  session: str = _PLAYWRIGHT_SESSION) -> str:
    """
    Take a snapshot, save to a known file, return YAML content.
    The YAML has element refs like [ref=e5] that the LLM uses to click/fill.
    """
    _SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap_file = _SNAP_DIR / "current.yml"
    snap_file.unlink(missing_ok=True)

    ok, out = _run_cmd(cli, ["snapshot", f"--filename={snap_file}"],
                       session=session, timeout=15)
    if snap_file.exists():
        return snap_file.read_text(encoding="utf-8")

    # Fallback: auto-named file referenced in stdout
    m = re.search(r'\[Snapshot\]\(([^)]+)\)', out)
    if m:
        auto = Path(m.group(1))
        if auto.exists():
            return auto.read_text(encoding="utf-8")

    return out   # raw page summary as last resort


def _has_refs(snap: str) -> bool:
    return bool(re.search(r'\[ref=e\d+\]', snap))


# ══════════════════════════════════════════════════════════════════════════════
# Dynamic Flutter URL discovery
# ══════════════════════════════════════════════════════════════════════════════

def _is_flutter_url(url: str) -> bool:
    """True if the URL serves a real Flutter web app (not DevTools/Observatory).
    Requires both Flutter markers AND a non-empty <title> to exclude Dart DevTools
    which also serves Flutter content but with an empty title.
    """
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2) as r:
            chunk = r.read(8192).decode("utf-8", errors="ignore").lower()
            has_flutter = any(kw in chunk for kw in [
                "flutter", "main.dart.js", "flutter_bootstrap.js",
                "flt-", "canvaskit", "flutter.js", "_flutter",
            ])
            if not has_flutter:
                return False
            # Dart DevTools has <title></title> (empty) — skip those
            title_match = re.search(r"<title>(.*?)</title>", chunk)
            if title_match and title_match.group(1).strip() == "":
                return False
            return True
    except Exception:
        return False


def _dart_ports() -> list[int]:
    """PowerShell: get TCP LISTEN ports owned by dart.exe, dartvm.exe, or flutter.exe.
    Handles multiple processes (each may own different ports).
    dartvm.exe is the actual process name on many Windows Flutter installs.
    """
    ps = (
        # Collect all dart / dartvm / flutter process IDs as a flat array
        "$ids = @(Get-Process dart,dartvm,flutter -EA 0 | "
        "Select-Object -ExpandProperty Id); "
        "if ($ids.Count -gt 0) { "
        "  Get-NetTCPConnection -EA 0 "
        "  | Where-Object { $ids -contains $_.OwningProcess -and $_.State -eq 'Listen' } "
        "  | Select-Object -ExpandProperty LocalPort "
        "  | Sort-Object -Unique "
        "}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
        return [int(p.strip()) for p in res.stdout.splitlines()
                if p.strip().isdigit()]
    except Exception:
        return []


def _find_flutter_url() -> str | None:
    """Locate a running Flutter web app. Returns URL string or None.

    Priority:
      1. dart.exe / flutter.exe live port scan  (most accurate — any port)
      2. Common Flutter dev ports scan
      3. Previously saved URL  (last resort — may be stale)
    Saved state is checked LAST so a stale entry never hides the live app.
    """
    # 1. Live scan — dart/flutter process ports (works with any dynamic port)
    live_ports = _dart_ports()
    logger.info(f"dart/flutter ports found: {live_ports}")
    for port in live_ports:
        url = f"http://localhost:{port}"
        if _is_flutter_url(url):
            _save_flutter_url(url)
            return url

    # 2. Common Flutter dev ports
    for port in _FLUTTER_COMMON_PORTS:
        url = f"http://localhost:{port}"
        if _is_flutter_url(url):
            _save_flutter_url(url)
            return url

    # 3. Saved state — last resort only (could be stale from a previous run)
    for f in [_FLUTTER_STATE_FILE, _SESSION_FILE]:
        try:
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                u = data.get("flutter_app_url", "").strip()
                if u and _is_flutter_url(u):
                    logger.warning(f"Using saved URL {u} — no live dart ports found")
                    return u
        except Exception:
            pass

    return None


def _find_all_flutter_urls() -> list[str]:
    """Return ALL valid Flutter web URLs currently reachable (not just the first)."""
    found: list[str] = []
    for port in _dart_ports():
        url = f"http://localhost:{port}"
        if _is_flutter_url(url):
            found.append(url)
    if found:
        return found
    for port in _FLUTTER_COMMON_PORTS:
        url = f"http://localhost:{port}"
        if _is_flutter_url(url):
            found.append(url)
    return found


def _save_flutter_url(url: str) -> None:
    try:
        _FLUTTER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _FLUTTER_STATE_FILE.exists():
            data = json.loads(_FLUTTER_STATE_FILE.read_text(encoding="utf-8"))
        data["flutter_app_url"] = url
        _FLUTTER_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"save_flutter_url: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Project scanner
# ══════════════════════════════════════════════════════════════════════════════

def _scan_project(cwd: str) -> dict:
    """
    Read the Flutter project to build a context dict:
      app_name, description, screens, routes, entry_point, has_auth
    """
    ctx = {
        "app_name":    "",
        "description": "",
        "screens":     [],
        "routes":      [],
        "has_auth":    False,
        "cwd":         cwd,
    }
    root = Path(cwd)

    # ── pubspec.yaml → app name + description ────────────────────────────────
    pubspec = root / "pubspec.yaml"
    if pubspec.exists():
        try:
            text = pubspec.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("name:"):
                    ctx["app_name"] = line.split(":", 1)[1].strip().replace("_", " ").title()
                if line.startswith("description:"):
                    ctx["description"] = line.split(":", 1)[1].strip()
        except Exception:
            pass

    # ── lib/ → dart screen/page files → screen names ────────────────────────
    lib = root / "lib"
    if lib.exists():
        screen_dirs = ["screens", "pages", "views", "features", "ui"]
        dart_files: list[Path] = []

        for d in screen_dirs:
            dart_files += list((lib / d).rglob("*.dart")) if (lib / d).exists() else []

        # Fall back to all dart files if no screen-specific dirs found
        if not dart_files:
            dart_files = list(lib.rglob("*.dart"))

        # Prioritise auth-related files so they aren't lost under the 40-file cap
        auth_keywords = {"login", "signin", "register", "signup", "auth", "password"}
        def _auth_priority(p: Path) -> int:
            return 0 if any(kw in p.stem.lower() for kw in auth_keywords) else 1
        dart_files.sort(key=_auth_priority)

        for f in dart_files[:40]:   # cap to avoid reading huge projects
            name = f.stem
            # Convert snake_case or camelCase to a readable name
            readable = re.sub(r"[_]", " ", name).title()
            if readable not in ctx["screens"]:
                ctx["screens"].append(readable)

            # Detect auth screens
            lower = name.lower()
            if any(kw in lower for kw in ["login", "signin", "register", "signup", "auth", "password"]):
                ctx["has_auth"] = True

        # ── main.dart → entry routes ────────────────────────────────────────
        main_dart = lib / "main.dart"
        if main_dart.exists():
            try:
                text = main_dart.read_text(encoding="utf-8")
                # Extract quoted route strings like '/login' or 'LoginPage'
                found = re.findall(r"['\"](/[\w/\-]+)['\"]", text)
                ctx["routes"] = list(dict.fromkeys(found))[:10]  # deduplicated
            except Exception:
                pass

        # ── router.dart / routes.dart if exists ─────────────────────────────
        for rfile in (lib / "routes.dart", lib / "router.dart",
                      lib / "config" / "routes.dart", lib / "core" / "routes.dart"):
            if rfile.exists():
                try:
                    text = rfile.read_text(encoding="utf-8")
                    found = re.findall(r"['\"](/[\w/\-]+)['\"]", text)
                    ctx["routes"] += found
                    ctx["routes"] = list(dict.fromkeys(ctx["routes"]))[:15]
                except Exception:
                    pass

    return ctx


def _format_project_context(ctx: dict) -> str:
    """Format project context into a readable string for the system prompt."""
    lines = []
    if ctx.get("app_name"):
        lines.append(f"App name: {ctx['app_name']}")
    if ctx.get("description"):
        lines.append(f"Description: {ctx['description']}")
    if ctx.get("screens"):
        lines.append(f"Known screens: {', '.join(ctx['screens'][:20])}")
    if ctx.get("routes"):
        lines.append(f"Known routes: {', '.join(ctx['routes'])}")
    if ctx.get("has_auth"):
        lines.append("The app has authentication (login/register screens)")
    return "\n".join(lines) if lines else "No project context available"


# ══════════════════════════════════════════════════════════════════════════════
# Credential Store — per-project test accounts
# ══════════════════════════════════════════════════════════════════════════════

def get_credentials(project_name: str) -> dict | None:
    """Return {email, password} for the project, or None if not stored."""
    try:
        if _CREDENTIALS_FILE.exists():
            data = json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
            return data.get(project_name) or data.get(project_name.lower())
    except Exception:
        pass
    return None


def save_credentials(project_name: str, email: str, password: str) -> None:
    """Save test credentials for a project to memory/test_credentials.json."""
    try:
        _CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _CREDENTIALS_FILE.exists():
            data = json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
        data[project_name] = {
            "email":    email,
            "password": password,
            "saved_at": datetime.now().isoformat(),
        }
        _CREDENTIALS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved credentials for {project_name}")
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# OpenAI key
# ══════════════════════════════════════════════════════════════════════════════

def _get_openai_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            key = data.get("openai_api_key", "").strip()
            if key:
                os.environ["OPENAI_API_KEY"] = key
                return key
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Error log
# ══════════════════════════════════════════════════════════════════════════════

def _log_test_error(project: str, task: str, steps: list[str],
                    error: str, screenshot_path: str | None) -> str:
    try:
        date_str  = datetime.now().strftime("%Y-%m-%d_%H-%M")
        safe_task = re.sub(r"[^\w\s-]", "", task)[:40].strip().replace(" ", "-")
        log_dir   = _TEST_LOGS_DIR / project
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file  = log_dir / f"{date_str}_{safe_task}.md"
        lines = [
            f"# Test Failure: {task}",
            f"\n**Project:** {project}",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Error:** {error}\n",
            "## Steps Taken\n",
        ]
        for i, s in enumerate(steps, 1):
            lines.append(f"{i}. {s}")
        if screenshot_path:
            lines.append(f"\n## Screenshot\n![screenshot]({screenshot_path})")
        log_file.write_text("\n".join(lines), encoding="utf-8")
        return str(log_file)
    except Exception as e:
        logger.warning(f"log_test_error: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# LLM — GPT-4o decides next playwright-cli command from snapshot
# ══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt(project_ctx: dict, credentials: dict | None,
                         app_url: str = "") -> str:
    creds_section = (
        f"TEST CREDENTIALS:\n  Email:    {credentials['email']}\n  Password: {credentials['password']}"
        if credentials
        else "No test credentials stored. If login is required, stop and report credentials needed."
    )
    url_lock = (
        f"""\n⚠ NAVIGATION LOCK — The app is at {app_url}.
  - The ONLY allowed goto target is exactly {app_url}.
  - NEVER goto any other URL. If you accidentally navigated away and see an error page,
    your very next command must be: [\"goto\", \"{app_url}\"]
  - Do NOT invent URLs, paths, hash fragments, or query strings."""
        if app_url else ""
    )
    return f"""You are a browser automation agent for Flutter web apps, powered by playwright-cli.

You can execute ANY task in the app: testing flows, filling forms, navigating screens,
clicking buttons, reading data, automating workflows \u2014 anything a user can do in Chrome.
You are not limited to QA testing. Treat the task description as your exact goal.

PROJECT CONTEXT:
{_format_project_context(project_ctx)}

{creds_section}
{url_lock}

You control the browser by choosing the next playwright-cli command.
A screenshot of the ACTUAL screen is provided with each step — use it to understand what is
currently visible, which fields are filled, and what error messages (if any) are showing.

IMPORTANT — FLUTTER CANVASKIT:
Flutter renders to <canvas>. Accessibility elements appear as flt-semantics overlays.
When refs ARE available: prefer fill/click with refs (more reliable).
When NO refs available (snapshot empty): use mousemove + mousedown + mouseup at pixel coords.
  Typical Flutter login layout (1280×800 viewport):
    Email field:    x=640 y=320
    Password field: x=640 y=400
    Login button:   x=640 y=480

FIELD FILLING — CRITICAL RULES:
  - After filling a field, take a snapshot BEFORE filling the next field.
  - Do NOT fill the same ref twice in a row.
  - The screenshot shows what is actually typed — trust it over the snapshot text.
  - If you already filled the email field (visible in screenshot), move on to the password.

RESPOND WITH JSON ONLY — no other text:
{{
  "command": ["fill", "e5", "email@example.com"],
  "flow_name": "Login Flow",
  "done": false,
  "passed": null,
  "message": "1-2 sentence: what you see and why you chose this action",
  "error": "exact error text visible on screen or null",
  "feedback": "UX observations (slow load, unresponsive element, layout bug) — or null",
  "assert": "exact text that MUST appear on screen after this action, or null"
}}

DETERMINISTIC ASSERTIONS — set "assert" after any key action:
  - After submitting login → assert: "dashboard" (or whatever the home screen title says)
  - After generating a visitor pass → assert: "pass" or the pass code text
  - After tapping a navigation button → assert: the screen title that should appear
  - After filling a form and submitting → assert: the success message text
  - For snapshot / non-assertable steps → assert: null
  Keep the assert value SHORT (1-3 words) — it is checked as a case-insensitive substring.
  Only assert something you are CONFIDENT should appear. Do not guess.

FLOW TRACKING — CRITICAL:
  Always set "flow_name" to the name of the current test flow (e.g. "Login Flow",
  "Visitor Pass Generation", "Onboarding Skip", "Discovery").
  On your FIRST step, set flow_name to "Discovery" — take a snapshot and in your
  "message" list ALL visible screens, sections, and interactive features you can see.
  This inventory helps you plan the test and avoid repeating flows.

FINAL REPORT — when you set done:true:
  Your "message" MUST be a complete test summary, e.g.:
  "Test complete. Flows tested: Login Flow (PASSED), Visitor Pass (PASSED — code generated
  correctly). Issues: Firebase returned 400 on first sign-up attempt (likely duplicate account).
  UX note: Visitor pass button was unresponsive on first tap."
  Be specific. Don't just say "Test complete."

COMMAND OPTIONS (array of CLI args, without 'playwright-cli -s=...' prefix):
  ["snapshot"]                        — refresh snapshot to see current state
  ["fill", "<ref>", "<text>"]        — fill a text field by ref
  ["click", "<ref>"]                 — click element by ref
  ["press", "Enter"]                 — keyboard press
  ["goto", "{app_url}"]              — ONLY use to recover if page lost (see NAVIGATION LOCK)
  ["mousemove", "<x>", "<y>"]        — move mouse (canvas fallback)
  ["mousedown"]                      — press mouse button (canvas fallback)
  ["mouseup"]                        — release mouse button (canvas fallback)
  ["type", "<text>"]                 — type into focused element (canvas fallback)

ONBOARDING / SPLASH SCREENS:
  The app may show a welcome/onboarding screen before login (e.g. "Welcome to Estate Access").
  If you see "Skip", "Next", "Get Started" or similar intro buttons — click "Skip" FIRST
  to jump straight to the login screen. Do NOT use goto URL to navigate.

LOGIN SEQUENCE (exact):
  1. If on onboarding → click Skip button (fastest path to login)
  2. snapshot → identify email ref and password ref from screenshot
  3. fill <email-ref> {credentials['email'] if credentials else 'EMAIL'}
  4. snapshot → verify email visible in screenshot
  5. fill <password-ref> {credentials['password'] if credentials else 'PASSWORD'}
  6. click <login-button-ref>  OR  press Enter
  7. wait (snapshot) → check screenshot for success (dashboard) or error message
  8. done:true, passed:true/false

CANVAS FALLBACK (no refs):
  mousemove 640 320 → mousedown → mouseup → type <email>
  mousemove 640 400 → mousedown → mouseup → type <password>
  mousemove 640 480 → mousedown → mouseup

ERROR DETECTION: capture any red banner, SnackBar, or "Invalid credentials" text in "error".
When done: done:true, passed:true/false, result summary in "message".

CRITICAL — DO NOT REPEAT FLOWS:
Once you have successfully completed a test flow (e.g. Login, Generate Visitor Pass, etc.),
do NOT loop back and repeat it. Each flow should be tested exactly ONCE.
After verifying a feature passes or fails, navigate to a DIFFERENT screen/feature —
OR set done:true if the full task is complete.
Repeating the same flow wastes steps and causes an infinite loop. Never do it."""


def _call_llm(client, system_prompt: str, snapshot: str,
               task: str, history: list, step: int,
               screenshot_b64: str | None = None) -> dict:
    """Decide next playwright-cli command.
    Tries Ollama (local) first — free, private, fast.
    Falls back to GPT-4o (cloud) if Ollama is unavailable or returns bad JSON.
    Note: Ollama doesn't support vision, so screenshots are cloud-only.
    """
    snap_hint = (
        "\n⚠ Snapshot is sparse — use the SCREENSHOT to see what is on screen. "
        "If the login form is visible, use CANVAS FALLBACK coords. DO NOT use goto."
        if len(snapshot) < 500 else ""
    )

    # Build the user turn (text + optional screenshot)
    user_text = (
        f"Step {step}. Task: {task}{snap_hint}\n\n"
        f"Current accessibility snapshot:\n```\n{snapshot[:10000]}\n```\n\n"
        "The screenshot shows the ACTUAL current screen. "
        "Use it to understand what is filled, visible, and what to do next. "
        "Respond with JSON only."
    )
    user_content_vision: list = [{"type": "text", "text": user_text}]
    if screenshot_b64:
        user_content_vision.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}", "detail": "low"},
        })

    history_tail = history[-10:]

    # ── Try local Ollama first ───────────────────────────────────────────────
    try:
        from llm import is_ollama_available, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
        if is_ollama_available():
            local_msgs = [{"role": "system", "content": system_prompt}]
            local_msgs += [
                {"role": m["role"], "content": (
                    " ".join(p["text"] for p in m["content"] if p.get("type") == "text")
                    if isinstance(m.get("content"), list) else m["content"]
                )}
                for m in history_tail
            ]
            local_msgs.append({"role": "user", "content": user_text})
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": local_msgs, "stream": False},
                timeout=OLLAMA_TIMEOUT,
            )
            if resp.status_code == 200:
                raw = resp.json().get("message", {}).get("content", "").strip()
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                try:
                    result = json.loads(raw)
                    logger.debug("flutter_tester: Ollama responded OK")
                    return result
                except Exception:
                    logger.warning("flutter_tester: Ollama returned non-JSON — falling back to GPT-4o")
            else:
                logger.warning(f"flutter_tester: Ollama HTTP {resp.status_code} — falling back to GPT-4o")
    except Exception as e:
        logger.warning(f"flutter_tester: Ollama unavailable ({e}) — using GPT-4o")

    # ── GPT-4o fallback (cloud, supports vision) ─────────────────────────────
    import openai
    messages = [{"role": "system", "content": system_prompt}]
    messages += history_tail
    messages.append({"role": "user", "content": user_content_vision})
    resp = client.chat.completions.create(
        model="gpt-4o", messages=messages, max_tokens=600, temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        return {"command": ["snapshot"], "done": False, "message": raw, "error": None}


# ══════════════════════════════════════════════════════════════════════════════
# Session management helpers
# ══════════════════════════════════════════════════════════════════════════════

def _clear_session(cli: str, app_url: str, log) -> None:
    """
    Wipe localStorage, sessionStorage, and document cookies so every test run
    starts from a fresh, unauthenticated state.  Then reload the app URL so
    Flutter reinitialises without any cached auth token.
    """
    log("Clearing browser session (localStorage + sessionStorage + cookies) …")

    # Get any element ref — all DOM elements share the same window
    snap = _get_snapshot(cli)
    m = re.search(r"\[ref=(e\d+)\]", snap)
    if m:
        ref = m.group(1)
        clear_js = (
            "(el) => { "
            "const w = el.ownerDocument.defaultView; "
            "try { w.localStorage.clear(); } catch(e) {} "
            "try { w.sessionStorage.clear(); } catch(e) {} "
            "try { w.document.cookie.split(';').forEach(c => { "
            "  const k = c.trim().split('=')[0]; "
            "  w.document.cookie = k + '=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/'; "
            "}); } catch(e) {} "
            "}"
        )
        _run_cmd(cli, ["eval", clear_js, ref], timeout=10)
        log("  Storage cleared.")
    else:
        log("  No element refs found — skipping JS storage clear.")

    # Reload to re-init Flutter without cached auth
    _run_cmd(cli, ["goto", app_url], timeout=15)
    log(f"  App reloaded at {app_url}")
    time.sleep(5)   # Flutter CanvasKit needs time to bootstrap again


def _detect_screen_state(cli: str, client: Any, snap: str,
                          screenshot_b64: str | None) -> str:
    """
    Ask GPT-4o to describe the current app screen in 1-2 sentences.
    Returns a plain-English description injected into the LLM context so it
    knows exactly where it is before the first navigation step.
    """
    system = (
        "You are a Flutter app screen inspector. "
        "Given the accessibility tree (and optional screenshot), describe the "
        "CURRENT state of the app in 1-2 sentences. Be specific:\n"
        "- Which screen is showing (login, home, dashboard, visitor pass, etc.)?\n"
        "- Is the user authenticated or on a guest/unauthenticated screen?\n"
        "- What key UI elements are immediately visible?\n"
        "Do NOT suggest actions. Only describe what you currently see."
    )
    user_parts: list = []
    if screenshot_b64:
        user_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}", "detail": "low"},
        })
    user_parts.append({
        "type": "text",
        "text": f"Accessibility tree (first 3000 chars):\n{snap[:3000]}\n\nDescribe the current app state.",
    })
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_parts},
            ],
            max_tokens=120,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"_detect_screen_state failed: {e}")
        return "(screen state unknown)"


def _wait_for_render(cli: str, prev_snap: str,
                      max_wait: float = 5.0, interval: float = 0.5) -> None:
    """
    Poll accessibility tree until it changes from prev_snap or max_wait elapses.
    Replaces blanket sleep(2.5) — returns early once Flutter has re-rendered.
    """
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(interval)
        new_snap = _get_snapshot(cli)
        if new_snap != prev_snap:
            return   # UI has changed — done waiting
    # timed out — Flutter may not have re-rendered but we continue anyway


# ══════════════════════════════════════════════════════════════════════════════
# Main agent loop — opens browser, runs steps, closes
# ══════════════════════════════════════════════════════════════════════════════

def _run_agent(cli: str, task: str, app_url: str, api_key: str,
               system_prompt: str, project_name: str, ui: Any = None,
               reset_session: bool = False) -> str:
    import openai

    def _log(msg: str):
        logger.info(msg)
        if ui:
            ui.write_log(f"[TESTER] {msg}")

    client        = openai.OpenAI(api_key=api_key)
    history: list = []
    steps:   list = []
    passed        = None
    final_message = f"Reached {_MAX_STEPS} steps limit."
    screenshot_path: str | None = None
    errors_seen: list[str]      = []

    # ── Per-run tracking (for professional test report) ───────────────────────
    run_ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_snap_dir = _SNAP_DIR / run_ts           # timestamped dir preserves all screenshots
    run_snap_dir.mkdir(parents=True, exist_ok=True)
    current_flow  = ""                          # what flow we're currently testing
    flows_results: list[dict] = []             # [{name, passed, errors, feedback}]
    feedbacks: list[str]    = []               # UX feedback notes from LLM

    (_TEST_LOGS_DIR / project_name).mkdir(parents=True, exist_ok=True)
    _SNAP_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"Starting test run {run_ts} — task: {task}")

    browser_proc = _open_browser(cli, app_url)

    if browser_proc is None:
        _log(f"Reusing existing Chrome — navigated to {app_url}")
    else:
        _log(f"Opening {app_url} in Chrome …")
        time.sleep(6)   # Flutter needs time to bootstrap CanvasKit
        # Confirm browser actually opened
        ok, probe = _run_cmd(cli, ["snapshot"], timeout=10)
        if not ok and "not open" in probe.lower():
            browser_proc.terminate()
            return f"Browser failed to open. playwright-cli error: {probe[:200]}"

    # ── Fix 1: Auto-enable accessibility ────────────────────────────────────
    # Flutter web shows a browser-level "Enable accessibility" button that MUST
    # be clicked before the semantic element tree populates with real refs.
    # IMPORTANT: use JS eval click (not ARIA click) — Flutter's button responds
    # only to real DOM pointer events, not accessibility tree actions.
    _log("Checking for Flutter accessibility prompt …")
    init_snap = _get_snapshot(cli)
    if "enable accessibility" in init_snap.lower():
        m = re.search(r"\[ref=(e\d+)\]", init_snap)
        if m:
            _log(f"Auto-enabling accessibility via JS click ({m.group(1)})")
            # JS .click() triggers Flutter's onclick handler; ARIA click does NOT
            _run_cmd(cli, ["eval", "(el) => el.click()", m.group(1)], timeout=10)
        else:
            # No ref — use keyboard Tab + Enter to click the focused button
            _log("Accessibility button has no ref — using keyboard Tab+Enter")
            _run_cmd(cli, ["press", "Tab"], timeout=5)
            _run_cmd(cli, ["press", "Enter"], timeout=5)
        # Wait for Flutter to build the semantic tree (typically 2-5 s)
        _log("Waiting for Flutter semantic tree …")
        for _w in range(20):          # up to 40 s
            time.sleep(2)
            _chk = _get_snapshot(cli)
            if "enable accessibility" not in _chk.lower() and len(_chk) > 10:
                _log(f"  Flutter tree ready ({len(_chk)} chars after {(_w+1)*2}s)")
                break
            _log(f"  tree loading … {len(_chk)} chars")
        else:
            _log("Warning: semantic tree still sparse — will rely on screenshots")
    _log("Browser ready — starting agent loop")

    # ── Session isolation: clear auth state before the test runs ─────────────
    # If the previous test left the app logged in, this wipes localStorage /
    # sessionStorage / cookies and reloads the app so every test starts fresh.
    if reset_session:
        _clear_session(cli, app_url, _log)
        # After reload we must re-enable accessibility
        _log("Re-checking accessibility after session reset …")
        init_snap2 = _get_snapshot(cli)
        if "enable accessibility" in init_snap2.lower():
            m2 = re.search(r"\[ref=(e\d+)\]", init_snap2)
            if m2:
                _run_cmd(cli, ["eval", "(el) => el.click()", m2.group(1)], timeout=10)
            else:
                _run_cmd(cli, ["press", "Tab"], timeout=5)
                _run_cmd(cli, ["press", "Enter"], timeout=5)
            for _w2 in range(15):
                time.sleep(2)
                _chk2 = _get_snapshot(cli)
                if "enable accessibility" not in _chk2.lower() and len(_chk2) > 10:
                    _log(f"  Accessibility re-enabled after reset ({len(_chk2)} chars)")
                    break

    # ── Screen-state awareness: tell the LLM exactly where the app is now ────
    # Take a quick screenshot + snapshot and ask GPT-4o to describe the screen.
    # This is injected as the very first history message so the LLM knows
    # whether it needs to navigate to login, logout first, or start mid-flow.
    _log("Detecting current screen state …")
    state_snap = _get_snapshot(cli)
    state_scr_path = str(_SNAP_DIR / "state_detect.png")
    _run_cmd(cli, ["screenshot", f"--filename={state_scr_path}"], timeout=10)
    try:
        state_scr_b64 = base64.b64encode(Path(state_scr_path).read_bytes()).decode()
    except Exception:
        state_scr_b64 = None
    screen_state = _detect_screen_state(cli, client, state_snap, state_scr_b64)
    _log(f"  Current state: {screen_state}")
    # Seed history so every LLM call is grounded in the real starting screen
    history.append({
        "role": "user",
        "content": (
            f"CURRENT SCREEN STATE (before you take any action):\n{screen_state}\n\n"
            f"Task to complete: {task}\n\n"
            "Start from the screen state described above. If the app is already "
            "on the required screen, proceed directly. If the app is in the wrong "
            "state (e.g. already logged in when you need to test login), navigate "
            "to the correct starting point first."
        ),
    })
    history.append({
        "role": "assistant",
        "content": (
            f"Understood. Current screen: {screen_state}. "
            f"I will navigate correctly from this state to complete: {task}"
        ),
    })

    # ── Fix 3: Dedup guard state ─────────────────────────────────────────────
    recent_cmds: list[str] = []   # last 3 command strings
    snap_counts: dict[str, int] = {}   # snap hash → how many times seen (stuck detection)

    try:
        for step in range(1, _MAX_STEPS + 1):
            # ── Cancellation check ───────────────────────────────────────────
            if _test_state["cancel_event"].is_set():
                final_message = "Test cancelled by you."
                _log("  !! Test cancelled by user request")
                break
            _test_state["step"] = step

            snap     = _get_snapshot(cli)

            # ── Stuck detection: same screen 4× in a row → stop ─────────────
            snap_hash = hashlib.md5(snap[:2000].encode()).hexdigest()
            snap_counts[snap_hash] = snap_counts.get(snap_hash, 0) + 1
            if snap_counts[snap_hash] >= 4:
                last_action = steps[-1][:80] if steps else "none"
                final_message = (
                    f"I'm stuck — the same screen has appeared {snap_counts[snap_hash]} times "
                    f"without progress. I'm stopping the test. Last action: {last_action}"
                )
                _log(f"  !! Stuck: snap hash seen {snap_counts[snap_hash]}× — stopping")
                passed = False
                break

            # ── In-loop: auto-handle accessibility overlay so LLM never sees it ──
            if "enable accessibility" in snap.lower():
                m = re.search(r"\[ref=(e\d+)\]", snap)
                if m:
                    _log(f"  [auto-acc] JS-clicking accessibility button ({m.group(1)})")
                    _run_cmd(cli, ["eval", "(el) => el.click()", m.group(1)], timeout=10)
                else:
                    _log("  [auto-acc] keyboard Tab+Enter on accessibility button")
                    _run_cmd(cli, ["press", "Tab"], timeout=5)
                    _run_cmd(cli, ["press", "Enter"], timeout=5)
                # Wait for real tree (check that button is gone, not just > N chars)
                for _w in range(15):   # up to 30 s
                    time.sleep(2)
                    _new = _get_snapshot(cli)
                    if "enable accessibility" not in _new.lower() and len(_new) > 10:
                        snap = _new
                        _log(f"  [auto-acc] tree enabled ({len(snap)} chars)")
                        break
                    _log(f"  [auto-acc] still waiting … {len(_new)} chars")
                else:
                    _log("  [auto-acc] giving up on accessibility — using screenshots")

            has_refs = _has_refs(snap)

            # ── Fix 2: Screenshot for GPT-4o vision ─────────────────────────
            scr_path = str(run_snap_dir / f"step_{step:02d}.png")
            _run_cmd(cli, ["screenshot", f"--filename={scr_path}"], timeout=10)
            try:
                screenshot_b64 = base64.b64encode(Path(scr_path).read_bytes()).decode()
            except Exception:
                screenshot_b64 = None

            _log(f"Step {step}/{_MAX_STEPS}  refs={'yes' if has_refs else 'NO (canvas mode)'}  "
                 f"snap_len={len(snap)}")

            decision = _call_llm(client, system_prompt, snap, task, history, step,
                                 screenshot_b64=screenshot_b64)
            command  = decision.get("command", [])

            # ── Fix 3: Dedup guard ───────────────────────────────────────────
            cmd_key = json.dumps(command)
            recent_cmds.append(cmd_key)
            if len(recent_cmds) > 3:
                recent_cmds.pop(0)
            if len(recent_cmds) == 3 and len(set(recent_cmds)) == 1:
                _log("  !! Dedup guard: same command 3× in a row — forcing snapshot")
                command = ["snapshot"]
                recent_cmds = []

            # ── Goto guard: block ALL goto commands ────────────────────────
            # The browser is already on the app. goto reloads Flutter and brings
            # back the accessibility overlay → infinite loop. Convert to snapshot.
            if command and command[0] == "goto":
                _log(f"  !! Goto guard: browser already on app — converting goto → snapshot")
                command = ["snapshot"]
                recent_cmds = []

            note      = decision.get("message", "")
            error     = decision.get("error")
            is_done   = decision.get("done", False)
            passed    = decision.get("passed")
            flow_name = (decision.get("flow_name") or "").strip()
            feedback  = (decision.get("feedback") or "").strip()
            assertion = (decision.get("assert") or "").strip()

            # ── Flow transition tracking ──────────────────────────────────────
            if flow_name and flow_name != current_flow:
                if current_flow:
                    # Close out previous flow with whatever pass/fail we have so far
                    flows_results.append({
                        "name": current_flow, "passed": passed,
                        "errors": list(errors_seen), "feedback": list(feedbacks),
                    })
                    feedbacks.clear()
                current_flow = flow_name
                _log(f"  [FLOW] Now testing: {flow_name}")

            if feedback and feedback.lower() not in ("null", "none"):
                feedbacks.append(feedback)
                _log(f"  [UX] {feedback}")

            step_str = f"{' '.join(str(a) for a in command)} — {note}"
            steps.append(step_str)
            _log(f"  → {step_str[:120]}")

            if error:
                errors_seen.append(error)
                _log(f"  ERROR: {error}")

            history.append({"role": "assistant", "content": f"step {step}: {step_str}"})

            if is_done or not command:
                status = "PASSED" if passed else ("FAILED" if passed is False else "DONE")
                final_message = note or "Test complete."
                _log(f"Test {status}: {final_message}")
                break

            # Screenshot on error or final step
            if error or (is_done and passed is False) or step == _MAX_STEPS:
                ts = datetime.now().strftime("%H%M%S")
                screenshot_path = str(
                    _TEST_LOGS_DIR / project_name / f"step{step}_{ts}.png"
                )
                _run_cmd(cli, ["screenshot", f"--filename={screenshot_path}"], timeout=10)
                _log(f"  Screenshot → {screenshot_path}")

            # Execute the command
            ok, out = _run_cmd(cli, command, timeout=20)
            if not ok:
                _log(f"  cmd failed: {out[:200]}")
                errors_seen.append(f"cli_err:{out[:120]}")
                # Inform the LLM the command failed so it can try a different approach
                history.append({
                    "role": "user",
                    "content": (
                        f"[step {step}] Your command {json.dumps(command)} FAILED: "
                        f"{out[:150]}. Please try a different approach to achieve the same goal."
                    )
                })

            # Wait for Flutter to re-render (dynamic — returns early once UI changes)
            if command[0] in ("fill", "click", "press", "goto", "type",
                               "mousedown", "mouseup", "mousemove"):
                _wait_for_render(cli, snap)

            # ── Deterministic assertion check ────────────────────────────────
            # The LLM specified what text MUST appear after this action.
            # We verify it against the live snapshot — no LLM judgment involved.
            if assertion and assertion.lower() not in ("null", "none", ""):
                post_snap = _get_snapshot(cli)
                if assertion.lower() in post_snap.lower():
                    _log(f"  [ASSERT] PASS — '{assertion}' found in snapshot (step {step})")
                    history.append({
                        "role": "user",
                        "content": (
                            f"[step {step}] ASSERTION PASSED: '{assertion}' is visible on screen."
                        ),
                    })
                else:
                    fail_msg = (
                        f"[step {step}] ASSERTION FAILED: expected '{assertion}' to be visible "
                        f"but it was NOT found in the snapshot. "
                        f"Snapshot excerpt: {post_snap[:300]}"
                    )
                    _log(f"  [ASSERT] FAIL — '{assertion}' NOT in snapshot (step {step})")
                    errors_seen.append(f"assert_fail:'{assertion}' not visible after step {step}")
                    history.append({"role": "user", "content": fail_msg})

    finally:
        _close_browser(cli, browser_proc)

    # ── Close out the last active flow ────────────────────────────────────────
    if current_flow:
        flows_results.append({
            "name": current_flow, "passed": passed,
            "errors": list(errors_seen), "feedback": list(feedbacks),
        })

    # ── Fix: passed=None at step limit means the task never completed = FAIL ──
    if passed is None and final_message.startswith("Reached"):
        passed = False
        final_message = (
            f"Test did not complete within {_MAX_STEPS} steps. "
            "The app may have more screens than expected, or the task was too broad."
        )

    # ── Build structured test report ──────────────────────────────────────────
    def _build_report() -> str:
        if not flows_results:
            return final_message

        parts: list[str] = []
        total    = len(flows_results)
        n_passed = sum(1 for f in flows_results if f["passed"] is True)
        n_failed = sum(1 for f in flows_results if f["passed"] is False)

        parts.append(
            f"Test complete. {n_passed}/{total} flow{'s' if total != 1 else ''} passed."
        )

        for fr in flows_results:
            icon   = "PASSED" if fr["passed"] is True else ("FAILED" if fr["passed"] is False else "INCOMPLETE")
            errs   = ", ".join(fr["errors"][:2]) if fr["errors"] else ""
            fb_str = "; ".join(fr["feedback"][:2]) if fr["feedback"] else ""
            line   = f"{fr['name']}: {icon}"
            if errs:
                line += f" — errors: {errs}"
            if fb_str:
                line += f" — UX: {fb_str}"
            parts.append(line)

        # Add any feedbacks not yet surfaced
        all_fb = [f for fr in flows_results for f in fr["feedback"]]
        if all_fb:
            parts.append(f"UX notes: {'; '.join(all_fb[:3])}")

        return " | ".join(parts)

    spoken_report = _build_report()
    _log(f"REPORT: {spoken_report}")

    # ── Save error log if anything failed ─────────────────────────────────────
    if errors_seen or passed is False:
        summary  = "; ".join(dict.fromkeys(errors_seen)) if errors_seen else "Test failed"
        log_path = _log_test_error(project_name, task, steps, summary, screenshot_path)
        if log_path:
            _log(f"Error log → {log_path}")
            spoken_report += " Detailed log saved to Sam Notes."

    return spoken_report


# ══════════════════════════════════════════════════════════════════════════════
# Skill entry point — called by the skill loader
# ══════════════════════════════════════════════════════════════════════════════

def _login_required(task: str) -> bool:
    t = task.lower()
    return any(w in t for w in ["login", "log in", "sign in", "signin", "auth",
                                  "credential", "password"])


def _run(parameters: dict, ui: Any, **ctx) -> str:
    intent = ctx.get("intent", "")
    intent_str = str(intent).lower()

    if "login" in intent_str or "sign_in" in intent_str:
        default_task = (
            "Test the login flow: locate the login screen, enter the stored credentials, "
            "submit, and verify successful authentication or report the exact error."
        )
    elif "signup" in intent_str or "register" in intent_str:
        default_task = (
            "Test the signup/registration flow: navigate to the registration screen, "
            "fill in the required fields with test data, submit, and verify success."
        )
    else:
        # Generic automation — rely on whatever the user described as the task
        default_task = (
            "Load the app, navigate the main screen, and complete the requested task."
        )
    task_from_params = (
        parameters.get("task") or parameters.get("test") or parameters.get("text")
    )
    task = (task_from_params or default_task).strip()

    # Resolve URL / port from voice command
    explicit_url: str | None = None
    port_param = parameters.get("port") or parameters.get("app_port")
    url_param  = parameters.get("url")  or parameters.get("app_url")
    if url_param:
        explicit_url = url_param if url_param.startswith("http") else f"http://{url_param}"
    elif port_param:
        explicit_url = f"http://localhost:{port_param}"
    if explicit_url:
        _save_flutter_url(explicit_url)

    api_key = _get_openai_key()
    if not api_key:
        return ("I need an OpenAI API key to run visual tests. "
                "Add it to config/api_keys.json under 'openai_api_key'.")

    cli = _ensure_cli()
    if not cli:
        return ("playwright-cli is not installed. "
                "Run: npm install -g @playwright/cli@latest")

    app_url = explicit_url
    if not app_url:
        all_urls = _find_all_flutter_urls()
        if not all_urls:
            if ui:
                ui.write_log("[TESTER] Can't find a running Flutter app automatically.")
            return (
                "I couldn't find a running Flutter app on any local port. "
                "What port is it running on? Say something like "
                "'test my app on port 54321' and I'll use that."
            )
        elif len(all_urls) == 1:
            app_url = all_urls[0]
            _save_flutter_url(app_url)
        else:
            # Multiple apps found — ask the user which one to test
            ports = [u.rsplit(":", 1)[-1] for u in all_urls]
            return (
                f"I found {len(all_urls)} Flutter apps running: ports {', '.join(ports)}. "
                f"Which one should I test? Say 'test my app on port {ports[0]}' or similar."
            )

    # Ask for a specific flow if the user didn't describe one
    if not task_from_params:
        return (
            "Found the app. What do you want me to test? For example: "
            "'test the login flow', 'test the visitor pass feature', "
            "or 'run a general check of the main screens'."
        )

    if ui:
        ui.write_log(f"[TESTER] Found app at: {app_url}")

    try:
        from actions.terminal import get_cwd
        cwd = get_cwd()
    except Exception:
        cwd = str(_ROOT)

    project_ctx  = _scan_project(cwd)
    project_name = project_ctx.get("app_name") or Path(cwd).name

    folder_name = Path(cwd).name
    cred_keys   = list(dict.fromkeys([
        project_name, project_name.lower(),
        project_name.split(" ")[0] if project_name else "",
        folder_name, folder_name.lower(),
    ]))
    credentials = next(
        (get_credentials(k) for k in cred_keys if k and get_credentials(k)),
        None,
    )
    if not credentials and _login_required(task):
        return (
            f"I don't have test credentials for {project_name} yet. "
            f"Tell me: 'Save Sam's credentials for {project_name} — "
            f"email is X, password is Y' and I'll store them and run the test."
        )

    logger.info(f"Testing '{project_name}' at {app_url}: {task!r}")
    if ui:
        ui.write_log(f"[TESTER] Project: {project_name} | Task: {task}")
        ui.write_log(f"[TESTER] Starting now. I'll update you when done or if stuck.")

    system_prompt = _build_system_prompt(project_ctx, credentials, app_url)

    # ── Determine if a session reset is needed before running ─────────────────
    # Reset when: (a) task involves auth flows, or (b) user explicitly says
    # "fresh", "clean", or "reset" — ensures the app starts unauthenticated.
    _auth_keywords = ("login", "log in", "sign in", "signin", "logout",
                      "log out", "sign out", "signout", "register", "signup",
                      "sign up", "authentication", "auth flow")
    _reset_keywords = ("fresh", "clean test", "reset session", "clear session",
                       "from scratch", "start fresh")
    task_lower = task.lower()
    reset_session = (
        any(kw in task_lower for kw in _auth_keywords) or
        any(kw in task_lower for kw in _reset_keywords)
    )
    if reset_session and ui:
        ui.write_log("[TESTER] Auth flow detected — will clear session before testing.")

    # ── Set shared test state so ai_loop + LLM know a test is running ─────────
    _test_state["cancel_event"].clear()
    _test_state.update({
        "running": True,
        "step":    0,
        "task":    task,
        "app_url": app_url,
        "project": project_name,
    })
    try:
        return _run_agent(
            cli=cli, task=task, app_url=app_url, api_key=api_key,
            system_prompt=system_prompt, project_name=project_name, ui=ui,
            reset_session=reset_session,
        )
    except Exception as e:
        logger.error(f"flutter_tester error: {e}")
        return f"Testing hit an unexpected error: {e}"
    finally:
        _test_state["running"] = False
        _test_state["step"] = 0


# ══════════════════════════════════════════════════════════════════════════════
# Skill manifest
# ══════════════════════════════════════════════════════════════════════════════

SKILL_MANIFEST = {
    "name": "flutter_tester",
    "description": (
        "Automate or test ANY task in a Flutter web app — finds the running app automatically, "
        "reads the project structure, uses stored credentials, drives the browser via "
        "playwright-cli. Can handle login flows, form filling, navigation, feature testing, "
        "or any other user task described in natural language."
    ),
    "intents": [
        # Testing intents
        "test_flutter_app", "test_the_app", "run_app_test",
        "test_login_flow", "test_signup", "test_feature",
        # General automation intents
        "automate_task", "automate_app", "fill_form", "navigate_app",
        "use_the_app", "do_in_app",
    ],
    "trigger_phrases": [
        # Testing
        "test my app", "test the app", "test the login",
        "test that the signup", "run app tests", "check the app works",
        "test flutter app", "test the login flow", "run a test on",
        "test signup", "test the feature", "test that",
        # Automation
        "automate", "automate the", "fill the form", "fill in the",
        "navigate to the", "navigate the app", "use the app",
        "open the app and", "do this in the app", "can you do this",
        "go to the app", "in the app", "on the app",
        "click on the", "submit the form", "complete the",
    ],
    "run": _run,
}
