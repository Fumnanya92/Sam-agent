# Sam v2 Migration Tracker

> Source: `sam_v2/docs/FEATURE_INVENTORY.md`
> Status key: `Not Started` | `In Progress` | `Done` | `Blocked`

| Feature | Old files | Status | Notes |
|---|---|---|---|
| Core assistant runtime loop | `main.py`, `conversation_state.py`, `llm.py`, `tts.py`, `ui.py`, `intents/handlers.py` | Not Started | Large monolith; split by boundaries before migration |
| Daemon API + dashboard backend | `daemon/main.py`, `daemon/api_routes.py`, `daemon/vault_routes.py`, `daemon/missing_routes.py`, `daemon/extra_routes.py` | Done | Minimal Sam v2 daemon skeleton migrated with `health`, `chat`, and `ws` only; live test passed (`python sam_v2/tests_live/test_daemon_live.py`) |
| React dashboard shell | `ui/src/App.tsx`, `ui/src/hooks/*`, `ui/src/pages/*`, `ui/src/components/*` | Not Started | Broad surface; many tabs depend on backend parity |
| Voice capture (Web Speech + websocket) | `speech_to_text_websocket.py`, `websocket_server.py`, `speech_client.html` | Not Started | Wake-word + transcript queue pipeline |
| Desktop launcher/orb shell | `launcher.py`, `start_launcher.*`, `orb/*` | Not Started | Validate product direction before carrying forward |
| Intent system + capability registry | `core/prompt.txt`, `core/capabilities.py`, `intents/*` | Not Started | High coupling; migrate incrementally |
| Memory subsystem | `memory/memory_manager.py`, `memory/temporary_memory.py`, `memory/session_state.py` | Done | Minimal Sam v2 memory foundation migrated in `sam_v2/memory` and live test passed (`python sam_v2/tests_live/test_memory_live.py`) |
| Vault/SQLite persistence | `vault/schema.py`, `daemon/vault_routes.py` | Done | Sam v2 storage foundation migrated in `sam_v2/storage` and live test passed (`python sam_v2/tests_live/test_vault_live.py`) |
| Task/goal/pipeline workflows | `goals/tracker.py`, `pipeline/engine.py`, related daemon routes | Not Started | Depends on vault + daemon core |
| System watchers + presence engine | `system/presence_engine.py`, `system/watchers/*`, `system/event_bus.py` | Not Started | Risky concurrency side effects |
| WhatsApp automation suite | `automation/whatsapp_*`, `assistant/message_reader.py` | Not Started | High fragility and external dependency |
| Comms channels (Telegram/Discord) | `comms/manager.py`, `comms/channels/*` | Not Started | Optional integration layer |
| Tooling agents (code/test/dev) | `agents/*`, `actions/dev_agent.py`, `actions/code_helper.py` | Not Started | Clarify `agent/` vs `agents/` ownership first |
| Authority/approval governance | `authority/*`, authority daemon routes | Done | Minimal Sam v2 approvals foundation migrated in `sam_v2/approvals` and live test passed (`python sam_v2/tests_live/test_approvals_live.py`) |
