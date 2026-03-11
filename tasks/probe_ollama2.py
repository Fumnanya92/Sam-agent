import requests, json

r = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "gpt-oss:120b-cloud",
        "messages": [{"role": "user", "content": 'Reply with only this JSON: {"ok": true}'}],
        "stream": False,
    },
    timeout=30,
)
print("Status:", r.status_code)
data = r.json()
print("Response:", data.get("message", {}).get("content", "")[:300])
