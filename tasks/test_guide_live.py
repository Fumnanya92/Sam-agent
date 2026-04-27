"""
tasks/test_guide_live.py — Live test for guide_task (co-pilot mode).

Connects to the running Sam via WebSocket and simulates a full guided session:
  1. Trigger co-pilot mode
  2. Sam plans + speaks step 1
  3. User says "done" → Sam verifies screen → speaks step 2
  4. User says "stop" → Sam cancels cleanly

Run while Sam is running:
    cd C:\\Users\\DELL.COM\\Desktop\\Darey\\Sam-Agent
    python tasks/test_guide_live.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WS_URL  = "ws://localhost:8765"
LOG_DIR = ROOT / "log"

# ── output helpers ─────────────────────────────────────────────────────────────
def out(text: str):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

_results = []

def record(label, status, sam_said="", detail=""):
    _results.append((label, status, sam_said, detail))
    icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[WARN]": "?? "}[status]
    out(f"\n  {icon} {status}  {label}")
    if sam_said:
        out(f"       Sam said: {sam_said[:160]!r}")
    if detail:
        out(f"       Detail:   {detail[:160]}")


# ── log helpers ────────────────────────────────────────────────────────────────
def _get_active_log() -> Path | None:
    files = sorted(LOG_DIR.glob("sam_main_*.log"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


_TRANSIENT_PHRASES = [
    "let me check your screen",
    "let me plan this out",
    "on it",
    "one moment",
]


def _is_transient(lines: list[str]) -> bool:
    """True if the only TTS so far is a short acknowledgment that precedes async work."""
    if len(lines) != 1:
        return False
    low = lines[0].lower()
    return any(p in low for p in _TRANSIENT_PHRASES)


def _tail_log(log_path: Path, start_offset: int, timeout: float = 40.0):
    """
    Watch the log until Sam finishes speaking.
    If the first TTS is a transient acknowledgment (e.g. 'Let me check your screen'),
    keep waiting for the substantive follow-up message before returning.
    Returns (tts_lines, error_lines, saw_idle).
    """
    tts_lines   = []
    error_lines = []
    idle_count  = 0
    deadline    = time.time() + timeout
    read_pos    = start_offset

    while time.time() < deadline:
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                f.seek(read_pos)
                chunk = f.read()
                read_pos = f.tell()
        except Exception:
            time.sleep(0.3)
            continue

        for line in chunk.splitlines():
            low = line.lower()
            if "tts start:" in low:
                try:
                    msg = line.split("TTS START:")[-1].strip().strip('"')
                except Exception:
                    msg = line
                tts_lines.append(msg)
                out(f"  [LOG] Sam speaks: {msg[:120]!r}")
            if "│ error" in low:
                error_lines.append(line.strip())
            if "idle → listening" in low and tts_lines:
                idle_count += 1

        # If we have an IDLE and the last TTS was NOT transient, we're done
        if idle_count >= 1 and not _is_transient(tts_lines):
            break
        # If we have 2+ IDLEs (transient + final), also stop
        if idle_count >= 2:
            break
        time.sleep(0.4)

    return tts_lines, error_lines, idle_count >= 1


# ── WebSocket sender ───────────────────────────────────────────────────────────
async def _send(text: str):
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "transcript", "isFinal": True, "text": text}))
        await asyncio.sleep(0.15)


def say(text: str):
    asyncio.run(_send(text))


# ── single step runner ─────────────────────────────────────────────────────────
def send_and_watch(label: str, message: str, expect_keywords: list[str],
                   wait: float = 45.0):
    log_path = _get_active_log()
    if not log_path:
        record(label, FAIL, detail="No log file found")
        return ""

    offset = log_path.stat().st_size
    out(f"\n>>> Sending: {message!r}")

    try:
        say(message)
    except Exception as e:
        record(label, FAIL, detail=f"WebSocket error: {e}")
        return ""

    tts_lines, errors, _ = _tail_log(log_path, offset, timeout=wait)
    sam_said = " | ".join(tts_lines)

    if not tts_lines:
        record(label, FAIL, detail=f"No spoken response within {wait}s")
        return ""

    combined = sam_said.lower()
    found = any(kw.lower() in combined for kw in expect_keywords) if expect_keywords else True

    real_errors = [e for e in errors if "│ error" in e.lower()
                   and "timeout" not in e.lower() and "tts" not in e.lower()]

    if not found:
        record(label, WARN, sam_said,
               detail=f"Missing keywords {expect_keywords[:3]!r} — Sam did respond")
    elif real_errors:
        record(label, WARN, sam_said,
               detail=f"Responded OK but errors: {real_errors[0][:80]}")
    else:
        record(label, PASS, sam_said)

    time.sleep(2.0)
    return sam_said


# ══════════════════════════════════════════════════════════════════════════════
def main():
    out("=" * 70)
    out("  GUIDE_TASK LIVE TEST — co-pilot feature end-to-end")
    out("=" * 70)

    log_path = _get_active_log()
    if not log_path:
        out("ERROR: No sam_main_*.log found. Is Sam running?")
        sys.exit(1)
    out(f"  Watching: {log_path.name}")
    out(f"  WebSocket: {WS_URL}\n")

    # ── STEP 1: Trigger co-pilot mode ─────────────────────────────────────────
    out("--- TEST 1: Trigger guide_task co-pilot mode ---")
    step1 = send_and_watch(
        "trigger co-pilot mode",
        "Sam guide me through creating a Google Form for my guests",
        # Sam should speak a step plan
        ["step", "1", "form", "google", "plan", "guide", "browser", "open",
         "chrome", "click", "navigate", "first"],
        wait=50,
    )

    if not step1:
        out("\nERROR: Sam did not respond to guide_task trigger. Aborting live test.")
        _print_results()
        sys.exit(1)

    out("\n  (Sam spoke the first step — waiting 3s before sending 'done'...)")
    time.sleep(3.0)

    # ── STEP 2: User says "done" → Sam verifies screen ────────────────────────
    out("\n--- TEST 2: User says 'done' — Sam verifies screen, speaks next step ---")
    step2 = send_and_watch(
        "say done → screen verify → step 2",
        "done",
        # Sam should check screen then either confirm + give step 2, or ask to retry
        ["step", "confirmed", "2", "check", "screen", "looking", "see", "not yet",
         "now", "next", "verified", "complete", "go ahead", "looks like", "yet"],
        wait=50,
    )

    if step2:
        out("\n  (Sam verified step + spoke step 2 — waiting 3s before sending 'stop'...)")
        time.sleep(3.0)
    else:
        out("\n  (Step 2 response missing — still sending stop to test abort...)")
        time.sleep(2.0)

    # ── STEP 3: User says "stop" → Sam cancels ────────────────────────────────
    out("\n--- TEST 3: User says 'stop' — Sam cancels guided session ---")
    send_and_watch(
        "say stop → session cancelled",
        "stop",
        ["cancel", "stop", "cancelled", "back", "normal", "session", "end",
         "ended", "exit", "stopping", "guide", "okay"],
        wait=20,
    )

    # ── STEP 4: Normal chat — confirm Sam is back to normal mode ─────────────
    out("\n--- TEST 4: Confirm Sam is back to normal (no guided_task state) ---")
    send_and_watch(
        "back to normal after cancel",
        "what time is it",
        ["pm", "am", ":", "time", "o'clock", "it's"],
        wait=20,
    )

    # ── RESULTS ───────────────────────────────────────────────────────────────
    _print_results()


def _print_results():
    out("\n\n" + "=" * 70)
    out("  GUIDE_TASK LIVE TEST — FINAL RESULTS")
    out("=" * 70)

    passed = [r for r in _results if r[1] == PASS]
    warned = [r for r in _results if r[1] == WARN]
    failed = [r for r in _results if r[1] == FAIL]

    for label, status, sam_said, detail in _results:
        icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[WARN]": "?? "}[status]
        out(f"  {icon} {status}  {label}")
        if sam_said:
            out(f"        \"{sam_said[:130]}\"")

    out("")
    out(f"  PASS:  {len(passed)}")
    out(f"  WARN:  {len(warned)}")
    out(f"  FAIL:  {len(failed)}")
    out(f"  TOTAL: {len(_results)}")
    out("=" * 70)

    if failed:
        out("\nFAILED:")
        for label, _, _, detail in failed:
            out(f"  !! {label}: {detail}")

    if warned:
        out("\nWARNINGS:")
        for label, _, sam_said, detail in warned:
            out(f"  ?? {label}")
            if sam_said:
                out(f"     Sam said: {sam_said[:130]!r}")
            if detail:
                out(f"     {detail}")


if __name__ == "__main__":
    main()
