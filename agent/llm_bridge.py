# agent/llm_bridge.py
# Shared LLM helper for Sam's agent layer.
#
# Strategy: Ollama-first (local, private, free).
# Falls back to OpenAI gpt-4o-mini ONLY when:
#   - need_vision=True  (Ollama has no vision capability)
#   - Ollama is unavailable
#   - Ollama returns invalid JSON after 2 retries (when require_json=True)
#
# When falling back, notifies user via speak() if provided.

import json
import re
import os
import requests

# Import shared helpers from llm.py — single source of truth
from llm import get_openai_key as _get_openai_key, is_ollama_available as _is_ollama_available, _resolve_ollama_model

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_TIMEOUT  = int(os.getenv("OLLAMA_TIMEOUT", "60"))
_OPENAI_MODEL    = "gpt-4o-mini"


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    model   = _resolve_ollama_model()
    payload = {
        "model":    model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
    }
    response = requests.post(
        f"{_OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=_OLLAMA_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Ollama returned {response.status_code}: {response.text[:200]}")
    return response.json().get("message", {}).get("content", "")


def _call_openai(system_prompt: str, user_prompt: str,
                 require_json: bool = False,
                 image_b64: str = None) -> str:
    api_key = _get_openai_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Add openai_api_key to config/api_keys.json"
        )

    if image_b64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text",      "text": user_prompt},
        ]
    else:
        user_content = user_prompt

    body = {
        "model": _OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.2,
    }
    if require_json and not image_b64:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI returned {response.status_code}: {response.text[:300]}")
    return response.json()["choices"][0]["message"]["content"]


def agent_llm_call(
    system_prompt: str,
    user_prompt:   str,
    require_json:  bool = False,
    need_vision:   bool = False,
    image_b64:     str  = None,
    speak              = None,
) -> str:
    """
    Shared LLM helper for the agent layer.
    Tries Ollama first; falls back to OpenAI with user notification.
    """
    if need_vision or image_b64:
        print("[LLMBridge] vision request -> OpenAI")
        return _call_openai(system_prompt, user_prompt, require_json=False, image_b64=image_b64)

    max_attempts = 2 if require_json else 1
    ollama_ok    = _is_ollama_available()

    if ollama_ok:
        for attempt in range(1, max_attempts + 1):
            try:
                text = _call_ollama(system_prompt, user_prompt)
                if require_json:
                    clean = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
                    json.loads(clean)
                    return clean
                return text
            except (ValueError, json.JSONDecodeError) as e:
                print(f"[LLMBridge] Ollama JSON invalid (attempt {attempt}): {e}")
                if attempt >= max_attempts:
                    break
            except Exception as e:
                print(f"[LLMBridge] Ollama failed (attempt {attempt}): {e}")
                break
    else:
        print("[LLMBridge] Ollama unavailable")

    if speak:
        speak("Ollama can't handle this one — using cloud for a moment.")
    print("[LLMBridge] falling back to OpenAI")
    return _call_openai(system_prompt, user_prompt, require_json=require_json)
