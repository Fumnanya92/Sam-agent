# Sam Unified System — Full Migration Plan
**Strategy: Option C — Clean Python FastAPI Daemon + React Dashboard (rethemed) + Rebuilt Orb**

---

## Context

Sam was the original personal AI assistant — Python-based, code-first, token-efficient, fast. Jarvis was adopted because it had more features (React dashboard, multi-agent, visual tools, workflow builder, SQLite vault, authority system). However Jarvis burns significantly more tokens because it is LLM-heavy by design and written in TypeScript (which the user doesn't know).

**Goal:** Migrate every Jarvis feature into Sam's Python ecosystem. Sam becomes the single, unified, production-grade AI assistant that is:
- Faster than Jarvis (code-first, Ollama handles 80%+ of tasks)
- Cheaper than Jarvis (token-efficient by architecture)
- More capable than both (all features merged)
- Maintainable (Python only, user can read and modify it)

**UI:** Rebuilt glass orb (minimal + fluid/organic) as quick-access launcher + Jarvis's React dashboard rethemed to **Emerald + Warm White** served by Python FastAPI.

---

## Feature Matrix — Sam vs Jarvis Side by Side

| Feature | Sam (Python) | Jarvis (TypeScript) | Unified Sam Target |
|---------|-------------|--------------------|--------------------|
| **Runtime** | Python 3 / asyncio | Bun / TypeScript | Python 3 / asyncio |
| **Primary UI** | Tkinter orb (ugly, basic) | React dashboard (15 pages) | Rebuilt glass orb + React dashboard (rethemed) |
| **Dashboard Theme** | None | Dark/flat (user hates it) | Emerald + Warm White |
| **LLM Providers** | Ollama + OpenAI | Anthropic, OpenAI, Groq, Gemini, Ollama, OpenRouter, NVIDIA (7) | All 7 + Ollama-first routing |
| **LLM Strategy** | Code-first, Ollama local | LLM-heavy, burns tokens | Code-first, Ollama default, cloud only for complex reasoning |
| **Token Efficiency** | ✅ Excellent | ❌ High burn | ✅ Excellent (Sam's approach) |
| **Voice (STT)** | Web Speech API via WebView | Whisper.cpp + built-in | Web Speech API (keep Sam's — it works) |
| **Voice (TTS)** | Edge TTS (Andrew Multilingual) | Edge TTS + ElevenLabs | Edge TTS + ElevenLabs premium option |
| **Wake Word** | Hotkey (Ctrl+Alt+S) | openwakeword-wasm | Both: hotkey + wake word |
| **Intent System** | 150+ intents, LLM-routed | Tool-based, no intent catalog | Sam's intent catalog + Jarvis's tool call pattern |
| **Actions/Tools** | 25 Python action handlers | 22 TypeScript tools | All 25 Sam actions + 4 new visual tools (Python ports) |
| **Skills System** | 600+ via Antigravity bridge | YAML roles (18 personas) | Both: dynamic skills + YAML roles |
| **Memory — Short term** | In-session JSON | In-session context | Keep Sam's temporary_memory.py |
| **Memory — Long term** | JSON files (flat) | SQLite vault (relational) | Migrate to SQLite (Jarvis's schema in Python) |
| **Memory — Vectors** | ❌ None | SQLite + transformers embeddings | Add vector embeddings (sentence-transformers) |
| **Conversation history** | Basic log | Full SQLite history | SQLite conversation history |
| **Multi-Agent** | Basic planner (5-step) | Full orchestrator + delegation + hierarchy + 9 roles | Full multi-agent in Python |
| **Agent Roles** | None | 18 YAML roles (CEO, Dev Lead, COS, etc.) | Port all 18 roles + keep Sam's skills |
| **Sub-agent execution** | ❌ | Full sub-agent runner | Python equivalent |
| **Authority/Permissions** | Basic approval gate | Full 0-5 permission levels + audit trail + emergency stop | Full authority system in Python |
| **Desktop Awareness** | ✅ presence_engine.py, screen OCR, stress detection | ✅ awareness/ subsystem (capture, OCR, context graph) | Merge both — Sam's presence + Jarvis's context graph |
| **Screen Capture** | mss + OCR (pytesseract) | Sharp + tesseract.js | Keep Python: mss + pytesseract |
| **Desktop Control** | pyautogui (keyboard/mouse) | Go sidecar (Win32/X11/macOS) | pyautogui (already works, skip sidecar complexity) |
| **Browser Control** | Playwright (Python) | Chrome DevTools Protocol via sidecar | Keep Python Playwright |
| **App Launching** | open_app.py (Windows search) | sidecar | Keep Sam's open_app.py |
| **Visual Tool: Screen View** | ❌ | show_screen() broadcast to dashboard | Port to Python — broadcast via WebSocket |
| **Visual Tool: Takeover Mode** | ❌ | takeover_begin/narrate/end | Port to Python — FastAPI WebSocket broadcast |
| **Visual Tool: Tutorial Steps** | ❌ | tutorial_step() with canvas annotations | Port to Python |
| **Visual Tool: UI Tests** | ❌ | broadcast_test_result() | Port to Python |
| **WhatsApp Automation** | ✅ Full (Playwright) — 9 files | ❌ None | Keep Sam's WhatsApp automation |
| **Telegram Channel** | ❌ | ✅ | Add python-telegram-bot |
| **Discord Channel** | ❌ | ✅ discord.js | Add discord.py |
| **Signal Channel** | ❌ | ✅ | Add Signal Python lib |
| **Workflow Builder** | ❌ | Visual n8n-style, 50+ nodes | Port core workflow engine to Python, keep React UI |
| **Goals/OKR Tracking** | Basic in memory | Full OKR system (goals, metrics, timelines) | Port goals system to Python + SQLite |
| **Content Pipeline** | ❌ | Draft→Review→Publish (Twitter, email) | Port content pipeline to Python |
| **Knowledge Graph** | Basic JSON memory (entities, relationships) | SQLite entity graph (facts, relationships, confidence) | Migrate to SQLite knowledge graph |
| **Commitments/Tasks** | Basic task tracking | Full what/when/context commitments engine | Port commitments to Python + SQLite |
| **WebSocket (real-time)** | websocket_server.py (speech only) | Full bidirectional WS for all events | Expand to full event WebSocket via FastAPI |
| **REST API** | ❌ None | Full API routes | FastAPI routes (replaces Jarvis's HTTP server) |
| **System Monitoring** | ✅ system_monitor.py (CPU, RAM, battery, disk) | ✅ health.ts | Keep Sam's system_monitor.py |
| **Presence Detection** | ✅ presence_engine.py (app focus, stress, suggestions) | ✅ awareness/service.ts | Keep Sam's presence_engine (it's better) |
| **Git Intelligence** | ✅ git_intelligence.py | Basic via sidecar | Keep Sam's git_intelligence.py |
| **Reminders** | ✅ reminders.py (Windows notifications) | ✅ heartbeat system | Keep Sam's reminders + add heartbeat checks |
| **Morning Briefing** | ✅ morning_briefing.py | ✅ heartbeat | Keep Sam's morning_briefing.py |
| **Personality** | core/prompt.txt | personality/ model + learner + adapter | Port personality learner to Python |
| **Config** | .env + api_keys.json | config.example.yaml | Unified YAML config (like Jarvis) + .env fallback |
| **Streaming responses** | ❌ (full response then speak) | ✅ streaming.ts | Add streaming via FastAPI SSE |
| **Docker** | ❌ | ✅ Dockerfile | Add Dockerfile for Sam |
| **Code first** | ✅ Yes | ❌ LLM-heavy | ✅ Enforce code-first everywhere |

---

## Architecture — Unified Sam

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAM UNIFIED SYSTEM                        │
│                                                                   │
│  ┌──────────────────────┐    ┌──────────────────────────────┐   │
│  │    Rebuilt Orb       │    │    React Web Dashboard        │   │
│  │  (PyQt6)             │    │  (Jarvis React, rethemed)    │   │
│  │                      │    │  Theme: Emerald + Warm White  │   │
│  │  - Frosted glass     │    │  15 pages: Chat, Tasks,       │   │
│  │  - Fluid breathing   │    │  Goals, Workflows, Memory,    │   │
│  │  - Minimal floating  │    │  Knowledge, Pipeline, etc.    │   │
│  │  - Quick voice input │    │                               │   │
│  │  - Opens dashboard   │    │                               │   │
│  └──────────┬───────────┘    └──────────────┬────────────────┘  │
│             │                                │                    │
│             └────────────┬───────────────────┘                   │
│                          │  WebSocket (ws://) + HTTP (REST)       │
│             ┌────────────▼────────────────────────┐              │
│             │         FastAPI Daemon               │              │
│             │         (Python 3 / uvicorn)         │              │
│             │         Port 3142                    │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  LLM Manager                  │   │              │
│             │  │  Ollama (local) ← PRIMARY     │   │              │
│             │  │  OpenAI / Anthropic / Groq    │   │              │
│             │  │  Gemini / OpenRouter          │   │              │
│             │  │  Fallback chain: local→cloud  │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Intent Router (from Sam)     │   │              │
│             │  │  150+ intents → action map    │   │              │
│             │  │  Code-first: 80% no LLM call  │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Action Handlers (25 from Sam)│   │              │
│             │  │  + 4 visual tools (new)       │   │              │
│             │  │  browser, computer, files,    │   │              │
│             │  │  code, search, media, etc.    │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Multi-Agent System           │   │              │
│             │  │  Orchestrator + Delegation    │   │              │
│             │  │  18 YAML Roles (Python port)  │   │              │
│             │  │  Sub-agent runner             │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  SQLite Vault                 │   │              │
│             │  │  conversations, tasks, goals, │   │              │
│             │  │  entities, facts, workflows,  │   │              │
│             │  │  documents, settings, vectors │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Awareness & Presence         │   │              │
│             │  │  presence_engine.py (Sam)     │   │              │
│             │  │  screen_vision.py (Sam)       │   │              │
│             │  │  context_graph (Jarvis→Py)    │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Authority System             │   │              │
│             │  │  Permission levels 0-5        │   │              │
│             │  │  Approval workflows           │   │              │
│             │  │  Audit trail (SQLite)         │   │              │
│             │  └──────────────────────────────┘   │              │
│             │                                      │              │
│             │  ┌──────────────────────────────┐   │              │
│             │  │  Comms Channels               │   │              │
│             │  │  WhatsApp (Sam's Playwright)  │   │              │
│             │  │  Telegram (python-telegram-bot│   │              │
│             │  │  Discord  (discord.py)        │   │              │
│             │  └──────────────────────────────┘   │              │
│             └──────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Critical Files

### From Sam (keep/extend):
- `main.py` → refactor into FastAPI daemon entry point
- `actions/` (all 25 handlers) → keep as-is, expose via API
- `intents/handlers.py` → keep intent routing, wire to FastAPI
- `memory/memory_manager.py` → migrate to SQLite vault
- `system/presence_engine.py` → keep, run as background task
- `system/screen_vision.py` → keep
- `system/git_intelligence.py` → keep
- `automation/` (WhatsApp, 9 files) → keep as-is
- `skills/` → keep all skills + antigravity bridge
- `tts.py` → keep
- `websocket_server.py` → replace with FastAPI WebSocket
- `conversation_state.py` → keep state machine, wire to FastAPI
- `assistant/morning_briefing.py` → keep
- `assistant/daily_planner.py` → keep
- `core/prompt.txt` → extend with Jarvis role prompts

### From Jarvis (port to Python):
- `src/vault/schema.ts` → `vault/schema.py` (SQLite via aiosqlite)
- `src/agents/orchestrator.ts` → `agents/orchestrator.py`
- `src/agents/delegation.ts` → `agents/delegation.py`
- `src/authority/engine.ts` → `authority/engine.py`
- `src/authority/approval.ts` → `authority/approval.py`
- `src/daemon/agent-service.ts` → `daemon/agent_service.py` (FastAPI)
- `src/comms/websocket.ts` → FastAPI WebSocket (`comms/ws.py`)
- `src/personality/model.ts` → `personality/model.py`
- `src/personality/learner.ts` → `personality/learner.py`
- `src/actions/tools/screen-view.ts` → `actions/tools/screen_view.py`
- `src/actions/tools/takeover.ts` → `actions/tools/takeover.py`
- `src/actions/tools/tutorial.ts` → `actions/tools/tutorial.py`
- `src/actions/tools/ui-test.ts` → `actions/tools/ui_test.py`
- `roles/*.yaml` → copy directly (YAML is language-agnostic)
- `src/workflows/` → `workflows/` (Python port)
- `src/goals/` → `goals/` (Python port)
- `src/vault/commitments.ts` → `vault/commitments.py`

### From Jarvis (keep React files, retheme only):
- `ui/src/` → copy entire React frontend into Sam project
- Change theme: all dark/flat colors → Emerald (#059669, #10b981) + Warm White (#fefce8, #fef9c3)
- All API calls: change port/endpoints to FastAPI Python backend (port 3142)
- Keep all 15 pages, 60+ components unchanged structurally

### New files to create:
- `daemon/main.py` — FastAPI entry point with uvicorn
- `daemon/ws_service.py` — WebSocket broadcast manager
- `daemon/api_routes.py` — REST API routes
- `vault/schema.py` — SQLite schema (aiosqlite)
- `agents/orchestrator.py` — Multi-agent orchestrator
- `llm/manager.py` — Multi-provider LLM manager (Ollama-first)
- `authority/engine.py` — Permission engine
- `comms/channels/telegram.py` — Telegram notifications
- `comms/channels/discord.py` — Discord notifications
- `orb/main.py` — Rebuilt glass orb (PyQt6)
- `orb/animations.py` — Fluid breathing animations
- `config/loader.py` — YAML config loader
- `config/sam.yaml` — Unified YAML config

---

## Implementation Phases

### Phase 1 — Foundation (FastAPI Daemon + SQLite)
1. Create `daemon/main.py` — FastAPI app with uvicorn on port 3142
2. Create `vault/schema.py` — SQLite via aiosqlite with all tables
3. Migrate `memory/memory_manager.py` → writes to SQLite
4. Create `daemon/ws_service.py` — WebSocket broadcast (replaces websocket_server.py)
5. Create `daemon/api_routes.py` — basic REST routes (health, chat, tasks)
6. Wire Sam's existing `ai_loop()` logic into FastAPI background task
7. **Verify:** `curl http://localhost:3142/health` returns 200

### Phase 2 — React Dashboard (Retheme + Rewire)
1. Copy Jarvis's `ui/src/` into Sam's project
2. Replace all theme colors with emerald + warm white palette
3. Update all API endpoint URLs to point to Python FastAPI (port 3142)
4. Update WebSocket event types to match Python daemon's broadcasts
5. Build React app, serve static files from FastAPI
6. **Verify:** Open browser, confirm all 15 pages load with new theme

### Phase 3 — Rebuilt Orb
1. Create `orb/main.py` using PyQt6
2. Frameless, always-on-top, translucent frosted glass window
3. Fluid breathing animation — smooth scale + glow pulse (organic, not robotic)
4. States: idle (dim glow) / listening (bright pulse) / thinking (spin) / speaking (wave)
5. Click to open web dashboard in browser
6. Right-click context menu (open dashboard, settings, quit)
7. Replace `launcher.py` and `ui.py` with new orb
8. **Verify:** Orb launches, breathing animation plays, click opens dashboard

### Phase 4 — Multi-Agent System (Python Port)
1. `agents/orchestrator.py` — agent selection, task decomposition
2. `agents/delegation.py` — assign tasks to specialist agents
3. `agents/hierarchy.py` — CEO → COS → specialist chain
4. `roles/loader.py` — load Jarvis's YAML roles (copy YAMLs as-is)
5. Wire to LLM manager with Ollama-first routing
6. **Verify:** Assign a complex task, confirm delegation works

### Phase 5 — Authority System (Python Port)
1. `authority/engine.py` — permission levels 0-5, action gating
2. `authority/approval.py` — approval request + user confirmation flow
3. `authority/audit.py` — SQLite audit trail
4. Wire all action handlers through authority engine
5. **Verify:** Attempt a level-3 action, confirm approval prompt fires in dashboard

### Phase 6 — Visual Tools (Python Port of 4 Jarvis tools)
1. `actions/tools/screen_view.py` — show_screen() broadcasts screenshot via WebSocket
2. `actions/tools/takeover.py` — takeover_begin/narrate/end broadcasts
3. `actions/tools/tutorial.py` — tutorial_step() with image + highlight metadata
4. `actions/tools/ui_test.py` — broadcast_test_result()
5. Wire broadcasts through ws_service.py
6. **Verify:** Trigger each from chat, confirm dashboard renders the cards

### Phase 7 — Comms Channels
1. `comms/channels/telegram.py` — python-telegram-bot, notifications + commands
2. `comms/channels/discord.py` — discord.py, server notifications
3. Keep Sam's WhatsApp automation as-is (already works)
4. Wire channel routing through daemon event system
5. **Verify:** Send a Telegram message, confirm Sam responds

### Phase 8 — Workflows + Goals + Content Pipeline (Python Port)
1. `workflows/engine.py` — workflow trigger + node execution
2. `workflows/nodes/` — port key node types (HTTP, email, file, code)
3. `goals/tracker.py` — OKR structure, daily check-ins
4. `pipeline/` — draft → review → publish flow
5. Wire to React dashboard pages (already have UI from Jarvis)
6. **Verify:** Create a goal, create a workflow trigger, run pipeline

### Phase 9 — Streaming + Advanced LLM
1. `llm/manager.py` — unified multi-provider (Ollama, OpenAI, Anthropic, Groq, Gemini, OpenRouter)
2. Ollama-first routing: code/system/local → Ollama; creative/complex → cloud
3. Add streaming via FastAPI SSE (Server-Sent Events) for real-time chat responses
4. Add token counting + cost tracking per session
5. **Verify:** Chat with streaming, confirm tokens counted, confirm Ollama handles 80%+

### Phase 10 — Personality + Skills Polish + Final Integration
1. `personality/model.py` — port Jarvis's personality learner to Python
2. Wire Sam's Antigravity 600+ skills into the FastAPI skill endpoint
3. Full integration test: start daemon, open dashboard, use orb, run complex multi-step task
4. Performance benchmarks: tokens per session Sam(old) vs Jarvis vs Sam(new)
5. **Verify:** All 12 verification checks below pass

---

## Token Efficiency Rules (enforced by architecture)

| Task Type | LLM Used | Rationale |
|-----------|----------|-----------|
| File operations, app launch, media control | No LLM (direct code) | Pure Python, zero tokens |
| System monitoring, git ops, screenshot | No LLM (direct code) | Pure Python, zero tokens |
| Intent detection (known intent) | Ollama (local) | Cheap, private, fast |
| Code generation | Ollama (Codellama/Qwen) | Local code model |
| WhatsApp reply drafting | Ollama (local) | Private messaging |
| Complex reasoning, research | Cloud LLM (Anthropic/OpenAI) | Only when needed |
| Multi-agent orchestration | Ollama for routing, cloud for execution | Hybrid |
| Streaming chat response | Ollama default, cloud opt-in | User controls |

---

## Final Verification Checklist

- [ ] Daemon boots: `python daemon/main.py` → health endpoint returns 200
- [ ] Dashboard loads: `http://localhost:3142` → all 15 pages render with emerald theme
- [ ] Orb works: launches, breathing animation plays, click opens dashboard
- [ ] Voice works: Ctrl+Alt+S → orb activates → speech recognized → response spoken
- [ ] Chat streams: type in dashboard chat → streaming response appears progressively
- [ ] Actions work: "Search for X", "Open Chrome", "Write a file" → execute correctly
- [ ] Multi-agent: "Plan my week" → orchestrator delegates to COS + planner agents
- [ ] Visual tools: "Show me the screen" → screenshot appears in dashboard live panel
- [ ] SQLite persists: restart daemon → conversation history, tasks, goals still present
- [ ] Token audit: run 10 common tasks, total tokens < 50% of Jarvis baseline
- [ ] Channels: send a Telegram message → Sam responds
- [ ] Authority: trigger a level-3 action → approval prompt fires in dashboard
