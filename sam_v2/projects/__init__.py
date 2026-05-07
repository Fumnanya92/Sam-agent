"""Project awareness helpers for Sam v2."""

from .diff_summary import DiffFileSummary, DiffSummary, DiffSummaryService
from .failure_analysis import CommandFailureAnalysis, FailureAnalysisService, resolve_flutter_command
from .inspector import ProjectInspection, ProjectInspector, inspection_metadata
from .registry import ProjectRecord, ProjectRegistry

__all__ = [
    "DiffFileSummary",
    "DiffSummary",
    "DiffSummaryService",
    "CommandFailureAnalysis",
    "FailureAnalysisService",
    "ProjectInspection",
    "ProjectInspector",
    "ProjectRecord",
    "ProjectRegistry",
    "inspection_metadata",
    "resolve_flutter_command",
]
