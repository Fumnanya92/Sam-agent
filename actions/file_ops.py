"""
actions/file_ops.py — DEPRECATED re-export shim.

The functions and module-level state previously defined here now live in
``actions/file_controller.py``. This shim keeps existing imports working
(``from actions.file_ops import create_note`` etc.) until callers can be
migrated to import directly from ``actions.file_controller``.

Strip-down phase (2026-05-01): scheduled for full removal once the four
existing import sites in ``intents/handlers.py`` and one in
``tests/test_new_features.py`` are updated.

Note: ``find_files`` here is the lightweight list-returning variant
(``find_files_quick`` in file_controller). The richer formatted-string
``find_files`` lives directly in file_controller and is exposed via the
dispatcher's ``find`` action.
"""
from actions.file_controller import (
    NOTES_DIR,
    DAILY_LOG,
    _CATEGORY_KEYWORDS,
    _infer_category,
    create_note,
    append_to_log,
    open_path,
    open_notes_folder,
)
from actions.file_controller import find_files_quick as find_files

__all__ = [
    "NOTES_DIR",
    "DAILY_LOG",
    "create_note",
    "append_to_log",
    "find_files",
    "open_path",
    "open_notes_folder",
]
