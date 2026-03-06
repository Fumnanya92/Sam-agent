"""
window_tracker.py — Active foreground window detection using Windows API.

Uses ctypes.windll (built-in on Windows) + psutil (already a project dependency).
Falls back gracefully on non-Windows platforms.
"""
import ctypes
import ctypes.wintypes


def get_foreground_window_info() -> dict:
    """
    Return info about the currently focused window.

    Returns a dict with keys:
        title   (str)  — window title text
        process (str)  — executable name, e.g. 'Code.exe'
        exe     (str)  — full path to executable
        pid     (int)  — process ID

    Returns empty strings / 0 on failure or non-Windows.
    """
    result = {"title": "", "process": "", "exe": "", "pid": 0}

    try:
        import psutil

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            result["title"] = buff.value

        # Process info
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        result["pid"] = pid.value

        if pid.value:
            try:
                proc = psutil.Process(pid.value)
                result["process"] = proc.name()
                result["exe"] = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    except Exception:
        # Non-Windows or unexpected failure — return empty result
        pass

    return result
