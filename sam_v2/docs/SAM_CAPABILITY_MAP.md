# Sam Capability Map

> Audit date: 2026-05-06
> Purpose: list what old Sam appears to do, what `sam_v2` currently contains, and what still needs real validation.
> Status key: `Not Started` | `Migrated But Unverified` | `Real-Tested` | `Blocked` | `Drop Candidate`

## Level 0 - Foundation

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Diagnostics and run logging | `main.py`, `daemon/main.py`, `system/session_logger.py`, `agent/error_handler.py`, `log/*` | `sam_v2/diagnostics/run_logger.py`, `sam_v2/diagnostics/reporting.py`, `sam_v2/diagnostics/test_logger.py`, `sam_v2/tests_live/test_diagnostics_live.py` | Real-Tested | Write runtime, action, error, summary, and test logs to disk from a real request and a real failing command | filesystem, runtime, workers | Low | 1 |
| Structured result and error model | `agent/error_handler.py`, broad exception handling in `main.py`, `intents/handlers.py` | `sam_v2/diagnostics/result.py`, `sam_v2/diagnostics/error_types.py` | Migrated But Unverified | Run one request path and one worker path, then prove error types remain stable across subsystems | diagnostics, runtime, workers | Medium | 2 |
| Storage and vault foundation | `vault/schema.py`, `daemon/vault_routes.py`, `goals/tracker.py`, `pipeline/engine.py` | `sam_v2/storage/schema.py`, `sam_v2/storage/db.py`, `sam_v2/storage/models.py`, `sam_v2/tests_live/test_vault_live.py` | Real-Tested | Create real SQLite DB, ensure schema, insert/read audit row, insert/read task row, confirm failure path | sqlite, filesystem | Low | 3 |
| Config loading | `config/*`, `memory/config_manager.py`, `.env`, `llm.py` | None beyond ad hoc constructor parameters in current modules | Not Started | Load config from file/env with clear failure reporting and no hardcoded secrets path | filesystem, env vars | Medium | 4 |

## Level 1 - Conversation and instruction understanding

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Plain conversation | `main.py`, `llm.py`, `core/prompt.txt`, `ui.py` | `sam_v2/core/runtime.py`, `sam_v2/core/request_handler.py`, `sam_v2/intents/router.py` | Migrated But Unverified | Real model/API call where Sam answers naturally to open chat, logs the run, and does not collapse into rigid intent labels | config, logging, model access | High | 5 |
| Instruction classification | `llm.py`, `core/prompt.txt`, `intents/handlers.py` | `sam_v2/intents/router.py` | Migrated But Unverified | Real model/API call classifying chat vs command vs goal vs approval-sensitive request, with pass/fail log output | plain conversation, model access | High | 6 |
| Goal and request understanding | `main.py`, `llm.py`, `goals/tracker.py`, `pipeline/engine.py` | `sam_v2/intents/router.py`, `sam_v2/workflows/goals.py`, `sam_v2/workflows/pipeline.py` | Migrated But Unverified | Real request like "help me fix a broken app" must be interpreted as a plan-worthy request rather than a hardcoded keyword action | instruction classification, workflows | High | 7 |
| Intent routing fallback | `intents/handlers.py`, `core/capabilities.py` | `sam_v2/intents/router.py`, `sam_v2/capabilities/registry.py`, `sam_v2/tests_live/test_intents_live.py` | Migrated But Unverified | Unknown request should fall back conversationally, log its decision, and avoid false confident action | capability registry, logging | Medium | 8 |
| Clarification decision | `main.py`, `llm.py`, `conversation_state.py` | None beyond minimal empty-input handling in `sam_v2/core/request_handler.py` | Not Started | Ambiguous request should trigger clarification instead of wrong action | conversation understanding, memory | High | 9 |
| Autonomous planning trigger | `main.py`, `agent/planner.py`, `agents/orchestrator.py` | Minimal routing only; no real planner trigger in `sam_v2` | Not Started | Real request should cause Sam to decide between act now, ask, or plan, with justification logged | conversation understanding, supervisor | High | 10 |

