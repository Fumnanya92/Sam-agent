# Orb-Window UX & File-Tracking Fixes — 2026-05-01

## Goal
Make the orb (Tk) window cleaner and stop Sam from losing track of files he writes / dumping code into the chat.

## Tasks
- [x] Fix orb "weird eye" — soften core gradient, replace off-centre glint with centred sheen
- [x] Fix chat input + chat log layout (place → pack so chat grows + input pinned to bottom)
- [x] Clamp window initial size to screen (no more overflow on small displays)
- [x] Add recent-files registry in `actions/file_controller.py` (`_register_written`, `get_last_written_file`, `list_recent_written`)
- [x] Have `create_file` / `write_file` log absolute path AND include it in the success string
- [x] New dispatcher actions: `recent_files`, `last_file` so LLM can query the registry
- [x] Persist generated code to `~/.sam/scripts/` instead of tempfile-and-delete
- [x] Add `run_script(path)` and `run_last_script(extension="py")` helpers in executor
- [x] Tighten codegen system prompt — never paste code in chat, runtime saves+runs and reports the path
- [x] Update `tasks/lessons.md`
- [ ] User-side smoke test (run Sam, see new orb + new layout, ask it to write+run code, then ask it again to "run the script you just wrote")

## Files Touched
- `ui.py` — three surgical edits (window sizing, left-panel layout, orb core drawing)
- `actions/file_controller.py` — new registry + path in messages + two new actions
- `agent/executor.py` — `_run_generated_code` rewritten to persist+register, new `run_script` / `run_last_script`, codegen prompt updated
- `tasks/lessons.md` — four new entries

## Verification
- File contents verified via Read tool after each Edit.
- Bash-side syntax checker shows a stale 29 KB cached snapshot (file mod-time 2026-04-28) — this is a known divergence between bash mounts and the file tools described in the system prompt. The actual files on disk reflect the edits.
- Recommended: user runs `python -m py_compile ui.py actions/file_controller.py agent/executor.py` locally before trusting.

## Not Done (deferred / discussion needed)
- Office page (team/org) audit — out of scope for this pass per user clarification.
- React UI orb / chat overlap — user clarified the issue is the Tk orb window, not the React UI.
- Other Tinker ideas (compact mode, snap-to-edge, mini-terminal, plan tab, voice meter, search) — awaiting selection.

## Tinker Ideas — implemented after main fixes
- [x] **Live FILES panel** in the right side of the orb window (between AGENTS and OUTPUT). Pulls from the `_RECENT_FILES` registry every 1.5s. Each row shows file name + truncated path + timestamp, with **▶ Run** (for `.py` only), **📁 Open in file manager**, and **📋 Copy path** buttons. Output of "Run" streams into the existing OUTPUT panel.

### Files Touched (this addendum)
- `ui.py` — added `sys` import; new FILES section in `_build_right_panel`; new methods `_refresh_files_panel`, `_build_file_row`, `_run_file`, `_open_file_location`, `_copy_path`.

---

# Strip-Down Phase — 2026-05-01

Audit completed via 4 parallel subagents (read-only). Full proposal in [`tasks/strip_down_plan.md`](strip_down_plan.md).

## Audit results (summary)
- **Phase 0 (regression I owe)**: `_RECENT_FILES` is in-process only — explains the tic-tac-toe forgetting symptom.
- **Phase 1 (briefings)**: 5 background producers; #1 boot greeting (`main.py:321-392`) doesn't check conversation state; #3 presence engine VS Code greeting (`system/presence_engine.py:354-404`) overlaps it.
- **Phase 2 (routing)**: "empty recycle bin" → "open_explorer" because the named-intent list in `core/prompt.txt` has no recycle-bin rule and `llm.py:get_ai_response` lacks an unknown-intent → `agent_task` fallback.
- **Phase 3 (duplicates)**: 10 candidate groups identified; A (file ops), E (briefings), J (comms/notifier no-cut) are low risk; F/G/H/I need deeper inspection. `agent/` vs `agents/` should NOT be auto-deleted (refactor audit was wrong on this — `agent/executor.py` owns the generic-code fallback we need).
- **Phase 4 (other persistence)**: pending actions, mode/mute, temp memory, generated-script registry all lose state on restart.

## Approved + Implemented (branch `strip-down-2026-05-01`)
- [x] **Phase 0** — disk-back `_RECENT_FILES` to `~/.sam/recent_files.json` (`actions/file_controller.py`)
- [x] **Phase 1 #1** — boot greeting (`main.py:321-392`) now checks conversation state, mute, and mode before speaking
- [x] **Phase 1 #3** — presence engine `vscode_open` (`system/presence_engine.py:354-404`) suppresses on first-of-session to avoid double-briefing
- [x] **Phase 2** — broadened `agent_task` rule in `core/prompt.txt` with CRITICAL system-task and default-fallback rules; added unknown-intent → `agent_task` fallback in `intents/handlers.py` (only fires for action-like requests)
- [x] **Phase 3a Group A** — file_ops content moved into `actions/file_controller.py`; `actions/file_ops.py` is now a deprecation shim (40 lines re-exporting from file_controller, with `find_files_quick` aliased to `find_files` for compatibility)
- [x] **Phase 3a Group E** — unused `from assistant.daily_planner import generate_daily_plan` removed from `main.py:46`; `assistant/daily_planner.py` is now a 27-line shim that delegates `generate_daily_plan` to `generate_morning_briefing` (one canonical briefing producer)
- [x] **Phase 3a Group J** — confirmed `comms/manager.py` and `system/notifier.py` stay separate (different scopes: external channels vs OS toasts). No code change.

