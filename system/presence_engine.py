"""
presence_engine.py — Sam's continuous environment awareness layer.

Runs a background daemon every 10 seconds that:
  1. Detects the active window and updates UserState
  2. Infers user mode (focused / debugging / browsing / idle)
  3. Detects stress signals (rapid window switching)
  4. Monitors Downloads folder for completed downloads
  5. Notices VS Code opening and greets with git context
  6. Tracks coding session duration and fires end-of-day ritual
  7. Enforces a gentle late-night boundary
  8. Queues suggestions when thresholds are crossed

Suggestions are consumed by main.py's ai_loop and delivered as
sound + UI log — no automatic voice unless the user responds.
"""
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from system.pattern_learner import PatternLearner


# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------

@dataclass
class UserState:
    mode: str = "idle"              # idle | focused | debugging | browsing
    stress_level: str = "low"       # low | medium | high
    active_app: str = ""            # e.g. 'Code.exe', 'chrome.exe'
    active_window_title: str = ""
    focus_start: Optional[datetime] = None   # when VS Code became foreground
    focus_minutes: float = 0               # continuous VS Code duration
    last_switch_times: list = field(default_factory=list)  # timestamps of app switches
    switch_count_last_minute: int = 0
    last_update: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PresenceEngine:
    """
    Background daemon that maintains UserState and produces suggestions.

    Usage:
        engine = PresenceEngine()
        engine.start()
        # main loop periodically calls engine.suggestions.get_nowait()
        snapshot = engine.get_state_snapshot()  # inject into LLM
    """

    # Apps considered "VS Code" (process name, lowercase)
    _VSCODE_NAMES = {"code.exe", "code - insiders.exe"}

    # Apps considered browsers (process name, lowercase)
    _BROWSER_NAMES = {"chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "brave.exe"}

    # Apps considered meeting/call tools — triggers meeting mode
    _MEETING_NAMES = {
        "zoom.exe", "zoom", "ms-teams.exe", "teams.exe", "teams",
        "discord.exe", "discord", "slack.exe", "slack",
        "googlemeet.exe", "meet.google.com",
    }

    # Per-key suggestion cooldowns in seconds
    _COOLDOWNS = {
        "break":              600,    # 10 minutes
        "debug_onset":        600,    # 10 minutes
        "stress":             600,    # 10 minutes
        "vscode_open":        600,    # 10 minutes — same project/state
        "vscode_welcome":    1800,    # 30 minutes
        "endofday":         14400,    # 4 hours
        "latenight":        10800,    # 3 hours
        "downloads_clutter":  86400,   # 24 hours
        "uncommitted":         1800,   # 30 minutes
        "morning_routine":    86400,   # 24 hours (once per day)
        "productivity_insight": 604800, # 7 days
        "git_danger":          60,    # 1 minute — re-alert quickly on merge/rebase
        "large_staged":       300,    # 5 minutes
        "dep_changed":        600,    # 10 minutes
    }

    # Threshold: suggest organising Downloads when this many files accumulate
    _DOWNLOADS_CLUTTER_THRESHOLD = 20

    # Threshold: suggest committing after this many minutes with pending changes
    _UNCOMMITTED_WARN_MINUTES = 120

    def __init__(self, poll_interval: int = 10):
        self.state = UserState()
        self.suggestions: queue.Queue = queue.Queue()
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Cooldown registry: suggestion key → datetime of last fire
        self._last_suggested: dict = {}

        # Debugging-mode onset flag
        self._debugging_notified = False

        # Build failure counter (tracked for session state + suggestions)
        self._build_failure_count: int = 0

        # VS Code transition flag (one-shot, consumed in _check_suggestions)
        self._vscode_just_opened: bool = False

        # Cached git context from last VS Code open scan
        self._last_git_context: Optional[dict] = None

        # Accumulated coding time this session (minutes)
        self._session_coding_minutes: float = 0

        # Downloads folder snapshot
        self._downloads_dir: Path = Path.home() / "Downloads"
        self._downloads_snapshot: set = self._snapshot_downloads()

        # Behavioral pattern learner
        self._pattern_learner = PatternLearner()

        # Suggestions held while focus shield is active — released as a batch when focus ends
        self._held_suggestions: list = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background presence loop."""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="SamPresenceEngine"
        )
        self._thread.start()

    def stop(self):
        """Signal the loop to exit."""
        self._running = False

    # ------------------------------------------------------------------
    # LLM-powered natural suggestion generator
    # ------------------------------------------------------------------

    def _llm_suggest(self, hint: str, context: dict | None = None, fallback: str = "") -> str:
        """Generate a short natural language observation using the LLM.

        Falls back to `fallback` if LLM is unavailable or slow.
        hint: what kind of observation to make (e.g. 'needs a break after coding 90 min')
        context: extra facts to include (app, project, time, etc.)
        """
        try:
            from agent.llm_bridge import agent_llm_call
            ctx_str = ""
            if context:
                ctx_str = " ".join(f"{k}={v}" for k, v in context.items() if v)
            prompt = (
                f"Context: {ctx_str}\n"
                f"Generate ONE short, natural, conversational message for Sam to say or show. "
                f"The message should be about: {hint}. "
                f"Max 20 words. No robotic openers. No 'I notice' or 'I observe'. "
                f"Be direct and human. Do not add quotes."
            )
            result = agent_llm_call(
                system="You are Sam, a sharp personal AI assistant living on the user's laptop.",
                user=prompt,
                require_json=False,
            )
            if result and len(result.strip()) > 3:
                return result.strip().strip('"\'')
        except Exception:
            pass
        return fallback

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self):
        while self._running:
            try:
                self._update_state()
                self._check_suggestions()
            except Exception:
                pass  # never crash the daemon
            time.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def _update_state(self):
        from system.window_tracker import get_foreground_window_info

        info = get_foreground_window_info()
        now = datetime.now()

        # Capture previous mode before any changes
        prev_mode = self.state.mode
        prev_app = self.state.active_app
        current_app = info.get("process", "").lower()

        self.state.active_app = current_app
        self.state.active_window_title = info.get("title", "")
        self.state.last_update = now

        # Record app switch for pattern learning
        self._pattern_learner.record_app(current_app)

        # ---- Track window switches ----
        if prev_app and prev_app != current_app:
            self.state.last_switch_times.append(now)

        cutoff = now.timestamp() - 60
        self.state.last_switch_times = [
            t for t in self.state.last_switch_times if t.timestamp() > cutoff
        ]
        self.state.switch_count_last_minute = len(self.state.last_switch_times)

        # ---- Determine mode ----
        is_vscode = current_app in self._VSCODE_NAMES
        is_browser = current_app in self._BROWSER_NAMES
        is_meeting = any(m in current_app for m in self._MEETING_NAMES)

        # --- Meeting detection: set system mode so TTS knows to go silent ----
        try:
            from conversation_state import controller as _ctrl
            prev_conv_mode = _ctrl.get_mode()
            if is_meeting and prev_conv_mode != "meeting":
                _ctrl.set_mode("meeting")
                self._queue({
                    "type": "meeting_detection",
                    "message": "Meeting detected. I'll go quiet — say 'Sam take notes' if you want me to listen in.",
                })
            elif not is_meeting and prev_conv_mode == "meeting":
                _ctrl.set_mode("normal")
                self._queue({
                    "type": "meeting_ended",
                    "message": "Meeting app closed. I'm back.",
                })
        except Exception:
            pass

        if is_vscode:
            if self.state.focus_start is None:
                self.state.focus_start = now
            self.state.focus_minutes = (
                now - self.state.focus_start
            ).total_seconds() / 60

            if self.state.switch_count_last_minute > 4:
                self.state.mode = "debugging"
                self.state.stress_level = "medium"
            else:
                self.state.mode = "focused"
                self.state.stress_level = "low"

        elif is_browser:
            self.state.focus_start = None
            self.state.focus_minutes = 0
            self.state.mode = "browsing"
            self.state.stress_level = "low"
            self._debugging_notified = False
            self._build_failure_count = 0

        else:
            self.state.focus_start = None
            self.state.focus_minutes = 0
            self.state.mode = "idle"
            self._debugging_notified = False

        # ---- Stress escalation (applies across any mode) ----
        if self.state.switch_count_last_minute > 6:
            self.state.stress_level = "high"

        # ---- Accumulate session coding time ----
        if self.state.mode in ("focused", "debugging"):
            self._session_coding_minutes += self._poll_interval / 60

        # ---- Detect VS Code opening ----
        if (prev_mode not in ("focused", "debugging")
                and self.state.mode in ("focused", "debugging")):
            self._vscode_just_opened = True

        # ---- Detect VS Code closing → save session + end-of-day ritual ----
        if (prev_mode in ("focused", "debugging")
                and self.state.mode not in ("focused", "debugging")):
            mins = self._session_coding_minutes
            self._session_coding_minutes = 0  # reset for next session
            # Record the completed session in the pattern learner
            project = (self._last_git_context or {}).get("project")
            self._pattern_learner.record_focus_session(mins, project=project)
            # Persist session context so next boot greeting is informed
            self._save_session_state(mins)
            # Flush any held suggestions now that focus has ended
            if self._held_suggestions:
                held = self._held_suggestions[:]
                self._held_suggestions.clear()
                n = len(held)
                self._queue({
                    "type": "held_release",
                    "message": (
                        f"{n} item{'s' if n > 1 else ''} quietly noted while you were coding."
                    ),
                })
                for s in held:
                    self._queue(s)
            if mins >= 30 and self._can_suggest("endofday"):
                commit_note = self._get_session_commit_note(int(mins))
                self._queue({
                    "type": "endofday",
                    "message": (
                        f"Good session — {int(mins)} minutes of coding. "
                        f"{commit_note}"
                        "Want me to archive today's notes?"
                    ),
                })
                self._mark_suggested("endofday")

        # ---- Download folder monitoring ----
        self._check_downloads()

    # ------------------------------------------------------------------
    # Focus Shield & Suggestion logic
    # ------------------------------------------------------------------

    def _focus_shield_active(self) -> bool:
        """
        Return True when the user has been in a focused/debugging session
        for at least 20 minutes.  While the shield is up, only safety-critical
        suggestions (stress, latenight, break) are allowed through.
        Non-urgent interruptions (downloads, uncommitted, patterns) are
        held until the session ends or the user goes idle.
        """
        return (
            self.state.mode in ("focused", "debugging")
            and self.state.focus_minutes >= 20
        )

    def _check_suggestions(self):
        mode = self.state.mode
        stress = self.state.stress_level
        mins = self.state.focus_minutes
        shield = self._focus_shield_active()

        # 1. VS Code just opened → git context greeting
        if self._vscode_just_opened:
            self._vscode_just_opened = False
            git = self._get_git_context()
            if git:
                # Build a fingerprint of current state to detect real changes
                new_key = f"{git['project']}|{git['branch']}|{git['summary']}"
                prev = self._last_git_context
                last_key = (
                    f"{prev['project']}|{prev['branch']}|{prev['summary']}"
                    if prev else ""
                )
                context_changed = new_key != last_key
                prev_project = prev["project"] if prev else None
                self._last_git_context = git

                if context_changed or self._can_suggest("vscode_open"):
                    self._mark_suggested("vscode_open")

                    # Richer briefing when actually switching to a different project
                    if prev_project and prev_project != git["project"]:
                        try:
                            import subprocess as _sp
                            last_commit = _sp.run(
                                ["git", "log", "-1", "--pretty=%s"], cwd=git["cwd"],
                                capture_output=True, text=True, timeout=3
                            ).stdout.strip()
                            message = (
                                f"Switching to {git['project']} on {git['branch']}. "
                                f"{git['summary']}."
                                + (f" Last commit: {last_commit}." if last_commit else "")
                            )
                        except Exception:
                            message = (
                                f"Back in {git['project']} on {git['branch']}. "
                                f"{git['summary']}."
                            )
                    else:
                        message = (
                            f"Back in {git['project']} on {git['branch']}. "
                            f"{git['summary']}."
                        )

                    self._queue({"type": "vscode_open", "message": message})

            elif self._can_suggest("vscode_welcome"):
                self._queue({
                    "type": "vscode_welcome",
                    "message": "Back in VS Code.",
                })
                self._mark_suggested("vscode_welcome")

        # 1b. Git intelligence checks (danger states, large files, deps)
        if (self.state.mode in ("focused", "debugging")
                and self._last_git_context
                and self._last_git_context.get("cwd")):
            try:
                from system.git_intelligence import get_git_status
                gs = get_git_status(self._last_git_context["cwd"])

                # Dangerous git state
                if gs.get("danger") and self._can_suggest("git_danger"):
                    self._mark_suggested("git_danger")
                    msg = {
                        "MERGING": "Heads up — your repo is mid-merge. Resolve conflicts before committing.",
                        "REBASING": "You're mid-rebase. Be careful with the next commit.",
                        "DETACHED_HEAD": "HEAD is detached — you're not on any branch. Create one before committing.",
                    }.get(gs["danger"], "")
                    if msg:
                        self._queue({"type": "git_danger", "message": msg})

                # Large files accidentally staged
                if gs.get("large_staged") and self._can_suggest("large_staged"):
                    self._mark_suggested("large_staged")
                    names = ", ".join(gs["large_staged"][:2])
                    self._queue({
                        "type": "large_staged",
                        "message": f"Large file staged: {names}. Was that intentional?",
                    })

                # Dependency file changed
                if gs.get("dep_changed") and self._can_suggest("dep_changed"):
                    self._mark_suggested("dep_changed")
                    deps = ", ".join(gs["dep_changed"][:2])
                    self._queue({
                        "type": "dep_changed",
                        "message": f"{deps} changed — want me to run install?",
                    })
            except Exception as _e:
                pass   # intelligence checks must never crash the presence loop

        # 2. Break suggestion after 90 consecutive minutes of focus
        if mode == "focused" and mins >= 90 and self._can_suggest("break"):
            msg = self._llm_suggest(
                f"user has been coding for {int(mins)} minutes and needs a short break",
                context={"project": (self._last_git_context or {}).get("project", ""), "minutes": int(mins)},
                fallback=f"You've been at it for {int(mins)} minutes. Quick stretch?",
            )
            self._queue({"type": "break", "message": msg})
            self._mark_suggested("break")

        # 3. Debugging onset — say once per debugging session
        if (mode == "debugging"
                and not self._debugging_notified
                and self._can_suggest("debug_onset")):
            self._build_failure_count += 1   # count each debugging burst
            msg = self._llm_suggest(
                "user seems to be debugging — offer a quiet helping hand",
                context={"project": (self._last_git_context or {}).get("project", "")},
                fallback="Looks like we're debugging. I'm here if you need me.",
            )
            self._queue({"type": "debug_onset", "message": msg})
            self._mark_suggested("debug_onset")
            self._debugging_notified = True

        if mode != "debugging":
            self._debugging_notified = False

        # 4. High stress nudge
        if stress == "high" and self._can_suggest("stress"):
            msg = self._llm_suggest(
                "user is switching windows rapidly and may be stressed or stuck",
                context={"switches_per_min": self.state.switch_count_last_minute},
                fallback="Looks like you're switching a lot. Want me to help with anything?",
            )
            self._queue({"type": "stress", "message": msg})
            self._mark_suggested("stress")

        # 4b. Focus guard — distraction detection (> 8 switches in last minute)
        if (self.state.switch_count_last_minute >= 8
                and mode not in ("focused", "debugging")
                and self._can_suggest("stress")):
            msg = self._llm_suggest(
                "user seems distracted, switching apps frequently",
                context={"app": self.state.active_app},
                fallback="You've been switching a lot. Want me to close distractions?",
            )
            self._queue({"type": "distraction", "message": msg})
            self._mark_suggested("stress")  # reuse stress cooldown

        # 5. Late-night boundary
        hour = datetime.now().hour
        if (hour >= 23 or hour < 4) and mode in ("focused", "debugging"):
            if self._can_suggest("latenight"):
                t = datetime.now().strftime("%I:%M %p")
                msg = self._llm_suggest(
                    f"it's {t} and the user is still working late",
                    context={"time": t},
                    fallback=f"It's {t}. Still here?",
                )
                self._queue({"type": "latenight", "message": msg})
                self._mark_suggested("latenight")

        # 6. Downloads folder clutter  (deferred while focus shield is active)
        try:
            n_downloads = len(self._downloads_snapshot)
            if (n_downloads >= self._DOWNLOADS_CLUTTER_THRESHOLD
                    and self._can_suggest("downloads_clutter")):
                suggestion = {
                    "type": "downloads_clutter",
                    "message": (
                        f"Downloads folder has {n_downloads} files. "
                        "Want me to help organise it?"
                    ),
                }
                if shield:
                    self._defer(suggestion)
                else:
                    self._queue(suggestion)
                self._mark_suggested("downloads_clutter")
        except Exception:
            pass

        # 7. Uncommitted changes reminder (after 2 hours of coding)
        #    Fires despite shield — it's actionable and time-sensitive.
        if (mode in ("focused", "debugging")
                and mins >= self._UNCOMMITTED_WARN_MINUTES
                and self._last_git_context
                and self._last_git_context.get("summary", "").startswith("0") is False
                and "clean" not in self._last_git_context.get("summary", "")
                and self._can_suggest("uncommitted")):
            git = self._last_git_context
            self._queue({
                "type": "uncommitted",
                "message": (
                    f"{git.get('summary', 'Uncommitted changes')} in "
                    f"{git.get('project', 'your repo')}. "
                    "Good time to commit?"
                ),
            })
            self._mark_suggested("uncommitted")

        # 8. Morning routine — offer to prepare workspace once a day
        #    Deferred if focus shield is active.
        if self._can_suggest("morning_routine"):
            suggestion = self._pattern_learner.get_morning_suggestion()
            if suggestion:
                item = {"type": "morning_routine", "message": suggestion}
                if shield:
                    self._defer(item)
                else:
                    self._queue(item)
                self._mark_suggested("morning_routine")

        # 9. Productivity insight — surface once a week; deferred during focus
        if self._can_suggest("productivity_insight"):
            insight = self._pattern_learner.get_productivity_insight()
            if insight:
                item = {"type": "productivity_insight", "message": insight}
                if mode == "idle":
                    self._queue(item)
                elif shield:
                    self._defer(item)
                self._mark_suggested("productivity_insight")

    # ------------------------------------------------------------------
    # Download folder
    # ------------------------------------------------------------------

    def _snapshot_downloads(self) -> set:
        """Return current set of filenames in ~/Downloads."""
        try:
            if self._downloads_dir.exists():
                return {p.name for p in self._downloads_dir.iterdir() if p.is_file()}
        except Exception:
            pass
        return set()

    def _check_downloads(self):
        """Compare current Downloads contents against the stored snapshot."""
        try:
            current = self._snapshot_downloads()
            new_files = current - self._downloads_snapshot
            for f in sorted(new_files):
                # Skip partial Chrome downloads and temp files
                if not f.endswith(('.crdownload', '.tmp', '.part')):
                    self._queue({
                        "type": "download",
                        "message": f"Download complete: {f}",
                    })
            self._downloads_snapshot = current
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Git context scan
    # ------------------------------------------------------------------

    def _get_session_commit_note(self, session_minutes: int) -> str:
        """
        Return a short note about commits made during this session.
        E.g. "3 commits landed. " or "" if nothing was committed or git unavailable.
        Uses the cached git repo path — works even after VS Code has closed.
        """
        if not self._last_git_context:
            return ""
        cwd = self._last_git_context.get("cwd", "")
        if not cwd or not os.path.exists(os.path.join(cwd, ".git")):
            return ""
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline',
                 f'--since={session_minutes} minutes ago'],
                cwd=cwd, capture_output=True, text=True, timeout=3,
            )
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            n = len(lines)
            if n == 0:
                return ""
            return f"{n} commit{'s' if n > 1 else ''} landed. "
        except Exception:
            return ""

    def _get_git_context(self) -> Optional[dict]:
        """
        Scan running Code.exe processes for one whose CWD contains a .git dir.
        Returns {project, branch, summary} or None if not found.
        """
        try:
            import psutil
            for proc in psutil.process_iter(['name', 'cwd']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if name not in self._VSCODE_NAMES:
                        continue
                    cwd = proc.info.get('cwd') or ''
                    if not cwd:
                        continue
                    git_dir = os.path.join(cwd, '.git')
                    if not os.path.exists(git_dir):
                        continue

                    # Found a git repo — get branch and status
                    branch = subprocess.run(
                        ['git', 'branch', '--show-current'],
                        cwd=cwd, capture_output=True, text=True, timeout=3
                    ).stdout.strip()

                    status_out = subprocess.run(
                        ['git', 'status', '--short'],
                        cwd=cwd, capture_output=True, text=True, timeout=3
                    ).stdout.strip()

                    n = len([l for l in status_out.splitlines() if l.strip()])
                    summary = (
                        f"{n} uncommitted change{'s' if n != 1 else ''}"
                        if n else "clean workspace"
                    )

                    return {
                        "project": os.path.basename(cwd),
                        "branch": branch or "main",
                        "summary": summary,
                        "cwd": cwd,
                    }
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _queue(self, suggestion: dict):
        """Put a suggestion on the queue (non-blocking)."""
        self.suggestions.put(suggestion)

    def _defer(self, suggestion: dict):
        """Hold a suggestion until the current focus session ends."""
        # Avoid duplicating the same suggestion type while held
        held_types = {s.get("type") for s in self._held_suggestions}
        if suggestion.get("type") not in held_types:
            self._held_suggestions.append(suggestion)

    def _save_session_state(self, session_minutes: float):
        """Persist last session context to disk for next-boot greeting."""
        try:
            from memory.session_state import save_session_state
            git = self._last_git_context or {}
            hour = datetime.now().hour
            state = {
                "timestamp": datetime.now().isoformat(),
                "git_project": git.get("project", ""),
                "git_branch": git.get("branch", ""),
                "git_cwd": git.get("cwd", ""),
                "uncommitted_count": self._parse_uncommitted(git.get("summary", "")),
                "commit_count": 0,   # filled by _get_session_commit_note separately
                "session_duration_minutes": round(session_minutes, 1),
                "build_failures": self._build_failure_count,
                "ended_late": hour >= 23 or hour < 4,
                "mode": self.state.mode,
            }
            # Count commits made this session
            cwd = git.get("cwd", "")
            if cwd and os.path.exists(os.path.join(cwd, ".git")):
                try:
                    import subprocess
                    result = subprocess.run(
                        ["git", "log", "--oneline", f"--since={int(session_minutes)} minutes ago"],
                        cwd=cwd, capture_output=True, text=True, timeout=3,
                    )
                    state["commit_count"] = len(
                        [l for l in result.stdout.splitlines() if l.strip()]
                    )
                except Exception:
                    pass
            save_session_state(state)
        except Exception:
            pass

    def _parse_uncommitted(self, summary: str) -> int:
        """Extract the number from a summary like '3 uncommitted changes'."""
        try:
            import re
            m = re.match(r"(\d+)", summary.strip())
            return int(m.group(1)) if m else 0
        except Exception:
            return 0

    def _can_suggest(self, key: str) -> bool:
        if key not in self._last_suggested:
            return True
        cooldown = self._COOLDOWNS.get(key, 600)
        elapsed = (datetime.now() - self._last_suggested[key]).total_seconds()
        return elapsed >= cooldown

    def _mark_suggested(self, key: str):
        self._last_suggested[key] = datetime.now()

    # ------------------------------------------------------------------
    # Public snapshot (for LLM injection)
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> dict:
        """Return a compact dict safe to inject into the LLM memory block."""
        snap = {
            "mode": self.state.mode,
            "stress_level": self.state.stress_level,
            "active_app": self.state.active_app,
            "focus_minutes": round(self.state.focus_minutes, 1),
        }
        if self._last_git_context:
            snap["git_project"] = self._last_git_context.get("project", "")
            snap["git_branch"] = self._last_git_context.get("branch", "")
        return snap
