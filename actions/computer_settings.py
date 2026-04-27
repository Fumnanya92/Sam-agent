# actions/computer_settings.py
# Computer UI settings — volume, brightness, dark mode, WiFi, window management.
# Gemini intent detection replaced with Sam's llm_bridge.

import json
import re
import time
import subprocess
import sys
import platform
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

_OS = platform.system()


# ─── Volume ────────────────────────────────────────────────────────────────────

def volume_up():
    if _OS == "Windows":
        for _ in range(5): pyautogui.press("volumeup")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        "set volume output volume (output volume of (get volume settings) + 10)"])
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"])


def volume_down():
    if _OS == "Windows":
        for _ in range(5): pyautogui.press("volumedown")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        "set volume output volume (output volume of (get volume settings) - 10)"])
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"])


def volume_mute():
    if _OS == "Windows":
        pyautogui.press("volumemute")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", "set volume with output muted"])
    else:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])


def volume_set(value: int):
    value = max(0, min(100, value))
    if _OS == "Windows":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            import math
            devices   = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol       = cast(interface, POINTER(IAudioEndpointVolume))
            vol_db    = -65.25 if value == 0 else max(-65.25, 20 * math.log10(value / 100))
            vol.SetMasterVolumeLevel(vol_db, None)
            return
        except Exception as e:
            print(f"[Settings] pycaw failed: {e}")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", f"set volume output volume {value}"])
        return
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"])


# ─── Brightness / Display ──────────────────────────────────────────────────────

def brightness_up():
    if _OS == "Windows":
        pyautogui.hotkey("win", "a"); time.sleep(0.3)
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to key code 144'])
    else:
        subprocess.run(["brightnessctl", "set", "+10%"])


def brightness_down():
    if _OS == "Windows":
        pyautogui.hotkey("win", "a"); time.sleep(0.3)
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to key code 145'])
    else:
        subprocess.run(["brightnessctl", "set", "10%-"])


def sleep_display():
    if _OS == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        except Exception:
            pass
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"])
    else:
        subprocess.run(["xset", "dpms", "force", "off"])


# ─── Window Management ─────────────────────────────────────────────────────────

def close_app():
    pyautogui.hotkey("command", "q") if _OS == "Darwin" else pyautogui.hotkey("alt", "f4")


def close_window():
    pyautogui.hotkey("command", "w") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "w")


def full_screen():
    pyautogui.hotkey("ctrl", "command", "f") if _OS == "Darwin" else pyautogui.press("f11")


def minimize_window():
    pyautogui.hotkey("command", "m") if _OS == "Darwin" else pyautogui.hotkey("win", "down")


def maximize_window():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to keystroke "f" using {control down, command down}'])
    else:
        pyautogui.hotkey("win", "up")


def snap_left():
    if _OS == "Windows": pyautogui.hotkey("win", "left")


def snap_right():
    if _OS == "Windows": pyautogui.hotkey("win", "right")


def switch_window():
    pyautogui.hotkey("command", "tab") if _OS == "Darwin" else pyautogui.hotkey("alt", "tab")


def show_desktop():
    if _OS == "Darwin":   pyautogui.hotkey("fn", "f11")
    elif _OS == "Windows": pyautogui.hotkey("win", "d")
    else:                  pyautogui.hotkey("super", "d")


def open_task_manager():
    if _OS == "Windows":
        pyautogui.hotkey("ctrl", "shift", "esc")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "Activity Monitor"])
    else:
        subprocess.Popen(["gnome-system-monitor"])


def open_task_view():
    if _OS == "Windows": pyautogui.hotkey("win", "tab")


def focus_search():
    pyautogui.hotkey("command", "l") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "l")


# ─── Browser Shortcuts ─────────────────────────────────────────────────────────

def pause_video():      pyautogui.press("space")


def refresh_page():
    pyautogui.hotkey("command", "r") if _OS == "Darwin" else pyautogui.press("f5")


def close_tab():
    pyautogui.hotkey("command", "w") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "w")


def new_tab():
    pyautogui.hotkey("command", "t") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "t")


def next_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "bracketright")
    else:               pyautogui.hotkey("ctrl", "tab")


def prev_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "bracketleft")
    else:               pyautogui.hotkey("ctrl", "shift", "tab")


def go_back():
    pyautogui.hotkey("command", "left") if _OS == "Darwin" else pyautogui.hotkey("alt", "left")


def go_forward():
    pyautogui.hotkey("command", "right") if _OS == "Darwin" else pyautogui.hotkey("alt", "right")


def zoom_in():
    pyautogui.hotkey("command", "equal") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "equal")


def zoom_out():
    pyautogui.hotkey("command", "minus") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "minus")


def zoom_reset():
    pyautogui.hotkey("command", "0") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "0")


def find_on_page():
    pyautogui.hotkey("command", "f") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "f")


def reload_page_n(n: int):
    for _ in range(n):
        refresh_page()
        time.sleep(0.8)


# ─── Scrolling ─────────────────────────────────────────────────────────────────

