import psutil
import json
from pathlib import Path

# Default processes Sam will never kill, even in auto mode
_DEFAULT_WHITELIST = {
    "explorer.exe", "svchost.exe", "winlogon.exe", "lsass.exe",
    "csrss.exe", "services.exe", "system", "smss.exe",
    "chrome.exe", "code.exe", "python.exe", "pythonw.exe",
}

_WHITELIST_FILE = Path(__file__).parent.parent / "config" / "process_whitelist.json"


def load_whitelist() -> set[str]:
    """Load user-customised whitelist from config, merged with defaults."""
    wl = set(_DEFAULT_WHITELIST)
    if _WHITELIST_FILE.exists():
        try:
            with open(_WHITELIST_FILE, "r") as f:
                data = json.load(f)
                wl.update(n.lower() for n in data.get("protected", []))
        except Exception:
            pass
    return wl


def save_whitelist_entry(name: str):
    """Add a process name to the persistent whitelist."""
    data = {"protected": []}
    if _WHITELIST_FILE.exists():
        try:
            with open(_WHITELIST_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    if name.lower() not in [n.lower() for n in data["protected"]]:
        data["protected"].append(name.lower())
    _WHITELIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_WHITELIST_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_heavy_processes(limit=5):
    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)
    return processes[:limit]


def _name_matches(query: str, proc_name: str) -> bool:
    """True when proc_name is the process the user intended.
    Prevents 'python' from matching 'pythonw.exe' or 'chrome' from matching 'chromedriver.exe'.
    """
    q = query.lower().strip()
    p = proc_name.lower().strip()
    if q == p:
        return True                  # exact: "chrome.exe" == "chrome.exe"
    if q + ".exe" == p:
        return True                  # "chrome" → "chrome.exe"
    if p.startswith(q + "."):
        return True                  # "python" → "python.exe"  (not pythonw.exe)
    return False


def kill_process_by_name(name: str, respect_whitelist: bool = True) -> list[str]:
    """Kill all processes matching name. Returns list of killed process names."""
    whitelist = load_whitelist() if respect_whitelist else set()
    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info['name'] or ""
            if _name_matches(name, proc_name):
                if proc_name.lower() in whitelist:
                    continue   # protected — skip silently
                proc.kill()
                killed.append(proc_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed
