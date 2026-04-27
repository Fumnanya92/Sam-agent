# agent/error_handler.py
# Error recovery module for Sam's agent layer.
# Adapted from Mark-XXX-main: Gemini replaced with agent/llm_bridge.py

import json
import re
from enum import Enum


class ErrorDecision(Enum):
    RETRY  = "retry"
    SKIP   = "skip"
    REPLAN = "replan"
    ABORT  = "abort"


ERROR_ANALYST_PROMPT = """You are an error recovery module for an AI assistant.

A task step has failed. Analyze the error and decide what to do.

DECISIONS:
- retry   : Transient error (network timeout, temporary file lock). Same step can succeed if retried.
- skip    : Step is not critical; task can succeed without it.
- replan  : Wrong approach. A different tool or method should be tried.
- abort   : Task is fundamentally impossible or unsafe to continue.

Return ONLY valid JSON (no markdown, no explanation):
{
  "decision": "retry|skip|replan|abort",
  "reason": "why it failed in one sentence",
  "fix_suggestion": "what to try instead (for replan only)",
  "max_retries": 1,
  "user_message": "Short message to tell the user (max 15 words)"
}
"""


def analyze_error(step: dict, error: str, attempt: int = 1, max_attempts: int = 2) -> dict:
    """Analyze a failed step and return a recovery decision."""
    from agent.llm_bridge import agent_llm_call

    if attempt >= max_attempts:
        print(f"[ErrorHandler] max attempts reached for step {step.get('step')} — forcing replan")
        return {
            "decision":       ErrorDecision.REPLAN,
            "reason":         f"Failed {attempt} times: {error[:100]}",
            "fix_suggestion": "Try a completely different approach or tool",
            "max_retries":    0,
            "user_message":   "Trying a different approach.",
        }

    prompt = f"""Failed step:
Tool: {step.get('tool')}
Description: {step.get('description')}
Parameters: {json.dumps(step.get('parameters', {}), indent=2)}
Critical: {step.get('critical', False)}

Error:
{error[:500]}

Attempt number: {attempt}"""

    try:
        text   = agent_llm_call(ERROR_ANALYST_PROMPT, prompt, require_json=True)
        result = json.loads(text)

        dec_map = {
            "retry":  ErrorDecision.RETRY,
            "skip":   ErrorDecision.SKIP,
            "replan": ErrorDecision.REPLAN,
            "abort":  ErrorDecision.ABORT,
        }
        result["decision"] = dec_map.get(
            result.get("decision", "replan").lower(), ErrorDecision.REPLAN
        )

        if step.get("critical") and result["decision"] == ErrorDecision.SKIP:
            result["decision"]     = ErrorDecision.REPLAN
            result["user_message"] = "Critical step failed, finding alternative approach."

        print(f"[ErrorHandler] decision: {result['decision'].value} — {result.get('reason', '')}")
        return result

    except Exception as e:
        print(f"[ErrorHandler] analysis failed: {e} — defaulting to replan")
        return {
            "decision":       ErrorDecision.REPLAN,
            "reason":         str(e),
            "fix_suggestion": "Try an alternative approach",
            "max_retries":    1,
            "user_message":   "Encountered an issue, adjusting approach.",
        }


def generate_fix(step: dict, error: str, fix_suggestion: str) -> dict:
    """Generate a replacement step when replan decision includes a fix suggestion."""
    from agent.llm_bridge import agent_llm_call

    system = (
        "You are an expert Python developer. Write clean, working Python code. "
        "Return ONLY the Python code. No explanation, no markdown, no backticks."
    )
    prompt = f"""A task step failed. Write Python code to accomplish the same goal differently.

Original step:
Tool: {step.get('tool')}
Description: {step.get('description')}
Parameters: {json.dumps(step.get('parameters', {}), indent=2)}

Error: {error[:300]}
Fix suggestion: {fix_suggestion}

Python code:"""

    try:
        code = agent_llm_call(system, prompt)
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        return {
            "step":        step.get("step"),
            "tool":        "code_helper",
            "description": f"Auto-fix for: {step.get('description')}",
            "parameters": {
                "action":      "run",
                "description": fix_suggestion,
                "code":        code,
                "language":    "python",
            },
            "depends_on": step.get("depends_on", []),
            "critical":   step.get("critical", False),
        }
    except Exception as e:
        print(f"[ErrorHandler] fix generation failed: {e}")
        return {
            "step":        step.get("step"),
            "tool":        "code_helper",
            "description": f"Fallback for: {step.get('description')}",
            "parameters":  {"action": "write", "description": step.get("description", "")},
            "depends_on":  step.get("depends_on", []),
            "critical":    step.get("critical", False),
        }
