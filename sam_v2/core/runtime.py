"""Minimal core assistant runtime for Sam v2."""

from __future__ import annotations

from pathlib import Path

from sam_v2.approvals import ApprovalManager, AuthorityConfig, AuthorityEngine
from sam_v2.capabilities import CapabilityRegistry
from sam_v2.diagnostics.result import SamResult
from sam_v2.diagnostics.run_logger import RunLogger
from sam_v2.storage.db import init_storage

from .request_handler import RequestHandler
from .session import RuntimeSession


class SamRuntime:
    def __init__(
        self,
        *,
        db_path: str | Path,
        memory_path: str | Path,
        session_path: str | Path,
        registry: CapabilityRegistry | None = None,
        authority_engine: AuthorityEngine | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.memory_path = Path(memory_path)
        self.session_path = Path(session_path)
        self.run_logger = RunLogger("sam_v2 core runtime")
        self.session = RuntimeSession()
        self.approval_manager = ApprovalManager(self.db_path)
        self.authority_engine = authority_engine or AuthorityEngine(AuthorityConfig(default_level=5))
        self.handler = RequestHandler(
            db_path=self.db_path,
            memory_path=self.memory_path,
            session_path=self.session_path,
            registry=registry,
            authority_engine=self.authority_engine,
            approval_manager=self.approval_manager,
        )
        self._started = False

    def start(self) -> SamResult:
        if self._started:
            return SamResult(status="success", summary="Runtime already started.", next_action="stop")

        self.run_logger.log(
            "startup_started",
            {
                "db_path": str(self.db_path),
                "memory_path": str(self.memory_path),
                "session_path": str(self.session_path),
                "session_id": self.session.session_id,
            },
        )
        storage_result = init_storage(self.db_path)
        self.run_logger.log("storage_initialized", {"status": storage_result.status, "summary": storage_result.summary})
        if not storage_result.ok:
            return storage_result

        approval_result = self.approval_manager.ensure_schema()
        self.run_logger.log(
            "approval_schema_initialized",
            {"status": approval_result.status, "summary": approval_result.summary},
        )
        if not approval_result.ok:
            return approval_result

        self._started = True
        result = SamResult(
            status="success",
            summary="Runtime started.",
            next_action="stop",
            metadata={"session_id": self.session.session_id},
        )
        self.run_logger.log("startup_complete", result.metadata)
        return result

    def handle_text(self, user_text: str) -> SamResult:
        if not self._started:
            start_result = self.start()
            if not start_result.ok:
                return start_result
        return self.handler.handle(user_text, self.session)

    def shutdown(self) -> SamResult:
        self.run_logger.log(
            "shutdown_complete",
            {
                "session_id": self.session.session_id,
                "request_count": self.session.request_count,
                "last_intent": self.session.last_intent,
            },
        )
        self._started = False
        return SamResult(status="success", summary="Runtime stopped.", next_action="stop")
