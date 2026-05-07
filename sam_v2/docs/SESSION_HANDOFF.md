# Sam v2 Session Handoff

## Repo

- Path: `C:\Users\DELL.COM\Desktop\Darey\Sam-Agent`
- Branch: `rebuild/sam-clean-v2`

## Scope Rule

- Work only in `sam_v2/`
- Old root `main.py` and old Sam files are reference only
- The active product surface is `python -m sam_v2`

## Current Sam v2 State

Sam v2 is now runnable and has a real native shell:

```bash
python -m sam_v2
```

Current launch modes:

- Native UI: `python -m sam_v2`
- Explicit native UI: `python -m sam_v2 --native-ui`
- CLI: `python -m sam_v2 --cli`
- One-shot: `python -m sam_v2 --once "what can you do" --json`

## What Is Working

### Runtime and Core

- `sam_v2` package entrypoint is wired
- config loading is real-tested
- storage/vault foundation is real-tested
- diagnostics/logging foundation is real-tested
- runtime request handling is real-tested
- conversation understanding has a real-tested path
- memory/session persistence is real-tested

### Project and Worker Flows

- Sam can scaffold a modular HTML tic-tac game project
- Sam stores project registry data
- Sam remembers the last active project
- Sam can answer where the remembered project is
- Sam can run the remembered project
- worker names are in use:
  - `Mason`
  - `Beacon`
  - `Pilot`
- Sam can plan a small project
- Sam can show delegation
- Sam can execute a delegated task on a small scaffolded project
- Sam can show progress and status

### Native UI

- native shell exists
- dashboard shows:
  - user messages
  - Sam replies
  - timestamps
  - current project panel
  - project action controls
- dashboard was intentionally simplified back to chat-first after the expanded cards crowded out the conversation area
- task popup preserves activity history
- task popup shows worker execution details
- worker execution visibility includes:
  - worker acceptance
  - command
  - folder
  - output lines
  - launch target / browser target

Current project action controls:

- `Open Folder`
- `Run Again`
- `Show Status`
- `Delegation`
- `Progress`

### Logging

- `sam_v2/logs/` resets on startup
- fresh logs are recreated automatically
- terminal debug logging was added for native UI and workers

## Important Recent Fixes

### Follow-up Conversation Fixes

These follow-ups were specifically fixed and tested:

- `please run the game you created`
- `great please run it`
- `where is it?`

### Project Launch Truthfulness

`run_project.py` was made truthful:

- `launched project at ...` only when launch really succeeds
- `launch target ... (browser disabled by SAM_V2_NO_BROWSER)` in test mode
- real failure if browser launch cannot be performed

## Important Recent Commits

- `ef48617` `fix: improve Sam v2 chat, run, and log behavior`
- `1dda5ed` `fix: preserve Sam v2 project follow-up context`
- `eda6710` `feat: stream Sam v2 worker execution in native UI`
- `2102d33` `fix: make Sam v2 project launch reporting truthful`
- `44c9837` `fix: improve Sam v2 run followups and debug logging`
- `e79aa17` `feat: add Sam v2 native project action controls`

## Latest Verified Behavior

The following were re-verified in the latest passes:

- `python -u sam_v2/tests_live/test_conversation_live.py`
- `python -u sam_v2/tests_live/test_project_scaffold_live.py`
- `python -u sam_v2/tests_live/test_native_ui_command_stream_live.py`
- `python -u sam_v2/tests_live/test_native_ui_project_actions_live.py`
- `python -u sam_v2/tests_live/test_native_ui_projects_tasks_live.py`
- `python -u sam_v2/tests_live/test_native_ui_approvals_logs_live.py`
- `python -u sam_v2/tests_live/test_native_ui_capabilities_git_live.py`
- `python -u sam_v2/tests_live/test_main_entry_live.py`
- `python -u sam_v2/tests_live/test_list_tasks_live.py`
- `python -u sam_v2/tests_live/test_list_approvals_live.py`

Direct runtime flow also verified:

1. Build a web tic-tac game
2. Run with `great please run it`
3. Sam resolves the remembered project and executes the saved run command

## Known Rough Edges

### Native UI Manual Feel

The native shell is functional, but still needs polish:

- cinematic motion can be improved
- execution card styling can be richer
- keep the dashboard chat-first; avoid loading more summary cards into the main panel
- add any future extra surfaces behind secondary views, drawers, or popups instead of pushing the chat area down

### Existing Local UI Changes

There is an unrelated local edit that was intentionally not part of the latest commits unless separately reviewed:

- `sam_v2/native_ui/orb.py`

Inspect it before assuming it belongs to the most recent fixes.

### External Repo Worker Blocker

There is still a known environment-sensitive blocker for some external worker subprocess paths, especially Flutter-based external repo execution. In-repo and controlled local project flows are working much better than that external edge.

## User Priorities

The user cares about:

- strong native UI
- visible execution
- strong organization and modular project structure
- minimal code dumping into one file
- being able to plan and execute projects with Sam
- truthful behavior over optimistic claims

## Best Next Task

### Native UI Discipline

Recommended next feature:

1. `Task detail / edit view`
2. `Approval action controls`
3. `Log detail viewer`
4. `Repo detail popup`
5. `Manual visual pass and motion polish`
6. `Orb refinement without changing dashboard density`

Why this is next:

- the project operator controls now exist
- the user explicitly wants the dashboard kept simple
- future UI work should respect that and move extra information out of the main chat surface

## Suggested First Read For Next Session

1. `sam_v2/docs/SESSION_HANDOFF.md`
2. `sam_v2/docs/MIGRATION_TRACKER.md`
3. `sam_v2/docs/SAM_CAPABILITY_MAP.md`
4. `sam_v2/native_ui/app.py`
5. `sam_v2/intents/router.py`
6. `sam_v2/projects/scaffolding.py`