def scroll_up(amount: int = 500):   pyautogui.scroll(amount)
def scroll_down(amount: int = 500): pyautogui.scroll(-amount)


def scroll_top():
    if _OS != "Darwin": pyautogui.hotkey("ctrl", "home")
    else:               pyautogui.hotkey("command", "up")


def scroll_bottom():
    if _OS != "Darwin": pyautogui.hotkey("ctrl", "end")
    else:               pyautogui.hotkey("command", "down")


def page_up():   pyautogui.press("pageup")
def page_down(): pyautogui.press("pagedown")


# ─── Clipboard / Editing ───────────────────────────────────────────────────────

def copy():
    pyautogui.hotkey("command", "c") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "c")


def paste():
    pyautogui.hotkey("command", "v") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "v")


def cut():
    pyautogui.hotkey("command", "x") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "x")


def undo():
    pyautogui.hotkey("command", "z") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "z")


def redo():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "z")
    else:               pyautogui.hotkey("ctrl", "y")


def select_all():
    pyautogui.hotkey("command", "a") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "a")


def save_file():
    pyautogui.hotkey("command", "s") if _OS == "Darwin" else pyautogui.hotkey("ctrl", "s")


def press_enter():   pyautogui.press("enter")
def press_escape():  pyautogui.press("escape")
def press_key(key: str): pyautogui.press(key)


def type_text(text: str, press_enter_after: bool = False):
    if not text:
        return
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        paste()
    else:
        pyautogui.write(str(text), interval=0.03)
    if press_enter_after:
        time.sleep(0.1)
        pyautogui.press("enter")


def write_on_screen(text: str):
    type_text(text)


# ─── System Actions ────────────────────────────────────────────────────────────

def take_screenshot():
    if _OS == "Windows":
        pyautogui.hotkey("win", "shift", "s")
    elif _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "3")
    else:
        pyautogui.hotkey("ctrl", "print_screen")


def lock_screen():
    if _OS == "Windows":
        pyautogui.hotkey("win", "l")
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"])
    else:
        subprocess.run(["gnome-screensaver-command", "-l"])


def open_system_settings():
    if _OS == "Windows":
        pyautogui.hotkey("win", "i")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "System Preferences"])
    else:
        subprocess.Popen(["gnome-control-center"])


def open_file_explorer():
    if _OS == "Windows":
        pyautogui.hotkey("win", "e")
    elif _OS == "Darwin":
        subprocess.Popen(["open", Path.home()])
    else:
        subprocess.Popen(["xdg-open", Path.home()])


def open_run():
    if _OS == "Windows": pyautogui.hotkey("win", "r")


def restart_computer():
    if _OS == "Windows":
        subprocess.run(["shutdown", "/r", "/t", "5"])
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to restart'])
    else:
        subprocess.run(["sudo", "reboot"])


def shutdown_computer():
    if _OS == "Windows":
        subprocess.run(["shutdown", "/s", "/t", "5"])
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to shut down'])
    else:
        subprocess.run(["sudo", "shutdown", "-h", "now"])


def dark_mode():
    if _OS == "Windows":
        pyautogui.hotkey("win", "a"); time.sleep(0.3)
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'])


def toggle_wifi():
    if _OS == "Windows":
        pyautogui.hotkey("win", "a"); time.sleep(0.3)
    elif _OS == "Darwin":
        subprocess.run(["networksetup", "-setairportpower", "en0", "toggle"])
    else:
        subprocess.run(["nmcli", "radio", "wifi"])


# ─── Action Map ────────────────────────────────────────────────────────────────

