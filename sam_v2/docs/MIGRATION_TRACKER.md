# Sam v2 Migration Tracker

> Source: `sam_v2/docs/FEATURE_INVENTORY.md`
> Status key: `Not Started` | `In Progress` | `Done` | `Blocked`

| Feature | Old files | Status | Notes |
|---|---|---|---|
| Core assistant runtime loop | `main.py`, `conversation_state.py`, `llm.py`, `tts.py`, `ui.py`, `intents/handlers.py` | Done | Minimal Sam v2 core runtime migrated in `sam_v2/core`; request handling, approval-aware routing, memory/session persistence, and run logging live tested (`python sam_v2/tests_live/test_runtime_live.py`) |
| Supervisor architecture (coding/testing/project execution) | `agents/orchestrator.py`, `agents/hierarchy.py`, `agents/delegation.py`, `agent/planner.py`, `agent/executor.py` | Done | Minimal Sam v2 supervisor controller migrated in `sam_v2/supervisor`; project-profile routing, worker selection, workflow-bridge handoff, and approval-aware execution live tested (`python sam_v2/tests_live/test_supervisor_live.py`) |
| Supervisor workflow execution bridge | `agent/planner.py`, `agent/executor.py`, `agent/task_queue.py`, `agents/orchestrator.py` | Done | Minimal Sam v2 supervisor workflow bridge migrated in `sam_v2/supervisor`; plan execution, retry policy, worker queue bridging, and approval pause behavior live tested (`python sam_v2/tests_live/test_workflow_bridge_live.py`) |
| Daemon API + dashboard backend | `daemon/main.py`, `daemon/api_routes.py`, `daemon/vault_routes.py`, `daemon/missing_routes.py`, `daemon/extra_routes.py` | Done | Minimal Sam v2 daemon skeleton migrated with `health`, `chat`, and `ws` only; live test passed (`python sam_v2/tests_live/test_daemon_live.py`) |
| React dashboard shell | `ui/src/App.tsx`, `ui/src/hooks/*`, `ui/src/pages/*`, `ui/src/components/*` | Not Started | Broad surface; many tabs depend on backend parity |
| Voice capture (Web Speech + websocket) | `speech_to_text_websocket.py`, `websocket_server.py`, `speech_client.html` | Not Started | Wake-word + transcript queue pipeline |
| Desktop launcher/orb shell | `launcher.py`, `start_launcher.*`, `orb/*` | Not Started | Validate product direction before carrying forward |
| Capability awareness + controlled upgrade proposals | `core/prompt.txt`, `memory/project_index.json`, capability-related prompt rules | Done | Minimal Sam v2 capability awareness foundation migrated in `sam_v2/capabilities`, `sam_v2/projects`, and `sam_v2/upgrades`; self-awareness, missing-capability detection, and approval-gated upgrade proposals live tested (`python sam_v2/tests_live/test_awareness_live.py`) |
| Intent system + capability registry | `core/prompt.txt`, `core/capabilities.py`, `intents/*` | Done | Minimal Sam v2 capability registry and intent router migrated in `sam_v2/capabilities` and `sam_v2/intents`; live test passed (`python sam_v2/tests_live/test_intents_live.py`) |
| Memory subsystem | `memory/memory_manager.py`, `memory/temporary_memory.py`, `memory/session_state.py` | Done | Minimal Sam v2 memory foundation migrated in `sam_v2/memory` and live test passed (`python sam_v2/tests_live/test_memory_live.py`) |
| Vault/SQLite persistence | `vault/schema.py`, `daemon/vault_routes.py` | Done | Sam v2 storage foundation migrated in `sam_v2/storage` and live test passed (`python sam_v2/tests_live/test_vault_live.py`) |
| Task/goal/pipeline workflows | `goals/tracker.py`, `pipeline/engine.py`, related daemon routes | Done | Minimal Sam v2 goal and pipeline workflow foundation migrated in `sam_v2/workflows` and live test passed (`python sam_v2/tests_live/test_workflows_live.py`) |
| System watchers + presence engine | `system/presence_engine.py`, `system/watchers/*`, `system/event_bus.py` | Not Started | Risky concurrency side effects |
| WhatsApp automation suite | `automation/whatsapp_*`, `assistant/message_reader.py` | Not Started | High fragility and external dependency |
| Comms channels (Telegram/Discord) | `comms/manager.py`, `comms/channels/*` | Not Started | Optional integration layer |
| Tooling agents (code/test/dev) | `agents/*`, `actions/dev_agent.py`, `actions/code_helper.py` | Done | Minimal Sam v2 worker foundation migrated in `sam_v2/workers`; queueing, monitor tracking, safe command execution, failure handling, and approval gating live tested (`python sam_v2/tests_live/test_workers_live.py`) |
| Authority/approval governance | `authority/*`, authority daemon routes | Done | Minimal Sam v2 approvals foundation migrated in `sam_v2/approvals` and live test passed (`python sam_v2/tests_live/test_approvals_live.py`) |