## Pending approval (next sessions)
- [ ] **Phase 4** — disk-back the rest: `conversation_state._pending` (`conversation_state.py:34`), mute/mode (`conversation_state.py:35-36`), `temporary_memory.last_code_file` and `last_search` (`memory/temporary_memory.py:18-42`), and on-startup glob of `~/.sam/scripts/` to register pre-existing scripts in the recent-files registry
- [ ] **Phase 3 batch two** — Group B (`cmd_control` + `terminal` merge), Group C (`whatsapp_controller` + `whatsapp_assistant` merge), Group D (`reply_drafter` + `whatsapp_reply_engine` merge)
- [ ] **Phase 3 deep-inspect** — Group F (`browser_control` + `chrome_controller` — different libs), Group G (`agent/task_queue` + `system/task_queue` — verify scopes), Group H (`agent/monitor` + `goals/tracker`), Group I (`agent/` vs `agents/` — keep both, document split clearly)
- [ ] **Migration** — update the 4 `from actions.file_ops import ...` sites in `intents/handlers.py` and 1 in `tests/test_new_features.py` to import from `actions.file_controller` directly, then delete `actions/file_ops.py` shim
- [ ] **Migration** — once nothing imports `assistant.daily_planner`, delete the shim too

## Files Touched This Pass
- `actions/file_controller.py` — disk-backed registry; moved-in note/log/find/open functions from file_ops
- `actions/file_ops.py` — replaced with deprecation re-export shim
- `main.py` — boot greeting gated on conversation state; removed unused daily_planner import
- `system/presence_engine.py` — first-of-session vscode_open suppression
- `core/prompt.txt` — two CRITICAL rules added for agent_task fallback
- `intents/handlers.py` — unknown-intent → agent_task fallback before chat default
- `assistant/daily_planner.py` — replaced with deprecation shim that delegates to morning_briefing
- `tasks/lessons.md` — five new lessons from this pass
- `tasks/strip_down_plan.md` — full audit + plan (created earlier this session)

## Review

### Fix 1: Orb "weird eye" — `ui.py` `_draw_orb`
- Replaced the dark→bright two-colour gradient (which read as iris/pupil) with a single blended mid-tone that fades gently at the edges using `(ratio ** 1.6) * 0.35` for soft falloff.
- Replaced the off-centre top-left specular highlight (eye glint) with a small centred top sheen at max alpha 28 — keeps the 3D feel without the staring-eye effect.

### Fix 2: Chat layout — `ui.py` `_build_left_panel`
- Switched from `place(rely=...)` to `pack(side="bottom"|"top")`. Input is packed first at bottom (`fill="x"`), then chat log packed at bottom with `fill="both", expand=True` so it always grows. Orb canvas / state label / transcription packed above in their own top container.
- Result: input is always pinned to the bottom and the chat log fills all remaining vertical space — no more "stuck" feeling, all conversation visible.

### Fix 3: Window size — `ui.py` `__init__`
- Replaced the hard-coded `1200x780` with screen-aware clamping: `target_w = min(1200, max(820, sw - 120))`, `target_h = min(780, max(580, sh - 140))`, then centred. Falls back to `1200x780` if the screen-info call fails.

### Fix 4: File-tracking — `actions/file_controller.py`
- Added module-level `_RECENT_FILES` (capped at 20). `_register_written(path, action)` deduplicates by absolute path and inserts at the front. Added `get_last_written_file(extension=None)` and `list_recent_written(limit=10)`.
- `create_file` and `write_file` now call `_register_written` on success and include `at {target.resolve()}` in their return strings — so the LLM sees the absolute path and can refer to it later.
- Dispatcher recognises two new actions: `recent_files` (lists last N writes with timestamps) and `last_file` (returns the most recent, optionally filtered by extension).

### Fix 5: Proactive run + persisted scripts — `agent/executor.py`
- `_run_generated_code` no longer uses `tempfile.NamedTemporaryFile(delete=False) → os.unlink`. Instead `_save_generated_script(code, description)` writes to `~/.sam/scripts/sam_<slug>_<timestamp>.py` and registers it with the file-controller registry.
- New top-level helpers `run_script(path)` and `run_last_script(extension="py")` so the LLM (and any future skill) can re-execute a saved script by absolute path or by "the last one".
- `_CODEGEN_SYSTEM` prompt now explicitly says: standalone runnable script with `__main__`, must `print` results, and must NEVER paste code into the chat — the runtime will save & run and surface the path.
