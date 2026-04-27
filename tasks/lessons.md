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

---

## 2026-03-14 — Sam Reimagining (10-phase)

### Always run tests/syntax checks before marking tasks complete
- **Mistake:** Marked the reimagining phases as done without running any verification. The user had to point this out.
- **Rule:** After every batch of file changes, run `python -c "import ast; ast.parse(open(f).read())"` on each modified file. Never write "complete" or check off a task without proof it parses/runs.

### Always update tasks/todo.md and tasks/lessons.md as part of finishing a task
- **Mistake:** Completed a 10-phase reimagining without writing either a todo list or capturing lessons. CLAUDE.md explicitly requires both.
- **Rule:** At task start → write todo.md plan with checkboxes. At task end → tick completed items, add review section. After any correction or non-trivial decision → append to lessons.md. Not optional.

### Edit tool requires a file Read first — subagent reads don't count
- **Pattern:** Three Edit calls failed with "File has not been read yet" because the files were read inside a subagent but the main context had no record of them.
- **Rule:** Before any `Edit`, confirm the file was read directly (not via subagent) in the current session. Read it yourself first if in doubt.

### Duplicate function definitions cause silent module errors
- **Pattern:** `total_skills()` was defined twice in `antigravity_bridge.py` — once above `_resolve()` and once after `_load_registry()`. Python accepts this syntactically but only the last definition wins. The first (wrong) location was the intended export.
- **Rule:** After adding a new function to a file, grep for its name to check for duplicates before finishing.

### Handler functions need temp_memory passed explicitly — closures don't capture it
- **Pattern:** `_handle_build_project`, `_handle_code_helper`, `_handle_agent_task` all received `temp_memory=None` in their signatures but were called from `handle_intent` without passing `temp_memory`. The auto-skill feature silently did nothing.
- **Fix:** Update both the call site (routing in `handle_intent`) AND the function signature simultaneously when adding a new parameter.
- **Rule:** When adding a parameter to a handler, grep for all call sites in the router and update them in the same edit.

### Skills pipeline requires two steps: activate (write to temp_memory) + prime (write to llm.py module state)
- **Pattern:** `auto_activate_for_task()` writes skill content to `temp_memory["active_skill_content"]`. But the LLM only picks it up if `prime_skill_context()` is also called to set the module-level `_pending_skill_content`. Calling only one step means skills are found but not injected.
- **Rule:** Skill activation is always two calls: `_auto_skill(desc, temp_memory)` followed by `prime_skill_context(content, name)`. Never one without the other.

### PendingAction expiry must be checked in get_pending(), not at set time
- **Pattern:** Setting expiry at creation time (`time.time() + 120`) is correct, but `get_pending()` must check `time.time() > pending.expires_at` and return None if expired. An unchecked pending action could execute stale commands minutes later.
- **Rule:** Always validate expiry in the getter, not just at storage time.

### TTS mute/meeting checks must use `force=True` sparingly
- **Pattern:** Most `edge_speak()` calls don't pass `force=True`. This is correct — they should respect mute/meeting mode. But critical startup messages or error alerts that the user must hear should pass `force=True`.
- **Rule:** Only pass `force=True` for genuinely critical system messages. All normal responses use default (force=False).

### Web Speech fragment buffering requires both browser-side AND server-side merge
- **Pattern:** Fixing only the browser (`pendingBuffer` + 1.2s timer) or only the server (1.5s merge loop) is insufficient alone. Browser-side delay handles the common case; server-side loop catches edge cases where the timer fires before all fragments arrive.
- **Rule:** For STT reliability, always maintain defence-in-depth: buffer at source, merge at server. Neither alone is sufficient.

### youtube-transcript-api uses instance-based API, not class method
- **Pattern:** Code written using `YouTubeTranscriptApi.get_transcript(video_id)` (class method) fails on the current version of `jdepoix/youtube-transcript-api`. The API changed to an instance-based model.
- **Fix:**
  ```python
  # WRONG (old, deprecated)
  transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
  transcript_text = " ".join(t["text"] for t in transcript_list)

  # CORRECT (current)
  fetched = YouTubeTranscriptApi().fetch(video_id)
  transcript_text = " ".join(s.text for s in fetched)
  ```
- **Rule:** When using a third-party API, always verify against the linked source (GitHub README) before writing the call. Snippet attributes are `.text`, `.start`, `.duration` (not dict keys).

### Syntax checks are not use-case tests — always run both
- **Pattern:** `python -m py_compile` only catches syntax errors. It says nothing about whether functions return correct values, modules actually import, or state flows correctly. Real bugs like wrong dict key names, missing packages, and incorrect API calls all pass syntax checks.
- **Rule:** After implementing any feature:
  1. Run `python -m py_compile` (syntax gate)
  2. Write and run a functional test that exercises the actual code path end-to-end
  3. Never mark done without both passing

### Log entry field names must match what consumers read
- **Pattern:** `session_logger.py` stored `"time": "HH:MM:SS"` — time only, no date. The `report_writer.py` consumes these entries and needs to know when things happened. Using an ambiguous `"time"` key (vs. `"timestamp"`) and dropping the date is a silent data quality bug.
- **Fix:** Changed to `"timestamp": "YYYY-MM-DD HH:MM:SS"` so downstream consumers have full context.
- **Rule:** When choosing field names for persisted data, use the most specific name (`timestamp` > `time`) and store the full datetime, not just the time component.

### New Python packages must be installed — code won't fail until runtime
- **Pattern:** `from youtube_transcript_api import YouTubeTranscriptApi` was written and syntax-checked successfully, but the package wasn't installed. No error until execution.
- **Rule:** After writing any `from X import Y` for a third-party package: (1) verify it's in `requirements.txt`, (2) confirm `pip show X` returns a version. If missing, install and add to REQUIREMENTS.txt.

---

## 2026-03-14 — Live Integration Tests

### agent_llm_call keyword args are system_prompt= and user_prompt= (NOT system= and user=)
- **Pattern:** `agent_llm_call(system="...", user="...")` was written in multiple places (`report_writer.py`, `handlers.py` `_handle_learn_from_youtube`). Python raises `TypeError: got an unexpected keyword argument 'system'` at runtime — passes syntax checks invisibly.
- **Fix:** The correct kwargs are `system_prompt=` and `user_prompt=`.
- **Rule:** Always write the full parameter name: `system_prompt=`, `user_prompt=`. Never abbreviate. Grep for `agent_llm_call(system=` before closing any PR.

### When renaming a field in a data producer, grep ALL consumers immediately
- **Pattern:** `session_logger.py` field renamed from `"time"` to `"timestamp"`. `report_writer.py` still used `e['time']` in three places. The KeyError was swallowed by a try/except, producing a silently wrong report.
- **Fix:** After renaming any JSON/dict field, run `grep -r 'e\["time"\]' .` across the codebase before finishing.
- **Rule:** Field rename = find-and-replace across all consumers in the same commit.

### Prompt intent rules must use CRITICAL prefix to override LLM ambiguity
- **Pattern:** Adding `"shut up Sam"` to the `silence_sam` trigger list produced no effect — the LLM still returned `chat`. Adding the same rule with `**CRITICAL —**` prefix and `ALWAYS intent: silence_sam. NEVER return chat for these phrases.` caused immediate compliance.
- **Rule:** For any intent that competes with `chat` (silence, cancel, confirm), add `CRITICAL —` and explicit `ALWAYS / NEVER` directives in `prompt.txt`. Without CRITICAL, ambiguous phrasing loses to chat.

### Live integration tests catch bugs that unit tests cannot
- **Pattern:** 14 passing unit tests did not catch: wrong kwargs in 2 files, wrong field name in report_writer, and a prompt rule too weak to override ambiguity. Live tests found all 4.
- **Rule:** Unit tests guard module contracts. Live tests guard integration contracts. Both required. Never mark a feature done without at least one live end-to-end call that exercises the real API/prompt.

### Mock UI for Sam handler tests needs a full stub — not a minimal stub
- **Pattern:** `_MockUI` was missing `write_log`, `start_speaking`, `add_agent_task`. This caused thread crashes in TTS and handler threads, masking real behavior.
- **Rule:** Standard Sam mock UI must include: `write_log`, `append_output`, `update_status`, `add_agent_task`, `update_agent_task`, `start_speaking`, `stop_speaking` — all as no-op stubs. Keep a reference mock class in `tasks/test_live.py` and reuse it.

---

## 2026-03-15 — Full-Feature Live Simulation (20/20 PASS)