## Level 2 - Memory and context

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Temporary memory | `memory/temporary_memory.py` | `sam_v2/memory/temporary.py`, `sam_v2/tests_live/test_memory_live.py` | Real-Tested | Use real runtime calls or direct memory operations and confirm pending intent/history updates in process | diagnostics | Low | 11 |
| Persistent memory | `memory/memory_manager.py`, `memory/memory.json` | `sam_v2/memory/manager.py`, `sam_v2/tests_live/test_memory_live.py` | Real-Tested | Save/update/reload real JSON file and confirm audit event in SQLite | storage, filesystem | Low | 12 |
| Session state | `memory/session_state.py`, `conversation_state.py` | `sam_v2/memory/session.py`, `sam_v2/core/session.py`, `sam_v2/tests_live/test_memory_live.py`, `sam_v2/tests_live/test_runtime_live.py` | Real-Tested | Save/load real session file and verify runtime request count or branch/project state persists | filesystem, runtime | Low | 13 |
| Project context | `memory/project_index.json`, `system/git_intelligence.py`, `assistant/daily_planner.py` | `sam_v2/projects/registry.py`, `sam_v2/capabilities/awareness.py`, `sam_v2/tests_live/test_awareness_live.py` | Migrated But Unverified | Register a real local project/repo, reload it, and prove Sam can reference its stack and commands in a request path | persistent memory, local repo | Medium | 14 |

## Level 3 - Safe local tools

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Read files | `actions/file_ops.py`, `actions/file_controller.py`, `actions/workspace.py` | No dedicated file-read tool yet | Not Started | Read a real repo file through Sam-facing tool flow and log the result | safe command tooling or dedicated tools package | Medium | 15 |
| List folders | `actions/file_ops.py`, `actions/workspace.py`, `actions/desktop.py` | No dedicated directory-list tool yet | Not Started | List a real project directory through Sam-facing tool flow and log the result | filesystem access | Low | 16 |
| Run safe terminal commands | `actions/terminal.py`, `actions/cmd_control.py`, `actions/dev_agent.py` | `sam_v2/workers/tooling.py`, `sam_v2/workers/queue.py`, `sam_v2/workers/monitor.py`, `sam_v2/tests_live/test_workers_live.py` | Real-Tested | Run real local safe commands and capture stdout, stderr, exit code, audit log, and failure path | approvals, diagnostics, filesystem | Medium | 17 |
| Inspect git state | `system/git_intelligence.py`, `actions/workspace.py`, `actions/code_helper.py` | No dedicated git-inspection feature yet | Not Started | Run `git status` or branch inspection through Sam-facing tool flow on a real repo | safe terminal commands, project context | Medium | 18 |
| Write draft files | `actions/file_ops.py`, `actions/code_helper.py`, `actions/dev_agent.py` | No dedicated draft-write tool yet | Not Started | Create a real draft file in a safe workspace and confirm contents plus audit log | filesystem, approvals | Medium | 19 |

## Level 4 - Project and code assistant

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Identify project | `memory/project_index.json`, `system/git_intelligence.py`, `assistant/message_reader.py` | `sam_v2/projects/registry.py`, `sam_v2/capabilities/awareness.py` | Migrated But Unverified | Given a real project name or path, Sam should resolve the correct project record and log confidence | project context | Medium | 20 |
| Inspect repo | `actions/code_helper.py`, `system/git_intelligence.py`, `agent/planner.py` | No dedicated repo-inspection path yet | Not Started | Point Sam at a real repo and require a structured inspection summary | identify project, read files, git inspection | High | 21 |
| Run tests and builds | `actions/dev_agent.py`, `agent/executor.py`, `agents/orchestrator.py` | `sam_v2/supervisor/supervisor.py`, `sam_v2/supervisor/workflow_bridge.py`, `sam_v2/workers/tooling.py`, `sam_v2/tests_live/test_supervisor_live.py` | Migrated But Unverified | Use a real repo's declared test/build commands, not placeholder scripts, and capture pass/fail logs | project context, safe commands | High | 22 |
| Understand failures | `agent/error_handler.py`, `agent/executor.py`, `actions/code_helper.py` | `sam_v2/projects/failure_analysis.py`, `sam_v2/supervisor/recovery.py`, diagnostics modules, `sam_v2/tests_live/test_failure_understanding_live.py` | Real-Tested | Feed Sam a real failing build/test run and require a useful explanation and next action | run tests/builds, logging | High | 23 |
| Edit code through worker | `actions/code_helper.py`, `actions/dev_agent.py`, `agents/orchestrator.py` | `sam_v2/workers/tooling.py`, `sam_v2/tests_live/test_worker_edit_live.py` | Real-Tested | Modify a real local git repo file through the worker, show a real diff, rerun the real test, and log the result | write access, approvals, repo inspection | High | 24 |
| Retry based on logs | `agent/executor.py`, `agent/monitor.py`, `agents/delegation.py` | `sam_v2/supervisor/recovery.py`, `sam_v2/supervisor/workflow_bridge.py`, `sam_v2/tests_live/test_workflow_bridge_live.py` | Migrated But Unverified | Use a real flaky command in a real project path and show retry policy chosen from actual failure output | diagnostics, workers | Medium | 25 |
| Summarize diff | `actions/code_helper.py`, `system/report_writer.py` | None yet | Not Started | Produce a summary from a real git diff after a code change | git inspection, code editing | Medium | 26 |
| Ask approval before push | `authority/*`, `system/git_intelligence.py`, `actions/dev_agent.py` | `sam_v2/approvals/*`, `sam_v2/intents/router.py`, `sam_v2/core/runtime.py`, `sam_v2/tests_live/test_push_approval_live.py` | Real-Tested | Real runtime request on a real repo context must create a pending `git.push` approval record and remain unexecuted until approval is granted | approvals, git inspection, runtime | High | 27 |

