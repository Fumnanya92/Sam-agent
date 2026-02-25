import subprocess
import requests
import time
import os

CHROME_PATH = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222
USER_DATA_DIR = r"C:\SamChrome"
WHATSAPP_URL = "https://web.whatsapp.com"


def is_debug_chrome_running() -> bool:
    try:
        response = requests.get(f"http://localhost:{DEBUG_PORT}/json", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def launch_debug_chrome():
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR, exist_ok=True)

    subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f'--user-data-dir={USER_DATA_DIR}',
        "--remote-allow-origins=*",
        "--new-window",
        WHATSAPP_URL
    ])

    time.sleep(5)  # allow Chrome to boot


def ensure_chrome_running():
    if not is_debug_chrome_running():
        launch_debug_chrome()
        return True
    return False