### Sam's TTS is non-blocking — `SPEAKING → IDLE` fires BEFORE audio plays
- **Pattern:** `edge_speak()` streams audio to a buffer (fast, ~1s), sets state to IDLE, then a second thread plays the actual soundfile (can take 15–20s for long responses). Log shows `SPEAKING → IDLE` when streaming finishes — NOT when audio finishes. `clear_transcript_queue` fires when audio playback ends (2nd `sam_done`). Any message sent after `SPEAKING → IDLE` but before actual audio finishes gets queued, then dropped by `clear_transcript_queue`.
- **Rule:** In any log-tailing watcher that sends a follow-up message, always wait for `IDLE → LISTENING` (post-playback) — not `SPEAKING → IDLE` (post-streaming). These are different events ~15–25s apart.

### `saw_speaking` log watcher must guard against stale `IDLE → LISTENING` from prior cycles
- **Pattern:** When `_tail_log_for_response` starts with `start_offset`, a previous test's `IDLE → LISTENING` line may still be in the file just past `start_offset` (it was logged at end of previous test's audio). Without a guard, this stale event fires `saw_speaking = True` immediately, causing the watcher to return as soon as the current test's first `TTS START` appears — before current audio finishes. The next message is then sent while audio is still playing; `clear_transcript_queue` drops it.
- **Fix:** `if "idle → listening" in low and tts_lines:` — only accept `IDLE → LISTENING` after the current test's TTS has already started.
- **Rule:** When using log events as synchronization signals, always ensure the event you're waiting for belongs to the CURRENT cycle, not a prior one. Require at least one current-cycle event (e.g., `tts_lines`) before accepting the terminal event.

### `fmt.upper()` in strptime destroys AM/PM format codes
- **Pattern:** `datetime.strptime(value.upper(), fmt.upper())` — `.upper()` is used on both value and format to normalize case. The value `.upper()` is correct (`"11:59 pm"` → `"11:59 PM"`). But `fmt.upper()` changes `%p` → `%P`, and Python's strptime does not recognize `%P`. Raises `ValueError: 'P' is a bad directive`. All AM/PM alarms silently fail.
- **Fix:** Only `.upper()` the value: `datetime.strptime(value.strip().upper(), fmt)`. The format string contains directives — never mutate them.
- **Rule:** In `datetime.strptime(text, fmt)`: uppercase `text` for case-insensitive matching; NEVER uppercase `fmt`. Format strings contain `%x` directives that are case-sensitive by design.

### Hardcoded strings in action files bypass LLM prompt rules
- **Pattern:** `actions/web_search.py` had 5 `"Sir, ..."` return strings. These values are spoken directly via `edge_speak()` without going through the LLM. The `core/prompt.txt` "never say Sir" rule has zero effect on them.
- **Rule:** After adding a rule to `prompt.txt` (e.g., "never say X"), grep the entire `actions/` directory for that phrase. Any hardcoded string that returns directly (not via LLM) must be fixed manually.

### Fixed-time sleeps for "wait until Sam is done" break under load
- **Pattern:** `clear_pending_state()` used `time.sleep(6)` then `time.sleep(12)` to wait for cancel TTS to finish. The cancel response includes a full TTS cycle (~13s audio). Fixed sleeps are guesses. Under load (or with longer responses), they undershoot.
- **Fix:** Use `_tail_log_for_response(log_path, offset, timeout=25.0)` which watches the log for `IDLE → LISTENING` — the actual post-audio signal. Then add a 1s buffer.
- **Rule:** Never use `time.sleep(N)` to "wait for Sam to finish." Always watch the log for `IDLE → LISTENING`. `sleep()` is only acceptable as a short buffer (≤ 2s) after the log signal fires.

### Test timeouts must account for full TTS cycle, not LLM response time
- **Pattern:** Default `wait=22.0` was based on LLM response time (~8s Ollama). But `IDLE → LISTENING` fires after: LLM call + streaming + audio playback. A long response (capabilities: 16+ seconds audio) requires 28+ seconds total. With 22s timeout, the watcher exits before `IDLE → LISTENING` fires, and the next message overlaps.
- **Fix:** Default changed to `wait=35.0`. Tests with short expected responses can override with smaller values.
- **Rule:** `wait` timeout = LLM time + TTS streaming time + audio playback time + 5s buffer. For unknown responses, 35s is safe. For one-liners (greetings), 15s is fine.

### Cloud model decline discards the original request in main.py
- **Pattern:** When `COMPLEX_INTENT` first fires in local mode, `main.py` intercepts with "want me to switch?" and stores the intent in `_complex_intents_suggested`. When user says "no", a `continue` skips the original `user_text`. Sam says "Alright, sticking with local" but never processes the user's actual request.
- **Workaround in tests:** After detecting cloud-decline TTS, wait for it to finish, then resend the original message. Sam processes it locally (won't ask again since it's in `_complex_intents_suggested`).
- **Real fix (future):** In `main.py`, after decline confirmation, re-enqueue original `user_text` for local processing instead of `continue`.
- **Rule:** When testing cloud-decline flows, always resend the original. Don't assume Sam handles it automatically.

