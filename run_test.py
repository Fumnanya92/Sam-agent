"""
run_test.py  — trigger Sam's flutter_tester skill directly and print live output.
"""
import sys, os, json, time
sys.path.insert(0, ".")

# Minimal UI shim so _log() calls print to console
class ConsoleUI:
    def write_log(self, msg):
        print(f"  {msg}", flush=True)

# Load the skill
from skills.flutter_tester import _run, save_credentials

# Ensure correct credentials are saved for the Estate project
save_credentials("Estate", "asecgroups229@gmail.com", "Bobby500")
print("Credentials confirmed for Estate.")

# Fire the test — Sam will auto-discover the port or ask if it can't find it
print("\n===  Sam: starting login flow test  ===\n")
result = _run(
    parameters={
        "task": (
            "Test the login flow: "
            "open the app, navigate to the login screen, "
            "enter email asecgroups229@gmail.com and password Bobby500, "
            "submit, and verify successful authentication. "
            "Report any error messages exactly as shown on screen."
        )
    },
    ui=ConsoleUI(),
    intent="test_login_flow",
)
print(f"\n===  Sam result  ===\n{result}\n")
