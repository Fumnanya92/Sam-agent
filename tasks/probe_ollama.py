"""Probe exactly what Ollama returns for the flutter_tester prompt."""
import sys, json, requests
sys.path.insert(0, ".")
from llm import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

system_prompt = (
    'You are a Flutter test assistant. '
    'Always respond with ONLY this JSON and nothing else: '
    '{"command": ["snapshot"], "done": false, "message": "ollama ok", "error": null}'
)
user_text = 'Step 1. Task: tap the Login button\n\nCurrent accessibility snapshot:\n```\n<button>Login</button>\n```\n\nRespond with JSON only.'

payload = {
    "model": OLLAMA_MODEL,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ],
    "stream": False,
}

resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT)
print("HTTP status:", resp.status_code)
body = resp.json()
raw = body.get("message", {}).get("content", "").strip()
print("Raw content repr:", repr(raw))
print()
print("Raw content:")
print(raw)
