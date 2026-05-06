"""Real Ollama live test for Sam v2 request understanding."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.result import SamResult
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.llm import OllamaClient


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _result_from_exception(exc: Exception) -> SamResult:
    return SamResult(
        status="failed",
        summary="Ollama live test failed.",
        error_type=ErrorType.MODEL_ERROR,
        error_message=str(exc),
        next_action="check_ollama",
    )


def main() -> int:
    print("=== Sam v2 Ollama Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_ollama_live")
    client = OllamaClient()

    try:
        try:
            _assert(client.is_available(), "Ollama API is not reachable")
            model_name = client.resolve_model()
            _assert(bool(model_name), "resolved model name was empty")
            print(f"[PASS] Ollama reachable with model: {model_name}")
        except Exception as exc:
            logger.fail_step("ollama_connectivity", str(exc))
            failures.append(f"Ollama connectivity test failed: {exc}")
        else:
            logger.pass_step("ollama_connectivity", {"model": client.resolve_model()})

        try:
            capability_result = client.classify_request(
                "Sam, what can you do?",
                capabilities=["capabilities", "chat", "create_goal", "list_goals", "create_draft", "list_workflows"],
                memory_block={"projects": {"active": {"value": "Sam-agent"}}},
            )
            _assert(capability_result.intent == "capabilities", f"unexpected intent: {capability_result.intent}")
            print("[PASS] Ollama capability classification")
        except Exception as exc:
            logger.fail_step("ollama_capability_classification", str(exc))
            failures.append(f"Ollama capability classification failed: {exc}")
        else:
            logger.pass_step(
                "ollama_capability_classification",
                {"intent": capability_result.intent, "confidence": capability_result.confidence},
            )

        try:
            ambiguous_result = client.classify_request(
                "Sam, check that thing from yesterday",
                capabilities=["capabilities", "chat", "create_goal", "list_goals", "create_draft", "list_workflows"],
                memory_block={"projects": {"active": {"value": "Sam-agent"}}},
            )
            _assert(
                ambiguous_result.needs_clarification or ambiguous_result.intent == "chat",
                "ambiguous request did not produce clarification or chat fallback",
            )
            print("[PASS] Ollama ambiguity handling")
        except Exception as exc:
            logger.fail_step("ollama_ambiguity_handling", str(exc))
            failures.append(f"Ollama ambiguity handling failed: {exc}")
        else:
            logger.pass_step(
                "ollama_ambiguity_handling",
                {
                    "intent": ambiguous_result.intent,
                    "needs_clarification": ambiguous_result.needs_clarification,
                },
            )
    except Exception as exc:
        result = _result_from_exception(exc)
        logger.fail_step("ollama_live_test", result.error_message or result.summary)
        failures.append(result.error_message or result.summary)

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Ollama live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All Ollama live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