---

## 2026-03-15 — Phase Tests + Skills Live Tests (19/19 PASS)

### morning_briefing.py used os.getenv() instead of get_openai_key() from llm.py
- **Pattern:** `morning_briefing.py` loaded the API key with `api_key = os.getenv("OPENAI_API_KEY")`. If the key is stored only in `config/api_keys.json` (not in env), this returns None and the briefing falls back to "Good morning." silently. The live test confirmed 13-char fallback response.
- **Fix:** `from llm import get_openai_key; api_key = get_openai_key()` — this checks both env var AND api_keys.json.
- **Rule:** Any module that needs the OpenAI key must call `from llm import get_openai_key` — do NOT scatter `os.getenv("OPENAI_API_KEY")` calls. Single source of truth.

### auto_activate_for_task failed for natural-language inputs — search is substring-based
- **Pattern:** `search_skills(task_description)` uses `q in skill["slug"].lower()` where `q` is the ENTIRE task string (e.g. "help me design a secure API"). No skill slug contains that full sentence, so results is empty and `auto_activate_for_task` returns None. The per-word scoring below was dead code.
- **Fix:** Added fallback in `auto_activate_for_task`: if `search_skills(full_desc)` returns nothing, iterate words in the description (skip stop-words, len < 3), call `search_skills(word)` for each, stop at first hit. This lets "help me design a **secure api** with authentication" find `api`-related skills.
- **Rule:** When feeding user intent phrases into keyword search functions, always provide a per-word fallback. User language is natural; skill slugs are short identifiers. They rarely share a long common substring.

### PresenceEngine meeting detection test requires mocking both window_tracker AND pattern_learner
- **Pattern:** Calling `engine._update_state()` directly in tests without mocking fails because: (1) `get_foreground_window_info()` makes a Win32 API call that returns actual foreground window (not zoom), (2) `_pattern_learner.record_app()` does file I/O to `memory/`.
- **Fix:** `engine._pattern_learner = MagicMock()` + `patch("system.window_tracker.get_foreground_window_info", return_value=fake_window)` before calling `_update_state()`.
- **Rule:** When unit-testing presence engine state transitions, mock the two external I/O surfaces: window tracker and pattern learner.

### AgentMonitor is a singleton — subscribers from earlier tests accumulate
- **Pattern:** `AgentMonitor()` returns the same instance every time (singleton `__new__`). Subscribing `_on_update` in a test permanently adds it to `_callbacks`. If multiple tests subscribe, every task notification fires ALL subscribers from all tests. Counts can exceed expected values.
- **Rule:** In tests that subscribe to AgentMonitor, track `len(received)` >= expected (not ==). Or unsubscribe after each test if the class supports it.

### edge_speak meeting mode test needs to patch system.notifier.notify at module level
- **Pattern:** `edge_speak` does `from system.notifier import notify` inside the hot path. This lazy import gets the current `system.notifier.notify` attribute at call time. Patching `system.notifier.notify` before the call works because Python's `from X import Y` fetches `Y` from the module object at execution time.
- **Rule:** To intercept a lazily-imported function inside another function, patch at `module.function_name` (e.g. `patch("system.notifier.notify")`). The patch must be active BEFORE the call that triggers the lazy import.

---

## 2026-03-15 — Chaos Session Post-Mortem

### Processing guard silently swallows guided-task abort
- **Pattern:** `_handle_guided_step_turn._action()` checked `params.get("processing")` BEFORE the abort ("stop"/"cancel") check. While a vision verify or autonomous click was mid-flight and `processing=True`, saying "stop" spawned a new thread that exited immediately — no response, no cleanup.
- **Fix:** Move the abort check to the TOP of `_action()`, before the processing guard. Abort must always win regardless of thread state.
- **Rule:** In any multi-turn handler that has both a processing guard AND abort handling, the abort check MUST come before the guard. Safety exits cannot be blocked by concurrency locks.

### Cloud-decline discards original request (confirmed bug — fix applied)
- **Pattern:** When user declines cloud switch ("no"), main.py set `_cloud_confirm_user_text = None` then `continue`. The original request was dropped. User had to repeat themselves.
- **Fix:** Set `_replay_user_text = _cloud_confirm_user_text` before clearing, so the request is replayed on local tier.
- **Rule:** When decline-gating any model switch, always re-enqueue the original user_text on the local path. Never discard it.

