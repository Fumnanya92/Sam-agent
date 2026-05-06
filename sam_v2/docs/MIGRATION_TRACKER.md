# Sam v2 Migration Tracker

> Source: `sam_v2/docs/FEATURE_INVENTORY.md`
> Truth-reset date: `2026-05-06`
> Status key: `Not Started` | `Migrated But Unverified` | `Real-Tested` | `Blocked` | `Drop Candidate`
> Rule: a feature is only `Real-Tested` when it has been proven on a real execution path for the kind of thing it claims to do. Broad module existence or in-process script coverage alone does not qualify.

| Feature | Old files | Status | Notes |
|---|---|---|---|
| Diagnostics and logging foundation | `main.py`, `daemon/main.py`, `system/session_logger.py`, `agent/error_handler.py` | Real-Tested | Real file-backed logs are currently proven by `python sam_v2/tests_live/test_diagnostics_live.py`; runtime action/summary logs and worker error logs are written and inspected from disk |
| Structured result and error model | broad old runtime/daemon error handling | Migrated But Unverified | `sam_v2/diagnostics/result.py` and `error_types.py` are in use, but there is no dedicated cross-subsystem stability validation yet |
| Storage/Vault foundation | `vault/schema.py`, `daemon/vault_routes.py`, `goals/tracker.py`, `pipeline/engine.py` | Real-Tested | Real SQLite DB path tested by `python sam_v2/tests_live/test_vault_live.py`; schema, audit row, task row, and failure path are proven |
| Config loading | `config/*`, `memory/config_manager.py`, `.env`, `llm.py` | Not Started | No clean `sam_v2` config layer yet |
| Core assistant runtime loop | `main.py`, `conversation_state.py`, `llm.py`, `tts.py`, `ui.py`, `intents/handlers.py` | Real-Tested | Current runtime conversation slice is now validated by `python sam_v2/tests_live/test_conversation_live.py` plus `python sam_v2/tests_live/test_runtime_live.py`; supported prompts cover chat, project listing, goal clarification, ambiguity handling, repo inspection prompting, and approval-sensitive push gating. TTS/UI/watcher behavior is still outside this validation scope |
| Supervisor architecture (coding/testing/project execution) | `agents/orchestrator.py`, `agents/hierarchy.py`, `agents/delegation.py`, `agent/planner.py`, `agent/executor.py` | Migrated But Unverified | Supervisor exists in `sam_v2/supervisor`, but test coverage uses demo scripts rather than a real project repo workflow |
| Supervisor workflow execution bridge | `agent/planner.py`, `agent/executor.py`, `agent/task_queue.py`, `agents/orchestrator.py` | Migrated But Unverified | Bridge exists, but it has not been proven against a real project workflow or true pause/resume recovery path |
| Daemon API + dashboard backend | `daemon/main.py`, `daemon/api_routes.py`, `daemon/vault_routes.py`, `daemon/missing_routes.py`, `daemon/extra_routes.py` | Migrated But Unverified | In-process `TestClient` coverage exists, but no full live daemon/server validation and no UI work should proceed yet |
| React dashboard shell | `ui/src/App.tsx`, `ui/src/hooks/*`, `ui/src/pages/*`, `ui/src/components/*` | Not Started | Broad surface; many tabs depend on backend parity |
| Voice capture (Web Speech + websocket) | `speech_to_text_websocket.py`, `websocket_server.py`, `speech_client.html` | Not Started | Wake-word + transcript queue pipeline |
| Desktop launcher/orb shell | `launcher.py`, `start_launcher.*`, `orb/*` | Not Started | Validate product direction before carrying forward |
| Capability awareness + controlled upgrade proposals | `core/prompt.txt`, `memory/project_index.json`, capability-related prompt rules | Migrated But Unverified | Awareness code exists, but there is no real request path proving truthful capability disclosure during actual assistant behavior |
| Intent system + capability registry | `core/prompt.txt`, `core/capabilities.py`, `intents/*` | Real-Tested | Real Ollama-backed understanding path and deterministic safety rails are now validated by `python sam_v2/tests_live/test_conversation_live.py` and `python sam_v2/tests_live/test_intents_live.py`; currently proven prompts cover chat, project listing, goal-style help requests, ambiguity clarification, repo inspection prompting, workflow/goal commands, and approval-sensitive push gating |
| Memory subsystem | `memory/memory_manager.py`, `memory/temporary_memory.py`, `memory/session_state.py` | Real-Tested | Real JSON and SQLite-backed audit path tested by `python sam_v2/tests_live/test_memory_live.py`, and real runtime-path persistence is now validated by `python sam_v2/tests_live/test_memory_runtime_live.py`; persistent memory, session state, runtime request history, and audit alignment are proven |
| Vault/SQLite persistence | `vault/schema.py`, `daemon/vault_routes.py` | Real-Tested | Same underlying storage feature as `Storage/Vault foundation`; kept here for migration continuity |
| Task/goal/pipeline workflows | `goals/tracker.py`, `pipeline/engine.py`, related API routes | Migrated But Unverified | Service methods exist and use real SQLite, but no true end-to-end user workflow or pause/resume validation yet |
| System watchers + presence engine | `system/presence_engine.py`, `system/watchers/*`, `system/event_bus.py` | Not Started | Risky concurrency side effects |
| WhatsApp automation suite | `automation/whatsapp_*`, `assistant/message_reader.py` | Not Started | High fragility and external dependency |
| Comms channels (Telegram/Discord) | `comms/manager.py`, `comms/channels/*` | Not Started | Optional integration layer |
| Tooling agents (code/test/dev) | `agents/*`, `actions/dev_agent.py`, `actions/code_helper.py` | Migrated But Unverified | Worker command execution is real, but project-aware coding/test/dev behavior has not been validated on a real repo problem |
| Authority/approval governance | `authority/*`, authority daemon routes | Real-Tested | Real SQLite-backed approval lifecycle tested by `python sam_v2/tests_live/test_approvals_live.py`; decisions, pending queue, approve path, and audit trail are proven |
