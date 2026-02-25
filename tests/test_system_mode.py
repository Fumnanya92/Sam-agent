import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from system.system_monitor import get_system_report
import json

report = get_system_report()
print(json.dumps(report, indent=2))
