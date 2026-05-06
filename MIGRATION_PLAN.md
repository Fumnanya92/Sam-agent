# Sam Clean Rebuild Migration Plan

## Purpose

This branch is for rebuilding Sam cleanly without damaging the current working code on `main`.

The goal is not to move everything at once. The goal is to rebuild Sam feature by feature, test each feature, then continue only after the migrated feature works properly.

## Current Repository State

- Default branch: `main`
- Existing branches seen:
  - `main`
  - `strip-down-2026-05-01`
  - `unified-sam`
  - `rebuild/sam-clean-v2`
- Latest verified main commit used as branch base:
  - `0f4d015ade241b2c970e291bc21ff6737d992bdc`
  - Message: `Merge pull request #1 from Fumnanya92/unified-sam`

## Known Capabilities From Recent Commit History

These are based on commit metadata and should be verified directly from the code before migration:

- Conversation loop
- System awareness
- File management
- Reminder handling
- Memory manager
- Daemon process
- Config loader
- WebSocket/live testing flow
- Goals
- Workflows
- Channels
- Personality system
- React UI / overlay identity changes from Jarvis to Sam
- Prompt feature-system awareness

## Main Problem We Are Solving

Sam appears to have too many features mixed together at once. This can cause feature clashes, hidden dependencies, unstable behavior, and difficulty testing.

The rebuild should separate Sam into clear layers:

1. Core assistant brain
2. Tool registry
3. Memory
4. Task/workflow system
5. External integrations
6. UI/API layer
7. Tests and diagnostics

## Rebuild Rules

1. Do not delete the old implementation at the start.
2. Do not migrate many features at the same time.
3. Every migrated feature must have a simple test path.
4. Every feature must define:
   - what it does
   - input it accepts
   - output it returns
   - dependencies it needs
   - how it can fail
5. If a feature is not used by Sam, do not migrate it yet.
6. UI polish comes after the backend assistant flow is stable.

## Proposed Clean Architecture

```text
sam/
  core/
    assistant.py
    runtime.py
    messages.py
  prompts/
    system_prompt.md
    prompt_builder.py
  tools/
    registry.py
    base.py
    file_tools.py
    reminder_tools.py
  memory/
    store.py
    models.py
  workflows/
    manager.py
    models.py
  integrations/
    websocket.py
    api.py
  diagnostics/
    logging.py
    healthcheck.py
  tests/
    test_assistant_basic.py
    test_tools_registry.py
```

This structure is only a starting proposal. It should be adjusted after direct code inspection.

## Migration Order

### Phase 1 — Discovery

- Inspect current files and folders.
- List current entry points.
- Identify which process starts Sam.
- Identify all tools Sam can call.
- Identify where prompts are stored.
- Identify where memory is read/written.
- Identify how the UI talks to the backend.

Deliverable:

- Updated `MIGRATION_PLAN.md`
- Optional `FEATURE_INVENTORY.md`

### Phase 2 — Minimal Sam Core

Build the smallest working Sam:

- Accept a user message
- Build a prompt
- Return a response
- Log request/response clearly
- No tools yet
- No memory yet
- No UI dependency yet

Test:

- Can Sam respond to a simple message?
- Can errors be logged clearly?
- Can this run from CLI or a simple test script?

### Phase 3 — Tool Registry

Migrate only the tool-calling foundation.

Test:

- Can Sam list available tools?
- Can Sam call one fake/test tool?
- Can tool errors return cleanly without crashing Sam?

### Phase 4 — File Management

Migrate file-related features only after tool registry works.

Test:

- Read file
- Write file
- List files in allowed workspace
- Reject unsafe paths

### Phase 5 — Memory

Migrate memory after basic assistant and tools are stable.

Test:

- Save memory
- Retrieve memory
- Clear/update memory safely
- Confirm Sam does not confuse memory with active instructions

### Phase 6 — Reminders / Tasks

Migrate reminders and task logic.

Test:

- Create reminder/task
- List reminder/task
- Mark reminder/task done
- Handle invalid date/time safely

### Phase 7 — Goals and Workflows

Migrate goals and workflows only after tasks work.

Test:

- Create goal
- Break goal into workflow steps
- Update workflow status
- Resume workflow without losing state

### Phase 8 — WebSocket / API Bridge

Migrate communication layer.

Test:

- Frontend can connect
- Backend can respond
- Disconnection does not crash runtime
- Logs show request path clearly

### Phase 9 — UI Cleanup

Only after Sam works from backend/test scripts:

- Remove unused copied UI areas
- Keep only screens Sam actually uses
- Connect UI to stable backend endpoints
- Add visible loading/error states

## Testing Checklist Per Feature

Before marking any feature as migrated, confirm:

- [ ] Feature has a clear purpose
- [ ] Feature works in isolation
- [ ] Feature works with Sam core
- [ ] Failure cases are handled
- [ ] Logs are understandable
- [ ] No unrelated feature was changed
- [ ] Commit is small and focused

## First Safe Coding Task

The first implementation task should not migrate existing features yet.

Recommended first task:

> Create a minimal `sam_v2` or `sam/core` skeleton with a basic assistant runtime and one simple test proving the new structure can run.

## Notes

This file should be updated as we inspect the code and learn more about the real current structure.