### COMPLEX_INTENTS was over-aggressive — Ollama handles most of them
- **Pattern:** `morning_briefing`, `daily_plan`, `standup`, `commit_writer` were all pushing users to OpenAI. Ollama handles these easily. User noticed Sam was always going to cloud.
- **Fix:** Removed all intents that don't genuinely require cloud-tier reasoning. Kept only: `code_explainer`, text transforms (`summarise`, `rephrase`, `expand`, `bullet`, `formal`, `casual`), `debug_screen`, `vscode_mode`.
- **Rule:** COMPLEX_INTENTS = intents that provably fail or degrade on 7B–13B models. Everything else stays local. Review this list before adding any new intent.

### fill_form with CSS selectors always fails — LLM doesn't know the DOM
- **Pattern:** `browser_control` `fill_form` action expects `fields: {CSS_selector: value}`. The LLM has no way to know CSS selectors for an arbitrary webpage it hasn't seen. It guesses `#name`, `input[name='email']`, etc. — all fail silently on real sites.
- **Fix (Clawd-inspired):** Added `fill_form_auto` — reads `page.accessibility.snapshot()` first, walks the tree for all textbox/combobox nodes, then matches each requested field description against actual accessible names (exact → substring → smart_type fallback). Uses `get_by_role(name=...)` which is the most reliable Playwright locator. Also added `scan_form` action to list all fields before filling.
- **Rule:** Form fill hierarchy: `fill_form_auto` (accessibility tree) > `fill_form_smart` (heuristic) > `fill_form` (CSS only). LLM prompt always uses `fill_form_auto`. CSS selectors are only for programmatic/known-DOM use.

### Guided mode was passive — "let me know when done" traps user in waiting loop
- **Pattern:** After every step advance, Sam said "Let me know when that's done." User had to provide a keyword. This felt rigid and un-assistant-like. The user wants Sam to offer to DO the step, not just coach.
- **Fix:** Changed step announcement to: "Say 'do it' and I'll handle it, or do it yourself and say done." This makes autonomous takeover the first offered option.
- **Rule:** Guided/co-pilot mode must always surface the autonomous path first. The user should feel like Sam is ready to act — not waiting to be told it happened.

### TTS loop trapped the user — STT never re-activated
- **Pattern:** When Sam was stuck in a vision-verify loop calling `_say()` repeatedly, each TTS call sent `sam_speaking` to the browser, suppressing the mic. `set_active` was only broadcast after each TTS _finished_. With rapid re-queued speech, the mic never got a window to open. User could not speak.
- **Root cause:** The abort check bug (above) prevented "stop" from breaking the loop.
- **Lesson:** The TTS-loop-traps-mic problem disappears when abort handling is correct. They are the same root cause.
- **Rule:** When debugging "Sam can't hear me", check if a multi-turn handler is looping with speech calls. The mic only activates between TTS cycles. Fix the handler loop first.

---

## 2026-03-15 — SAM CO-PILOT (guide_task feature)

### Multi-turn bypass pattern: pending_intent + continue in main.py
- **Pattern:** The correct way to own the next voice turn without going through the LLM is to set `temp_memory.set_pending_intent("my_intent")` in a handler, then add `if temp_memory.pending_intent == "my_intent": ... ; continue` in `main.py` above `long_term_memory = load_memory()`. This skips the LLM entirely for continuation turns.
- **Rule:** Always place the bypass check AFTER `create_note` and BEFORE `long_term_memory = load_memory()`. The same `continue` pattern as `create_note` applies. Do NOT call `temp_memory.reset()` before delegating to the handler — the handler needs to read parameters first.

### agent_llm_call cannot use require_json=True AND need_vision=True simultaneously
- **Pattern:** When `need_vision=True` or `image_b64` is provided, `agent_llm_call` in `llm_bridge.py` forces `require_json=False` before the OpenAI call. Any structured response must be engineered via prompt engineering (force a prefix like `CONFIRMED:` / `NOT YET:`) and parsed with string matching.
- **Rule:** For vision verification returns, use a forced-prefix prompt (`"Start your response with exactly 'CONFIRMED:' or 'NOT YET:'"`) then parse with `str.startswith()`. Keep a keyword heuristic fallback. Never use `require_json=True` with vision calls.

