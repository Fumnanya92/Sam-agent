"""
launcher.py — Small floating button to start Sam.
Run this to put a persistent SAM orb on your desktop.
Click it to launch Sam. Drag to reposition.
"""
import os
import sys
import subprocess
import tkinter as tk
from pathlib import Path


SAM_DIR  = Path(__file__).resolve().parent
SAM_MAIN = SAM_DIR / "main.py"

# ── Orb geometry ───────────────────────────────────────────────
SIZE   = 90
RADIUS = 40
CX, CY = SIZE // 2, SIZE // 2

_sam_proc = None  # track the launched subprocess


def _find_python_exe() -> str:
    """
    Return a path to python.exe (not pythonw.exe).

    When the launcher is started via start_launcher.bat it uses pythonw.exe,
    which means sys.executable == pythonw.exe.  Spawning Sam with pythonw.exe
    gives the child process sys.stdout = None, which breaks pywebview's
    WebView2 initialisation silently.  We switch to python.exe (same dir) and
    use CREATE_NO_WINDOW so no console window appears on screen.
    """
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        candidate = str(Path(exe).parent / "python.exe")
        if Path(candidate).exists():
            return candidate
    return exe


def is_sam_running() -> bool:
    global _sam_proc
    if _sam_proc is None:
        return False
    return _sam_proc.poll() is None  # None = still running


def launch_sam():
    global _sam_proc
    if is_sam_running():
        return  # already running
    try:
        python_exe = _find_python_exe()
        log_path   = SAM_DIR / "sam_session.log"

        # Open log file in write mode (truncates previous session)
        log_handle = open(log_path, "w", encoding="utf-8")

        _sam_proc = subprocess.Popen(
            [python_exe, str(SAM_MAIN)],
            cwd=str(SAM_DIR),
            stdout=log_handle,
            stderr=log_handle,
            # CREATE_NO_WINDOW — run as console app but no console window visible.
            # This gives Sam full I/O (stdout/stderr → log file) without a black
            # terminal flashing on screen.
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Parent closes its handle; child's inherited copy keeps the file open.
        log_handle.close()
    except Exception as e:
        print(f"Failed to launch Sam: {e}")


def draw_orb(canvas: tk.Canvas, pulsing: bool = False):
    """Draw the glowing SAM orb on the canvas."""
    canvas.delete("all")

    # Outer glow rings (dark → bright)
    glow_layers = [
        (RADIUS + 18, "#001122", "#000000"),
        (RADIUS + 10, "#002244", "#001133"),
        (RADIUS + 4,  "#004488", "#002255"),
        (RADIUS,      "#006699", "#003366"),
        (RADIUS - 8,  "#0088bb", "#004477"),
        (RADIUS - 16, "#00aadd", "#005588"),
    ]
    for r, fill, outline in glow_layers:
        canvas.create_oval(
            CX - r, CY - r, CX + r, CY + r,
            fill=fill, outline=outline, width=1
        )

    # Inner bright circle
    ir = RADIUS - 22
    canvas.create_oval(
        CX - ir, CY - ir, CX + ir, CY + ir,
        fill="#001a33", outline="#00ccff", width=2
    )

    # SAM text
    color = "#00ffff" if pulsing else "#8ffcff"
    canvas.create_text(CX, CY, text="SAM", fill=color,
                       font=("Consolas", 11, "bold"))

    # Tiny status dot (green = running, grey = idle)
    dot_color = "#00ff88" if is_sam_running() else "#334455"
    canvas.create_oval(CX + 22, CY + 22, CX + 30, CY + 30,
                       fill=dot_color, outline="")


class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SAM")
        self.root.geometry(f"{SIZE}x{SIZE}+30+30")
        self.root.overrideredirect(True)          # no title bar
        self.root.wm_attributes("-topmost", True) # always on top
        self.root.wm_attributes("-alpha", 0.92)   # slight transparency
        self.root.configure(bg="#000000")

        self.canvas = tk.Canvas(
            self.root, width=SIZE, height=SIZE,
            bg="#000000", highlightthickness=0, cursor="hand2"
        )
        self.canvas.pack()

        # ── Drag support ──────────────────────────────────────
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._dragging = False

        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # ── Hover glow ────────────────────────────────────────
        self.canvas.bind("<Enter>", lambda _: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda _: self._set_hover(False))
        self._hovered = False

        draw_orb(self.canvas)
        self._pulse_frame = 0
        self._animate()

    def _set_hover(self, val: bool):
        self._hovered = val

    def _on_press(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()
        self._dragging = False

    def _on_drag(self, event):
        self._dragging = True
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._dragging:
            launch_sam()
        self._dragging = False

    def _animate(self):
        self._pulse_frame += 1
        pulse = (self._pulse_frame % 40) < 20  # blink every ~640ms
        draw_orb(self.canvas, pulsing=(self._hovered or (is_sam_running() and pulse)))
        self.root.after(32, self._animate)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Launcher().run()
