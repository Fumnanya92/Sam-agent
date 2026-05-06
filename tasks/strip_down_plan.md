# Sam-Agent Strip-Down Plan — 2026-05-01

## Diagnosis (from 4 parallel read-only audits)

Sam is suffering from four overlapping problems that compound each other:

1. **Memory loss across restarts** — Sam forgets recent file paths because the registry lives in process memory only. This is the direct cause of "I asked you to run the html tic-tac-toe game" → "where is it saved?" after a restart. (Including a regression I introduced earlier today — see Phase 0.)
2. **Wrong tool gets picked when no perfect match exists** — "empty my recycle bin" → "Done: open_explorer" because the LLM is forced to choose from a fixed intent list with no fallback to "just write Python and run it". Adding more named actions makes this worse, not better.
3. **Multiple briefings stacking on boot** — startup greeting + presence-engine VS Code greeting + proactive reasoner all fire near-simultaneously, with the startup greeting NOT checking if you're already talking. Hence "briefings cutting into each other."
4. **Real duplicate features** — at least 10 pairs of files that overlap in purpose (file_controller vs file_ops, cmd_control vs terminal, whatsapp_controller vs whatsapp_assistant, morning_briefing vs daily_planner, browser_control vs chrome_controller, etc.).

---

## Phase 0 — Self-flagged regression (mine to fix)

The `_RECENT_FILES` list I added to `actions/file_controller.py` earlier today is module-level and not disk-backed. Every restart wipes it. This single bug is the technical reason Sam "literally just created" a file but couldn't find it later.

**Fix (≤ 25 lines):**
- On import, attempt to read `~/.sam/recent_files.json` and seed `_RECENT_FILES`. If file missing or corrupt, start empty (silent).
- After every `_register_written` call, write the current list back to that JSON file (best-effort, no crash on permission errors).
- Cap at 20 entries (already enforced).

**Affected:** `actions/file_controller.py` only. Touches the Phase-0 symptom directly.

---

## Phase 1 — Briefings: kill the overlap

**Concrete sources** (from audit):
| # | File:line | Cadence | Speaks? | Conversation gate? | Status |
|---|---|---|---|---|---|
| 1 | `main.py:321-392` startup greeting | once at boot | YES | **NO** | the loud one |
| 2 | `main.py:474-488` 7 AM brief | daily 7 AM | queued | YES | OK |
| 3 | `system/presence_engine.py:354-404` VS Code "back in project" | every VS Code open | queued | YES | overlaps #1 |
| 4 | `agents/proactive_reasoner.py:57-66` | every 5 min | queued | YES | weak dedup |
| 5 | `actions/reminders.py:35-40` | as scheduled | queued | YES | OK |

**Fixes:**
- **#1 (`main.py:321-392`)** — gate the startup greeting on conversation state. If the user is already talking when boot finishes, log it but don't speak it.
- **#1 vs #3** — these say almost the same thing on VS Code open. Pick one. Recommend: keep the boot greeting, drop the presence_engine "back in project" line on VS Code open (or fold its git-context into the boot greeting once and never repeat for that session).
- **#4 (proactive reasoner)** — change initial sleep from 60 s to ~120 s so it doesn't cut in while user is still replying to the boot greeting. Also persist `_last_suggestion_ts` to disk so cooldown survives restart.

---

## Phase 2 — Routing: stop forcing the LLM into wrong intents

**Trace of the recycle-bin bug (audit-provided):**
- `main.py:655` user input → `llm.py:187 get_llm_output` → builds prompt from `core/prompt.txt` → `intents/handlers.py:96-124 _DISPATCH_TABLE`.
- The system prompt lists a closed set of intents. None match "empty recycle bin." LLM picks the closest by inference → `open_app` with `app_name="explorer"`.
- The generic-code fallback (`agent/executor.py:103 _run_generated_code`, edited earlier today) is reachable ONLY if the planner returns an unknown tool inside an `agent_task` plan. The primary LLM dispatch path (`llm.py:get_ai_response`) has **no** "unknown intent → write code and run" fallback.

