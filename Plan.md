 Here is Claude's plan:                                                                           ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Sam → JARVIS: The Agency Plan
                            
 Context
                                                
 You've built a sophisticated voice assistant, but you're frustrated for three connected reasons:

 1. Half-finished work piles up — fixes don't hit 100%, and you can't tell what's working from
 what isn't.
 2. Duplicate work — you've re-implemented the same capability multiple times because Sam didn't
 surface that it already existed (or didn't actually run it when asked).
 3. Sam doesn't act like JARVIS — it waits for commands, can't find your projects on its own,
 can't reuse browser sessions, fails at WhatsApp 95% of the time, and "knows" about skills it
 never uses.

 After deep recon I confirmed the structural gap: Sam's prompt advertises ~156 intents but only
 ~73 are wired. The most agentic pieces you've built (the agents/ multi-agent orchestrator,
 Antigravity skills framework, Authority engine, Personality learner, FastAPI daemon, dashboard)
 are scaffolded but never called from the main loop.

 This plan does three things in order:
 - Phase 0: Single source of truth for "what Sam can do." Visible in the UI. Deletes dead code.
 Stops the duplicate-implementation cycle.
 - Phases 1-3: Turn Sam from a reactive command bot into an autonomous partner — JARVIS-shaped.

 You said yes to all three phases (with Tool Forge approval-gated by default), dedicated Sam
 browser profile, and explicitly: tracking everything in the UI, no dead code in the repo.

 ---
 Phase 0 — Capability Registry & Cleanup (3-4 days) — NEW PRIORITY

 The hidden problem: every time you ask Sam to do something, you don't know if it's already
 implemented, broken, or missing. Same for me as your collaborator. We need ONE list, in code,
 surfaced in the UI, that is the source of truth. After this phase, "I forgot I built that" never
  happens again.

 0A. The Capability Registry (1.5 days)

 - New file: core/capabilities.py — declarative registry. Every action becomes:
 Capability(
     name="whatsapp_summary",
     handler="actions.whatsapp.summarize",
     description="Summarise recent WhatsApp messages",
     triggers=["summarise whatsapp", "what's new on whatsapp"],
     status="broken",            # working | broken | wip | planned
     last_verified="2026-04-12",
     test="tests/capabilities/test_whatsapp_summary.py",
     dependencies=["chrome_profile", "whatsapp_web_session"],
 )
 - One Python module = one source of truth. The handler dispatcher in intents/handlers.py becomes
  a 10-line loop that reads the registry, instead of 700 elif branches.
 - core/prompt.txt is generated FROM this registry, not hand-edited. No more drift between what
 the LLM is told and what Sam can actually do.

 0B. Capability Dashboard panel (1 day)

 - Files: daemon/api_routes.py add /api/capabilities (list + per-capability status +
 run-test-now); React dashboard adds a "Capabilities" tab.
 - Filter by status (working / broken / wip / planned). Click a capability → shows last-verified
 timestamp, test result history, and a "Run test now" button that triggers the test via the
 existing background queue and streams output.
 - This is the list you wanted: visible, sortable, actionable. When you say "Sam, what can you
 do?" Sam can also speak from it.

 0C. Dead code reaper (1 day)

 - Pass over the working tree:
   - Every actions/*.py not referenced by a Capability → delete or convert.
   - The git-deleted backup files (backup/mic.html, backup/test_*.py, etc., visible in git
 status) → finalize the deletes in one commit.
   - The duplicate orchestration: agent/ (old) vs agents/ (new). Pick one — agents/ is the better
  foundation. Migrate any unique logic from agent/ and delete it.
   - tasks/probe_ollama*.py, tasks/find_app.py, tasks/run_flutter_test.py, tasks/test_*.py →
 either promote to capabilities (with tests) or delete.
 - CI gate (tests/test_no_orphans.py): fails if a Python module under actions/ or agents/ isn't
 referenced by either a Capability, an __init__, or another live module. Stops the rot at PR
 time.

 0D. Skill registry + visible activation (½ day)

 - The Antigravity skills framework already auto-activates skills based on task description, but
 Sam doesn't tell you when it does, and you can't see what's loaded.
 - Surface in the UI: a "Skills" panel that lists every skill present, the last task that
 activated it, and lets you toggle skills on/off.
 - In the prompt, replace the static skill list with a runtime-injected one from the registry, so
  Sam genuinely knows what skills it has right now.

 0E. WhatsApp surgery — your specific pain point (1 day)

 You called WhatsApp out: 95% failure rate, even reading is poor. Three concrete root causes from
  the recon:
 1. Browser launches fresh → WhatsApp Web isn't authenticated → fails silently.
 2. WhatsApp DOM selectors drift; current code has hardcoded selectors.
 3. No retry/recovery loop on the read flow.

 Fixes (folded into Phase 1B + 0E):
 - Once the dedicated Sam Chrome profile lands (Phase 1), do a one-time WhatsApp Web QR scan into
  Sam's profile. Persistent. Solves auth.
 - Replace hardcoded selectors in actions/whatsapp*.py with the same fill_form_auto
 accessibility-tree approach browser_control.py already uses. WhatsApp Web is mostly
 accessible-named.
 - Add a Capability test that reads the latest message from a known test contact every morning.
 If it fails, capability status flips to broken automatically and you see it in the UI before you
  ask.

 End of Phase 0 — what changes for you: open the dashboard. See exactly 1 list of every Sam
 capability with red/green status. No duplicate work. No dead modules. WhatsApp either works or
 is visibly red and we know why.

 ---
 Phase 1 — "See the Machine" (4-5 days)

 Goal: Sam can find anything on your laptop without being told where, and uses your real browser
 sessions.

 1A. Project Index (2 days)

 - New file: system/project_index.py
 - Startup + every 30 min: scan C:\Users\DELL.COM\Desktop\ and C:\Users\DELL.COM\Documents\ for
 project signatures (package.json, pubspec.yaml, pyproject.toml, *.sln, Cargo.toml, go.mod,
 .git/).
 - For each: name (from manifest), stack, languages, git remote, last-modified, README first
 paragraph.
 - Persist to memory/project_index.json with content hashes for incremental rescans.
 - Helper find_project(name_or_alias) with fuzzy match — "guest attendance app" matches
 "GuestAttendanceApp", "guest-attendance", etc.
 - Wire into every intent that takes a project (open_app, code_helper, dev_agent,
 test_flutter_app) so Sam stops asking "where is it?"
 - Capability: registered in registry as project_search.

 1B. Persistent Sam browser profile (1 day)

 - actions/browser_control.py line ~185: replace new_context() with
 launch_persistent_context(user_data_dir=%LOCALAPPDATA%\Sam\BrowserProfile).
 - One-time bootstrap script scripts/bootstrap_sam_browser.py: launches the profile interactively
  so you can sign into Gmail, GitHub, Supabase, X, LinkedIn, WhatsApp Web ONCE.
 - After that, every Sam browser action runs as a logged-in human.
 - Removes the credential-vault problem entirely — sessions live in the OS-protected browser
 profile.

 1C. Wire the orphaned multi-agent system (½ day)

 - agents/orchestrator.py + 9 role YAMLs are built but intents/handlers.py still routes
 agent_task to old agent/executor.py.
 - Reroute _handle_agent_task() → agents/orchestrator.py. Old agent/ deletion handled in Phase
 0C.

 1D. Skill auto-activation EVERYWHERE (½ day)

 - Today auto_activate_for_task() only fires inside _handle_agent_task. Move to the top of
 handle_intent() so every task gets relevant skills injected.
 - Log each activation to the UI Skills panel from 0D so you SEE which skill Sam reached for.

 1E. Briefings: scripted → evolving (1 day)

 - assistant/morning_briefing.py: replace template with LLM-driven dump of (yesterday's session
 log + calendar + project_index status + emotional_state + 3 web facts) → "Write Sam's brief,
 natural, max 4 sentences."
 - Same engine reused for end-of-day reflection and post-meeting recaps.

 End of Phase 1 — what changes: "Sam, open the Guest Attendance app" works first try. "Sam, post
 on LinkedIn we're hiring" opens already-logged-in LinkedIn. WhatsApp messages work because the
 session is real. Skills visibly fire. Morning brief feels like a person, not a script.

 ---
 Phase 2 — "Real Agency in Code & Browser" (8-10 days)

 Goal: Sam can debug a real bug end-to-end; Sam tests apps before declaring done.

 2A. Code Surgeon — real debug loop (4-5 days)

 Replace the naive "write → run → did-it-crash → retry" in actions/code_helper.py and
 actions/dev_agent.py.

 - New module: agents/code_surgeon.py
 - For "the submit button isn't working":
   a. Locate — project_index.find_project("guest app")
   b. Comprehend — read README, manifest, infer stack
   c. Reproduce — start dev server (command from manifest), launch persistent browser, navigate,
 click, capture network + console
   d. Diagnose — pass error + relevant code (LLM-selected via filename heuristics + grep) to LLM
 with diagnose prompt
   e. Patch — generate diff, surface in UI: "say apply"
   f. Verify — re-run reproduction; check the original failure mode is gone (not just that
 nothing crashed)
   g. Report — voice + dashboard summary of root cause + fix
 - New action actions/db_inspector.py: thin wrapper to query Supabase (.env from project, REST or
  postgrest). Lets Sam do "query the DB" cleanly.
 - Registered as Capability: debug_app.

 2B. Test Runner — pre-handoff testing (2-3 days)

 - New module: agents/test_runner.py
 - Per-stack default recipe: Flutter → flutter test + critical UI flow; Node/Next → npm test +
 Playwright on top 3 routes; Python → pytest.
 - Generate Playwright tests from project route map + fill_form_auto.
 - Block "done" until tests pass OR you say "ship it anyway." Result visible in Capabilities
 panel.

 - every page in Sam ui should explain what that page is for and a how to use
 

 2C. Browser as Sam's hands (2 days)

 With persistent profile from 1B, build high-level verbs in actions/browser_control.py:
 - post_to(platform, content, attachments=[]) — knows DOM/URL for X, LinkedIn, Facebook, Reddit,
 IG.
 - summarize_inbox(provider="gmail") — opens Gmail, scans top N unread.
 - do_in(site, instruction) — generic "navigate, follow English instruction using accessibility
 tree."
 - Each registered as a Capability with a green/red test.

 ---
 Phase 3 — "True Autonomy" (10-14 days)

 Goal: Sam works in the background, notices things on its own, extends itself when a tool is
 missing.

 3A. Background Task Queue (3-4 days)

 - New module: system/task_queue.py
 - Async worker pool; ai_loop submits long-running jobs (debug a project, run a suite, scrape).
 - Tasks visible in the existing AgentMonitor dashboard panel — you watch Sam work in real time.
 - Voice: "I'm working on it" → user moves on → Sam reports back via TTS or notification
 (respects meeting mode).

 3B. Event Bus & Watchers (3-4 days)

 - New module: system/event_bus.py + system/watchers/{file,calendar,git,system}.py
 - Subscribers:
   - File changes in indexed projects (per-project: auto-rerun tests on save? configurable)
   - Calendar 10 min before meeting → mute Sam, open meeting link
   - System errors (Windows event log: app crashes you should know about)
   - GitHub PR comments / CI failures (optional local tunnel)
 - Each event → bus → reasoner decides whether to act.

 3C. Proactive Reasoner — Sam's inner voice (2-3 days)

 Today presence_engine emits hardcoded suggestions. Replace.
 - New module: agents/proactive_reasoner.py
 - Every 5 min: dump (presence + recent events + project_index + session log + goals) to LLM.
 Prompt: "Anything Sam should mention or do? Reply null or {action, reason}."
 - Non-null → through Authority engine → speak (or pending-action gate if it changes state).
 - Cheap: Ollama, no cloud.

 3D. Tool Forge — Sam writes its own actions (4-5 days)

 Approval-gated, default off per your call.

 - New module: agents/tool_forge.py
 - When LLM emits an intent with no matching Capability:
   a. Recognize gap (registry miss).
   b. LLM drafts new actions/<intent>.py following Capability template + a generated test.
   c. Run the test. Pass → present diff in UI: "I built a new tool — say apply to load it."
   d. On approval: register Capability, hot-reload (importlib.reload), re-run original intent.
 - Self-healing variant: when one of Sam's modules throws, same flow — diagnose, patch, present,
 apply.
 - Gated by config/forge.json: { "enabled": false, "auto_apply": false }. You flip on when you
 trust it.
 - This directly addresses your "I don't like manually adding intents" — Sam owns intent
 creation, you own approval.

 ---
 Critical Files

 Modified:
 - core/prompt.txt — auto-generated from core/capabilities.py
 - intents/handlers.py — collapsed from elif chain into registry-driven dispatcher
 - actions/browser_control.py — persistent profile + new high-level verbs
 - actions/whatsapp*.py — accessibility-tree selectors + use Sam profile
 - actions/code_helper.py, actions/dev_agent.py — superseded by code_surgeon
 - assistant/morning_briefing.py — LLM-driven, not scripted
 - system/presence_engine.py — emits to event_bus
 - main.py — start project_index, event_bus, task_queue, proactive_reasoner
 - daemon/api_routes.py — /api/capabilities, /api/skills endpoints
 - React dashboard — Capabilities panel + Skills panel + live AgentMonitor expansion

 New:
 - core/capabilities.py (the registry)
 - system/project_index.py
 - system/task_queue.py
 - system/event_bus.py + system/watchers/*.py
 - agents/code_surgeon.py
 - agents/test_runner.py
 - agents/tool_forge.py
 - agents/proactive_reasoner.py
 - actions/db_inspector.py
 - tests/test_capability_registry.py (parity check)
 - tests/test_no_orphans.py (dead code gate)
 - scripts/bootstrap_sam_browser.py
 - config/forge.json, config/triggers.json

 Reused (don't rebuild):
 - agents/orchestrator.py, agents/role_loader.py — wire into intent loop
 - skills/antigravity_bridge.py — call earlier + surface in UI
 - daemon/api_routes.py Authority + Personality systems — route through them
 - system/session_logger.py, system/report_writer.py — feed proactive_reasoner

 Deleted (Phase 0):
 - agent/ (old orchestration), once unique logic is migrated to agents/
 - All tasks/probe_*.py, tasks/find_app.py, tasks/test_*.py not promoted to Capabilities
 - Backup/* deletes finalized
 - Any actions/*.py not referenced by a Capability

 ---
 Verification Plan

 For each phase, end-to-end voice + dashboard test. Status visible in Capabilities panel
 throughout.

 Phase 0:
 - Open dashboard → Capabilities tab loads → ~80 capabilities listed with green/red/yellow.
 - Click "Run all tests" → background queue runs them; statuses update live.
 - pytest tests/test_capability_registry.py tests/test_no_orphans.py → both pass.
 - WhatsApp summary works on a real chat — capability flips green.
 - git status is clean (no orphan files).

 Phase 1:
 - "Sam, open the Guest Attendance app" → opens, no clarifying question.
 - "Sam, post on LinkedIn we're hiring" → posts via already-logged-in browser.
 - "Sam, what skills do you have right now?" → reads from Skills panel state.
 - Morning brief sounds different two days in a row (LLM-generated).

 Phase 2:
 - "Sam, the submit button on the Guest app isn't working" → Sam locates, reproduces, diagnoses,
 applies fix, verifies, reports. You don't touch the keyboard.
 - "Sam, ship the leads dashboard" → runs test recipe, blocks on red, only declares done when
 green.

 Phase 3:
 - Edit file in a watched project → auto-tests run in background → green = silent, red = Sam
 tells you.
 - Don't talk to Sam for 30 min while context-switching → reasoner notices, surfaces a useful
 nudge.
 - Ask Sam something with no matching Capability → Sam drafts the action, runs the test, presents
  the diff. You approve. Capability lights up green. Sam uses it on the next turn.

 ---
 Order of Operations

 1. Phase 0 (this is the ground we don't lose anymore)
 2. Phase 1
 3. Phase 2
 4. Phase 3 in order: 3A → 3B → 3C → 3D

 Each phase ends with the Capabilities dashboard fully green for that phase's deliverables. We
 don't move to the next phase with red flags from the previous.
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Claude has written up a plan and is ready to execute. Would you like to proceed?

 ❯ 1. Yes, auto-accept edits
   2. Yes, manually approve edits
   3. No, refine with Ultraplan on Claude Code on the web
   4. Tell Claude what to change
      shift+tab to approve with this feedback

 ctrl-g to edit in Notepad · ~\.claude\plans\first-and-first-i-rippling-lemon.md
