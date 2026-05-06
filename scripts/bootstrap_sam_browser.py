"""
scripts/bootstrap_sam_browser.py

One-time setup: launch Chrome with the persistent Sam browser profile
so you can log in to WhatsApp Web (and other sites) once.

After this, every Sam browser action runs inside an already-authenticated
session — no QR scan on next launch.

Usage:
    python scripts/bootstrap_sam_browser.py
"""

import os
import subprocess
import sys
import time


def find_chrome() -> str | None:
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            r"Google\Chrome\Application\chrome.exe",
        ),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def main():
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chrome not found. Install Chrome and try again.")
        sys.exit(1)

    local = os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")
    profile_dir = os.path.join(local, "Sam", "BrowserProfile")
    os.makedirs(profile_dir, exist_ok=True)

    print(f"Sam browser profile: {profile_dir}")
    print()
    print("Chrome will open. Please:")
    print("  1. Go to https://web.whatsapp.com and scan the QR code.")
    print("  2. Sign in to any other sites Sam needs (Gmail, GitHub, etc.).")
    print("  3. Close Chrome when done — Sam will reuse this session automatically.")
    print()
    input("Press Enter to launch Chrome...")

    proc = subprocess.Popen([
        chrome,
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile_dir}",
        "https://web.whatsapp.com",
    ])

    print(f"Chrome launched (PID {proc.pid}). Log in and then close it.")
    print("This script will wait until Chrome exits...")
    proc.wait()
    print("Chrome closed. Sam profile saved.")
    print(f"Profile path: {profile_dir}")


if __name__ == "__main__":
    main()
