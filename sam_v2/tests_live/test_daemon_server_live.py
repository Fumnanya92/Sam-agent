"""Real local-server validation for the Sam v2 daemon skeleton."""

from __future__ import annotations

import asyncio
import shutil
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

import requests
import uvicorn
import websockets

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.daemon import create_app
from sam_v2.diagnostics.test_logger import TestRunLogger
from sam_v2.storage.db import fetch_audit_event


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
        except Exception as exc:  # pragma: no cover - exercised in live run
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(f"server did not become ready: {last_error}")


async def _websocket_roundtrip(base_url: str, session_id: str) -> dict:
    ws_url = base_url.replace("http://", "ws://") + "/ws"
    async with websockets.connect(ws_url, open_timeout=5) as websocket:
        health_response = await asyncio.to_thread(requests.get, f"{base_url}/health", timeout=5)
        health_payload = health_response.json()
        _assert(health_payload["websocket_clients"] >= 1, "websocket client count did not increase")

        chat_response = await asyncio.to_thread(
            requests.post,
            f"{base_url}/api/chat",
            json={"message": "hello from real daemon server test", "session_id": session_id},
            timeout=5,
        )
        _assert(chat_response.status_code == 200, "chat endpoint did not return 200")
        chat_payload = chat_response.json()

        message = await asyncio.wait_for(websocket.recv(), timeout=5)
        return {
            "chat_payload": chat_payload,
            "websocket_message": message,
        }


def main() -> int:
    print("=== Sam v2 Daemon Server Live Test ===")
    failures: list[str] = []
    logger = TestRunLogger("test_daemon_server_live")

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_daemon_server_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "daemon_server_live.db"

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    session_id = "real-daemon-live"
    app = create_app(db_path)
    server, thread = _start_server(app, port)

    try:
        try:
            health_payload = _wait_for_server(base_url)
            _assert(health_payload["status"] == "ok", "health status mismatch")
            _assert(health_payload["service"] == "sam_v2_daemon", "health service mismatch")
            print("[PASS] Real HTTP health endpoint")
        except Exception as exc:
            logger.fail_step("real_http_health", str(exc))
            failures.append(f"Real HTTP health test failed: {exc}")
        else:
            logger.pass_step("real_http_health", health_payload)

        try:
            result = asyncio.run(_websocket_roundtrip(base_url, session_id))
            chat_payload = result["chat_payload"]
            websocket_message = result["websocket_message"]
            _assert(chat_payload["status"] == "success", "chat payload status mismatch")
            _assert('"type":"chat_message"' in websocket_message.replace(" ", ""), "websocket event type mismatch")
            _assert("hello from real daemon server test" in websocket_message, "websocket content mismatch")

            audit_id = chat_payload["metadata"]["audit_id"]
            audit_result, audit_event = fetch_audit_event(db_path, int(audit_id))
            _assert(audit_result.ok and audit_event is not None, "chat audit event missing")
            _assert(audit_event.event_type == "chat_received", "chat audit event type mismatch")
            print("[PASS] Real websocket broadcast and audit persistence")
        except Exception as exc:
            logger.fail_step("real_websocket_and_audit", str(exc))
            failures.append(f"Real websocket/audit test failed: {exc}")
        else:
            logger.pass_step("real_websocket_and_audit", {"audit_id": audit_id})

        try:
            bad_response = requests.post(f"{base_url}/api/chat", json={"session_id": session_id}, timeout=5)
            _assert(bad_response.status_code == 422, "invalid chat payload did not fail with 422")
            print("[PASS] Real invalid request failure path")
        except Exception as exc:
            logger.fail_step("real_invalid_request", str(exc))
            failures.append(f"Real invalid request test failed: {exc}")
        else:
            logger.pass_step("real_invalid_request")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        logger.complete(False, failures)
        print("[FAIL] Daemon server live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    logger.complete(True, failures)
    print("[PASS] All daemon server live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
