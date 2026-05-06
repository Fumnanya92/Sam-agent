"""Live test for Sam v2 storage foundation."""

from __future__ import annotations

import shutil
from pathlib import Path
import sys
import uuid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sam_v2.storage.db import (
    create_task,
    fetch_audit_event,
    fetch_task,
    init_storage,
    log_audit_event,
)
from sam_v2.storage.models import AuditEvent, TaskRecord


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=== Sam v2 Vault Storage Live Test ===")
    failures = []

    temp_root = REPO_ROOT / "sam_v2" / "tests_live" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = temp_root / f"sam_v2_vault_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = tmp_dir / "vault_live.db"
        print(f"[INFO] Temp DB: {db_path}")

        try:
            result = init_storage(db_path)
            _assert(result.ok, f"init_storage failed: {result.summary} | {result.error_message}")
            print("[PASS] Schema initialized")
        except Exception as exc:
            failures.append(f"Schema init test failed: {exc}")

        audit_id = None
        try:
            audit = AuditEvent(
                event_type="migration_test",
                actor="sam_v2/tests_live",
                summary="Inserted from live storage test",
                metadata_json='{"case":"audit_insert_read"}',
            )
            write_result, audit_id = log_audit_event(db_path, audit)
            _assert(write_result.ok and audit_id is not None, f"audit insert failed: {write_result.error_message}")

            read_result, loaded = fetch_audit_event(db_path, audit_id)
            _assert(read_result.ok and loaded is not None, f"audit read failed: {read_result.error_message}")
            _assert(loaded.summary == audit.summary, "audit summary mismatch")
            print("[PASS] Audit insert/read")
        except Exception as exc:
            failures.append(f"Audit test failed: {exc}")

        task_id = None
        try:
            task = TaskRecord(
                title="Storage migration validation task",
                status="pending",
                priority="high",
                notes="created by live test",
            )
            write_result, task_id = create_task(db_path, task)
            _assert(write_result.ok and task_id is not None, f"task insert failed: {write_result.error_message}")

            read_result, loaded = fetch_task(db_path, task_id)
            _assert(read_result.ok and loaded is not None, f"task read failed: {read_result.error_message}")
            _assert(loaded.title == task.title, "task title mismatch")
            print("[PASS] Task insert/read")
        except Exception as exc:
            failures.append(f"Task test failed: {exc}")

        try:
            # Intentional failure: title is NOT NULL.
            bad_task = TaskRecord(title=None)  # type: ignore[arg-type]
            result, _ = create_task(db_path, bad_task)
            _assert(not result.ok, "intentional failure did not fail")
            print("[PASS] Intentional failure path (invalid task) handled")
        except Exception as exc:
            failures.append(f"Intentional failure test failed: {exc}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    if failures:
        print("[FAIL] Live test failed")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("[PASS] All live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
