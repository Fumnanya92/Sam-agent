# SAM MASTER ARCHITECTURE PLAN

Vision: Personal JARVIS for the user

CORE OBJECTIVE

Sam must become:

- A second brain
- A system automation assistant
- A productivity commander
- A proactive presence

He evolves gradually. No overload. Layered intelligence.

OVERALL SYSTEM ARCHITECTURE

Sam consists of 6 Layers:

- Layer 0 — Infrastructure
- Layer 1 — Memory Core
- Layer 2 — Conversation Intelligence
- Layer 3 — Productivity Engine
- Layer 4 — Automation Engine
- Layer 5 — Strategic Autonomy

We build in this exact order.

PHASE 0 — Infrastructure (DONE)

- UI working
- WebSocket STT working
- OpenAI LLM working
- TTS working
- Conversation loop stable

Do NOT modify unless broken.

PHASE 1 — MEMORY CORE (Foundation)

Goal:

Sam remembers you and your world.

Build:

1.1 Expand Memory Schema

Memory structure (JSON):

```json
{
  "identity": {},
  "preferences": {},
  "relationships": {},
  "emotional_state": {},
  "goals": {},
  "projects": {},
  "tasks": {},
  "automation_preferences": {},
  "daily_state": {}
}
```

1.2 Strengthen LLM Prompt

- Inject memory as structured JSON into prompts when relevant.
- Enforce disciplined memory updates (explicit update commands; sanitize inputs).
- Prevent storing junk (validation + heuristics).

1.3 Identity Memory

Sam must correctly store:
- Name
- Primary project
- Long-term goal
- Character aspiration
- Current blockers

1.4 Recall Test

Sam must answer:
- What is my main project?
- What is my long-term goal?
- What are my blockers?

If these fail, Phase 1 is incomplete.

PHASE 2 — CONVERSATION INTELLIGENCE

Goal:

Sam becomes context-aware.

2.1 Short-Term Context Buffer

- Store last 5–10 messages in RAM as the short-term buffer.

2.2 Reference Understanding

Sam must resolve references like:
- "him"
- "continue from yesterday"
- "fix that bug"

2.3 Daily State Tracking

Store:
- last_focus
- last_briefing_date
- today_priority
- unfinished_tasks

PHASE 3 — MORNING BRIEFING SYSTEM

Goal:

Sam becomes proactive.

3.1 Scheduled 7AM Check

- If running, deliver briefing once per day.

3.2 Briefing Structure

- Greeting
- Primary project
- Yesterday’s focus
- Today’s priority question

PHASE 4 — PRODUCTIVITY ENGINE

Goal:

Sam reduces your mental load.

4.1 Task System

Allow:
- "Add task"
- "Mark task done"
- "What’s pending?"

4.2 Focus Mode

Command: Work mode
Actions:
- Launch dev tools
- Silence notifications (future)
- Start focus timer

4.3 Daily Shutdown Summary

- At shutdown: summarize progress, store summary, prepare next day focus

PHASE 5 — AUTOMATION ENGINE

Goal:

Sam operates systems.

5.1 WhatsApp Automation

- Send messages
- Read messages (future)
- Announce notifications

5.2 App Control

- Open apps
- Switch focus
- Launch project workspace

5.3 File Intelligence

- Organize folders
- Search local files
- Monitor logs

PHASE 6 — STRATEGIC AUTONOMY

Goal:

Sam thinks ahead.

6.1 Weekly Review

- Auto summary of progress, tasks completed, missed priorities

6.2 Suggest High-Leverage Actions

- Project-aware suggestions

6.3 Learning From Transcripts

- Ingest transcripts, extract insights, update memory

DEVELOPMENT RULES

- Never skip phases.
- Never overload features.
- One stable layer at a time.
- Each phase must be testable.
- Every phase must improve usefulness.

CURRENT POSITION

- Infrastructure ✅
- Starting Phase 1

NOW WE RESTART PROPERLY

We go back to: PHASE 1 — MEMORY CORE

Step 1: Confirm memory schema expansion.
Step 2: Update LLM memory injection.
Step 3: Test identity storage.
Step 4: Test recall accuracy.

No scheduler. No automation. No tasks. Just memory.

---

Next actions (recommended):
1. Implement expanded memory schema in `memory/memory_manager.py`.
2. Add a short-term buffer in `memory/temporary_memory.py` for recent messages.
3. Add APIs: `get_memory()`, `update_memory(path, value)`, `query_memory(key)`.
4. Update `llm.py` to accept `memory_block` and inject structured memory into prompts.
5. Add unit tests for identity memory (store/retrieve) and context buffer.

I will implement the memory schema and `User Profile Memory` (identity store + recall test) next unless you want adjustments.
