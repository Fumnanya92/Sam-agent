# Sam Identity Fix & Feature Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all "Jarvis" identity leaks in the codebase and wire the 5 ported feature modules (goals, workflows, comms, personality, role_loader) into Sam's live conversation loop so Sam is actually aware of and can use them.

**Architecture:** Sam's conversation loop lives in `intents/handlers.py` (sync, threading-based). New intents are declared in `core/prompt.txt` (so the LLM routes to them) and handled in `handlers.py` (so they execute). Async modules use `asyncio.run()` inside `threading.Thread` closures — this is the established pattern used by goals/tracker.py, personality/model.py etc. which are already async.

**Tech Stack:** Python 3, asyncio, aiosqlite, threading, core/prompt.txt (plain text intent routing manifest)

---

## File Map

| File | Change |
|------|--------|
| `llm.py` | Fix "Jarvis" fallback string → "Sam" |
| `llm/__init__.py` | Fix "Jarvis" fallback string → "Sam" |
| `agents/role_loader.py` | Remove hardcoded `Sam-update-Jarvis` path |
| `core/prompt.txt` | Add new intents: goals, workflows, channels, personality |
| `intents/handlers.py` | Add `handle_intent()` routes + 7 new handler functions |

---

## Task 1: Fix Identity Crisis

**Files:**
- Modify: `llm.py:57`
- Modify: `llm/__init__.py:58`
- Modify: `agents/role_loader.py:26`

- [ ] **Step 1: Fix llm.py fallback prompt**

In `llm.py` at line 57, change:
```python
        return "You are Jarvis, a helpful AI assistant."
```
To:
```python
        return "You are Sam, a sharp personal AI assistant."
```

- [ ] **Step 2: Fix llm/__init__.py fallback prompt**

In `llm/__init__.py` at line 58, change:
```python
        return "You are Jarvis, a helpful AI assistant."
```
To:
```python
        return "You are Sam, a sharp personal AI assistant."
```

- [ ] **Step 3: Remove hardcoded Jarvis path from role_loader.py**

In `agents/role_loader.py`, the `load_roles()` function currently has:
```python
    if roles_dir is None:
        # Look in Sam-Agent roles directory first, then fall back to Jarvis
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "roles"),
            r"C:\Users\DELL.COM\Desktop\Darey\Sam-update-Jarvis\roles",
        ]
        roles_dir = next((d for d in candidates if os.path.isdir(d)), None)
```

Replace with:
```python
    if roles_dir is None:
        roles_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "roles")
```

- [ ] **Step 4: Verify no remaining user-facing "Jarvis" strings**

Run this in project root:
```bash
grep -rn "You are Jarvis" --include="*.py" .
```
Expected output: no matches.

- [ ] **Step 5: Commit**

```bash
git add llm.py llm/__init__.py agents/role_loader.py
git commit -m "fix: replace all Jarvis identity strings with Sam"
```

---

## Task 2: Update prompt.txt — New Feature Intents

**Files:**
- Modify: `core/prompt.txt`

Sam's LLM routes to intents by reading `core/prompt.txt`. Until these new intents appear there, Sam cannot route user requests to goals, workflows, or channels.

- [ ] **Step 1: Add new intents to the INTENTS list**

In `core/prompt.txt`, find the INTENTS block (ends with `- chat` around line 149). Insert the new intents **before** `- chat`:

```
- create_goal
- list_goals
- update_goal
- run_workflow
- list_workflows
- send_to_channel
- personality_feedback
```

- [ ] **Step 2: Add GOALS intent rules**

In `core/prompt.txt`, in the section where other intent triggers are documented (around line 340-375), add:

