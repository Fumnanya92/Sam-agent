# agent/planner.py
# AI task planner for Sam's agent layer.
# Adapted from Mark-XXX-main: Gemini replaced with agent/llm_bridge.py

import json
import re


PLANNER_PROMPT = """You are the planning module of Sam, a personal AI assistant.
Your job: break any user goal into a sequence of steps using ONLY the tools listed below.

RULES:
- Max 5 steps. Use the minimum steps needed.
- Use web_search for ANY information retrieval or research.
- Use file_controller to save content to disk.
- Use cmd_control to open files or run system commands.
- Never reference previous step results in parameters. Every step is independent.

AVAILABLE TOOLS:

open_app           : app_name: string
web_search         : query: string, mode: "search"|"compare" (optional)
browser_control    : action: "go_to"|"search"|"click"|"type"|"scroll"|"get_text"|"press"|"close", url/query/text (as needed)
file_controller    : action: "write"|"create_file"|"read"|"list"|"delete"|"move"|"copy"|"find"|"disk_usage", path, name, content
cmd_control        : task: string (natural language)
computer_settings  : action: string, description: string, value: string (optional)
computer_control   : action: "type"|"click"|"hotkey"|"press"|"scroll"|"screenshot"|"screen_find"|"screen_click", text/x/y/keys/description (as needed)
send_message       : receiver: string, message_text: string, platform: string
set_reminder       : date: YYYY-MM-DD, time: HH:MM, message: string
desktop_control    : action: "wallpaper"|"organize"|"clean"|"list"|"stats", path/mode (optional)
youtube_video      : action: "play"|"summarize"|"trending", query: string (for play)
weather_report     : city: string
find_flights       : origin: string, destination: string, date: string, return_date: string (optional)
code_helper        : action: "write"|"edit"|"run"|"explain"|"build"|"optimize"|"screen_debug", description: string, language/file_path (optional)
build_project      : description: string, language: string (optional)

OUTPUT — return ONLY valid JSON (no markdown, no explanation):
{
  "goal": "...",
  "steps": [
    {
      "step": 1,
      "tool": "tool_name",
      "description": "what this step does",
      "parameters": {},
      "critical": true
    }
  ]
}
"""


def create_plan(goal: str, context: str = "") -> dict:
    from agent.llm_bridge import agent_llm_call

    user_input = f"Goal: {goal}"
    if context:
        user_input += f"\n\nContext: {context}"

    try:
        text = agent_llm_call(PLANNER_PROMPT, user_input, require_json=True)
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        plan = json.loads(text)

        if "steps" not in plan or not isinstance(plan["steps"], list):
            raise ValueError("Invalid plan structure")

        print(f"[Planner] plan: {len(plan['steps'])} steps")
        for s in plan["steps"]:
            print(f"  Step {s['step']}: [{s['tool']}] {s['description']}")

        return plan

    except json.JSONDecodeError as e:
        print(f"[Planner] JSON parse failed: {e}")
        return _fallback_plan(goal)
    except Exception as e:
        print(f"[Planner] planning failed: {e}")
        return _fallback_plan(goal)


def _fallback_plan(goal: str) -> dict:
    print("[Planner] using fallback plan (web_search)")
    return {
        "goal":  goal,
        "steps": [
            {
                "step":        1,
                "tool":        "web_search",
                "description": f"Search for: {goal}",
                "parameters":  {"query": goal},
                "critical":    True,
            }
        ],
    }


def replan(goal: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    from agent.llm_bridge import agent_llm_call

    completed_summary = "\n".join(
        f"  - Step {s['step']} ({s['tool']}): DONE" for s in completed_steps
    )

    prompt = f"""Goal: {goal}

Already completed:
{completed_summary if completed_summary else '  (none)'}

Failed step: [{failed_step.get('tool')}] {failed_step.get('description')}
Error: {error}

Create a REVISED plan for the remaining work only. Do not repeat completed steps."""

    try:
        text = agent_llm_call(PLANNER_PROMPT, prompt, require_json=True)
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        plan = json.loads(text)
        print(f"[Planner] revised plan: {len(plan.get('steps', []))} steps")
        return plan
    except Exception as e:
        print(f"[Planner] replan failed: {e}")
        return _fallback_plan(goal)
