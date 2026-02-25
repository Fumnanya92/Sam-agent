import os
from pathlib import Path

# Load .env manually without depending on python-dotenv
env_path = Path(__file__).resolve().parents[1] / '.env'
import sys

# Ensure project root is on sys.path so imports work when running this script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Run planner
from assistant.daily_planner import generate_daily_plan

print(generate_daily_plan())
