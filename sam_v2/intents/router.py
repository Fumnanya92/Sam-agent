"""Minimal intent parser and router for Sam v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sam_v2.approvals import ApprovalManager, AuthorityEngine
from sam_v2.capabilities import CapabilityRegistry, build_default_registry
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.result import SamResult
from sam_v2.workflows import GoalService, PipelineService


@dataclass
class IntentRequest:
    intent: str
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


class IntentRouter:
    def __init__(
        self,
        *,
        db_path: str | Path,
        registry: CapabilityRegistry | None = None,
        authority_engine: AuthorityEngine | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.registry = registry or build_default_registry()
        self.authority_engine = authority_engine
        self.approval_manager = approval_manager
        self.goal_service = GoalService(self.db_path)
        self.pipeline_service = PipelineService(self.db_path)

    def parse(self, user_text: str) -> IntentRequest:
        text = user_text.strip()
        lowered = text.lower()

        if any(phrase in lowered for phrase in ["what can you do", "capabilities", "list capabilities"]):
            return IntentRequest(intent="capabilities", raw_text=text)

        if lowered.startswith("create goal:"):
            return IntentRequest(
                intent="create_goal",
                parameters={"title": text.split(":", 1)[1].strip()},
                raw_text=text,
            )

        if lowered in {"list goals", "show goals", "what goals do i have"}:
            return IntentRequest(intent="list_goals", raw_text=text)

        if lowered.startswith("create draft:"):
            payload = text.split(":", 1)[1].strip()
            return IntentRequest(
                intent="create_draft",
                parameters={"title": payload[:60] or "Untitled draft", "body": payload, "content_type": "report"},
                raw_text=text,
            )

        if lowered in {"list workflows", "list drafts", "show drafts"}:
            return IntentRequest(intent="list_workflows", raw_text=text)

        return IntentRequest(intent="chat", raw_text=text)

    def handle(self, user_text: str) -> SamResult:
        request = self.parse(user_text)
        capability = self.registry.get(request.intent)
        if capability is None:
            return SamResult(
                status="failed",
                summary="Intent is not registered.",
                error_type=ErrorType.MISSING_CAPABILITY,
                error_message=request.intent,
                next_action="ask_user",
            )

        approval_result = self._check_authority(request, capability.action_category)
        if approval_result is not None:
            return approval_result

        if request.intent == "capabilities":
            lines = [f"{item.intent}: {item.description}" for item in self.registry.list_all()]
            return SamResult(
                status="success",
                summary="Capabilities listed.",
                next_action="stop",
                metadata={"intent": request.intent, "capabilities": lines},
            )

        if request.intent == "create_goal":
            title = request.parameters.get("title", "").strip()
            if not title:
                return SamResult(
                    status="failed",
                    summary="Goal title is required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing title",
                    next_action="ask_user",
                )
            result, goal = self.goal_service.create_goal(title=title)
            return self._service_result("create_goal", result, goal.id if goal else None)

        if request.intent == "list_goals":
            result, goals = self.goal_service.list_goals(status="active")
            return self._service_result(
                "list_goals",
                result,
                metadata={
                    "count": len(goals),
                    "titles": [goal.title for goal in goals],
                },
            )

        if request.intent == "create_draft":
            title = str(request.parameters.get("title", "")).strip()
            body = str(request.parameters.get("body", "")).strip()
            if not title or not body:
                return SamResult(
                    status="failed",
                    summary="Draft title and body are required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing title/body",
                    next_action="ask_user",
                )
            result, draft = self.pipeline_service.create_draft(
                title=title,
                body=body,
                content_type=request.parameters.get("content_type", "report"),
            )
            return self._service_result("create_draft", result, draft.id if draft else None)

        if request.intent == "list_workflows":
            result, drafts = self.pipeline_service.list_documents(limit=20)
            return self._service_result(
                "list_workflows",
                result,
                metadata={
                    "count": len(drafts),
                    "titles": [draft.title for draft in drafts],
                },
            )

        return SamResult(
            status="success",
            summary="No actionable intent matched; treating as chat.",
            next_action="stop",
            metadata={"intent": "chat", "message": request.raw_text},
        )

    def _check_authority(self, request: IntentRequest, action_category: str) -> SamResult | None:
        if self.authority_engine is None:
            return None

        decision = self.authority_engine.check(
            agent_id="sam_v2_router",
            agent_level=5,
            role_id="supervisor",
            tool_name=request.intent,
            action_category=action_category,
        )
        if not decision.allowed:
            return SamResult(
                status="blocked",
                summary="Intent blocked by authority rules.",
                error_type=ErrorType.MISSING_PERMISSION,
                error_message=decision.reason,
                next_action="request_approval",
                metadata={"intent": request.intent, "action_category": action_category},
            )

        if decision.requires_approval:
            if self.approval_manager is None:
                return SamResult(
                    status="needs_approval",
                    summary="Intent requires approval.",
                    error_type=ErrorType.MISSING_PERMISSION,
                    error_message=decision.reason,
                    next_action="request_approval",
                    metadata={"intent": request.intent, "action_category": action_category},
                )

            create_result, approval = self.approval_manager.create_request(
                agent_id="sam_v2_router",
                agent_name="Sam v2 Router",
                tool_name=request.intent,
                tool_arguments=request.parameters,
                action_category=action_category,
                reason=decision.reason,
                context=request.raw_text,
            )
            if not create_result.ok or approval is None:
                return SamResult(
                    status="failed",
                    summary="Approval was required but request creation failed.",
                    error_type=create_result.error_type or ErrorType.FILE_ACCESS_ERROR,
                    error_message=create_result.error_message,
                    next_action="retry",
                )

            return SamResult(
                status="needs_approval",
                summary="Intent requires approval before execution.",
                error_type=ErrorType.MISSING_PERMISSION,
                error_message=decision.reason,
                next_action="request_approval",
                metadata={"approval_id": approval.id, "intent": request.intent},
            )

        return None

    def _service_result(
        self,
        intent: str,
        result: SamResult,
        identifier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SamResult:
        merged_metadata = {"intent": intent}
        if identifier is not None:
            merged_metadata["id"] = identifier
        if metadata:
            merged_metadata.update(metadata)
        return SamResult(
            status=result.status,
            summary=result.summary,
            error_type=result.error_type,
            error_message=result.error_message,
            next_action=result.next_action,
            metadata=merged_metadata,
        )
