"""Project awareness helpers for Sam v2."""

from .failure_analysis import CommandFailureAnalysis, FailureAnalysisService, resolve_flutter_command
from .inspector import ProjectInspection, ProjectInspector, inspection_metadata
from .registry import ProjectRecord, ProjectRegistry

__all__ = [
    "CommandFailureAnalysis",
    "FailureAnalysisService",
    "ProjectInspection",
    "ProjectInspector",
    "ProjectRecord",
    "ProjectRegistry",
    "inspection_metadata",
    "resolve_flutter_command",
]