**Fixes (Kelvin's "I don't want to code every task" requirement):**
- **`core/prompt.txt`** — broaden the `agent_task` trigger to explicitly catch system-cleanup / "do this thing on my computer" type requests where no specific named intent fits. Add one or two examples ("empty recycle bin", "free up disk space", "kill all chrome processes") so the LLM learns the shape.
- **`llm.py:get_ai_response` (~lines 300-320)** — when the parsed intent is not in `_RECOGNIZED_INTENTS`, route to `agent_task` with the original user text as `goal`, instead of falling back to a chat reply. That gives the planner+`_run_generated_code` path a chance to actually run.
- **Reduce intent surface area** — the audit found the named-intent list is one of the reasons the LLM gets confused. Cuts in Phase 3 directly help here.

---

## Phase 3 — Duplicate features: the cuts

Ranked by safety + clarity. Phase-3 only proceeds with explicit batched approval.

| # | Group | Files | Recommendation | Risk |
|---|---|---|---|---|
| A | File ops dup | `actions/file_controller.py` ⊕ `actions/file_ops.py` | KEEP `file_controller`; merge note categorization into it; DELETE `file_ops` | Low — file_ops is thinner |
| B | Command dup | `actions/cmd_control.py` ⊕ `actions/terminal.py` | MERGE into one with `approval_required` flag | Medium — terminal has approval flow that must survive |
| C | WhatsApp dup | `automation/whatsapp_controller.py` ⊕ `automation/whatsapp_assistant.py` | KEEP `whatsapp_assistant`; DELETE controller after migrating its `_speak()` and PendingAction state | Medium |
| D | WhatsApp reply dup | `automation/reply_drafter.py` ⊕ `automation/whatsapp_reply_engine.py` | MERGE into `whatsapp_reply_engine`, absorb pyperclip flow | Medium |
| E | Briefing dup | `assistant/morning_briefing.py` ⊕ `assistant/daily_planner.py` | MERGE into one `daily_briefing` (folds Phase 1 cleanups too) | Low |
| F | Browser dup | `actions/browser_control.py` ⊕ `automation/chrome_controller.py` | KEEP `browser_control` (Playwright, standard); leave `chrome_controller` ONLY if WhatsApp DOM still needs it; otherwise delete | High — WhatsApp may depend on it |
| G | Task queue dup | `agent/task_queue.py` ⊕ `system/task_queue.py` | NEEDS VERIFICATION — may have different scopes | Medium |
| H | Monitor vs tracker | `agent/monitor.py` ⊕ `goals/tracker.py` | NEEDS VERIFICATION — likely different scopes (UI updates vs OKR persistence) | Medium |
| I | `agent/` vs `agents/` | `agent/executor.py` etc. ⊕ `agents/orchestrator.py` etc. | DO NOT auto-delete. Likely intentional split: `agent/` = primary executor, `agents/` = sub-agent hierarchy. The audit recommendation to delete `agent/executor.py` is wrong — it owns `_run_generated_code` which Phase 2 needs. Treat as documentation gap, not duplication. | Critical risk if removed |
| J | Comms/notifier | `comms/manager.py` ⊕ `system/notifier.py` | KEEP both. Different scopes (comms = external channels, notifier = OS toasts). | Low — no cut |

**Approval grain:** I recommend approving A, E, and the comms/notifier "no cut" decision in batch one (low risk). Then B, C, D as batch two (medium risk — needs careful migration). F/G/H/I require deeper inspection per cut, not blanket approval.

---

## Phase 4 — Other persistence gaps (after Phase 0)

These were caught by the memory audit and should be addressed once Phase 0 lands so the pattern is consistent:

- `conversation_state._pending` (`conversation_state.py:34`) — pending action lost across restart. Persist to `~/.sam/pending_action.json` with 120 s expiry. Fixes "Do you want to proceed?" survival.
- `conversation_state` mode/mute (`conversation_state.py:35-36`) — extend existing `memory/session_state.json` to hold mute and mode.
- `temporary_memory.last_code_file` and `last_search` (`memory/temporary_memory.py:18-42`) — persist to `memory/memory.json` under a `temp` key so "run my last script" / "what did I last search for" survive a restart even outside the new disk-backed registry.
- Generated scripts at `~/.sam/scripts/` — already on disk; the only gap is the registry not knowing about them post-restart. Phase 0 fixes this for new writes; for existing scripts, an on-startup glob+register would catch any pre-existing files.

---

## Suggested Execution Order

1. **Phase 0** (10–25 lines, my regression) — gates real value of every other phase.
2. **Phase 1 #1 (gate boot greeting)** — single-line condition, immediate UX win.
3. **Phase 2 (routing fallback)** — unlocks "Sam figures it out" behavior.
4. **Phase 3 batch one (A, E, comms/notifier no-cut)** — low risk, biggest dedup gains.
5. **Phase 1 #3 (presence engine merge)** — depends on #1.
6. **Phase 4 (other persistence gaps)** — pattern reuse from Phase 0.
7. **Phase 3 batch two (B, C, D)** — only after batch one is verified clean.
8. **Phase 3 deep-inspect F, G, H, I** — needs per-cut investigation.
