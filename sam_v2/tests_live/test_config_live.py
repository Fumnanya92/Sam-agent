"""Real local config/env validation for Sam v2."""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

import requests
import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.config import load_config
from sam_v2.daemon import create_app_from_config
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.llm import OllamaClient


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _start_server(app, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def _wait_for_server(base_url: str, timeout_seconds: float = 15.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(f"config-backed daemon did not become ready: {last_error}")


def main() -> int:
    print("=== Sam v2 Config Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_config_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_config_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = tmp_dir / "sam.yaml"
    env_path = tmp_dir / ".env"
    configured_data_dir = tmp_dir / "config_data"
    configured_db_path = configured_data_dir / "daemon_from_config.db"
    configured_port = _free_port()

    yaml_path.write_text(
        "\n".join(
            [
                "daemon:",
                "  port: 9999",
                "  data_dir: ./config_data",
                "  db_path: ./config_data/daemon_from_config.db",
                "llm:",
                "  primary:",
                "    provider: ollama",
                "    model: yaml-model",
                "    base_url: http://localhost:11434",
                "    timeout_seconds: 11",
                "  fallback:",
                "    provider: openai",
                "    model: gpt-4o-mini",
                "voice:",
                "  tts: edge",
                "  stt: webspeech",
                "  wake_hotkey: ctrl+alt+s",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env_path.write_text("SAM_V2__LLM__PRIMARY__MODEL=dotenv-model\n", encoding="utf-8")

    original_port = os.environ.get("SAM_V2__DAEMON__PORT")
    server: uvicorn.Server | None = None
    thread: threading.Thread | None = None
    try:
        os.environ["SAM_V2__DAEMON__PORT"] = str(configured_port)

        try:
            result, config = load_config(config_path=yaml_path, env_file=env_path)
            _assert(result.ok and config is not None, f"config load failed: {result.error_message}")
            _assert(config.daemon.port == configured_port, "daemon port env override mismatch")
            _assert(config.daemon.db_path == configured_db_path.resolve(), "daemon db path normalization mismatch")
            _assert(config.llm.primary.model == "dotenv-model", "dotenv model override mismatch")
            _assert(config.llm.primary.base_url == "http://localhost:11434", "llm base_url mismatch")
            print("[PASS] YAML, .env, and os.environ config merge")
        except Exception as exc:
            logger.fail_step("config_merge", str(exc))
            failures.append(f"Config merge test failed: {exc}")
        else:
            logger.pass_step("config_merge")

        try:
            client = OllamaClient(config_path=yaml_path, env_file=env_path)
            _assert(client.settings.model == "dotenv-model", "ollama model setting mismatch")
            _assert(client.settings.timeout_seconds == 11, "ollama timeout setting mismatch")
            _assert(client.is_available(), "ollama not reachable through config-backed settings")
            print("[PASS] Ollama client reads config layer")
        except Exception as exc:
            logger.fail_step("ollama_config_wiring", str(exc))
            failures.append(f"Ollama config wiring test failed: {exc}")
        else:
            logger.pass_step("ollama_config_wiring")

        try:
            app = create_app_from_config(config_path=yaml_path, env_file=env_path)
            server, thread = _start_server(app, configured_port)
            health_payload = _wait_for_server(f"http://127.0.0.1:{configured_port}")
            _assert(health_payload["status"] == "ok", "daemon health status mismatch")
            _assert(
                Path(health_payload["db_path"]).resolve() == configured_db_path.resolve(),
                "daemon db path from config mismatch",
            )
            _assert(configured_db_path.exists(), "config-backed daemon db file was not created")
            print("[PASS] Daemon reads config layer")
        except Exception as exc:
            logger.fail_step("daemon_config_wiring", str(exc))
            failures.append(f"Daemon config wiring test failed: {exc}")
        else:
            logger.pass_step("daemon_config_wiring", {"port": configured_port, "db_path": str(configured_db_path)})
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        if original_port is None:
            os.environ.pop("SAM_V2__DAEMON__PORT", None)
        else:
            os.environ["SAM_V2__DAEMON__PORT"] = original_port
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Config live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All config live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
