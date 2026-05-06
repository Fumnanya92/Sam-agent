"""Minimal command-based tooling workers for Sam v2."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.reporting import ActionLogger, ErrorLogger, SummaryLogger
from sam_v2.diagnostics.result import SamResult
from sam_v2.diagnostics.run_logger import RunLogger
from sam_v2.storage.db import log_audit_event
from sam_v2.storage.models import AuditEvent

from .monitor import WorkerTask, worker_monitor


@dataclass
class CommandSpec:
    name: str
    worker_type: str
    command: list[str]
    description: str
    cwd: str | Path | None = None
    timeout_seconds: int = 60
    action_category: str = "execute_command"
    environment: dict[str, str] = field(default_factory=dict)


class ToolingWorker:
    def __init__(
        self,
        *,
        db_path: str | Path,
        authority_engine: AuthorityEngine | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.authority_engine = authority_engine or AuthorityEngine(AuthorityConfig(default_level=5))
        self.approval_manager = approval_manager or ApprovalManager(self.db_path)

    def execute(self, spec: CommandSpec) -> tuple[SamResult, WorkerTask]:
        task = worker_monitor.create_task(
            name=spec.name,
            worker_type=spec.worker_type,
            description=spec.description,
        )
        run_logger = RunLogger(f"sam_v2 worker {spec.name}")
        action_logger = ActionLogger(f"sam_v2 worker {spec.name}", correlation_id=run_logger.run_id)
        error_logger = ErrorLogger(f"sam_v2.workers.{spec.worker_type}")
        summary_logger = SummaryLogger(f"sam_v2 worker {spec.name}", correlation_id=run_logger.run_id)
        run_logger.log(
            "worker_task_created",
            {
                "task_id": task.task_id,
                "worker_type": spec.worker_type,
                "command": spec.command,
                "cwd": str(spec.cwd) if spec.cwd else "",
            },
        )
        action_logger.log("worker_task_created", status="started", data={"task_id": task.task_id})

        decision = self.authority_engine.check(
            agent_id=f"worker:{spec.worker_type}",
            agent_level=5,
            role_id="worker",
            tool_name=spec.name,
            action_category=spec.action_category,
        )
        if not decision.allowed:
            worker_monitor.mark_failed(task.task_id, decision.reason)
            result = SamResult(
                status="blocked",
                summary="Worker command blocked by authority rules.",
                error_type=ErrorType.MISSING_PERMISSION,
                error_message=decision.reason,
                next_action="request_approval",
                metadata={"task_id": task.task_id, "worker_type": spec.worker_type},
            )
            action_logger.log("worker_blocked", status="blocked", data={"task_id": task.task_id})
            error_logger.log(
                event="worker_blocked",
                error_type=result.error_type,
                error_message=result.error_message or result.summary,
                metadata={"task_id": task.task_id, "worker_type": spec.worker_type},
            )
            summary_logger.write(result, metadata={"task_id": task.task_id})
            return (result, worker_monitor.get_task(task.task_id) or task)

        if decision.requires_approval:
            schema_result = self.approval_manager.ensure_schema()
            if not schema_result.ok:
                worker_monitor.mark_failed(task.task_id, schema_result.error_message or schema_result.summary)
                result = SamResult(
                    status="failed",
                    summary="Approval schema initialization failed.",
                    error_type=schema_result.error_type or ErrorType.FILE_ACCESS_ERROR,
                    error_message=schema_result.error_message,
                    next_action=schema_result.next_action or "retry",
                    metadata={"task_id": task.task_id},
                )
                error_logger.log(
                    event="approval_schema_failed",
                    error_type=result.error_type,
                    error_message=result.error_message or result.summary,
                    metadata={"task_id": task.task_id},
                )
                summary_logger.write(result, metadata={"task_id": task.task_id})
                return (result, worker_monitor.get_task(task.task_id) or task)

            create_result, approval = self.approval_manager.create_request(
                agent_id=f"worker:{spec.worker_type}",
                agent_name=f"Sam v2 {spec.worker_type} worker",
                tool_name=spec.name,
                tool_arguments={
                    "command": spec.command,
                    "cwd": str(spec.cwd) if spec.cwd else "",
                    "worker_type": spec.worker_type,
                },
                action_category=spec.action_category,
                reason=decision.reason,
                context=spec.description,
            )
            if not create_result.ok or approval is None:
                worker_monitor.mark_failed(task.task_id, create_result.error_message or create_result.summary)
                result = SamResult(
                    status="failed",
                    summary="Approval request creation failed.",
                    error_type=create_result.error_type or ErrorType.FILE_ACCESS_ERROR,
                    error_message=create_result.error_message,
                    next_action=create_result.next_action or "retry",
                    metadata={"task_id": task.task_id},
                )
                error_logger.log(
                    event="approval_request_failed",
                    error_type=result.error_type,
                    error_message=result.error_message or result.summary,
                    metadata={"task_id": task.task_id},
                )
                summary_logger.write(result, metadata={"task_id": task.task_id})
                return (result, worker_monitor.get_task(task.task_id) or task)

            worker_monitor.mark_needs_approval(task.task_id, decision.reason)
            run_logger.log("worker_needs_approval", {"task_id": task.task_id, "approval_id": approval.id})
            result = SamResult(
                status="needs_approval",
                summary="Worker command requires approval.",
                error_type=ErrorType.MISSING_PERMISSION,
                error_message=decision.reason,
                next_action="request_approval",
                metadata={"task_id": task.task_id, "approval_id": approval.id},
            )
            action_logger.log("worker_needs_approval", status="needs_approval", data={"task_id": task.task_id})
            summary_logger.write(result, metadata={"task_id": task.task_id})
            return (result, worker_monitor.get_task(task.task_id) or task)

        worker_monitor.mark_running(task.task_id)
        run_logger.log("worker_started", {"task_id": task.task_id})
        action_logger.log("worker_started", status="running", data={"task_id": task.task_id})

        try:
            completed = subprocess.run(
                spec.command,
                cwd=str(spec.cwd) if spec.cwd else None,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                env=None if not spec.environment else spec.environment,
            )
            output = completed.stdout.strip()
            error_output = completed.stderr.strip()

            for line in [*output.splitlines(), *error_output.splitlines()]:
                if line.strip():
                    worker_monitor.append_output(task.task_id, line.strip())

            if completed.returncode != 0:
                error_type = ErrorType.TEST_FAILED if spec.worker_type == "test" else ErrorType.COMMAND_FAILED
                worker_monitor.mark_failed(task.task_id, error_output or f"exit_code={completed.returncode}")
                run_logger.log(
                    "worker_failed",
                    {
                        "task_id": task.task_id,
                        "returncode": completed.returncode,
                        "stderr": error_output[:500],
                    },
                )
                result = SamResult(
                    status="failed",
                    summary="Worker command failed.",
                    error_type=error_type,
                    error_message=error_output or f"exit_code={completed.returncode}",
                    next_action="retry",
                    metadata={
                        "task_id": task.task_id,
                        "worker_type": spec.worker_type,
                        "returncode": completed.returncode,
                        "stdout": output,
                    },
                )
                action_logger.log("worker_failed", status="failed", data={"task_id": task.task_id})
                error_logger.log(
                    event="worker_failed",
                    error_type=result.error_type,
                    error_message=result.error_message or result.summary,
                    metadata={"task_id": task.task_id, "returncode": completed.returncode},
                )
                summary_logger.write(result, metadata={"task_id": task.task_id})
                return (result, worker_monitor.get_task(task.task_id) or task)

            audit_result, audit_id = log_audit_event(
                self.db_path,
                AuditEvent(
                    event_type="worker_command_executed",
                    actor=f"sam_v2.workers.{spec.worker_type}",
                    summary=spec.description,
                    metadata_json=json.dumps(
                        {
                            "task_id": task.task_id,
                            "command": spec.command,
                            "cwd": str(spec.cwd) if spec.cwd else "",
                            "worker_type": spec.worker_type,
                        }
                    ),
                ),
            )
            worker_monitor.mark_done(task.task_id)
            run_logger.log(
                "worker_completed",
                {
                    "task_id": task.task_id,
                    "audit_id": audit_id,
                    "audit_status": audit_result.status,
                },
            )
            summary = output.splitlines()[-1] if output else f"{spec.worker_type} worker completed."
            result = SamResult(
                status="success",
                summary=summary,
                next_action="stop",
                metadata={
                    "task_id": task.task_id,
                    "worker_type": spec.worker_type,
                    "stdout": output,
                    "audit_event_id": audit_id,
                },
            )
            action_logger.log("worker_completed", status="success", data={"task_id": task.task_id, "audit_event_id": audit_id})
            summary_logger.write(result, metadata={"task_id": task.task_id})
            return (result, worker_monitor.get_task(task.task_id) or task)
        except subprocess.TimeoutExpired as exc:
            worker_monitor.mark_failed(task.task_id, f"timed out after {spec.timeout_seconds}s")
            run_logger.log("worker_timeout", {"task_id": task.task_id})
            result = SamResult(
                status="failed",
                summary="Worker command timed out.",
                error_type=ErrorType.TIMEOUT,
                error_message=str(exc),
                next_action="retry",
                metadata={"task_id": task.task_id, "worker_type": spec.worker_type},
            )
            error_logger.log(
                event="worker_timeout",
                error_type=result.error_type,
                error_message=result.error_message or result.summary,
                metadata={"task_id": task.task_id},
            )
            summary_logger.write(result, metadata={"task_id": task.task_id})
            return (result, worker_monitor.get_task(task.task_id) or task)
        except OSError as exc:
            worker_monitor.mark_failed(task.task_id, str(exc))
            run_logger.log("worker_os_error", {"task_id": task.task_id, "error": str(exc)})
            result = SamResult(
                status="failed",
                summary="Worker command could not start.",
                error_type=ErrorType.COMMAND_FAILED,
                error_message=str(exc),
                next_action="ask_user",
                metadata={"task_id": task.task_id, "worker_type": spec.worker_type},
            )
            error_logger.log(
                event="worker_os_error",
                error_type=result.error_type,
                error_message=result.error_message or result.summary,
                metadata={"task_id": task.task_id},
            )
            summary_logger.write(result, metadata={"task_id": task.task_id})
            return (result, worker_monitor.get_task(task.task_id) or task)
