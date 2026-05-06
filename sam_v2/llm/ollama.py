"""Minimal Ollama client for Sam v2 understanding tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from config.loader import load_config


@dataclass
class OllamaSettings:
    base_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout_seconds: int = 20


@dataclass
class OllamaIntentOutput:
    intent: str
    parameters: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str = ""
    response_text: str = ""
    confidence: str = "low"
    model: str = ""
    source: str = "ollama"


class OllamaClient:
    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or self._load_settings()
        self._resolved_model: str | None = None

    def is_available(self) -> bool:
        try:
            response = self._request("GET", "/api/tags")
            return bool(response.get("models", []))
        except Exception:
            return False

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model

        configured = self.settings.model
        try:
            response = self._request("GET", "/api/tags")
            models = [item.get("name", "") for item in response.get("models", []) if item.get("name")]
            if not models:
                self._resolved_model = configured
                return self._resolved_model

            for model_name in models:
                if configured == model_name or model_name.startswith(configured.split(":")[0]):
                    self._resolved_model = model_name
                    return self._resolved_model

            self._resolved_model = models[0]
            return self._resolved_model
        except Exception:
            self._resolved_model = configured
            return self._resolved_model

    def classify_request(
        self,
        user_text: str,
        *,
        capabilities: list[str],
        memory_block: dict[str, Any] | None = None,
    ) -> OllamaIntentOutput:
        model = self.resolve_model()
        memory_json = json.dumps(memory_block or {}, ensure_ascii=True)
        capability_text = ", ".join(capabilities)
        prompt = "\n".join(
            [
                "You are Sam v2's request understanding layer.",
                "Return JSON only.",
                "Supported intents: capabilities, create_goal, list_goals, create_draft, list_workflows, chat.",
                "If the request is ambiguous, set needs_clarification to true and provide clarification_question.",
                "If the request does not map cleanly to a supported action, use intent chat.",
                "Do not invent unsupported capabilities.",
                "Parameters for create_goal: {\"title\": \"...\"}.",
                "Parameters for create_draft: {\"title\": \"...\", \"body\": \"...\", \"content_type\": \"report\"}.",
                "For chat, provide a brief conversational response_text.",
                "For clarification, response_text may be empty.",
                f"Available capabilities: {capability_text}",
                f"Memory context JSON: {memory_json}",
                f"User request: {user_text}",
                'Return fields: intent, parameters, needs_clarification, clarification_question, response_text, confidence.',
            ]
        )
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        response = self._request("POST", "/api/generate", payload)
        raw_body = str(response.get("response", "")).strip()
        parsed = self._parse_json_object(raw_body)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama response was not valid JSON.")

        return OllamaIntentOutput(
            intent=str(parsed.get("intent", "chat") or "chat"),
            parameters=parsed.get("parameters", {}) if isinstance(parsed.get("parameters"), dict) else {},
            needs_clarification=bool(parsed.get("needs_clarification", False)),
            clarification_question=str(parsed.get("clarification_question", "") or ""),
            response_text=str(parsed.get("response_text", "") or ""),
            confidence=str(parsed.get("confidence", "low") or "low"),
            model=model,
        )

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(
            f"{self.settings.base_url.rstrip('/')}{path}",
            method=method,
            data=body,
            headers=headers,
        )
        with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_settings(self) -> OllamaSettings:
        config = load_config()
        primary = config.get("llm", {}).get("primary", {})
        return OllamaSettings(
            base_url=str(primary.get("base_url", "http://localhost:11434")),
            model=str(primary.get("model", "llama3.2")),
            timeout_seconds=int(primary.get("timeout_seconds", 20)),
        )

    def _parse_json_object(self, text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                start = cleaned.index("{")
                end = cleaned.rindex("}") + 1
            except ValueError:
                return None
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                return None
