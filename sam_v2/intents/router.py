"""Minimal intent parser and router for Sam v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sam_v2.approvals import ApprovalManager, AuthorityEngine
from sam_v2.capabilities import CapabilityAwarenessService, CapabilityRegistry, build_default_registry
from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.result import SamResult
from sam_v2.llm import OllamaClient, OllamaIntentOutput
from sam_v2.projects import (
    ProjectInspector,
    ProjectRegistry,
    ProjectScaffoldRequest,
    ProjectScaffolder,
    inspection_metadata,
)
from sam_v2.storage import TaskRecord, create_task, update_task
from sam_v2.tools import SafeLocalTools
from sam_v2.upgrades import UpgradeProposalManager
from sam_v2.workers import CommandSpec, ToolingWorker
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
        self.upgrade_manager = UpgradeProposalManager(self.db_path.with_name("upgrades.json"))
        self.project_inspector = ProjectInspector(
            registry=self.project_registry,
            tools=SafeLocalTools(db_path=self.db_path),
        )
        self.tooling_worker = ToolingWorker(
            db_path=self.db_path,
            authority_engine=self.authority_engine,
            approval_manager=self.approval_manager,
        )
        self.project_scaffolder = ProjectScaffolder(
            workspace_root=Path.cwd() / "sam_v2" / "workspace" / "projects",
            project_registry=self.project_registry,
            tooling_worker=self.tooling_worker,
        )
        self.awareness = CapabilityAwarenessService(
            self.registry,
            project_registry=self.project_registry,
            upgrade_manager=self.upgrade_manager,
        )

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

        if "request upgrade for " in lowered or "propose upgrade for " in lowered:
            marker = "request upgrade for " if "request upgrade for " in lowered else "propose upgrade for "
            capability_text = text[lowered.index(marker) + len(marker):].strip()
            return IntentRequest(
                intent="propose_upgrade",
                parameters={"capability_name": capability_text},
                raw_text=text,
                source="rules",
            )

        if (
            ("do you have " in lowered or lowered.startswith("can you ") or lowered.startswith("do you support "))
            and any(
                phrase in lowered
                for phrase in ["browser worker", "voice input", "react dashboard", "meeting assistant", "remote access"]
            )
        ):
            capability_text = ""
            for phrase in ["browser worker", "voice input", "react dashboard", "meeting assistant", "remote access"]:
                if phrase in lowered:
                    capability_text = phrase
                    break
            return IntentRequest(
                intent="awareness_check",
                parameters={"capability_name": capability_text.replace(" ", "_")},
                raw_text=text,
                source="rules",
            )

        if lowered.startswith("create goal:"):
            return IntentRequest(
                intent="create_goal",
                parameters={"title": text.split(":", 1)[1].strip()},
                raw_text=text,
                source="rules",
            )

        if lowered.startswith("create task:"):
            return IntentRequest(
                intent="create_task",
                parameters={"title": text.split(":", 1)[1].strip()},
                raw_text=text,
                source="rules",
            )

        scaffold_markers = [
            "start a new html game project called ",
            "create a new html game project called ",
            "scaffold a new html game project called ",
        ]
        for marker in scaffold_markers:
            if lowered.startswith(marker):
                return IntentRequest(
                    intent="scaffold_project",
                    parameters={"name": text[len(marker):].strip(), "project_type": "html_game"},
                    raw_text=text,
                    source="rules",
                )

        if lowered.startswith("update task "):
            payload = text[len("update task "):].strip()
            task_id_text, _, remainder = payload.partition(":")
            status_text, sep, notes_text = remainder.partition("|")
            return IntentRequest(
                intent="update_task",
                parameters={
                    "task_id": task_id_text.strip(),
                    "status": status_text.strip(),
                    "notes": notes_text.strip() if sep else "",
                },
                raw_text=text,
                source="rules",
            )

        if "help me fix" in lowered or "broken app" in lowered:
            return IntentRequest(intent="plan_request", raw_text=text, source="rules")

        if "that thing" in lowered or "from yesterday" in lowered or "yesterday" in lowered:
            return IntentRequest(
                intent="chat",
                raw_text=text,
                needs_clarification=True,
                clarification_question="What specifically would you like me to check from yesterday?",
                source="rules",
                confidence="medium",
            )

        if lowered in {"list goals", "show goals", "what goals do i have"}:
            return IntentRequest(intent="list_goals", raw_text=text, source="rules")

        if any(
            phrase in lowered
            for phrase in {"list my projects", "show my projects", "what projects do i have", "show projects"}
        ):
            return IntentRequest(intent="list_projects", raw_text=text, source="rules")

        if lowered.startswith("show project ") or lowered.startswith("identify project "):
            prefix = "show project " if lowered.startswith("show project ") else "identify project "
            return IntentRequest(
                intent="project_details",
                parameters={"query": text[len(prefix):].strip()},
                raw_text=text,
                source="rules",
            )

        if lowered.startswith("run project "):
            return IntentRequest(
                intent="run_project",
                parameters={"query": text[len("run project "):].strip()},
                raw_text=text,
                source="rules",
            )

        if lowered in {"run it", "start it"}:
            return IntentRequest(
                intent="run_project",
                parameters={"use_memory": True},
                raw_text=text,
                source="rules",
            )

        if lowered.startswith("inspect project "):
            return IntentRequest(
                intent="inspect_project_repo",
                parameters={"query": text[len("inspect project "):].strip()},
                raw_text=text,
                source="rules",
            )

        if lowered.startswith("inspect git state for project "):
            return IntentRequest(
                intent="inspect_git_state",
                parameters={"query": text[len("inspect git state for project "):].strip()},
                raw_text=text,
                source="rules",
            )

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
            awareness_result = self.awareness.describe_self()
            if not awareness_result.ok:
                return self._service_result("capabilities", awareness_result)
            awareness_result.metadata.setdefault("intent", request.intent)
            awareness_result.metadata.setdefault("source", request.source)
            awareness_result.metadata.setdefault("confidence", request.confidence)
            return awareness_result

        if request.intent == "awareness_check":
            capability_name = str(request.parameters.get("capability_name", "")).strip()
            if not capability_name:
                return SamResult(
                    status="failed",
                    summary="Capability name is required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing capability name",
                    next_action="ask_user",
                    metadata={"intent": "awareness_check", "source": request.source},
                )
            awareness_result = self.awareness.check_request(capability_name)
            awareness_result.metadata.setdefault("intent", "awareness_check")
            awareness_result.metadata.setdefault("source", request.source)
            awareness_result.metadata.setdefault("confidence", request.confidence)
            return awareness_result

        if request.intent == "propose_upgrade":
            capability_name = str(request.parameters.get("capability_name", "")).strip().replace(" ", "_")
            if not capability_name:
                return SamResult(
                    status="failed",
                    summary="Capability name is required for an upgrade proposal.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing capability name",
                    next_action="ask_user",
                    metadata={"intent": "propose_upgrade", "source": request.source},
                )
            proposal_result = self.awareness.propose_upgrade(
                capability_name,
                f"User requested upgrade support for {capability_name}.",
            )
            proposal_result.metadata.setdefault("intent", "propose_upgrade")
            proposal_result.metadata.setdefault("source", request.source)
            proposal_result.metadata.setdefault("confidence", request.confidence)
            return proposal_result

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

        if request.intent == "create_task":
            title = str(request.parameters.get("title", "")).strip()
            if not title:
                return SamResult(
                    status="failed",
                    summary="Task title is required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing title",
                    next_action="ask_user",
                )
            result, task_id = create_task(self.db_path, TaskRecord(title=title))
            return self._service_result("create_task", result, identifier=str(task_id) if task_id is not None else None)

        if request.intent == "scaffold_project":
            project_name = str(request.parameters.get("name", "")).strip()
            project_type = str(request.parameters.get("project_type", "html_game")).strip() or "html_game"
            scaffold_result = self.project_scaffolder.scaffold(
                ProjectScaffoldRequest(name=project_name, project_type=project_type)
            )
            scaffold_result.metadata.setdefault("intent", "scaffold_project")
            scaffold_result.metadata.setdefault("source", request.source)
            scaffold_result.metadata.setdefault("confidence", request.confidence)
            return scaffold_result

        if request.intent == "update_task":
            task_id_text = str(request.parameters.get("task_id", "")).strip()
            status_text = str(request.parameters.get("status", "")).strip()
            notes_text = str(request.parameters.get("notes", "")).strip()
            if not task_id_text.isdigit():
                return SamResult(
                    status="failed",
                    summary="Task id is required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing or invalid task id",
                    next_action="ask_user",
                )
            if not status_text and not notes_text:
                return SamResult(
                    status="failed",
                    summary="Task update needs a status or notes value.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing update values",
                    next_action="ask_user",
                )
            result, task = update_task(
                self.db_path,
                int(task_id_text),
                status=status_text or None,
                notes=notes_text or None,
            )
            return self._service_result("update_task", result, identifier=str(task.id) if task is not None else task_id_text)

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

        if request.intent == "project_details":
            query = str(request.parameters.get("query", "")).strip()
            if not query:
                return SamResult(
                    status="failed",
                    summary="Project name is required.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing project query",
                    next_action="ask_user",
                    metadata={"intent": "project_details", "source": request.source},
                )
            project_result, project = self.project_registry.find_project(query)
            if not project_result.ok or project is None:
                return self._service_result("project_details", project_result, metadata={"query": query})
            return SamResult(
                status="success",
                summary=(
                    f"Project {project.name} is a {project.stack or 'unspecified'} project on branch "
                    f"{project.active_branch or 'unknown'}."
                ),
                next_action="stop",
                metadata={
                    "intent": "project_details",
                    "project_id": project.project_id,
                    "name": project.name,
                    "root_path": project.root_path,
                    "stack": project.stack,
                    "test_command": project.test_command or [],
                    "build_command": project.build_command or [],
                    "active_branch": project.active_branch,
                    "source": request.source,
                    "confidence": request.confidence,
                },
            )

        if request.intent == "run_project":
            query = str(request.parameters.get("query", "")).strip()
            if request.parameters.get("use_memory"):
                daily_state = memory_block.get("daily_state", {}) if isinstance(memory_block, dict) else {}
                query = str(daily_state.get("last_project_id", {}).get("value", "")).strip()
            if not query:
                return SamResult(
                    status="failed",
                    summary="Project name is required to run a project.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing project query",
                    next_action="ask_user",
                    metadata={"intent": "run_project", "source": request.source},
                )
            project_result, project = self.project_registry.find_project(query)
            if not project_result.ok or project is None:
                return self._service_result("run_project", project_result, metadata={"query": query})
            if not project.run_command:
                return SamResult(
                    status="failed",
                    summary=f"Project {project.name} does not have a run command configured.",
                    error_type=ErrorType.MISSING_CAPABILITY,
                    error_message="missing run command",
                    next_action="ask_user",
                    metadata={
                        "intent": "run_project",
                        "project_id": project.project_id,
                        "name": project.name,
                        "source": request.source,
                    },
                )
            worker_result, _task = self.tooling_worker.execute(
                CommandSpec(
                    name=f"run_project_{project.project_id}",
                    worker_type="dev",
                    command=project.run_command,
                    description=f"Run project {project.name}",
                    cwd=project.root_path,
                    timeout_seconds=30,
                )
            )
            worker_result.metadata.setdefault("intent", "run_project")
            worker_result.metadata.setdefault("project_id", project.project_id)
            worker_result.metadata.setdefault("name", project.name)
            worker_result.metadata.setdefault("root_path", project.root_path)
            worker_result.metadata.setdefault("run_command", project.run_command)
            worker_result.metadata.setdefault("source", request.source)
            worker_result.metadata.setdefault("confidence", request.confidence)
            return worker_result

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

        if request.intent == "inspect_project_repo":
            query = str(request.parameters.get("query", "")).strip()
            if not query:
                return SamResult(
                    status="failed",
                    summary="Project name is required for repo inspection.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing project query",
                    next_action="ask_user",
                    metadata={"intent": "inspect_project_repo", "source": request.source},
                )
            inspect_result, inspection = self.project_inspector.inspect(query)
            if not inspect_result.ok or inspection is None:
                return self._service_result("inspect_project_repo", inspect_result, metadata={"query": query})
            metadata = inspection_metadata(inspection)
            metadata["intent"] = "inspect_project_repo"
            metadata["source"] = request.source
            metadata["confidence"] = request.confidence
            changed_summary = (
                "clean working tree"
                if inspection.is_clean
                else f"{len(inspection.changed_files)} changed file(s)"
            )
            return SamResult(
                status="success",
                summary=(
                    f"{inspection.name} is on branch {inspection.branch or 'unknown'} with a "
                    f"{changed_summary}."
                ),
                next_action="stop",
                metadata=metadata,
            )

        if request.intent == "inspect_git_state":
            query = str(request.parameters.get("query", "")).strip()
            if not query:
                return SamResult(
                    status="failed",
                    summary="Project name is required for git inspection.",
                    error_type=ErrorType.TOOL_FAILED,
                    error_message="missing project query",
                    next_action="ask_user",
                    metadata={"intent": "inspect_git_state", "source": request.source},
                )
            project_result, project = self.project_registry.find_project(query)
            if not project_result.ok or project is None:
                return self._service_result("inspect_git_state", project_result, metadata={"query": query})
            git_result, snapshot = self.project_inspector.tools.inspect_git_state(project.root_path)
            if not git_result.ok or snapshot is None:
                return self._service_result("inspect_git_state", git_result, metadata={"query": query})
            return SamResult(
                status="success",
                summary=f"Git state for {project.name}: branch {snapshot.branch}, clean={snapshot.is_clean}.",
                next_action="stop",
                metadata={
                    "intent": "inspect_git_state",
                    "project_id": project.project_id,
                    "name": project.name,
                    "repo_root": snapshot.repo_root,
                    "branch": snapshot.branch,
                    "is_clean": snapshot.is_clean,
                    "changed_files": snapshot.changed_files,
                    "staged_files": snapshot.staged_files,
                    "unstaged_files": snapshot.unstaged_files,
                    "untracked_files": snapshot.untracked_files,
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
        merged_metadata = dict(result.metadata)
        merged_metadata["intent"] = intent
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