### Steps JSON must be stored as a serialized string in temp_memory.parameters
- **Pattern:** `temp_memory.update_parameters()` skips values that are `None` or `""`. Python lists ARE stored correctly (they're not None/""), BUT re-reading a list via `get_parameters()["steps"]` returns the Python list — which is correct. However, updating a single key (e.g. `"current_step"`) merges into the dict, and `update_parameters` skip-filter doesn't affect non-None/non-"" values like `0` or `1`. Any integer step count works.
- **Rule:** When storing state across guided turns, test integer `0` explicitly — it is NOT `None` or `""` so it persists correctly in `update_parameters`.

### Hybrid click mode via explicit user request is simpler than proactive offering
- **Pattern:** The original idea was to have Sam proactively spot the element and offer "want me to click it?" But this would require PendingAction + temporarily clearing pending_intent + restoring it — complex state juggling. The simpler pattern: detect "click it" / "you do it" phrases inside the guided turn handler and execute `screen_click` directly. No extra state needed.
- **Rule:** When adding automation to a guidance flow, prefer explicit user commands ("click it for me") over proactive AI offers. It's simpler to implement and gives the user full control over when automation fires.

---

## 2026-03-15 — GUIDED TASK LIVE SESSION (post-chaos fixes)

### Never force verification on the user — trust first
- **Pattern (BAD):** Sam called OpenAI vision verify on EVERY "done" utterance, looping "Let me check your screen." even when the user had clearly completed the step. This was hostile UX.
- **Rule:** In guided/co-pilot flows, TRUST the user when they say done/ok/yeah/finished. Vision verify is OPTIONAL and only triggered when user explicitly asks ("can you check", "verify"). The power dynamic is: user leads, Sam assists.

### "stop" in interrupt_commands silently eats guide session cancellation
- **Pattern:** `interrupt_commands = ["mute", "quit", "exit", "stop"]` in main.py runs BEFORE the guided_task bypass. When user says "stop" mid-session, Sam silently reset temp_memory without speaking the cancellation message.
- **Fix:** Added a guided-abort check block BEFORE the interrupt_commands check: if `pending_intent == "guided_task"` AND the word is an abort word, route to `_handle_guided_step_turn` first. The handler speaks "Guided session stopped." then returns, interrupt block is never reached.
- **Rule:** Any multi-turn bypass intent must have its abort words checked BEFORE main.py's global interrupt handlers. Otherwise the global handler silently swallows them.

### Race condition: rapid user speech fires parallel guided_task threads
- **Pattern:** While one `_handle_guided_step_turn` thread was running a vision check (10s), the user spoke again. The state went IDLE→LISTENING, the new turn bypassed to guided_task and spawned a second thread. Both threads read/write temp_memory simultaneously.
- **Fix:** Add `processing` flag to temp_memory.parameters. At thread start: if `params.get("processing"): return`. Set True on entry, False in `finally:`.
- **Rule:** ALL guided/multi-turn handlers that use temp_memory state AND may take >2s MUST have a processing guard to prevent parallel threads.

### Vision check spam ("Let me check your screen" repeated) is disabling
- **Pattern:** Every user turn in guided mode triggered the screen check path → OpenAI vision call → "Let me check your screen" announcement → "That step doesn't look complete yet" → restart loop.
- **Root cause:** Logic defaulted to vision verify unless abort/click phrases were detected. User had no way to just say "done" and move on.
- **Fix:** Invert logic. Default = trust. Vision = explicit request only.
- **Rule:** Co-pilot/guided flows must default to trusting user signals. Vision AI is expensive (money + latency + OpenAI dependency). Reserve it for explicit verification requests.

### OpenAI usage in guided mode was unavoidable for vision — but now unnecessary
- **Pattern:** User complained Sam was always using OpenAI. The reason: every "done" triggered vision verify which requires OpenAI. Ollama cannot do vision.
- **Fix:** Trust-first approach means vision is no longer called on every turn. Ollama handles all text-only steps. OpenAI only used if user explicitly says "can you check".
- **Rule:** Design features to minimize cloud API calls. Vision is a premium feature — gate it behind explicit user request.

### Log disappears when Sam is closed (max_files=5 too aggressive)
- **Pattern:** Sam creates 3 new log files per session (main/components/errors). With max_files=5, restarting Sam twice could wipe the previous session's logs.
- **Fix:** Increased to max_files=25 which gives ~8 sessions of history.
- **Rule:** For a personal AI agent, log retention should be generous (25+). Disk space is cheap, debugging sessions is hard.


