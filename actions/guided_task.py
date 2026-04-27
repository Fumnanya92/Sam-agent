"""
actions/guided_task.py — SAM CO-PILOT core logic.

Functions:
  generate_task_steps      — LLM generates a 5-8 step plan (text-only API call)
  verify_step_completion   — Vision AI checks if a step is done in a screenshot
  _parse_verification_result — Parses CONFIRMED:/NOT YET: prefix, heuristic fallback
"""
import json


def generate_task_steps(task_description: str) -> list[str]:
    """
    Ask the LLM to break the user's task into 5-8 clear, ordered steps.
    Returns a list of non-empty step strings.
    Raises RuntimeError if the LLM response contains no valid JSON array.
    """
    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        "You are Sam, a practical AI co-pilot guiding a user through a computer task step by step.\n"
        "Generate 5 to 8 ordered steps to complete the given task.\n"
        "Rules:\n"
        "  - Each step is one clear, actionable sentence (click X, type Y, navigate to Z).\n"
        "  - Target non-technical users — use plain language.\n"
        "  - Return ONLY a JSON array of strings. No preamble, no markdown fences.\n"
        'Example: ["Open Chrome and go to forms.google.com", '
        '"Click the Blank form option with the plus icon", '
        '"Click Add question to start building your form"]'
    )
    user_prompt = (
        f"Generate 5 to 8 step-by-step computer instructions to complete this task: "
        f"{task_description}"
    )

    raw = agent_llm_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        require_json=False,   # parse manually — LLM sometimes wraps in fences
    )

    # Strip markdown code fences if LLM included them
    clean = raw.strip()
    if clean.startswith("```"):
        clean = "\n".join(
            line for line in clean.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    # Extract the JSON array from the response
    start = clean.find("[")
    end   = clean.rfind("]")
    if start == -1 or end <= start:
        raise RuntimeError(
            f"generate_task_steps: no JSON array in LLM response: {clean[:200]}"
        )

    steps = json.loads(clean[start : end + 1])
    if not isinstance(steps, list) or not steps:
        raise RuntimeError("generate_task_steps: LLM returned empty or invalid step list")

    return [str(s).strip() for s in steps if str(s).strip()]


def verify_step_completion(
    step_text: str,
    step_num: int,
    total_steps: int,
    image_b64: str,
) -> tuple[bool, str]:
    """
    Send the screenshot to GPT-4o vision and ask whether the step was completed.

    Constraint: need_vision=True forces require_json=False inside agent_llm_call.
    The system prompt engineers a "CONFIRMED:" / "NOT YET:" prefix so parsing
    is deterministic.

    Returns: (is_complete, feedback_sentence)
    """
    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        f"You are Sam's vision verification module.\n"
        f"The user is working on step {step_num} of {total_steps}: \"{step_text}\"\n"
        f"Analyze the screenshot and determine if this step has been completed.\n"
        f"IMPORTANT: You MUST begin your response with exactly 'CONFIRMED:' if the step "
        f"is visibly done, or exactly 'NOT YET:' if it is not yet complete.\n"
        f"After the prefix, write ONE sentence describing what you see on screen "
        f"that led to your conclusion. Be specific."
    )
    user_prompt = (
        f"Has the user completed step {step_num}: '{step_text}'? "
        f"Start with CONFIRMED: or NOT YET: then describe what you see."
    )

    vision_text = agent_llm_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        need_vision=True,
        image_b64=image_b64,
    )

    return _parse_verification_result(vision_text)


def _parse_verification_result(vision_text: str) -> tuple[bool, str]:
    """
    Parse the vision AI response.
    Primary: looks for CONFIRMED: or NOT YET: prefix.
    Fallback: keyword heuristic for when the model ignores the prefix instruction.
    """
    text  = (vision_text or "").strip()
    upper = text.upper()

    if upper.startswith("CONFIRMED:"):
        return True,  text[len("CONFIRMED:"):].strip()

    if upper.startswith("NOT YET:"):
        return False, text[len("NOT YET:"):].strip()

    # Fallback keyword heuristic
    lower   = text.lower()
    POSITIVE = ["can see", "is open", "shows", "completed", "done",
                "successfully", "visible on screen", "has been done", "i can confirm"]
    NEGATIVE = ["not yet", "don't see", "doesn't appear", "cannot see", "can't see",
                "no sign", "not visible", "not complete", "still on", "not done",
                "hasn't been", "unable to confirm"]

    pos = sum(1 for s in POSITIVE if s in lower)
    neg = sum(1 for s in NEGATIVE if s in lower)
    return (pos >= neg), text
