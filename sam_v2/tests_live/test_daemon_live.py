"""Live test for the Sam v2 daemon skeleton."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from sam_v2.daemon.main import create_app
from sam_v2.storage.db import fetch_audit_event


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Daemon Live Test ===")
    failures = []

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_daemon_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "daemon_live.db"

    try:
        app = create_app(db_path)
        with TestClient(app) as client:
            try:
                response = client.get("/health")
                _assert(response.status_code == 200, "health endpoint did not return 200")
                payload = response.json()
                _assert(payload["status"] == "ok", "health payload status was not ok")
                print("[PASS] Health endpoint")
            except Exception as exc:
                failures.append(f"Health test failed: {exc}")

            try:
                with client.websocket_connect("/ws") as websocket:
                    chat_response = client.post(
                        "/api/chat",
                        json={"message": "hello from daemon live test", "session_id": "live-test"},
                    )
                    _assert(chat_response.status_code == 200, "chat endpoint did not return 200")
                    chat_payload = chat_response.json()
                    _assert(chat_payload["status"] == "success", "chat result was not success")

                    message = websocket.receive_json()
                    _assert(message["type"] == "chat_message", "unexpected websocket event type")
                    _assert(
                        message["payload"]["content"] == "hello from daemon live test",
                        "websocket content mismatch",
                    )
                    print("[PASS] Chat + websocket broadcast")

                    audit_id = chat_payload["metadata"]["audit_id"]
                    audit_result, audit_event = fetch_audit_event(db_path, audit_id)
                    _assert(audit_result.ok and audit_event is not None, "audit event was not persisted")
                    _assert(audit_event.event_type == "chat_received", "audit event type mismatch")
                    print("[PASS] Audit persistence for chat")
            except Exception as exc:
                failures.append(f"WebSocket/chat test failed: {exc}")

            try:
                bad_response = client.post("/api/chat", json={"session_id": "live-test"})
                _assert(bad_response.status_code == 422, "invalid chat payload did not fail with 422")
                print("[PASS] Invalid chat request failure path")
            except Exception as exc:
                failures.append(f"Failure-path test failed: {exc}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        print("[FAIL] Daemon live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("[PASS] All daemon live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
