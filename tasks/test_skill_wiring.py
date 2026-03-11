"""Simulate exactly what Sam does when user says 'test the login flow'."""
import sys
sys.path.insert(0, ".")

from skills.loader import skill_loader

class FakeUI:
    def write_log(self, msg):
        print("[UI]", msg)

# Replicate exactly what handlers._handle_skill does
intent = "test_the_app"
parameters = {"task": "test the login flow", "url": "http://localhost:49218"}

try:
    result = skill_loader.run(
        intent, parameters, FakeUI(),
        reminder_engine=None,
        watcher=None,
        terminal_runner=None,
    )
    print("Result:", result)
except Exception as e:
    import traceback
    traceback.print_exc()