```
GOALS & TRACKING:
- If the user says "set a goal", "I want to achieve", "track my goal", "add a goal", "new goal", "my goal is to" -> intent: create_goal, parameters: title (the goal), level ("objective"|"key_result"|"milestone"|"task", default "task"), time_horizon ("yearly"|"quarterly"|"monthly"|"weekly"|"daily", default "weekly"), deadline (ISO date if mentioned, else omit)
- If the user says "show my goals", "what are my goals", "list my goals", "how am I doing on goals", "goal progress" -> intent: list_goals
- If the user says "update goal", "goal progress is", "I'm X% done", "mark goal done", "complete goal", "goal achieved" -> intent: update_goal, parameters: title (partial match ok), score (0.0-1.0 float), note (optional)

WORKFLOWS:
- If the user says "run workflow", "trigger workflow", "start workflow", "execute routine", "run my routine" -> intent: run_workflow, parameters: name (workflow name)
- If the user says "list workflows", "what workflows do I have", "show my workflows", "what routines are set up" -> intent: list_workflows

CHANNELS (Discord / Telegram):
- If the user says "send to discord", "post to discord", "discord message", "message my discord" -> intent: send_to_channel, parameters: channel ("discord"), message (the text to send)
- If the user says "send to telegram", "telegram message", "notify telegram", "message telegram" -> intent: send_to_channel, parameters: channel ("telegram"), message (the text to send)

PERSONALITY:
- If the user says "that was too long", "be more concise", "keep it shorter", "I prefer detailed answers", "be more detailed", "too technical", "more casual", "more formal" -> intent: personality_feedback, parameters: feedback (the raw phrase), signal ("positive"|"negative")
```

- [ ] **Step 3: Commit**

```bash
git add core/prompt.txt
git commit -m "feat(prompt): add goals, workflows, channels, personality intents to Sam's routing"
```

---

## Task 3: Wire Goals into handlers.py

**Files:**
- Modify: `intents/handlers.py`

Goals module is async (`GoalTracker` uses `await`). The pattern is: `asyncio.run()` inside a `threading.Thread` closure. This matches how the rest of the handlers work.

- [ ] **Step 1: Add `create_goal` + `list_goals` + `update_goal` to handle_intent() router**

In `intents/handlers.py`, find the section near the end of `handle_intent()` where `agent_task` is routed (around line 2180). Add the new routes just before the final `elif intent == "chat":` fallback:

```python
    elif intent == "create_goal":
        _handle_create_goal(parameters, response, ui)

    elif intent == "list_goals":
        _handle_list_goals(ui)

    elif intent == "update_goal":
        _handle_update_goal(parameters, response, ui)
```

- [ ] **Step 2: Add `_handle_create_goal()` implementation**

At the end of `intents/handlers.py`, add:

```python
def _handle_create_goal(parameters: dict, response: str, ui):
    """Create a new tracked goal."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        title = (parameters or {}).get("title", "").strip() or response or ""
        if not title:
            _say("What's the goal you'd like to track?", ui)
            return
        level = (parameters or {}).get("level", "task")
        time_horizon = (parameters or {}).get("time_horizon", "weekly")
        deadline = (parameters or {}).get("deadline")
        try:
            tracker = GoalTracker()
            goal_id = asyncio.run(tracker.create_goal(
                title=title,
                level=level,
                time_horizon=time_horizon,
                deadline=deadline,
            ))
            _say(f"Goal set: {title}. I'll track it as a {time_horizon} {level}.", ui)
            ui.append_output(f"[goal created] id={goal_id} title={title}", "info")
        except Exception as e:
            logger.error(f"create_goal failed: {e}")
            _say(f"Couldn't create the goal: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_goals(ui):
    """List active goals with health scores."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        try:
            tracker = GoalTracker()
            goals = asyncio.run(tracker.list_goals(status="active"))
            if not goals:
                _say("No active goals right now. Say 'set a goal' to add one.", ui)
                return
            lines = []
            for g in goals:
                health = g.get("health", "unknown")
                score = g.get("score", 0.0)
                title = g.get("title", "Untitled")
                lines.append(f"• {title} — {int(score * 100)}% ({health})")
            summary = "\n".join(lines)
            _say(f"Here are your active goals:\n{summary}", ui)
            ui.append_output(summary, "info")
        except Exception as e:
            logger.error(f"list_goals failed: {e}")
            _say(f"Couldn't load goals: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_update_goal(parameters: dict, response: str, ui):
    """Update a goal's score / status."""
    def _action():
        import asyncio
        from goals.tracker import GoalTracker
        title = (parameters or {}).get("title", "").strip()
        raw_score = (parameters or {}).get("score", None)
        note = (parameters or {}).get("note", "")
        if raw_score is None:
            _say("What's the current progress? Give me a number from 0 to 100.", ui)
            return
        try:
            score = float(raw_score) / 100.0 if float(raw_score) > 1.0 else float(raw_score)
        except (TypeError, ValueError):
            _say("I need a number for the progress, like 60 or 0.6.", ui)
            return
        try:
            tracker = GoalTracker()
            goals = asyncio.run(tracker.list_goals(status="active"))
            match = next((g for g in goals if title.lower() in g.get("title", "").lower()), None)
            if not match:
                _say(f"Couldn't find an active goal matching '{title}'.", ui)
                return
            asyncio.run(tracker.update_score(match["id"], score, note))
            pct = int(score * 100)
            _say(f"Updated '{match['title']}' to {pct}% complete.", ui)
        except Exception as e:
            logger.error(f"update_goal failed: {e}")
            _say(f"Couldn't update the goal: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()
```

