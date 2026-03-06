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
