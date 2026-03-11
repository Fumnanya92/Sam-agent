"""Run a real end-to-end test of the Flutter app on the given port."""
import sys
sys.path.insert(0, ".")

from skills.flutter_tester import _run

class FakeUI:
    def write_log(self, msg):
        print(msg)

_run(
    parameters={"task": "test the login flow", "url": "http://localhost:49218"},
    ui=FakeUI(),
)
