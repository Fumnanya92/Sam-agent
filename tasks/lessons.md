# Sam-Agent Lessons

## 2026-03-06

### Speech recognition fragments mid-sentence at number/punctuation boundaries
- **Pattern:** Browser Web Speech API fires two `isFinal` events for one utterance when it hits a number (e.g. "Set an alarm for one." + "17."). The second fragment becomes a separate conversation turn.
- **Fix:** In `websocket_server.py` `get_transcription()`, after consuming the first transcript, peek the queue for 800ms. If a short continuation (≤4 words) arrives, strip trailing punctuation and merge.

### Echo detection fails when speech recognizer transcribes TTS output slightly differently
- **Pattern:** Sam says "1:17 PM", mic captures "117" — exact substring check fails, echo slips through and triggers another LLM call.
- **Fix:** Use `difflib.SequenceMatcher` ratio alongside the exact check. Ratio > 0.75 on transcripts longer than 20 chars flags it as an echo. Guard with `len > 20` to avoid false positives on short commands.

### Reminder engine only supports relative time, not absolute clock times
- **Pattern:** "Set alarm for 1:17" interpreted as "set alarm for 1 hour" because `ReminderEngine.add()` only accepted `minutes/hours` offsets.
- **Fix:** Add `fire_at: datetime | None = None` parameter to `add()`. When provided, use it directly (roll to tomorrow if past). Update `_handle_set_reminder` to parse `fire_at` string from LLM params using `datetime.strptime` with multiple format fallbacks. Update `prompt.txt` to instruct LLM to extract `fire_at` for specific clock times.

### LLM intent detection misses natural dictation phrases
- **Pattern:** User says "open notes and write" → LLM routes to `open_app` instead of `start_dictation` because the trigger list was too narrow.
- **Fix:** Extend `start_dictation` trigger phrases in `prompt.txt` to include write/type/dictate variants. Deliberately exclude bare "open notes" (no modifier) to avoid `open_app` ambiguity.

### Always add `encoding='utf-8'` when opening files on Windows
- **Pattern:** Python system default encoding on Windows is `cp1252`. Files with emoji or non-ASCII characters (logs, prompt files) cause `UnicodeDecodeError` when opened without explicit encoding.
- **Rule:** Always pass `encoding='utf-8'` in any `open()` call.

---

## 2026-03-09

### Flutter tester runs in isolated thread — ai_loop has zero awareness of it
- **Pattern:** `_handle_skill` starts the tester in a daemon thread. The `ai_loop` calls the LLM for every voice input with NO knowledge that a background task is running. The LLM responds to "why is it on a loop?" as if the loop is inside the app, not in Sam's own code.
- **Fix:** Add a module-level `_test_state` dict in `flutter_tester.py`. Set `running=True` before the test and `False` in finally. In `ai_loop`, inject `flutter_test_running` into `memory_for_prompt` when the flag is set. Add a `FLUTTER TEST AWARENESS` section to `core/prompt.txt` so the LLM understands to acknowledge the running test and direct user to say "stop the test".

### Flutter tester can never be stopped by voice — no cancellation path
- **Pattern:** The agent loop in `_run_agent()` runs to 25 steps with no way for the user to interrupt it via voice. Saying "stop" only resets the sam conversation state, not the browser test.
- **Fix:** Add a `threading.Event()` cancel_event to `_test_state`. Check it at the top of every agent loop iteration. Add `cancel_test()` export function. Add `stop_test` intent in `prompt.txt`, `handlers.py`, and the intents list.

### Flutter tester loops endlessly when task is generic — LLM re-tests same flow
- **Pattern:** User says "test the estate app" with no specific flow. The LLM found "Generate Visitor Pass" and tested it. On step completion it returned to the main screen and saw the same button again — so it re-tested the same flow at steps 6, 11, 16, 20... The 25-step dedup guard never triggered because the full command cycle was different each time.
- **Fix 1 (LLM instruction):** Add "CRITICAL — DO NOT REPEAT FLOWS" to `_build_system_prompt()`: once a flow is completed, move to a different feature or set done:true.
- **Fix 2 (clarification gate):** If the user provides no `task` parameter, `_run()` now asks "What do you want me to test?" before starting. Generic task = ask first.

### Flutter tester silently picks first valid port when multiple apps are running
- **Pattern:** 7 DartVM ports were found. The code iterated and picked the first valid Flutter URL (49218) without asking. User had no chance to confirm or pick the right one.
- **Fix:** Add `_find_all_flutter_urls()`. In `_run()`, if >1 valid URL is found and no explicit port was given, return a clarification message listing all ports and asking which to test.

### Flutter tester has no deterministic assertions — relies entirely on LLM visual judgment
- **Pattern:** After login submits, Sam says "looks like we're on the dashboard" — but this is pure LLM interpretation. If the dashboard loads with wrong data or the screen title differs, Sam misses the failure.
- **Fix:** Add `"assert"` field to the LLM JSON response schema. LLM outputs a short string (1-3 words) that MUST appear in the snapshot after the action (e.g. `"assert": "dashboard"` after login submit). `_run_agent()` does a case-insensitive substring check on the post-action snapshot and logs `[ASSERT] PASS/FAIL` with context. Assertion failure is added to `errors_seen` and fed back into LLM history.

### Flutter tester has no session isolation — re-running auth flows finds app already logged in
- **Pattern:** User says "test the login flow" twice. First run logs in successfully. Second run starts with a logged-in session — the LLM doesn't know the app is already authenticated and tries to navigate to login, gets confused by the dashboard.
- **Fix:** Detect auth-related tasks (login, logout, signup, register) in `_run()`. Set `reset_session=True`. In `_run_agent()` before the step loop, call `_clear_session()` which evals `localStorage.clear() + sessionStorage.clear() + cookie wipe` via playwright-cli, then does a `goto` to reload the app from a clean state.

### Flutter tester does not know which screen it is on before starting
- **Pattern:** After a previous test (e.g. login), the app is on the dashboard. A new test starts, the LLM takes a snapshot at step 1 and tries to navigate — but it doesn't know it's on the dashboard, not the login screen. Navigation actions are wrong from step 1.
- **Fix:** After browser is ready, call `_detect_screen_state()` — takes a snapshot + screenshot and asks GPT-4o to describe the current screen in 1-2 sentences. Inject this as the very first history message so the LLM starts with full awareness: "Current screen: authenticated dashboard. Task: test login flow. Navigate to logout first, then test login."

### Flutter tester uses blanket sleep(2.5) between every interactive command
- **Pattern:** `time.sleep(2.5)` waits regardless of whether Flutter has re-rendered. Fast interactions waste time unnecessarily; slow render operations (network calls) may still not be ready at 2.5s.
- **Fix:** Replace with `_wait_for_render(cli, snap)` which polls the accessibility tree every 0.5s until the snapshot changes from the pre-command snapshot, or 5s max. Fast steps return early; slow steps get the full window.

### Flutter tester has no stuck detection — same screen cycling is uncaught
- **Pattern:** The dedup guard only catches the exact same command 3× in a row. A cycling pattern (click A → fill B → click C → back → repeat) is not caught. The test runs to 25 steps.
- **Fix:** Track `snap_counts[md5(snap[:2000])]` inside the agent loop. If the same screen hash appears 4+ times, stop and report stuck with the last action to the user.

