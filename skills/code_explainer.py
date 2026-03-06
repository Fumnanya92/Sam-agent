"""
skills/code_explainer.py — Explain code from clipboard or screen vision.

Reads code from clipboard, sends it to the LLM with an explanation-focused prompt.
Returns a concise verbal explanation — what Sam will speak aloud.

Trigger phrases:
  "explain this code"  /  "what does this do"  /  "explain that function"  /
  "break this down"  /  "what is this code doing"
"""

from __future__ import annotations
from typing import Any

_SYSTEM_PROMPT = (
    "You are a senior developer giving a clear, spoken explanation to a colleague. "
    "Explain what the code does in plain English, in 2–4 sentences max. "
    "Mention the key logic and purpose — no markdown, no code blocks in your answer. "
    "Speak as if you're explaining it out loud."
)


def _run(parameters: dict, ui: Any, **ctx) -> str:
    # Step 1: Get code from clipboard
    code = _read_clipboard()

    if not code or len(code.strip()) < 10:
        return (
            "I couldn't find code on your clipboard. "
            "Copy the code you want explained, then ask me again."
        )

    if len(code) > 4000:
        code = code[:4000] + "\n# (truncated)"

    # Step 2: Send to LLM for plain-text explanation
    explanation = _explain_via_llm(code)
    if not explanation:
        return "I wasn't able to explain that piece of code right now — try again."

    # Step 3: Show in UI log
    ui.write_log(f"[CodeExplainer]\n{explanation}")

    return explanation


def _read_clipboard() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _explain_via_llm(code: str) -> str:
    try:
        import os, requests
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            from llm import get_openai_key
            api_key = get_openai_key()
        if not api_key:
            return ""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Explain this code:\n\n{code}"},
            ],
            "temperature": 0.2,
            "max_tokens": 250,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload, timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""


SKILL_MANIFEST = {
    "name": "code_explainer",
    "description": "Explain what a code snippet does in plain English",
    "intents": ["code_explainer", "explain_code", "explain_this"],
    "trigger_phrases": [
        "explain this code",
        "explain that function",
        "what does this code do",
        "what is this doing",
        "break this down",
        "explain this to me",
        "what does this function do",
    ],
    "run": _run,
}
