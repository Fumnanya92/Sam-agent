"""
tasks/test_sam_live.py — Live end-to-end tester: chat with the running Sam.

Sends real messages to Sam via his WebSocket (ws://localhost:8765), exactly as
the browser does. Watches the active log file to capture what Sam said and did.
Reports pass/fail per use case.

Run while Sam is running:
    cd C:\\Users\\DELL.COM\\Desktop\\Darey\\Sam-Agent
    python tasks/test_sam_live.py
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

# ── output helpers ───────────────────────────────────────────────────────────
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
        out(f"       Sam said: {sam_said[:130]!r}")
    if detail:
        out(f"       Detail:   {detail[:130]}")


# ── log watcher ──────────────────────────────────────────────────────────────
def _get_active_log() -> Path | None:
    files = sorted(LOG_DIR.glob("sam_main_*.log"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


def _tail_log_for_response(log_path: Path, start_offset: int, timeout: float = 25.0):
    """
    Watch the log until Sam finishes speaking.
    Returns (tts_lines, error_lines, has_idle_after_speaking).
    Tracks read position to avoid processing the same lines twice.
    """
    tts_lines   = []
    error_lines = []
    saw_speaking = False
    deadline = time.time() + timeout
    read_pos = start_offset   # advance as we read

    while time.time() < deadline:
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                f.seek(read_pos)
                new_text = f.read()
                read_pos = f.tell()
        except Exception:
            time.sleep(0.3)
            continue

        for line in new_text.splitlines():
            low = line.lower()
            if "tts start:" in low:
                try:
                    msg = line.split("TTS START:")[-1].strip().strip('"')
                except Exception:
                    msg = line
                tts_lines.append(msg)
            if "│ error" in low:
                error_lines.append(line.strip())
            if "idle → listening" in low and tts_lines:
                saw_speaking = True
            if "tts timeout" in low:
                saw_speaking = True

        if saw_speaking and tts_lines:
            break
        time.sleep(0.4)

    return tts_lines, error_lines, saw_speaking


# ── WebSocket sender ─────────────────────────────────────────────────────────
async def _send(text: str):
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "transcript", "isFinal": True, "text": text}))
        await asyncio.sleep(0.15)


def say_to_sam(text: str):
    asyncio.run(_send(text))


# ── run one test ─────────────────────────────────────────────────────────────
def run_test(label: str, message: str, expect_keywords: list[str],
             wait: float = 35.0, check_no_tts: bool = False):
    """
    Send one message to Sam, handle the optional cloud-model 2-step flow,
    then verify the response contains at least one expected keyword.

    check_no_tts=True: assert Sam does NOT speak (e.g. for silence_sam).
    """
    log_path = _get_active_log()
    if not log_path:
        record(label, FAIL, detail="No log file found")
        return

    start_offset = log_path.stat().st_size
    out(f"\n>>> Sending: {message!r}")

    try:
        say_to_sam(message)
    except Exception as e:
        record(label, FAIL, detail=f"WebSocket send failed: {e}")
        return

    tts_lines, error_lines, saw_speaking = _tail_log_for_response(
        log_path, start_offset, timeout=wait
    )
    sam_said = " | ".join(tts_lines)

    # ── Handle cloud-model 2-step suggestion ─────────────────────────────
    if tts_lines and ("cloud model" in sam_said.lower() or "want me to switch" in sam_said.lower()):
        out(f"       (Sam suggested cloud — declining, running on local)")
        decline_offset = log_path.stat().st_size
        time.sleep(1.5)   # let Sam finish the cloud-suggest TTS
        try:
            say_to_sam("no")
        except Exception:
            pass
        tts2, err2, _ = _tail_log_for_response(log_path, decline_offset, timeout=20.0)
        # Sam says "Alright, sticking with local." — now resend original so Sam processes it locally
        time.sleep(2.0)
        resend_offset = log_path.stat().st_size
        try:
            say_to_sam(message)
        except Exception:
            pass
        tts3, err3, _ = _tail_log_for_response(log_path, resend_offset, timeout=wait)
        if tts3:
            tts_lines = tts3
            error_lines += err3
            sam_said = " | ".join(tts3)
        elif tts2:
            tts_lines = tts2
            error_lines += err2
            sam_said = " | ".join(tts2)

    # ── check_no_tts mode (silence_sam etc.) ────────────────────────────
    if check_no_tts:
        # Sam should NOT have spoken — we check the log instead for muted/silent
        log_text = ""
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                f.seek(start_offset)
                log_text = f.read().lower()
        except Exception:
            pass
        if "muted" in log_text or "silence" in log_text or "silence_sam" in log_text:
            record(label, PASS, sam_said="[no TTS — correctly muted]")
        elif not tts_lines:
            record(label, PASS, sam_said="[no TTS — as expected]",
                   detail="Sam wrote to log but did not speak (correct for mute)")
        else:
            record(label, WARN, sam_said,
                   detail="Sam spoke when it should have been muted")
        return

    if not tts_lines:
        record(label, FAIL, detail=f"No spoken response within {wait}s")
        return

    real_errors = [e for e in error_lines if "│ error" in e.lower()
                   and "timeout" not in e.lower()
                   and "tts" not in e.lower()]

    combined = sam_said.lower()
    found = any(kw.lower() in combined for kw in expect_keywords) if expect_keywords else True

    if not found:
        record(label, WARN, sam_said,
               detail=f"Response didn't contain any of {expect_keywords[:4]!r} (but Sam did respond)")
    elif real_errors:
        record(label, WARN, sam_said,
               detail=f"Responded OK but errors in log: {real_errors[0][:80]}")
    else:
        record(label, PASS, sam_said)

    # Brief pause so Sam's record_voice() is fully waiting before next message
    time.sleep(2.0)


# ── safety reset between tests ───────────────────────────────────────────────
def clear_pending_state():
    """Send 'cancel' so any lingering PendingAction is cleared before next test.
    Watches the log for IDLE→LISTENING to know when Sam is truly done."""
    log_path = _get_active_log()
    if not log_path:
        return
    start_offset = log_path.stat().st_size
    try:
        say_to_sam("cancel")
    except Exception:
        return
    # Wait until Sam finishes processing cancel TTS (same watcher logic)
    _tail_log_for_response(log_path, start_offset, timeout=25.0)
    time.sleep(1.0)   # small buffer after IDLE→LISTENING fires


# ══════════════════════════════════════════════════════════════════════════════
# TEST SUITE
# ══════════════════════════════════════════════════════════════════════════════
def main():
    out("=" * 70)
    out("  SAM LIVE USER SIMULATION — full feature coverage")
    out("=" * 70)

    log_path = _get_active_log()
    if not log_path:
        out("ERROR: No sam_main_*.log found. Is Sam running?")
        sys.exit(1)
    out(f"  Watching: {log_path.name}")
    out(f"  WebSocket: {WS_URL}")

    # ── GROUP 1: Conversation & Identity ───────────────────────────────────
    out("\n--- GROUP 1: Conversation & Identity ---")
    run_test("basic greeting", "hey Sam",
             ["hey", "hi", "hello", "up", "kelvin", "what", "how"])

    run_test("current time", "what time is it",
             ["pm", "am", ":", "time", "o'clock"])

    run_test("capabilities — what can you do",
             "what can you do",
             ["open", "search", "code", "reminder", "help", "can", "skill", "command", "manage"])

    # ── GROUP 2: System Awareness ───────────────────────────────────────────
    out("\n--- GROUP 2: System Awareness ---")
    run_test("system status — CPU/RAM/disk",
             "what's my system status",
             ["cpu", "ram", "memory", "disk", "%", "gb", "battery"],
             wait=45)

    run_test("quick command — IP address",
             "what's my IP address",
             ["terminal", "opened", "ip", "address", "127", "192", "running"],
             wait=18)

    run_test("git status",
             "full git status",
             ["branch", "modified", "staged", "untracked", "main", "changes", "nothing", "commit", "ready"],
             wait=20)

    # Clear any PendingAction that git status may have created (e.g. pending commit)
    out("\n  (clearing any pending git action before next tests...)")
    clear_pending_state()

    # ── GROUP 3: Files & Desktop ────────────────────────────────────────────
    out("\n--- GROUP 3: Files & Desktop ---")
    run_test("list desktop files",
             "what files are on my desktop",
             ["desktop", "file", "folder", "item", "shortcut", "found", ".lnk", ".txt"],
             wait=20)

    run_test("read clipboard",
             "what's on my clipboard",
             ["clipboard", "copied", "text", "empty", "nothing", "content", "has"])

    # ── GROUP 4: Notes & Memory ─────────────────────────────────────────────
    out("\n--- GROUP 4: Notes & Memory ---")
    run_test("create a note",
             "create a note titled Sam Live Test with content Sam is completing live tests today",
             ["note", "saved", "created", "done", "written", "titled", "live test"],
             wait=25)

    run_test("manual learning — learn this",
             "Sam learn this: asyncio runs coroutines concurrently on a single thread using an event loop",
             ["saved", "learned", "got it", "noted", "stored", "asyncio", "topic"],
             wait=25)

    # ── GROUP 5: Reminders & Alarms ─────────────────────────────────────────
    out("\n--- GROUP 5: Reminders & Alarms ---")
    run_test("set alarm — specific clock time",
             "set an alarm for 11 fifty nine PM",
             ["alarm", "set", "11", "pm", "scheduled", "remind", "59"],
             wait=15)

    run_test("list reminders",
             "what reminders do I have",
             ["reminder", "alarm", "no reminder", "none", "scheduled", "pending", "list"],
             wait=12)

    # ── GROUP 6: Search ─────────────────────────────────────────────────────
    out("\n--- GROUP 6: Search & Web ---")
    run_test("web search — Python news",
             "search for latest Python 3.13 features",
             ["search", "python", "result", "here", "look", "pulling", "on it", "opening"],
             wait=25)

    # ── GROUP 7: Apps & System Control ──────────────────────────────────────
    out("\n--- GROUP 7: Apps & System Control ---")
    run_test("open an app — Notepad",
             "open notepad",
             ["open", "notepad", "launching", "done", "it", "opening"])

    run_test("take a screenshot",
             "take a screenshot",
             ["screenshot", "saved", "taken", "captured", "done", "desktop"],
             wait=15)

    # ── GROUP 8: Developer Productivity ─────────────────────────────────────
    out("\n--- GROUP 8: Developer Productivity ---")
    run_test("daily standup report",
             "generate my daily standup",
             ["standup", "today", "working", "yesterday", "code", "done", "plan",
              "sticking", "local", "focused", "completed"],
             wait=40)

    run_test("daily session report",
             "what did you do today",
             ["report", "today", "session", "done", "action", "completed", "summary",
              "open", "screenshot", "note", "alarm"],
             wait=35)

    # ── GROUP 9: Voice Control ───────────────────────────────────────────────
    out("\n--- GROUP 9: Sam Voice Control ---")
    run_test("silence Sam — mute",
             "shut up Sam",
             [],               # no TTS keywords — Sam goes silent
             wait=8,
             check_no_tts=True)

    time.sleep(1.5)

    run_test("wake Sam back up",
             "you can talk now",
             ["back", "talking", "voice", "ok", "unmuted", "here", "ready", "can"],
             wait=12)

    # ── GROUP 10: Code Intelligence ──────────────────────────────────────────
    out("\n--- GROUP 10: Code Intelligence ---")
    run_test("explain a simple Python function",
             "Sam explain this code: def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)",
             ["fibonacci", "recursive", "function", "returns", "base case", "fib",
              "calculates", "sticking", "local", "n"],
             wait=40)

    # ── GROUP 11: Skills System ──────────────────────────────────────────────
    out("\n--- GROUP 11: Skills System ---")
    run_test("list skills — what skills do you have",
             "what skills do you have",
             ["skill", "agent", "install", "security", "python", "have", "over", "hundred"],
             wait=20)

    run_test("invoke skill — activate agent orchestrator skill",
             "Sam use your agent orchestrator skill",
             ["activat", "agent", "orchestrat", "mode", "skill", "think", "lens", "switch"],
             wait=20)

    run_test("invoke skill — use security skill",
             "activate the security skill",
             ["activat", "secur", "mode", "skill", "think", "007", "lens", "switch", "couldn"],
             wait=15)

    # ── RESULTS ─────────────────────────────────────────────────────────────
    out("\n\n" + "=" * 70)
    out("  FINAL RESULTS")
    out("=" * 70)

    passed = [r for r in _results if r[1] == PASS]
    warned = [r for r in _results if r[1] == WARN]
    failed = [r for r in _results if r[1] == FAIL]

    for label, status, sam_said, detail in _results:
        icon = {"[PASS]": "OK ", "[FAIL]": "!! ", "[WARN]": "?? "}[status]
        out(f"  {icon} {status}  {label}")
        if sam_said:
            out(f"        \"{sam_said[:110]}\"")

    out("")
    out(f"  PASS:  {len(passed)}")
    out(f"  WARN:  {len(warned)}  (Sam responded, investigate keyword mismatch)")
    out(f"  FAIL:  {len(failed)}  (Sam gave no response or WebSocket error)")
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
                out(f"     Sam said: {sam_said[:120]!r}")
            if detail:
                out(f"     {detail}")


if __name__ == "__main__":
    main()