ACTION_MAP = {
    "volume_up": volume_up, "volume_down": volume_down,
    "mute": volume_mute, "unmute": volume_mute,
    "volume_increase": volume_up, "volume_decrease": volume_down,
    "increase_volume": volume_up, "decrease_volume": volume_down,
    "turn_up_volume": volume_up, "turn_down_volume": volume_down,
    "louder": volume_up, "quieter": volume_down,
    "silence": volume_mute, "toggle_mute": volume_mute,
    "brightness_up": brightness_up, "brightness_down": brightness_down,
    "increase_brightness": brightness_up, "decrease_brightness": brightness_down,
    "brighter": brightness_up, "dimmer": brightness_down,
    "sleep_display": sleep_display, "turn_off_screen": sleep_display,
    "screen_off": sleep_display, "display_off": sleep_display,
    "pause_video": pause_video, "play_video": pause_video,
    "pause": pause_video, "play": pause_video,
    "close_app": close_app, "close_window": close_window,
    "quit_app": close_app, "exit_app": close_app,
    "full_screen": full_screen, "fullscreen": full_screen,
    "minimize": minimize_window, "minimize_window": minimize_window,
    "maximize": maximize_window, "maximize_window": maximize_window,
    "snap_left": snap_left, "snap_right": snap_right,
    "switch_window": switch_window, "alt_tab": switch_window,
    "show_desktop": show_desktop, "desktop": show_desktop,
    "task_manager": open_task_manager, "open_task_manager": open_task_manager,
    "task_view": open_task_view,
    "screenshot": take_screenshot, "take_screenshot": take_screenshot,
    "lock_screen": lock_screen, "lock": lock_screen,
    "open_settings": open_system_settings, "system_settings": open_system_settings,
    "settings": open_system_settings,
    "file_explorer": open_file_explorer, "open_explorer": open_file_explorer,
    "run": open_run, "open_run": open_run,
    "restart": restart_computer, "restart_computer": restart_computer,
    "shutdown": shutdown_computer, "shut_down": shutdown_computer,
    "dark_mode": dark_mode, "toggle_dark_mode": dark_mode, "night_mode": dark_mode,
    "toggle_wifi": toggle_wifi, "wifi": toggle_wifi,
    "focus_search": focus_search, "address_bar": focus_search,
    "refresh_page": refresh_page, "reload_page": refresh_page, "reload": refresh_page,
    "close_tab": close_tab, "new_tab": new_tab, "open_tab": new_tab,
    "next_tab": next_tab, "prev_tab": prev_tab, "previous_tab": prev_tab,
    "go_back": go_back, "back": go_back, "go_forward": go_forward, "forward": go_forward,
    "zoom_in": zoom_in, "zoom_out": zoom_out, "zoom_reset": zoom_reset,
    "find_on_page": find_on_page,
    "scroll_up": scroll_up, "scroll_down": scroll_down,
    "scroll_top": scroll_top, "scroll_bottom": scroll_bottom,
    "page_up": page_up, "page_down": page_down,
    "copy": copy, "paste": paste, "cut": cut,
    "undo": undo, "redo": redo, "select_all": select_all,
    "save": save_file, "save_file": save_file,
    "enter": press_enter, "press_enter": press_enter,
    "escape": press_escape, "press_escape": press_escape,
}


# ─── Intent Detection (Gemini → llm_bridge) ────────────────────────────────────

_DETECT_SYSTEM = (
    "You are detecting the user's computer-control intent. "
    "Return ONLY valid JSON: {\"action\": \"action_name\", \"value\": null_or_value}. "
    "Map the intent to one of the available actions. "
    "Never return actions not in the list. "
    "Return ONLY the JSON object, no explanation, no markdown."
)


def _detect_action(description: str) -> dict:
    from agent.llm_bridge import agent_llm_call
    available = ", ".join(sorted(ACTION_MAP.keys())) + \
                ", volume_set, type_text, write_on_screen, reload_n, press_key"
    prompt = (
        f'User said: "{description}"\n\n'
        f"Available actions: {available}\n\n"
        f'Return JSON, e.g. {{"action": "volume_up", "value": null}}'
    )
    try:
        raw    = agent_llm_call(_DETECT_SYSTEM, prompt, require_json=True)
        text   = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        return json.loads(text)
    except Exception as e:
        print(f"[Settings] Intent detection failed: {e}")
        return {"action": description.lower().replace(" ", "_"), "value": None}


# ─── Entry Point ───────────────────────────────────────────────────────────────

def computer_settings(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    if not _PYAUTOGUI:
        return "pyautogui is not installed. Run: pip install pyautogui"

    params      = parameters or {}
    raw_action  = params.get("action", "").strip()
    description = params.get("description", "").strip()
    value       = params.get("value", None)

    if not raw_action and description:
        detected   = _detect_action(description)
        raw_action = detected.get("action", "")
        if value is None:
            value = detected.get("value")

    action = raw_action.lower().strip().replace(" ", "_").replace("-", "_")

    if not action:
        return "No action could be determined."

    print(f"[Settings] Action: {action}  Value: {value}")

    if action == "volume_set":
        try:
            volume_set(int(value or 50))
            return f"Volume set to {value}%."
        except Exception as e:
            return f"Could not set volume: {e}"

    if action in ("type_text", "write_on_screen", "type", "write"):
        text = str(value or params.get("text", ""))
        if not text:
            return "No text provided to type."
        type_text(text, press_enter_after=bool(params.get("press_enter", False)))
        return f"Typed: {text[:60]}"

    if action == "press_key":
        key = str(value or params.get("key", ""))
        if not key:
            return "No key specified."
        press_key(key)
        return f"Pressed: {key}"

    if action in ("reload_n", "refresh_n", "reload_page_n"):
        try:
            reload_page_n(int(value or 1))
            n = int(value or 1)
            return f"Reloaded page {n} time{'s' if n > 1 else ''}."
        except Exception as e:
            return f"Could not reload: {e}"

    if action in ("scroll_up", "scroll_down"):
        try:
            amount = int(value or 500)
            scroll_up(amount) if action == "scroll_up" else scroll_down(amount)
            return f"Scrolled {'up' if action == 'scroll_up' else 'down'}."
        except Exception as e:
            return f"Scroll failed: {e}"

    func = ACTION_MAP.get(action)
    if not func:
        return f"Unknown action: '{raw_action}'."
    try:
        func()
        return f"Done: {action}."
    except Exception as e:
        return f"Action failed ({action}): {e}"
