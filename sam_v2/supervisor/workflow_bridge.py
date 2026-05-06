"""Bridge a small execution plan into workers, approvals, and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sam_v2.approvals import ApprovalManager, AuthorityEngine
from sam_v2.diagnostics.reporting import ActionLogger, ErrorLogger, SummaryLogger
from sam_v2.diagnostics.result import SamResult
from sam_v2.diagnostics.run_logger import RunLogger
from sam_v2.workers import CommandSpec, ToolingWorker, WorkerQueue

from .recovery import RecoveryPolicy

StepType = Literal["worker_command"]


@dataclass
class ExecutionStep:
    step_id: str
    title: str
    step_type: StepType
    command_spec: CommandSpec
    max_attempts: int = 2


@dataclass
class ExecutionPlan:
    plan_id: str
    goal: str
    steps: list[ExecutionStep] = field(default_factory=list)


class WorkflowBridge:
    def __init__(
        self,
        *,
        db_path: str | Path,
        worker: ToolingWorker | None = None,
        queue: WorkerQueue | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        authority_engine: AuthorityEngine | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.worker = worker or ToolingWorker(
            db_path=self.db_path,
            authority_engine=authority_engine,
            approval_manager=approval_manager,
        )
        self.queue = queue or WorkerQueue(self.worker)
        self.recovery_policy = recovery_policy or RecoveryPolicy()

    def execute_plan(self, plan: ExecutionPlan) -> SamResult:
        run_logger = RunLogger(f"sam_v2 workflow {plan.plan_id}")
        action_logger = ActionLogger(f"sam_v2 workflow {plan.plan_id}", correlation_id=run_logger.run_id)
        error_logger = ErrorLogger("sam_v2.supervisor.workflow")
        summary_logger = SummaryLogger(f"sam_v2 workflow {plan.plan_id}", correlation_id=run_logger.run_id)

        run_logger.log("plan_started", {"plan_id": plan.plan_id, "goal": plan.goal, "step_count": len(plan.steps)})
        action_logger.log("plan_started", status="started", data={"plan_id": plan.plan_id, "goal": plan.goal})

        completed_steps: list[str] = []

        for step in plan.steps:
            run_logger.log("step_started", {"step_id": step.step_id, "title": step.title})
            action_logger.log("step_started", status="started", data={"step_id": step.step_id, "title": step.title})

            attempt = 1
            while attempt <= step.max_attempts:
                queue_result = self.queue.submit(step.command_spec)
                if not queue_result.ok:
                    result = SamResult(
                        status="failed",
                        summary="Failed to queue workflow step.",
                        error_type=queue_result.error_type,
                        error_message=queue_result.error_message,
                        next_action=queue_result.next_action,
                        metadata={"plan_id": plan.plan_id, "step_id": step.step_id},
                    )
                    error_logger.log(
                        event="step_queue_failed",
                        error_type=result.error_type,
                        error_message=result.error_message or result.summary,
                        metadata={"plan_id": plan.plan_id, "step_id": step.step_id},
                    )
                    summary_logger.write(result, metadata={"plan_id": plan.plan_id, "completed_steps": completed_steps})
                    return result

                step_result = self.queue.run_next()
                step_result.metadata.setdefault("plan_id", plan.plan_id)
                step_result.metadata.setdefault("step_id", step.step_id)
                step_result.metadata.setdefault("attempt", attempt)

                decision = self.recovery_policy.decide(
                    step_result,
                    attempt=attempt,
                    max_attempts=step.max_attempts,
                )
                run_logger.log(
                    "step_result",
                    {
                        "step_id": step.step_id,
                        "attempt": attempt,
                        "status": step_result.status,
                        "decision": decision.action,
                    },
                )

                if step_result.ok:
                    completed_steps.append(step.step_id)
                    action_logger.log(
                        "step_completed",
                        status="success",
                        data={"step_id": step.step_id, "attempt": attempt},
                    )
                    break

                if decision.should_retry:
                    action_logger.log(
                        "step_retrying",
                        status="retry",
                        data={"step_id": step.step_id, "attempt": attempt},
                    )
                    attempt += 1
                    continue

                if step_result.status in {"needs_approval", "blocked"}:
                    action_logger.log(
                        "plan_paused_for_approval",
                        status=step_result.status,
                        data={"step_id": step.step_id, "approval_id": step_result.metadata.get("approval_id")},
                    )
                    summary_logger.write(
                        step_result,
                        metadata={"plan_id": plan.plan_id, "completed_steps": completed_steps},
                    )
                    return step_result

                error_logger.log(
                    event="step_failed",
                    error_type=step_result.error_type,
                    error_message=step_result.error_message or step_result.summary,
                    metadata={"plan_id": plan.plan_id, "step_id": step.step_id, "attempt": attempt},
                )
                summary_logger.write(
                    step_result,
                    metadata={"plan_id": plan.plan_id, "completed_steps": completed_steps},
                )
                return step_result

        result = SamResult(
            status="success",
            summary=f"Workflow plan '{plan.goal}' completed.",
            next_action="stop",
            metadata={
                "plan_id": plan.plan_id,
                "completed_steps": completed_steps,
                "step_count": len(plan.steps),
            },
        )
        run_logger.log("plan_completed", result.metadata)
        action_logger.log("plan_completed", status="success", data=result.metadata)
        summary_logger.write(result, metadata={"plan_id": plan.plan_id})
        return result
