"""
LLM Manager - unified interface for Ollama (local) and cloud providers.
Phase 9 will add full multi-provider support. For now this wraps Sam's llm.py.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import llm as sam_llm  # Sam's existing llm.py


class LLMManager:
    async def complete(
        self, prompt: str, system: str = "", model_tier: str = "local"
    ) -> str:
        """
        Complete a prompt. model_tier: 'local' (Ollama) or 'cloud' (OpenAI/Anthropic).
        Wraps Sam's existing llm.py, respecting the model_tier preference.
        """
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        # Temporarily override the model tier if caller specifies one
        original_tier = sam_llm.get_model_tier()
        tier_changed = False
        if model_tier == "local" and sam_llm.OLLAMA_AVAILABLE:
            if original_tier != "local":
                sam_llm.set_model_tier("local")
                tier_changed = True
        elif model_tier == "cloud":
            if original_tier != "cloud":
                sam_llm.set_model_tier("cloud")
                tier_changed = True

        try:
            # Run sync llm call in thread pool to not block async loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _call_ask(full_prompt),
            )
            return response or ""
        finally:
            # Restore original tier
            if tier_changed:
                sam_llm.set_model_tier(original_tier)

    def complete_sync(self, prompt: str, system: str = "") -> str:
        """Synchronous completion for non-async contexts."""
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        return _call_ask(full_prompt) or ""


def _call_ask(prompt: str) -> str:
    """
    Call Sam's LLM layer. sam_llm.py exposes get_ai_response() which routes
    to Ollama or OpenAI based on MODEL_TIER. We pass the prompt as the user
    message and extract the text field from the returned dict.
    """
    result = sam_llm.get_ai_response(prompt)
    if isinstance(result, dict):
        return result.get("text", "")
    return str(result) if result else ""
