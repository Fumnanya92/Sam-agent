"""Test that _call_llm uses Ollama first and GPT-4o only as fallback."""
import sys, json
sys.path.insert(0, ".")

from skills.flutter_tester import _call_llm

# ── Test 1: Ollama first ─────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Ollama-first routing")
print("=" * 60)

class MustNotCallGPT:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                raise AssertionError("GPT-4o called — Ollama did NOT take over!")

result = _call_llm(
    client=MustNotCallGPT(),
    system_prompt=(
        'You are a Flutter test assistant. '
        'Always respond with ONLY this JSON and nothing else: '
        '{"command": ["snapshot"], "done": false, "message": "ollama ok", "error": null}'
    ),
    snapshot="<button>Login</button>",
    task="tap the Login button",
    history=[],
    step=1,
    screenshot_b64=None,
)

print("Raw result:", json.dumps(result, indent=2))
if result.get("command") or result.get("message"):
    print("\nPASS — Ollama responded and returned parseable JSON")
else:
    print("\nFAIL — unexpected empty result")

# ── Test 2: Fallback to GPT-4o when Ollama is forced off ────────────────────
print()
print("=" * 60)
print("TEST 2: GPT-4o fallback when Ollama raises")
print("=" * 60)

import unittest.mock as mock

with mock.patch("skills.flutter_tester.requests.post", side_effect=ConnectionError("simulated Ollama down")):
    gpt_called = []

    class FakeGPT:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    gpt_called.append(True)
                    class Msg:
                        content = '{"command": ["snapshot"], "done": false, "message": "gpt ok", "error": null}'
                    class Choice:
                        message = Msg()
                    class Resp:
                        choices = [Choice()]
                    return Resp()

    result2 = _call_llm(
        client=FakeGPT(),
        system_prompt="You are a Flutter test assistant.",
        snapshot="<button>Login</button>",
        task="tap the Login button",
        history=[],
        step=1,
        screenshot_b64=None,
    )

    print("Raw result:", json.dumps(result2, indent=2))
    if gpt_called and result2.get("message") == "gpt ok":
        print("\nPASS — GPT-4o fallback triggered correctly")
    else:
        print("\nFAIL — GPT-4o fallback did not trigger")
