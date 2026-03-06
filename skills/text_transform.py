"""
skills/text_transform.py — Clipboard text transformation skill.

Reads clipboard text, sends it to the LLM in a focused transform prompt,
writes the result back to clipboard, and speaks a confirmation.

Supported transforms (inferred from intent/parameters):
  summarise    — shorten to key points
  rephrase     — rewrite in cleaner language
  expand       — flesh out to a paragraph
  bullet       — convert to bullet points
  formal       — make professional / formal
  casual       — make conversational / friendly

Trigger phrases:
  "summarise this"  /  "rephrase that"  /  "expand this"  /
  "bullet points"  / "make this formal"  /  "make this casual"
"""

from __future__ import annotations
from typing import Any

_TRANSFORM_PROMPTS = {
    "summarise":  "Summarise the following text into 2–3 concise sentences:",
    "rephrase":   "Rewrite the following text in cleaner, clearer language (same tone):",
    "expand":     "Expand the following into a well-written paragraph:",
    "bullet":     "Convert the following into a concise bullet-point list:",
    "formal":     "Rewrite the following in a professional, formal tone:",
    "casual":     "Rewrite the following in a friendly, conversational tone:",
}

_DEFAULT_TRANSFORM = "rephrase"


def _run(parameters: dict, ui: Any, **ctx) -> str:
    # Determine transform type
    transform = (
        parameters.get("transform")
        or parameters.get("action")
        or _DEFAULT_TRANSFORM
    ).lower()

    if transform not in _TRANSFORM_PROMPTS:
        # Map common synonyms
        synonyms = {
            "shorten": "summarise", "summarize": "summarise",
            "rewrite": "rephrase", "clean up": "rephrase",
            "bullets": "bullet", "list": "bullet",
            "professional": "formal", "business": "formal",
            "friendly": "casual", "relaxed": "casual",
        }
        transform = synonyms.get(transform, _DEFAULT_TRANSFORM)

    instruction = _TRANSFORM_PROMPTS.get(transform, _TRANSFORM_PROMPTS[_DEFAULT_TRANSFORM])

    # Read clipboard
    text = _read_clipboard()
    if not text:
        return "I couldn't read anything from your clipboard. Copy the text first, then ask me."

    if len(text) > 3000:
        text = text[:3000] + "…"

    # Call the LLM with a tight focused prompt
    result = _transform_via_llm(instruction, text)
    if not result:
        return "I wasn't able to transform that — try again in a moment."

    # Write result back to clipboard
    _write_clipboard(result)

    # Show in UI log
    ui.write_log(f"[TextTransform: {transform}]\n{result[:200]}{'…' if len(result) > 200 else ''}")

    return (
        f"Done. I've {transform}d the text and copied the result to your clipboard."
    )


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


def _write_clipboard(text: str):
    try:
        import subprocess
        subprocess.run(
            ["powershell", "-command", f"Set-Clipboard -Value @'\n{text}\n'@"],
            capture_output=True, timeout=5,
        )
    except Exception:
        # Fallback: clip.exe
        try:
            import subprocess
            subprocess.run(["clip"], input=text.encode("utf-8", errors="replace"), timeout=3)
        except Exception:
            pass


def _transform_via_llm(instruction: str, text: str) -> str:
    """
    Call the LLM directly with a simple non-JSON prompt.
    Returns plain text result (not a JSON envelope).
    """
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
                {"role": "system", "content": "You are a precise text editor. Follow the instruction exactly. Return ONLY the transformed text — no preamble, no explanation."},
                {"role": "user", "content": f"{instruction}\n\n{text}"},
            ],
            "temperature": 0.3,
            "max_tokens": 600,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""


SKILL_MANIFEST = {
    "name": "text_transform",
    "description": "Summarise, rephrase, expand, or reformat clipboard text",
    "intents": [
        "text_transform", "summarise_text", "rephrase_text",
        "expand_text", "bullet_text", "make_formal", "make_casual",
    ],
    "trigger_phrases": [
        "summarise this", "summarize this", "shorten this",
        "rephrase that", "rewrite this", "clean this up",
        "expand this", "make this longer",
        "bullet points", "convert to bullets",
        "make this formal", "make this professional",
        "make this casual", "make this friendly",
    ],
    "run": _run,
}