## Level 5 - Workflows, tasks, and goals

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Create task | `goals/tracker.py`, `daemon/vault_routes.py` | `sam_v2/storage/db.py`, `sam_v2/storage/models.py` | Migrated But Unverified | Create task through Sam-facing request or service path, then reload from SQLite with logs | storage, conversation understanding | Medium | 28 |
| Track task | `goals/tracker.py`, `system/task_queue.py` | Basic task table only; no tracking service yet | Not Started | Update task state over multiple steps and show durable history | create task, storage | Medium | 29 |
| Create goal | `goals/tracker.py` | `sam_v2/workflows/goals.py`, `sam_v2/tests_live/test_workflows_live.py` | Migrated But Unverified | Create goal from a real request path and verify storage plus follow-up listing | storage, instruction understanding | Medium | 30 |
| Run workflow steps | `pipeline/engine.py`, `workflows/engine.py`, `agent/task_queue.py` | `sam_v2/workflows/pipeline.py`, `sam_v2/supervisor/workflow_bridge.py`, `sam_v2/tests_live/test_workflow_bridge_live.py` | Migrated But Unverified | Execute a real multi-step local workflow against real commands or files with logs | workers, approvals, diagnostics | High | 31 |
| Pause and resume workflows | `pipeline/engine.py`, `agent/monitor.py`, `goals/tracker.py` | Partial pause-via-approval behavior in `sam_v2/supervisor/workflow_bridge.py` | Migrated But Unverified | Pause a real running workflow for approval, then resume and complete it | approvals, workflow steps | High | 32 |

## Level 6 - External integrations

| Capability | Old files involved | `sam_v2` files involved | Status | Real live test required | Dependencies | Risk | Recommended order |
|---|---|---|---|---|---|---|---|
| Browser automation | `automation/chrome_controller.py`, `automation/chrome_debug.py`, `system/screen_vision.py`, `actions/browser_control.py` | None | Not Started | Open real browser session, inspect page, and return a verified result | approvals, UI/browser access | High | 33 |
| WhatsApp automation | `automation/whatsapp_*`, `assistant/message_reader.py`, `actions/send_message.py` | None | Not Started | Use controlled test account and verify read/draft/send flow | browser automation, approvals | High | 34 |
| Telegram and Discord | `comms/manager.py`, `comms/channels/*` | None | Not Started | Send and receive a real test message through one channel | config loading, daemon/runtime | Medium | 35 |
| Meeting assistant | `assistant/*`, possible `roles/*` support, `system/notifier.py` | None | Drop Candidate | Define actual product scope first; no clear clean `sam_v2` target yet | conversation, calendar/transcription tooling | High | 36 |
| Voice capture | `speech_to_text_websocket.py`, `websocket_server.py`, `speech_client.html`, `tts.py` | None in current `sam_v2` | Not Started | Speak real input, capture transcript, route it to runtime, and log output | conversation, websocket/daemon | High | 37 |
| Desktop launcher and orb | `launcher.py`, `start_launcher.bat`, `start_launcher.vbs`, `orb/*`, `start_orb.py` | None | Not Started | Start one real local Sam session from launcher/orb without duplicate process issues | runtime, voice or daemon | High | 38 |

## Notes

- `sam_v2` currently has meaningful foundational code, but the conversation and repo-assistant layers are not yet proven against a real model-backed understanding path.
- `Real-Tested` here only means the feature has at least one documented real artifact path already proven, such as a real SQLite DB, real filesystem writes, or real local command execution.
- `Migrated But Unverified` means code exists, but it is not yet validated to the stricter standard the user asked for.