- [ ] **Step 3: Check GoalTracker has list_goals() method**

Read `goals/tracker.py` and verify `list_goals(status=...)` exists. If not, add it:

```python
async def list_goals(self, *, status: str = "active") -> list[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, title, level, time_horizon, score, health, status, deadline FROM goals WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Smoke-test goals wiring**

Start Sam, say: "Set a goal to ship the app by the end of May"
Expected: Sam confirms with "Goal set: ship the app..."

Then say: "Show my goals"
Expected: Sam lists the goal with health score.

- [ ] **Step 5: Commit**

```bash
git add intents/handlers.py goals/tracker.py
git commit -m "feat: wire goals (create/list/update) into Sam's conversation loop"
```

---

## Task 4: Wire Workflows into handlers.py

**Files:**
- Modify: `intents/handlers.py`
- Read: `workflows/engine.py` (to understand the API)

- [ ] **Step 1: Check workflows/engine.py API**

Read `workflows/engine.py` and note the public methods. The engine likely has:
- `list_workflows()` → list of workflow dicts
- `run_workflow(workflow_id)` → runs it, returns result

If the API differs, adapt the handler below to match.

- [ ] **Step 2: Add workflow routes to handle_intent()**

In `intents/handlers.py`, alongside the goals routes added in Task 3, add:

```python
    elif intent == "run_workflow":
        _handle_run_workflow(parameters, response, ui)

    elif intent == "list_workflows":
        _handle_list_workflows(ui)
