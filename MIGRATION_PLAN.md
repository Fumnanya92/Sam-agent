# Sam Autonomous Assistant Rebuild Plan

## Product Vision

Sam is not just a chatbot.

Sam should become an autonomous personal/business assistant that can help a real person or business owner get work done with minimal input.

The long-term direction is closer to:

- Friday / Jarvis-style personal assistant
- CEO assistant that answers to the boss
- Real work agent that can plan, execute, report, and ask for approval when needed
- Assistant that can operate across projects, files, tasks, messages, reminders, business workflows, and integrations

The goal is to build Sam as an assistant operating system, not as a random collection of features.

## Core Principle

Sam should be able to move from:

> User gives instruction → Sam replies

To:

> User gives goal → Sam understands context → plans work → uses tools → executes safely → reports progress → asks for permission when required → remembers useful context → improves future execution

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

The rebuild should separate Sam into clear assistant layers:

1. Assistant identity and behavior
2. Core reasoning/runtime loop
3. Planning and task execution
4. Tool registry and permissions
5. Memory and context
6. Project/business workspace awareness
7. Communication/reporting layer
8. UI/API layer
9. Tests, diagnostics, and safety checks

## What Sam Should Become

### 1. Personal Chief-of-Staff Assistant

Sam should help the owner manage work like a real assistant:

- understand goals
- break goals into steps
- track open tasks
- remember important context
- follow up on pending work
- summarize progress
- prepare messages, reports, and documents
- help manage projects and priorities

### 2. Business Operations Assistant

Sam should support business workflows such as:

- project planning
- task tracking
- client follow-ups
- document preparation
- report generation
- invoice/report preparation
- customer/vendor operations
- internal SOPs and checklists

### 3. Tool-Using Agent

Sam should not only talk. Sam should be able to use tools safely:

- read files
- write files
- search project context
- create tasks
- schedule reminders
- inspect code
- call APIs
- work with GitHub
- prepare emails/messages
- eventually integrate with calendar, WhatsApp, browser, and business tools

### 4. Autonomous But Controlled

Sam should act with minimal input, but not recklessly.

Sam needs clear permission levels:

- `suggest_only`: Sam can advise but not act
- `draft`: Sam can prepare work for review
- `execute_safe`: Sam can perform low-risk actions
- `approval_required`: Sam must ask before sensitive actions
- `blocked`: Sam must never perform the action

Examples of actions that should require approval:

- sending messages/emails
- deleting files
- changing production code
- spending money
- publishing public content
- contacting clients/residents/users
- changing business/legal documents

## Assistant OS Architecture

```text
sam/
  identity/
    profile.py
    behavior_policy.md
    communication_style.md

  core/
    runtime.py
    assistant.py
    message.py
    session.py

  planner/
    goal_parser.py
    task_planner.py
    execution_plan.py
    progress_tracker.py

  tools/
    registry.py
    base.py
    permissions.py
    file_tools.py
    github_tools.py
    reminder_tools.py
    message_tools.py

  memory/
    store.py
    retrieval.py
    models.py
    memory_policy.md

  workspace/
    projects.py
    business_context.py
    documents.py
    tasks.py

  integrations/
    api.py
    websocket.py
    cli.py

  diagnostics/
    logging.py
    audit_log.py
    healthcheck.py

  tests/
    test_assistant_basic.py
    test_planner.py
    test_tool_registry.py
    test_permissions.py
```

This structure is a starting proposal. It should be adjusted after direct code inspection.

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
   - permission level required
5. If a feature does not support the autonomous assistant vision, do not migrate it yet.
6. UI polish comes after the assistant runtime is stable.
7. Every action Sam takes should be visible in logs or audit history.

## Migration Order

### Phase 1 — Discovery

- Inspect current files and folders.
- List current entry points.
- Identify which process starts Sam.
- Identify all tools Sam can call.
- Identify where prompts are stored.
- Identify where memory is read/written.
- Identify how the UI talks to the backend.
- Identify which features support autonomous assistant behavior.
- Identify which features are unused, copied, or confusing.

Deliverable:

- Updated `MIGRATION_PLAN.md`
- `FEATURE_INVENTORY.md`
- `AUTONOMY_MODEL.md`

### Phase 2 — Minimal Assistant Runtime

Build the smallest working Sam:

- accept a user message
- understand the instruction
- classify whether it is chat, task, goal, or command
- return a response
- log request/response clearly
- no real tools yet
- no UI dependency yet

Test:

- Can Sam respond to a simple message?
- Can Sam identify a task vs casual chat?
- Can errors be logged clearly?
- Can this run from CLI or a simple test script?

### Phase 3 — Planning Layer

Add planning before tool execution.

Sam should be able to turn a goal into:

- objective
- assumptions
- required context
- steps
- risks
- required tools
- approval points
- expected output

Test:

- Given a goal, can Sam produce a structured plan?
- Can Sam identify missing information?
- Can Sam identify actions that require approval?

### Phase 4 — Tool Registry and Permissions

Migrate only the tool-calling foundation.

Test:

- Can Sam list available tools?
- Can Sam call one fake/test tool?
- Can Sam block a tool if permission is missing?
- Can tool errors return cleanly without crashing Sam?

### Phase 5 — File and Workspace Awareness

Migrate file-related and project-awareness features.

Test:

- Read file
- Write draft file
- List files in allowed workspace
- Reject unsafe paths
- Summarize a project folder
- Create a simple project note/checklist

### Phase 6 — Memory

Migrate memory after assistant, planning, and tools are stable.

Test:

- Save memory
- Retrieve memory
- Update memory
- Separate long-term memory from current instructions
- Confirm Sam does not confuse old context with active commands

### Phase 7 — Tasks, Follow-Ups, and Reminders

Migrate reminders and task logic.

Test:

- Create task
- List task
- Update task status
- Create reminder draft
- Track follow-up items
- Handle invalid date/time safely

### Phase 8 — Goals and Workflows

Migrate goals and workflows only after task logic works.

Test:

- Create goal
- Break goal into workflow steps
- Update workflow status
- Resume workflow without losing state
- Report what is done, pending, blocked, and next

### Phase 9 — Communication Layer

Migrate message/email/report drafting.

Test:

- Draft a WhatsApp message
- Draft an email
- Draft a report
- Ask approval before sending/publishing
- Keep tone/style consistent

### Phase 10 — WebSocket / API Bridge

Migrate communication between backend and frontend.

Test:

- Frontend can connect
- Backend can respond
- Disconnection does not crash runtime
- Logs show request path clearly

### Phase 11 — UI Cleanup

Only after Sam works from backend/test scripts:

- Remove unused copied UI areas
- Keep only screens Sam actually uses
- Connect UI to stable backend endpoints
- Add visible loading/error states
- Show task progress, plans, memory, and approval requests clearly

## Testing Checklist Per Feature

Before marking any feature as migrated, confirm:

- [ ] Feature supports the assistant vision
- [ ] Feature has a clear purpose
- [ ] Feature works in isolation
- [ ] Feature works with Sam core
- [ ] Permission level is defined
- [ ] Failure cases are handled
- [ ] Logs are understandable
- [ ] No unrelated feature was changed
- [ ] Commit is small and focused

## First Safe Coding Task

The first implementation task should not migrate existing features yet.

Recommended first task:

> Create `AUTONOMY_MODEL.md` and `FEATURE_INVENTORY.md`, then scaffold a minimal assistant runtime that can classify user input as chat, task, goal, or command.

## Notes

This file should be updated as we inspect the code and learn more about the real current structure.
