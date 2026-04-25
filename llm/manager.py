"""
LLM Manager — unified async interface for all providers.
Phase 9: full multi-provider with streaming, token counting, cost tracking.

Provider routing:
  local   → Ollama (default, free, private)
  openai  → OpenAI  (gpt-4o-mini default)
  anthropic → Anthropic (claude-haiku-4-5 default)
  groq    → Groq    (llama-3.3-70b-versatile)
  gemini  → Google Gemini (gemini-1.5-flash)
  openrouter → OpenRouter proxy

Auto-routing (model_tier="auto"):
  - Code/system/simple tasks  → local (Ollama)
  - Complex reasoning/creative → cloud (Anthropic > OpenAI)
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Optional

logger = logging.getLogger("sam.llm.manager")

Provider = Literal["local", "openai", "anthropic", "groq", "gemini", "openrouter", "auto"]

# Cost per 1K tokens in USD (approximate, updated 2025)
COST_PER_1K: dict[str, dict[str, float]] = {
    "local":       {"input": 0.0,      "output": 0.0},
    "openai":      {"input": 0.00015,  "output": 0.0006},   # gpt-4o-mini
    "anthropic":   {"input": 0.00025,  "output": 0.00125},  # claude-haiku-4-5
    "groq":        {"input": 0.00006,  "output": 0.00006},  # llama-3.3-70b
    "gemini":      {"input": 0.000075, "output": 0.0003},   # gemini-1.5-flash
    "openrouter":  {"input": 0.0002,   "output": 0.0006},   # approx
}

LOCAL_TASK_KEYWORDS = {
    "code", "debug", "file", "run", "search", "open", "system",
    "git", "install", "list", "remind", "weather", "calculate",
}


@dataclass
class LLMUsage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    @property
    def cost_usd(self) -> float:
        rates = COST_PER_1K.get(self.provider, {"input": 0.0, "output": 0.0})
        return (self.input_tokens * rates["input"] + self.output_tokens * rates["output"]) / 1000


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage
    provider: str


# Session-level token accumulator
_session_usage: list[LLMUsage] = []


def session_stats() -> dict:
    total_cost = sum(u.cost_usd for u in _session_usage)
    total_tokens = sum(u.input_tokens + u.output_tokens for u in _session_usage)
    by_provider: dict[str, int] = {}
    for u in _session_usage:
        by_provider[u.provider] = by_provider.get(u.provider, 0) + u.input_tokens + u.output_tokens
    return {
        "total_calls": len(_session_usage),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "by_provider": by_provider,
    }


class LLMManager:
    def __init__(self) -> None:
        self._ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self._openai_key = os.getenv("OPENAI_API_KEY", "")
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._groq_key = os.getenv("GROQ_API_KEY", "")
        self._gemini_key = os.getenv("GEMINI_API_KEY", "")
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self._ollama_ok: Optional[bool] = None  # cached availability

    # ── Public: complete ──────────────────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model_tier: Provider = "auto",
        max_tokens: int = 2048,
    ) -> str:
        resp = await self.complete_with_usage(
            prompt, system=system, model_tier=model_tier, max_tokens=max_tokens
        )
        return resp.text

    async def complete_with_usage(
        self,
        prompt: str,
        system: str = "",
        model_tier: Provider = "auto",
        max_tokens: int = 2048,
    ) -> LLMResponse:
        provider = self._resolve_provider(prompt, model_tier)
        t0 = time.monotonic()
        try:
            text, usage = await self._dispatch(provider, prompt, system, max_tokens)
        except Exception as e:
            logger.warning(f"[LLM] {provider} failed ({e}), falling back to local")
            try:
                text, usage = await self._call_local(prompt, system, max_tokens)
                provider = "local"
            except Exception as e2:
                logger.error(f"[LLM] Local fallback also failed: {e2}")
                text = f"[LLM error: {e2}]"
                usage = LLMUsage(provider="local", model=self._ollama_model)

        usage.latency_ms = int((time.monotonic() - t0) * 1000)
        _session_usage.append(usage)
        logger.info(f"[LLM] {provider} — {usage.input_tokens}in/{usage.output_tokens}out tokens, {usage.latency_ms}ms, ${usage.cost_usd:.6f}")
        return LLMResponse(text=text, usage=usage, provider=provider)

    # ── Public: streaming ─────────────────────────────────────────────────────

    async def stream(
        self,
        prompt: str,
        system: str = "",
        model_tier: Provider = "auto",
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Yields text chunks as they arrive. Falls back to complete() if provider doesn't stream."""
        provider = self._resolve_provider(prompt, model_tier)
        try:
            async for chunk in self._dispatch_stream(provider, prompt, system, max_tokens):
                yield chunk
        except Exception as e:
            logger.warning(f"[LLM stream] {provider} failed ({e}), using complete()")
            text = await self.complete(prompt, system=system, model_tier=model_tier, max_tokens=max_tokens)
            yield text

    # ── Sync wrapper (for non-async callers) ─────────────────────────────────

    def complete_sync(self, prompt: str, system: str = "", model_tier: Provider = "auto") -> str:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Called from within async context — use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, self.complete(prompt, system=system, model_tier=model_tier))
                    return future.result(timeout=60)
            return loop.run_until_complete(self.complete(prompt, system=system, model_tier=model_tier))
        except Exception as e:
            logger.error(f"[LLM sync] Error: {e}")
            return ""

    # ── Provider routing ──────────────────────────────────────────────────────

    def _resolve_provider(self, prompt: str, tier: Provider) -> str:
        if tier == "local":
            return "local"
        if tier in ("openai", "anthropic", "groq", "gemini", "openrouter"):
            return tier
        # auto: use local if Ollama available and task is simple
        if tier == "auto" or tier == "cloud":
            words = set(prompt.lower().split())
            is_simple = bool(words & LOCAL_TASK_KEYWORDS)
            ollama_up = self._check_ollama()
            if tier == "auto" and is_simple and ollama_up:
                return "local"
            # Pick best available cloud provider
            if self._anthropic_key:
                return "anthropic"
            if self._openai_key:
                return "openai"
            if self._groq_key:
                return "groq"
            if self._gemini_key:
                return "gemini"
            if ollama_up:
                return "local"
        return "local"

    def _check_ollama(self) -> bool:
        if self._ollama_ok is not None:
            return self._ollama_ok
        try:
            import requests
            r = requests.get(f"{self._ollama_url}/api/tags", timeout=2)
            self._ollama_ok = r.status_code == 200
        except Exception:
            self._ollama_ok = False
        return self._ollama_ok

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, provider: str, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        loop = asyncio.get_running_loop()
        if provider == "local":
            return await self._call_local(prompt, system, max_tokens)
        if provider == "openai":
            return await loop.run_in_executor(None, lambda: self._call_openai(prompt, system, max_tokens))
        if provider == "anthropic":
            return await loop.run_in_executor(None, lambda: self._call_anthropic(prompt, system, max_tokens))
        if provider == "groq":
            return await loop.run_in_executor(None, lambda: self._call_groq(prompt, system, max_tokens))
        if provider == "gemini":
            return await loop.run_in_executor(None, lambda: self._call_gemini(prompt, system, max_tokens))
        if provider == "openrouter":
            return await loop.run_in_executor(None, lambda: self._call_openrouter(prompt, system, max_tokens))
        return await self._call_local(prompt, system, max_tokens)

    async def _dispatch_stream(self, provider: str, prompt: str, system: str, max_tokens: int) -> AsyncIterator[str]:
        if provider == "local":
            async for chunk in self._stream_local(prompt, system, max_tokens):
                yield chunk
        elif provider == "openai":
            async for chunk in self._stream_openai(prompt, system, max_tokens):
                yield chunk
        elif provider == "anthropic":
            async for chunk in self._stream_anthropic(prompt, system, max_tokens):
                yield chunk
        else:
            # Groq/Gemini/OpenRouter — fall back to complete
            text, _ = await self._dispatch(provider, prompt, system, max_tokens)
            yield text

    # ── Local (Ollama) ────────────────────────────────────────────────────────

    async def _call_local(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import aiohttp
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._ollama_url}/api/chat",
                json={"model": self._ollama_model, "messages": messages, "stream": False,
                      "options": {"num_predict": max_tokens}},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                data = await resp.json()

        text = data.get("message", {}).get("content", "")
        in_tok = data.get("prompt_eval_count", len(prompt.split()))
        out_tok = data.get("eval_count", len(text.split()))
        return text, LLMUsage("local", self._ollama_model, in_tok, out_tok)

    async def _stream_local(self, prompt: str, system: str, max_tokens: int) -> AsyncIterator[str]:
        import aiohttp
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._ollama_url}/api/chat",
                json={"model": self._ollama_model, "messages": messages, "stream": True,
                      "options": {"num_predict": max_tokens}},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                async for line in resp.content:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break
                    except Exception:
                        continue

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def _call_openai(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import requests
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._openai_key}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=60,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, LLMUsage("openai", model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    async def _stream_openai(self, prompt: str, system: str, max_tokens: int) -> AsyncIterator[str]:
        import aiohttp
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._openai_key}"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                async for line in resp.content:
                    line = line.decode().strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            chunk = data["choices"][0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            continue

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _call_anthropic(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import requests
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self._anthropic_key, "anthropic-version": "2023-06-01"},
            json=payload,
            timeout=60,
        )
        data = resp.json()
        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        return text, LLMUsage("anthropic", model, usage.get("input_tokens", 0), usage.get("output_tokens", 0))

    async def _stream_anthropic(self, prompt: str, system: str, max_tokens: int) -> AsyncIterator[str]:
        import aiohttp
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if system:
            payload["system"] = system
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self._anthropic_key, "anthropic-version": "2023-06-01"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                async for line in resp.content:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                chunk = data.get("delta", {}).get("text", "")
                                if chunk:
                                    yield chunk
                        except Exception:
                            continue

    # ── Groq ──────────────────────────────────────────────────────────────────

    def _call_groq(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import requests
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._groq_key}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=30,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, LLMUsage("groq", model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    # ── Gemini ────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import requests
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        full = f"{system}\n\n{prompt}" if system else prompt
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self._gemini_key}",
            json={"contents": [{"parts": [{"text": full}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens}},
            timeout=60,
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return text, LLMUsage("gemini", model, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))

    # ── OpenRouter ────────────────────────────────────────────────────────────

    def _call_openrouter(self, prompt: str, system: str, max_tokens: int) -> tuple[str, LLMUsage]:
        import requests
        model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._openrouter_key}",
                     "HTTP-Referer": "https://github.com/sam-agent"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=60,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, LLMUsage("openrouter", model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


# Module-level singleton
_manager: Optional[LLMManager] = None


def get_manager() -> LLMManager:
    global _manager
    if _manager is None:
        _manager = LLMManager()
    return _manager
