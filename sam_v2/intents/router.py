"""Minimal intent parser and router for Sam v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sam_v2.approvals import ApprovalManager, AuthorityEngine
from sam_v2.capabilities import CapabilityRegistry, build_default_registry
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.result import SamResult
from sam_v2.llm import OllamaClient, OllamaIntentOutput
from sam_v2.projects import ProjectRegistry
from sam_v2.workflows import GoalService, PipelineService


@dataclass
class IntentRequest:
    intent: str
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""
    response_text: str = ""
    confidence: str = "low"
    source: str = "rules"


class IntentRouter:
    def __init__(
        self,
        *,
        db_path: str | Path,
        registry: CapabilityRegistry | None = None,
        authority_engine: AuthorityEngine | None = None,
        approval_manager: ApprovalManager | None = None,
        model_client: OllamaClient | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.registry = registry or build_default_registry()
        self.authority_engine = authority_engine
        self.approval_manager = approval_manager
        self.goal_service = GoalService(self.db_path)
        self.pipeline_service = PipelineService(self.db_path)
        self.model_client = model_client or OllamaClient()
        self.project_registry = ProjectRegistry(self.db_path.with_name("projects.json"))

    def parse(self, user_text: str, memory_block: dict[str, Any] | None = None) -> IntentRequest:
        text = user_text.strip()
        rule_request = self._parse_with_rules(text)
        if rule_request.intent != "chat":
            return rule_request

        llm_request = self._parse_with_llm(text, memory_block)
        if llm_request is not None:
            return llm_request

        return rule_request

    def _parse_with_rules(self, text: str) -> IntentRequest:
        lowered = text.lower()

        if any(phrase in lowered for phrase in ["what can you do", "capabilities", "list capabilities"]):
            return IntentRequest(intent="capabilities", raw_text=text, source="rules")

        if lowered.startswith("create goal:"):
            return IntentRequest(
                intent="create_goal",
                parameters={"title": text.split(":", 1)[1].strip()},
                raw_text=text,
                source="rules",
            )

        if "help me fix" in lowered or "broken app" in lowered:
            return IntentRequest(intent="plan_request", raw_text=text, source="rules")

        if lowered in {"list goals", "show goals", "what goals do i have"}:
            return IntentRequest(intent="list_goals", raw_text=text, source="rules")

        if any(
            phrase in lowered
            for phrase in {"list my projects", "show my projects", "what projects do i have", "show projects"}
        ):
            return IntentRequest(intent="list_projects", raw_text=text, source="rules")

        if lowered.startswith("create draft:"):
            payload = text.split(":", 1)[1].strip()
            return IntentRequest(
                intent="create_draft",
                parameters={"title": payload[:60] or "Untitled draft", "body": payload, "content_type": "report"},
                raw_text=text,
                source="rules",
            )

        if lowered in {"list workflows", "list drafts", "show drafts"}:
            return IntentRequest(intent="list_workflows", raw_text=text, source="rules")

        if "inspect this repo" in lowered or "inspect the repo" in lowered or "what is broken" in lowered:
            return IntentRequest(
                intent="inspect_repo",
                raw_text=text,
                source="rules",
            )

        if "push the changes" in lowered or lowered.startswith("push changes") or lowered.startswith("git push"):
            return IntentRequest(intent="push_changes", raw_text=text, source="rules")

        return IntentRequest(intent="chat", raw_text=text, source="rules")

    def handle(self, user_text: str, memory_block: dict[str, Any] | None = None) -> SamResult:
        request = self.parse(user_text, memory_block)
        if request.needs_clarification:
            return SamResult(
                status="success",
                summary=request.clarification_question or "I need a bit more detail before I act.",
                next_action="ask_user",
                metadata={
                    "intent": "clarify",
                    "source": request.source,
                    "confidence": request.confidence,
                },
            )

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
                metadata={
                    "intent": request.intent,
                    "capabilities": lines,
                    "source": request.source,
                    "confidence": request.confidence,
                },
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

        if request.intent == "list_projects":
            project_result, projects = self.project_registry.list_projects()
            if not project_result.ok:
                return self._service_result("list_projects", project_result)
            if not projects:
                return SamResult(
                    status="success",
                    summary="I do not have any registered projects yet.",
                    next_action="ask_user",
                    metadata={
                        "intent": "list_projects",
                        "count": 0,
                        "projects": [],
                        "source": request.source,
                        "confidence": request.confidence,
                    },
                )
            names = [project.name for project in projects]
            return SamResult(
                status="success",
                summary=f"I know about {len(names)} project(s): {', '.join(names)}.",
                next_action="stop",
                metadata={
                    "intent": "list_projects",
                    "count": len(names),
                    "projects": names,
                    "source": request.source,
                    "confidence": request.confidence,
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

        if request.intent == "push_changes":
            return self._request_push_approval(request)

        if request.intent == "inspect_repo":
            return SamResult(
                status="success",
                summary="I can inspect a repo, but I need the project path or registered project name first.",
                next_action="ask_user",
                metadata={
                    "intent": "inspect_repo",
                    "source": request.source,
                    "confidence": request.confidence,
                },
            )

        if request.intent == "plan_request":
            return SamResult(
                status="success",
                summary="I can help with that, but I need the project name or the specific issue first.",
                next_action="ask_user",
                metadata={
                    "intent": "plan_request",
                    "source": request.source,
                    "confidence": request.confidence,
                },
            )

        return SamResult(
            status="success",
            summary=request.response_text or "No actionable intent matched; treating as chat.",
            next_action="stop",
            metadata={
                "intent": "chat",
                "message": request.raw_text,
                "source": request.source,
                "confidence": request.confidence,
            },
        )

    def _parse_with_llm(self, text: str, memory_block: dict[str, Any] | None = None) -> IntentRequest | None:
        if not text:
            return None
        if not self.model_client.is_available():
            return None
        try:
            output = self.model_client.classify_request(
                text,
                capabilities=[item.intent for item in self.registry.list_all()],
                memory_block=memory_block,
            )
        except Exception:
            return None
        return self._intent_request_from_llm(text, output)

    def _intent_request_from_llm(self, text: str, output: OllamaIntentOutput) -> IntentRequest:
        supported_intents = {item.intent for item in self.registry.list_all()}
        intent = output.intent if output.intent in supported_intents else "chat"
        return IntentRequest(
            intent=intent,
            parameters=output.parameters,
            raw_text=text,
            needs_clarification=output.needs_clarification,
            clarification_question=output.clarification_question,
            response_text=output.response_text,
            confidence=output.confidence,
            source=output.source,
        )

    def _request_push_approval(self, request: IntentRequest) -> SamResult:
        if self.approval_manager is None:
            return SamResult(
                status="needs_approval",
                summary="Pushing changes requires approval before I continue.",
                error_type=ErrorType.MISSING_PERMISSION,
                error_message="git push requires approval",
                next_action="request_approval",
                metadata={"intent": "push_changes", "source": request.source, "confidence": request.confidence},
            )

        ensure_result = self.approval_manager.ensure_schema()
        if not ensure_result.ok:
            return SamResult(
                status="failed",
                summary="Approval store could not be prepared for a push request.",
                error_type=ensure_result.error_type or ErrorType.FILE_ACCESS_ERROR,
                error_message=ensure_result.error_message,
                next_action=ensure_result.next_action or "retry",
                metadata={"intent": "push_changes", "source": request.source},
            )

        create_result, approval = self.approval_manager.create_request(
            agent_id="sam_v2_router",
            agent_name="Sam v2 Router",
            tool_name="git.push",
            tool_arguments={"request_text": request.raw_text},
            action_category="execute_command",
            reason="Git push is approval-sensitive.",
            context=request.raw_text,
        )
        if not create_result.ok or approval is None:
            return SamResult(
                status="failed",
                summary="Approval request creation failed for push action.",
                error_type=create_result.error_type or ErrorType.FILE_ACCESS_ERROR,
                error_message=create_result.error_message,
                next_action=create_result.next_action or "retry",
                metadata={"intent": "push_changes", "source": request.source},
            )

        return SamResult(
            status="needs_approval",
            summary="Pushing changes requires approval before I continue.",
            error_type=ErrorType.MISSING_PERMISSION,
            error_message="git push requires approval",
            next_action="request_approval",
            metadata={
                "intent": "push_changes",
                "approval_id": approval.id,
                "source": request.source,
                "confidence": request.confidence,
            },
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
        merged_metadata.setdefault("source", "rules")
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
