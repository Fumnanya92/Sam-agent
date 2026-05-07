"""Project planning and delegation reporting helpers for Sam v2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sam_v2.diagnostics.error_types import ErrorType
from sam_v2.diagnostics.result import SamResult
from sam_v2.workers import FileWriteSpec, ToolingWorker

from .registry import ProjectRecord, ProjectRegistry


IMPLEMENTATION_PLAN = """# Implementation Plan

## Project

{project_name}

## Build slices

1. Keep `index.html` as the shell only.
2. Keep `styles.css` responsible for presentation only.
3. Keep `app.js` responsible for game logic only.
4. Keep `run_project.py` as the local validation command.

## Next implementation steps

1. Add score tracking and rematch flow.
2. Extract win-check logic into smaller helpers if complexity grows.
3. Add accessibility labels and keyboard support.
"""

TESTING_PLAN = """# Testing Plan

## Project

{project_name}

## Current checks

1. `python run_project.py` confirms the modular scaffold is wired correctly.

## Next testing steps

1. Add lightweight rule validation for win detection.
2. Add a browser smoke check for reset behavior.
3. Add regression checks for draw handling.
"""

DELEGATION_REPORT = """# Delegation Report

## Project

{project_name}

## Worker ownership

- Mason (`code`): owns `IMPLEMENTATION_PLAN.md`, `index.html`, `styles.css`, and `app.js`
- Beacon (`test`): owns `TESTING_PLAN.md` and future validation coverage
- Pilot (`dev`): owns `DELEGATION.md`, `run_project.py`, and project run verification

## Completed planning actions

1. Mason wrote the implementation plan.
2. Beacon wrote the testing plan.
3. Pilot wrote this delegation report.
"""


@dataclass
class ProjectPlanRequest:
    query: str


class ProjectPlanner:
    def __init__(
        self,
        *,
        project_registry: ProjectRegistry,
        tooling_worker: ToolingWorker,
    ) -> None:
        self.project_registry = project_registry
        self.tooling_worker = tooling_worker

    def plan(self, request: ProjectPlanRequest) -> SamResult:
        project_result, project = self.project_registry.find_project(request.query)
        if not project_result.ok or project is None:
            return project_result

        project_root = Path(project.root_path)
        if not project_root.exists():
            return SamResult(
                status="failed",
                summary="Project root does not exist on disk.",
                error_type=ErrorType.FILE_ACCESS_ERROR,
                error_message=project.root_path,
                next_action="ask_user",
            )

        writes = [
            (
                "IMPLEMENTATION_PLAN.md",
                IMPLEMENTATION_PLAN.format(project_name=project.name),
                "Mason",
                "code",
                "Write the implementation plan for the project.",
            ),
            (
                "TESTING_PLAN.md",
                TESTING_PLAN.format(project_name=project.name),
                "Beacon",
                "test",
                "Write the testing plan for the project.",
            ),
            (
                "DELEGATION.md",
                DELEGATION_REPORT.format(project_name=project.name),
                "Pilot",
                "dev",
                "Write the delegation report for the project.",
            ),
        ]

        delegation: list[dict[str, str]] = []
        for filename, content, worker_name, worker_type, description in writes:
            write_result, task = self.tooling_worker.execute_write(
                FileWriteSpec(
                    name=f"plan_{project.project_id}_{filename.replace('.', '_')}",
                    worker_type=worker_type,
                    worker_name=worker_name,
                    target_path=project_root / filename,
                    content=content,
                    description=description,
                    overwrite=True,
                )
            )
            if not write_result.ok:
                write_result.metadata.setdefault("project_id", project.project_id)
                write_result.metadata.setdefault("name", project.name)
                write_result.metadata.setdefault("root_path", project.root_path)
                write_result.metadata.setdefault("delegation", delegation)
                return write_result
            delegation.append(
                {
                    "task_id": task.task_id,
                    "worker_name": task.worker_name,
                    "worker_type": task.worker_type,
                    "artifact": filename,
                    "status": task.status,
                }
            )

        self._update_project_files(project, [item[0] for item in writes])
        return SamResult(
            status="success",
            summary=(
                f"Planned {project.name} with named worker ownership. "
                "Mason owns implementation, Beacon owns testing, and Pilot owns coordination."
            ),
            next_action="stop",
            metadata={
                "project_id": project.project_id,
                "name": project.name,
                "root_path": project.root_path,
                "delegation": delegation,
                "plan_files": [item[0] for item in writes],
            },
        )

    def show_delegation(self, query: str) -> SamResult:
        project_result, project = self.project_registry.find_project(query)
        if not project_result.ok or project is None:
            return project_result

        report_path = Path(project.root_path) / "DELEGATION.md"
        if not report_path.exists():
            return SamResult(
                status="failed",
                summary="Delegation report not found for this project.",
                error_type=ErrorType.FILE_ACCESS_ERROR,
                error_message=str(report_path),
                next_action="ask_user",
            )

        try:
            report_text = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            return SamResult(
                status="failed",
                summary="Delegation report could not be read.",
                error_type=ErrorType.FILE_ACCESS_ERROR,
                error_message=str(exc),
                next_action="retry",
            )

        return SamResult(
            status="success",
            summary="Delegation is tracked for this project.",
            next_action="stop",
            metadata={
                "project_id": project.project_id,
                "name": project.name,
                "root_path": project.root_path,
                "delegation_report": report_text,
                "workers": ["Mason", "Beacon", "Pilot"],
            },
        )

    def _update_project_files(self, project: ProjectRecord, extra_files: list[str]) -> None:
        merged = list(dict.fromkeys((project.important_files or []) + extra_files))
        self.project_registry.register(
            ProjectRecord(
                project_id=project.project_id,
                name=project.name,
                root_path=project.root_path,
                stack=project.stack,
                test_command=project.test_command,
                build_command=project.build_command,
                run_command=project.run_command,
                deployment_method=project.deployment_method,
                risk_level=project.risk_level,
                active_branch=project.active_branch,
                important_files=merged,
            )
        )