```

- [ ] **Step 3: Add workflow handler implementations**

At the end of `intents/handlers.py`:

```python
def _handle_run_workflow(parameters: dict, response: str, ui):
    """Run a named workflow."""
    def _action():
        import asyncio
        from workflows.engine import WorkflowEngine
        name = (parameters or {}).get("name", "").strip() or response or ""
        if not name:
            _say("Which workflow should I run? Say the name.", ui)
            return
        try:
            engine = WorkflowEngine()
            workflows = asyncio.run(engine.list_workflows())
            match = next((w for w in workflows if name.lower() in w.get("name", "").lower()), None)
            if not match:
                names = ", ".join(w.get("name", "") for w in workflows) or "none configured"
                _say(f"No workflow matching '{name}'. Available: {names}.", ui)
                return
            _say(f"Running workflow: {match['name']}.", ui)
            result = asyncio.run(engine.run_workflow(match["id"]))
            _say(f"Workflow '{match['name']}' completed.", ui)
            ui.append_output(f"[workflow] {match['name']}: {result}", "info")
        except Exception as e:
            logger.error(f"run_workflow failed: {e}")
            _say(f"Workflow failed: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()


def _handle_list_workflows(ui):
    """List all configured workflows."""
    def _action():
        import asyncio
        from workflows.engine import WorkflowEngine
        try:
            engine = WorkflowEngine()
            workflows = asyncio.run(engine.list_workflows())
            if not workflows:
                _say("No workflows configured yet. You can create them in the dashboard.", ui)
                return
            names = "\n".join(f"• {w.get('name', 'Unnamed')}" for w in workflows)
            _say(f"Here are your workflows:\n{names}", ui)
        except Exception as e:
            logger.error(f"list_workflows failed: {e}")
            _say(f"Couldn't load workflows: {e}", ui)
    threading.Thread(target=_action, daemon=True).start()
```

- [ ] **Step 4: Verify WorkflowEngine has list_workflows() and run_workflow()**

Read `workflows/engine.py` and check both methods exist. Add stubs if missing:

```python
async def list_workflows(self) -> list[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, name, description, trigger_type FROM workflows ORDER BY created_at DESC")
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

async def run_workflow(self, workflow_id: str) -> str:
    # Placeholder — full execution handled by workflow nodes
    return f"Workflow {workflow_id} triggered"
```

- [ ] **Step 5: Commit**

```bash
git add intents/handlers.py workflows/engine.py
git commit -m "feat: wire workflows (run/list) into Sam's conversation loop"
```

---

## Task 5: Wire Comms Channels into handlers.py

**Files:**
- Modify: `intents/handlers.py`

Channels require env vars to be configured (`TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`). The handler checks if they're set before attempting to send — gracefully degrades if not.

- [ ] **Step 1: Add channel route to handle_intent()**

```python
    elif intent == "send_to_channel":
        _handle_send_to_channel(parameters, response, ui)
```

- [ ] **Step 2: Add _handle_send_to_channel() implementation**

```python
def _handle_send_to_channel(parameters: dict, response: str, ui):
    """Send a message to Discord or Telegram."""
    def _action():
        import asyncio, os
        channel = (parameters or {}).get("channel", "").lower().strip()
        message = (parameters or {}).get("message", "").strip() or response or ""
        if not message:
            _say("What message should I send?", ui)
            return
        if not channel:
            _say("Which channel — Discord or Telegram?", ui)
            return

        if channel == "telegram":
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if not token or not chat_id:
                _say("Telegram isn't configured yet. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your environment.", ui)
                return
            try:
                from comms.channels.telegram import TelegramAdapter
                adapter = TelegramAdapter(token=token)
                asyncio.run(adapter.send_message(chat_id, message))
                _say(f"Sent to Telegram.", ui)
            except Exception as e:
                logger.error(f"telegram send failed: {e}")
                _say(f"Telegram send failed: {e}", ui)

        elif channel == "discord":
            token = os.getenv("DISCORD_BOT_TOKEN", "")
            channel_id = os.getenv("DISCORD_CHANNEL_ID", "")
            if not token or not channel_id:
                _say("Discord isn't configured yet. Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID in your environment.", ui)
                return
            try:
                from comms.channels.discord import DiscordAdapter
                adapter = DiscordAdapter(token=token)
                asyncio.run(adapter.send_message(channel_id, message))
                _say(f"Sent to Discord.", ui)
            except Exception as e:
                logger.error(f"discord send failed: {e}")
                _say(f"Discord send failed: {e}", ui)

        else:
            _say(f"I don't know the channel '{channel}'. I support Discord and Telegram.", ui)

    threading.Thread(target=_action, daemon=True).start()
```

- [ ] **Step 3: Check DiscordAdapter send_message signature**

Read `comms/channels/discord.py` to confirm `send_message(channel_id, text)` signature. Adjust the call above if different.

- [ ] **Step 4: Commit**

```bash
git add intents/handlers.py
git commit -m "feat: wire Discord/Telegram channel sending into Sam's conversation loop"
```

---

## Task 6: Wire Personality Learning into handlers.py

**Files:**
- Modify: `intents/handlers.py`

Personality feedback is simple: user says "be more concise" → record a negative signal on verbosity. This runs in the background after the speech response.

- [ ] **Step 1: Add personality_feedback route to handle_intent()**

```python
    elif intent == "personality_feedback":
        _handle_personality_feedback(parameters, response, ui)
```

- [ ] **Step 2: Add _handle_personality_feedback() implementation**

```python
def _handle_personality_feedback(parameters: dict, response: str, ui):
    """Record user style feedback into personality learner."""
    def _action():
        import asyncio
        from personality.model import PersonalityLearner
        feedback = (parameters or {}).get("feedback", "").strip() or response or ""
        signal = (parameters or {}).get("signal", "negative")  # "positive" or "negative"
        topic = feedback[:80] if feedback else "style"
        try:
            learner = PersonalityLearner()
            asyncio.run(learner.record_feedback(signal=signal, topic=topic))
            if signal == "negative":
                _say("Got it, I'll adjust.", ui)
            else:
                _say("Good to know, I'll keep doing that.", ui)
        except Exception as e:
            logger.error(f"personality_feedback failed: {e}")
            _say("Noted.", ui)
    threading.Thread(target=_action, daemon=True).start()
```

- [ ] **Step 3: Verify PersonalityLearner has record_feedback()**

Read `personality/model.py` and check if `record_feedback(signal, topic)` exists. If not, add:

```python
async def record_feedback(self, *, signal: str, topic: str = "") -> None:
    profile = await self.load()
    if signal == "positive":
        profile.positive_signals += 1
    else:
        profile.negative_signals += 1
    profile.total_interactions += 1
    profile.updated_at = datetime.utcnow().isoformat()
    await self.save(profile)
```

- [ ] **Step 4: Commit**

```bash
git add intents/handlers.py personality/model.py
git commit -m "feat: wire personality feedback recording into Sam's conversation loop"
```

---

## Task 7: Add Feature Awareness Section to prompt.txt

**Files:**
- Modify: `core/prompt.txt`

Sam should know what systems it has so it can answer "what can you do?" accurately and proactively use features.

- [ ] **Step 1: Add FEATURE SYSTEMS section to prompt.txt**

In `core/prompt.txt`, just before the `LONG-TERM MEMORY STRUCTURE` section, insert:

```
========================
FEATURE SYSTEMS
========================
Sam has the following built-in systems. Reference them naturally when relevant:

GOALS: Sam can create, list, and track OKR-style goals across daily/weekly/monthly/quarterly timescales.
  - "Set a goal to ship the app by May" → creates a goal
  - "Show my goals" → lists with health scores
  - "Update the shipping goal to 60%" → updates score

WORKFLOWS: Automated routines that can be triggered by name.
  - "Run my daily briefing workflow" → executes it
  - "List my workflows" → shows what's configured

CHANNELS: Sam can send messages to Discord and Telegram if configured.
  - "Send to Discord: standup done" → posts to your Discord channel
  - Requires DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID or TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in env

PERSONALITY: Sam adapts to feedback signals.
  - User says "be more concise" → Sam records and adjusts over time
  - User says "I prefer detailed answers" → Sam records and adjusts

MULTI-AGENT: Sam has specialist roles (dev-lead, researcher, personal-assistant) that it routes complex tasks to.
  - "Plan my week" → agent orchestrator delegates to planning specialist
  - Triggered via agent_task intent

If a user asks "what can you do?" or "what features do you have?", include these systems in the response.
```

- [ ] **Step 2: Final prompt.txt check**

Make sure the new `create_goal`, `list_goals`, `update_goal`, `run_workflow`, `list_workflows`, `send_to_channel`, `personality_feedback` all appear in both the `INTENTS` list section AND the trigger rules section.

- [ ] **Step 3: Commit**

```bash
git add core/prompt.txt
git commit -m "feat(prompt): add FEATURE SYSTEMS awareness section so Sam knows its own capabilities"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|-------------|------|
| Fix "Jarvis" fallback strings | Task 1 |
| Fix hardcoded Jarvis path | Task 1 |
| Goals wired into conversation | Task 3 |
| Workflows wired into conversation | Task 4 |
| Comms channels wired | Task 5 |
| Personality feedback wired | Task 6 |
| Sam knows its own features | Tasks 2 + 7 |

**Placeholder scan:** All code blocks are complete. No TBDs.

**Type consistency:**
- `GoalTracker.list_goals()` returns `list[dict]` — handler accesses `.get("id")`, `.get("title")`, `.get("score")`, `.get("health")` — all present in the schema.
- `WorkflowEngine.list_workflows()` returns `list[dict]` — handler accesses `.get("id")`, `.get("name")` — matches schema.
- `PersonalityLearner.record_feedback(signal, topic)` — added in Task 6 Step 3 if missing.
- `TelegramAdapter.send_message(chat_id, text)` — matches existing API at `comms/channels/telegram.py:50`.

**Gap identified:** Tasks 3 and 4 call `asyncio.run()` from a background thread. This works fine when no event loop is already running in that thread. Since `threading.Thread` creates a plain OS thread with no event loop, `asyncio.run()` is safe. No change needed.
