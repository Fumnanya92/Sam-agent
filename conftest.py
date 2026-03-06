# These files are standalone runner scripts, not pytest test suites.
# Pytest would crash importing them because they call sys.exit() at module level.
collect_ignore = [
    "tests/archive",
    "tests/test_advanced_system_mode.py",
    "tests/test_debug_vscode_mode.py",
    "tests/test_intent_refactoring.py",
    "tests/test_screen_vision.py",
    "tests/test_system_integration.py",
    "tests/test_whatsapp_integration.py",
]
collect_ignore_glob = ["tests/archive/*"]
