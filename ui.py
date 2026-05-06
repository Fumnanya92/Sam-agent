"""
ui.py — Sam Tkinter window.

Drawn entirely in Python via PIL — no face.png required.
Orb states: idle | wake | listening | thinking | speaking
"""

import os
import sys
import json
import math
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from queue import Queue, Empty
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw

# ── Design tokens (mirrors React UI palette) ──────────────────────────────────
_BG           = "#07070A"
_PANEL_BG     = "#0D1117"
_HEADER_BG    = "#0A0C12"
_BORDER       = "#1B3A2F"
_EMERALD      = "#10b981"
_EMERALD_SOFT = "#6ee7b7"
_EMERALD_DIM  = "#064e3b"
_TEXT_1       = "#E6E6E6"
_TEXT_2       = "#A0AEC0"
_TEXT_DIM     = "#4A5568"
_YELLOW       = "#f59e0b"
_GREEN_OK     = "#34d399"
_RED          = "#ef4444"

# ── Orb geometry ──────────────────────────────────────────────────────────────
_ORB_PX     = 300
_CX         = 150
_CY         = 150
_CORE_R     = 36
_RING_RADII = [138, 102, 74]
_BG_TUPLE   = (7, 7, 10, 255)

_STATE_COLORS = {
    "idle":      {"ring": (16, 185, 129),  "core_o": (6, 78, 59),    "core_i": (110, 231, 183), "glow": (16, 185, 129)},
    "wake":      {"ring": (110, 231, 183), "core_o": (6, 78, 59),    "core_i": (180, 245, 220), "glow": (110, 231, 183)},
    "listening": {"ring": (16, 185, 129),  "core_o": (6, 78, 59),    "core_i": (110, 231, 183), "glow": (16, 185, 129)},
    "thinking":  {"ring": (139, 92, 246),  "core_o": (46, 16, 101),  "core_i": (196, 181, 253), "glow": (139, 92, 246)},
    "speaking":  {"ring": (96, 165, 250),  "core_o": (30, 27, 75),   "core_i": (191, 219, 254), "glow": (96, 165, 250)},
}
_STATE_LABELS = {
    "idle": "ONLINE", "wake": "WAKING", "listening": "LISTENING",
    "thinking": "THINKING", "speaking": "SPEAKING",
}
_STATE_LABEL_COLORS = {
    "idle": _EMERALD_SOFT, "wake": _EMERALD_SOFT, "listening": _EMERALD_SOFT,
    "thinking": "#c4b5fd", "speaking": "#93c5fd",
}


def _lerp(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


class SamUI:
    def __init__(self, face_path=None, size=None):
        # face_path / size kept for API compatibility, ignored
        self._state   = "idle"
        self._t       = 0.0
        self._prev_tk = None   # prevents GC of last ImageTk

        # ── Root window ─────────────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.title("SAM")
        self.root.configure(bg=_BG)
        self.root.resizable(True, True)
        self.root.minsize(820, 580)

        # Clamp initial size to the available screen so the window never
        # overflows on small displays. Leaves a margin for taskbar / titlebar.
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            target_w = min(1200, max(820, sw - 120))
            target_h = min(780,  max(580, sh - 140))
            x = max(0, (sw - target_w) // 2)
            y = max(0, (sh - target_h) // 2 - 20)
            self.root.geometry(f"{target_w}x{target_h}+{x}+{y}")
        except Exception:
            self.root.geometry("1200x780")

        self._build_header()
        tk.Frame(self.root, bg=_BORDER, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=_BG)
        body.pack(fill="both", expand=True)

        self._build_left_panel(body)
        tk.Frame(body, bg=_BORDER, width=1).pack(side="left", fill="y")
        self._build_right_panel(body)

        self._command_queue = Queue()
        self.root.after(20, self._process_command_queue)
        self.root.after(50, self._animate)

        cfg_file = Path(__file__).resolve().parent / "config" / "api_keys.json"
        if not cfg_file.exists():
            self._show_setup_ui(cfg_file)

        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    # ── Header ──────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=_HEADER_BG, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        logo = tk.Frame(hdr, bg=_HEADER_BG)
        logo.pack(side="left", padx=14, fill="y")

        dot = tk.Canvas(logo, width=10, height=10, bg=_HEADER_BG, highlightthickness=0)
        dot.pack(side="left", pady=13)
        dot.create_oval(1, 1, 9, 9, fill=_EMERALD, outline="")

        tk.Label(logo, text="  S A M", fg=_EMERALD_SOFT, bg=_HEADER_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left", fill="y")

        # Dashboard shortcut — opens browser to the React UI
        def _open_dashboard():
            import webbrowser
            webbrowser.open("http://localhost:3142")

        tk.Button(
            hdr, text="Open Dashboard",
            command=_open_dashboard,
            bg=_HEADER_BG, fg=_TEXT_DIM,
            activebackground=_EMERALD_DIM, activeforeground=_EMERALD_SOFT,
            font=("Segoe UI", 8), relief="flat",
            padx=10, pady=0, cursor="hand2", bd=0,
        ).pack(side="left", padx=(18, 0), pady=9)

        status = tk.Frame(hdr, bg=_HEADER_BG)
        status.pack(side="right", padx=14, fill="y")

        self._status_lbl = tk.Label(
            status, text="offline", fg=_TEXT_DIM,
            bg=_HEADER_BG, font=("Segoe UI", 9),
        )
        self._status_lbl.pack(side="right", fill="y", pady=1)

        self._status_dot = tk.Canvas(
            status, width=8, height=8, bg=_HEADER_BG, highlightthickness=0,
        )
        self._status_dot.pack(side="right", padx=(0, 6), pady=14)
        self._status_dot.create_oval(1, 1, 7, 7, fill=_TEXT_DIM, outline="", tags="dot")

    # ── Left panel ──────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        lf = tk.Frame(parent, bg=_BG, width=480)
        lf.pack(side="left", fill="y")
        lf.pack_propagate(False)
        self.left_frame = lf

        # ── Bottom-anchored layout (pack-based) so the chat box always
        # expands to fill remaining space and the input stays pinned at the
        # bottom — no overlap, no "stuck" feeling on small windows.

        # Input (packed FIRST at bottom so it always reserves its slot)
        self._typed_input_queue = None
        self._input_placeholder = "Say something or type here..."

        input_border = tk.Frame(lf, bg=_BORDER)
        input_border.pack(side="bottom", fill="x", padx=18, pady=(4, 12))

        self.text_entry = tk.Entry(
            input_border,
            bg="#111318", fg=_TEXT_DIM,
            insertbackground=_EMERALD_SOFT,
            font=("Segoe UI", 11), relief="flat",
        )
        self.text_entry.pack(fill="x", padx=1, pady=1, ipady=6)
        self.text_entry.insert(0, self._input_placeholder)
        self.text_entry.bind("<FocusIn>",  self._clear_placeholder)
        self.text_entry.bind("<FocusOut>", self._restore_placeholder)
        self.text_entry.bind("<Return>",   self._submit_text)

        # Chat log (above the input — fills remaining vertical space)
        chat_border = tk.Frame(lf, bg=_BORDER)
        chat_border.pack(side="bottom", fill="both", expand=True, padx=18, pady=(0, 4))
        chat_inner = tk.Frame(chat_border, bg=_PANEL_BG)
        chat_inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.text_box = ScrolledText(
            chat_inner,
            fg=_TEXT_1, bg=_PANEL_BG,
            insertbackground=_EMERALD_SOFT,
            height=8, borderwidth=0, wrap="word",
            font=("Segoe UI", 10), padx=12, pady=8,
        )
        self.text_box.pack(fill="both", expand=True)
        self.text_box.configure(state="disabled")
        self.text_box.tag_configure("sam",  foreground=_EMERALD_SOFT)
        self.text_box.tag_configure("user", foreground=_TEXT_1)
        self.text_box.tag_configure("sys",  foreground=_TEXT_DIM)

        # ── Top-anchored area: orb canvas + state label + transcription
        # Sits above the chat log and naturally shrinks/grows.
        top_area = tk.Frame(lf, bg=_BG)
        top_area.pack(side="top", fill="both", expand=False, pady=(8, 0))

        self.canvas = tk.Canvas(
            top_area, width=_ORB_PX, height=_ORB_PX,
            bg=_BG, highlightthickness=0,
        )
        self.canvas.pack(pady=(8, 4))

        # State label
        self._state_var = tk.StringVar(value="ONLINE")
        self._state_lbl = tk.Label(
            top_area, textvariable=self._state_var,
            fg=_EMERALD_SOFT, bg=_BG,
            font=("Segoe UI", 9, "bold"),
        )
        self._state_lbl.pack(pady=(0, 2))

        # Transcription
        self.transcription_var = tk.StringVar(value="")
        tk.Label(
            top_area, textvariable=self.transcription_var,
            fg=_TEXT_2, bg=_BG,
            font=("Segoe UI", 10), wraplength=440, justify="center",
        ).pack(pady=(0, 4))

    # ── Right panel ──────────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        rf = tk.Frame(parent, bg=_PANEL_BG)
        rf.pack(side="right", fill="both", expand=True)
        self.right_frame = rf

        # Agents header
        ah = tk.Frame(rf, bg=_PANEL_BG)
        ah.pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(ah, text="AGENTS", fg=_EMERALD_SOFT, bg=_PANEL_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._agent_count_var = tk.StringVar(value="0 running")
        tk.Label(ah, textvariable=self._agent_count_var, fg=_TEXT_DIM, bg=_PANEL_BG,
                 font=("Segoe UI", 9)).pack(side="right")
        tk.Frame(rf, bg=_BORDER, height=1).pack(fill="x", padx=14, pady=(0, 4))

        # Scrollable agent list
        aw = tk.Frame(rf, bg=_PANEL_BG, height=220)
        aw.pack(fill="x", padx=10, pady=(0, 6))
        aw.pack_propagate(False)

        self._agent_canvas = tk.Canvas(aw, bg=_PANEL_BG, highlightthickness=0)
        asb = tk.Scrollbar(aw, orient="vertical", command=self._agent_canvas.yview,
                           bg=_PANEL_BG, troughcolor=_PANEL_BG, width=4)
        self._agent_canvas.configure(yscrollcommand=asb.set)
        asb.pack(side="right", fill="y")
        self._agent_canvas.pack(side="left", fill="both", expand=True)

        self._agent_inner = tk.Frame(self._agent_canvas, bg=_PANEL_BG)
        self._agent_cw = self._agent_canvas.create_window(
            (0, 0), window=self._agent_inner, anchor="nw",
        )
        self._agent_inner.bind(
            "<Configure>",
            lambda e: self._agent_canvas.configure(
                scrollregion=self._agent_canvas.bbox("all")),
        )
        self._agent_canvas.bind(
            "<Configure>",
            lambda e: self._agent_canvas.itemconfig(self._agent_cw, width=e.width),
        )
        self._agent_rows: dict = {}

        # ── FILES section — what Sam has written this session ───────────────
        tk.Frame(rf, bg=_BORDER, height=1).pack(fill="x", padx=14, pady=4)
        fh = tk.Frame(rf, bg=_PANEL_BG)
        fh.pack(fill="x", padx=14, pady=(4, 4))
        tk.Label(fh, text="FILES", fg=_EMERALD_SOFT, bg=_PANEL_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._files_count_var = tk.StringVar(value="none yet")
        tk.Label(fh, textvariable=self._files_count_var, fg=_TEXT_DIM, bg=_PANEL_BG,
                 font=("Segoe UI", 9)).pack(side="right")
        tk.Frame(rf, bg=_BORDER, height=1).pack(fill="x", padx=14, pady=(0, 4))

        fw = tk.Frame(rf, bg=_PANEL_BG, height=140)
        fw.pack(fill="x", padx=10, pady=(0, 6))
        fw.pack_propagate(False)

        self._files_canvas = tk.Canvas(fw, bg=_PANEL_BG, highlightthickness=0)
        fsb = tk.Scrollbar(fw, orient="vertical", command=self._files_canvas.yview,
                           bg=_PANEL_BG, troughcolor=_PANEL_BG, width=4)
        self._files_canvas.configure(yscrollcommand=fsb.set)
        fsb.pack(side="right", fill="y")
        self._files_canvas.pack(side="left", fill="both", expand=True)

        self._files_inner = tk.Frame(self._files_canvas, bg=_PANEL_BG)
        self._files_cw = self._files_canvas.create_window(
            (0, 0), window=self._files_inner, anchor="nw",
        )
        self._files_inner.bind(
            "<Configure>",
            lambda e: self._files_canvas.configure(
                scrollregion=self._files_canvas.bbox("all")),
        )
        self._files_canvas.bind(
            "<Configure>",
            lambda e: self._files_canvas.itemconfig(self._files_cw, width=e.width),
        )
        self._files_known: list[str] = []   # last-rendered absolute paths
        # Schedule the first refresh after the window has finished mounting.
        self.root.after(800, self._refresh_files_panel)

        # Output header
        tk.Frame(rf, bg=_BORDER, height=1).pack(fill="x", padx=14, pady=4)
        oh = tk.Frame(rf, bg=_PANEL_BG)
        oh.pack(fill="x", padx=14, pady=(4, 4))
        tk.Label(oh, text="OUTPUT", fg=_EMERALD_SOFT, bg=_PANEL_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        for label, cmd in [("copy", self._copy_output), ("clear", self._clear_output)]:
            tk.Button(oh, text=label, command=cmd,
                      bg=_PANEL_BG, fg=_TEXT_DIM, activebackground="#0a1830",
                      font=("Segoe UI", 9), relief="flat", padx=8, pady=0,
                      cursor="hand2").pack(side="right")

        # Output text
        ow = tk.Frame(rf, bg=_BORDER)
        ow.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        osb = tk.Scrollbar(ow, bg=_PANEL_BG, troughcolor=_PANEL_BG, width=4)
        osb.pack(side="right", fill="y")
        self.output_box = tk.Text(
            ow, bg=_PANEL_BG, fg=_TEXT_1,
            insertbackground=_EMERALD_SOFT,
            font=("Segoe UI", 10), wrap="word",
            relief="flat", padx=12, pady=8,
            state="disabled", yscrollcommand=osb.set,
        )
        self.output_box.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        osb.configure(command=self.output_box.yview)

        self.output_box.tag_configure("info",   foreground=_EMERALD_SOFT)
        self.output_box.tag_configure("ok",     foreground=_GREEN_OK)
        self.output_box.tag_configure("warn",   foreground=_YELLOW)
        self.output_box.tag_configure("error",  foreground=_RED)
        self.output_box.tag_configure("normal", foreground=_TEXT_1)
        self.output_box.tag_configure("dim",    foreground=_TEXT_DIM)

    # ── Orb drawing ──────────────────────────────────────────────────────────────

    def _draw_orb(self) -> Image.Image:
        state = self._state
        t     = self._t
        pal   = _STATE_COLORS.get(state, _STATE_COLORS["idle"])
        ring_c  = pal["ring"]
        core_o  = pal["core_o"]
        core_i  = pal["core_i"]
        glow_c  = pal["glow"]

        img  = Image.new("RGBA", (_ORB_PX, _ORB_PX), _BG_TUPLE)
        draw = ImageDraw.Draw(img)

        # Per-state ring alphas & core scale
        if state == "idle":
            breathe     = 0.5 + 0.5 * math.sin(t * 0.8)
            ring_alphas = [int(10 + 8 * breathe), int(14 + 12 * breathe), int(18 + 16 * breathe)]
            core_scale  = 1.0 + 0.06 * breathe
            glow_alpha  = int(28 + 18 * breathe)

        elif state == "wake":
            pulse       = min(1.0, t * 2)
            ring_alphas = [int(90 * (1 - pulse)), int(100 * (1 - pulse * 0.9)), int(110 * (1 - pulse * 0.8))]
            core_scale  = 1.0 + 0.15 * (1 - pulse)
            glow_alpha  = int(90 * (1 - pulse) + 30)

        elif state == "listening":
            pulse       = (t * 1.6) % 1.0
            ring_alphas = [
                max(0, int(90 * (1 - pulse))),
                max(0, int(90 * (1 - max(0.0, pulse - 0.12)))),
                max(0, int(90 * (1 - max(0.0, pulse - 0.24)))),
            ]
            core_scale  = 1.0 + 0.10 * math.sin(t * 4)
            glow_alpha  = 80

        elif state == "thinking":
            ring_alphas = None   # drawn as rotating arcs below
            core_scale  = 1.0 + 0.04 * math.sin(t * 1.5)
            glow_alpha  = 40

        elif state == "speaking":
            wave        = (t * 1.8) % 1.0
            ring_alphas = [
                max(0, int(80 * (1 - wave))),
                max(0, int(80 * (1 - max(0.0, wave - 0.16)))),
                max(0, int(80 * (1 - max(0.0, wave - 0.32)))),
            ]
            core_scale  = 1.0 + 0.12 * abs(math.sin(t * 5))
            glow_alpha  = 70

        else:
            ring_alphas = [18, 26, 36]
            core_scale  = 1.0
            glow_alpha  = 28

        core_r   = int(_CORE_R * core_scale)
        glow_max = core_r + 30

        # Soft glow halo
        for g in range(glow_max, core_r, -1):
            ratio = 1.0 - (g - core_r) / (glow_max - core_r)
            a = int(glow_alpha * ratio * ratio * 0.6)
            if a > 0:
                draw.ellipse([_CX - g, _CY - g, _CX + g, _CY + g],
                             fill=(*glow_c, a))

        # Atmosphere rings
        if state == "thinking":
            dash_deg, gap_deg = 50, 30
            rot = (t * 60) % 360
            for ring_r, base_a in zip(_RING_RADII, [30, 50, 70]):
                seg = 0
                while seg < 360:
                    s = (seg + rot) % 360
                    e = (s + dash_deg) % 360
                    draw.arc(
                        [_CX - ring_r, _CY - ring_r, _CX + ring_r, _CY + ring_r],
                        start=s, end=e, fill=(*ring_c, base_a), width=2,
                    )
                    seg += dash_deg + gap_deg
        else:
            for ring_r, alpha in zip(_RING_RADII, ring_alphas):
                if alpha > 0:
                    draw.ellipse(
                        [_CX - ring_r, _CY - ring_r, _CX + ring_r, _CY + ring_r],
                        outline=(*ring_c, alpha), width=1,
                    )

        # Core sphere — uniform soft glow (no iris/pupil look)
        # Blend the two palette colours into a single mid tone, then radiate
        # outward as a soft halo so the core reads as a glowing pearl, not an eye.
        core_mid = _lerp(core_o, core_i, 0.62)
        for i in range(core_r, 0, -1):
            ratio = i / core_r            # 1 = edge, 0 = centre
            # Centre stays bright, edges fade gently (no hard ring)
            edge_fade = 1.0 - (ratio ** 1.6) * 0.35
            c = tuple(int(v * edge_fade) for v in core_mid)
            draw.ellipse([_CX - i, _CY - i, _CX + i, _CY + i], fill=(*c, 255))

        # Subtle top sheen — soft, centred, very low alpha so the orb still
        # looks 3D without the "eye glint" effect.
        sheen_r = int(core_r * 0.55)
        sheen_y_off = int(core_r * 0.18)
        for i in range(sheen_r, 0, -1):
            a = int(28 * (1 - i / sheen_r) ** 2)
            if a > 0:
                draw.ellipse(
                    [_CX - i, _CY - sheen_y_off - i, _CX + i, _CY - sheen_y_off + i],
                    fill=(255, 255, 255, a),
                )

        return img

    # ── Animation loop ───────────────────────────────────────────────────────────

    def _animate(self):
        self._t += 0.05

        img   = self._draw_orb()
        tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(_CX, _CY, image=tk_img)
        self._prev_tk = tk_img

        try:
            lbl   = _STATE_LABELS.get(self._state, "ONLINE")
            color = _STATE_LABEL_COLORS.get(self._state, _EMERALD_SOFT)
            self._state_var.set(lbl)
            self._state_lbl.configure(fg=color)
        except Exception:
            pass

        self.root.after(50, self._animate)

    # ── Thread-safe queue ─────────────────────────────────────────────────────────

    def _enqueue(self, func, *args, **kwargs):
        try:
            self._command_queue.put((func, args, kwargs))
        except Exception:
            pass

    def _process_command_queue(self):
        try:
            while True:
                func, args, kwargs = self._command_queue.get_nowait()
                try:
                    func(*args, **kwargs)
                except Exception:
                    pass
        except Empty:
            pass
        self.root.after(20, self._process_command_queue)

    # ── Public API — voice state ──────────────────────────────────────────────────

    def start_speaking(self):
        self._enqueue(lambda: setattr(self, "_state", "speaking"))

    def stop_speaking(self):
        self._enqueue(lambda: setattr(self, "_state", "idle"))

    def set_voice_state(self, state: str):
        """state: idle | wake | listening | thinking | speaking"""
        self._enqueue(lambda: setattr(self, "_state", state))

    def set_connected(self, connected: bool):
        self._enqueue(self._set_connected_impl, connected)

    def _set_connected_impl(self, connected: bool):
        try:
            color = _GREEN_OK if connected else _TEXT_DIM
            self._status_dot.delete("dot")
            self._status_dot.create_oval(1, 1, 7, 7, fill=color, outline="", tags="dot")
            self._status_lbl.configure(
                text="online" if connected else "offline",
                fg=_EMERALD_SOFT if connected else _TEXT_DIM,
            )
        except Exception:
            pass

    # ── Public API — chat log ─────────────────────────────────────────────────────

    def write_log(self, text: str):
        self._enqueue(self._write_log_impl, text)

    def _write_log_impl(self, text: str):
        try:
            lower = text.lower()
            tag = ("sam"  if lower.startswith(("sam:", "ai:")) else
                   "user" if lower.startswith(("you:", "user:")) else "sys")
            self.text_box.configure(state="normal")
            self.text_box.insert(tk.END, text + "\n", tag)
            self.text_box.see(tk.END)
            self.text_box.configure(state="disabled")
        except Exception:
            pass

    def set_transcription(self, text: str):
        self._enqueue(lambda: self.transcription_var.set(text))

    def clear_transcription(self):
        self._enqueue(lambda: self.transcription_var.set(""))

    def highlight_text_input(self):
        self._enqueue(self._highlight_input_impl)

    def unhighlight_text_input(self):
        self._enqueue(self._unhighlight_input_impl)

    def _highlight_input_impl(self):
        try:
            self.text_entry.configure(
                highlightbackground=_YELLOW, highlightcolor=_YELLOW,
                highlightthickness=1, fg=_TEXT_1,
            )
        except Exception:
            pass

    def _unhighlight_input_impl(self):
        try:
            fg = _TEXT_DIM if self.text_entry.get() == self._input_placeholder else _TEXT_1
            self.text_entry.configure(highlightthickness=0, fg=fg)
        except Exception:
            pass

    def _clear_placeholder(self, event=None):
        try:
            if self.text_entry.get() == self._input_placeholder:
                self.text_entry.delete(0, tk.END)
                self.text_entry.configure(fg=_TEXT_1)
        except Exception:
            pass

    def _restore_placeholder(self, event=None):
        try:
            if not self.text_entry.get().strip():
                self.text_entry.delete(0, tk.END)
                self.text_entry.insert(0, self._input_placeholder)
                self.text_entry.configure(fg=_TEXT_DIM)
        except Exception:
            pass

    def _submit_text(self, event=None):
        try:
            text = self.text_entry.get().strip()
            if text and text != self._input_placeholder and self._typed_input_queue is not None:
                self._typed_input_queue.put(text)
                self.text_entry.delete(0, tk.END)
                self._restore_placeholder()
        except Exception:
            pass

    # ── Public API — agent panel ──────────────────────────────────────────────────

    def set_typed_input_queue(self, q):
        self._typed_input_queue = q

    def add_agent_task(self, task_id: str, name: str, status: str = "running"):
        self._enqueue(self._add_agent_task_impl, task_id, name, status)

    def _add_agent_task_impl(self, task_id: str, name: str, status: str):
        try:
            dot_c = _YELLOW if status == "running" else (_GREEN_OK if status == "done" else _RED)
            row   = tk.Frame(self._agent_inner, bg=_PANEL_BG, pady=3)
            row.pack(fill="x", padx=8)

            dot = tk.Canvas(row, width=8, height=8, bg=_PANEL_BG, highlightthickness=0)
            dot.create_oval(1, 1, 7, 7, fill=dot_c, outline="")
            dot.pack(side="left", padx=(0, 8))

            name_var   = tk.StringVar(value=name[:40])
            status_var = tk.StringVar(value=status)

            tk.Label(row, textvariable=name_var, fg=_TEXT_2, bg=_PANEL_BG,
                     font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)
            status_lbl = tk.Label(row, textvariable=status_var, fg=dot_c, bg=_PANEL_BG,
                                  font=("Segoe UI", 9))
            status_lbl.pack(side="right")

            self._agent_rows[task_id] = (row, name_var, status_var, status_lbl, dot)
            self._refresh_agent_count()
        except Exception:
            pass

    def update_agent_task(self, task_id: str, status: str):
        self._enqueue(self._update_agent_task_impl, task_id, status)

    def _update_agent_task_impl(self, task_id: str, status: str):
        try:
            data = self._agent_rows.get(task_id)
            if not data:
                return
            _, name_var, status_var, status_lbl, dot = data
            color = _YELLOW if status == "running" else (_GREEN_OK if status == "done" else _RED)
            status_var.set(status)
            status_lbl.configure(fg=color)
            dot.delete("all")
            dot.create_oval(1, 1, 7, 7, fill=color, outline="")
            self._refresh_agent_count()
        except Exception:
            pass

    def _refresh_agent_count(self):
        try:
            running = sum(1 for (_, _, sv, _, _) in self._agent_rows.values()
                         if sv.get() == "running")
            total   = len(self._agent_rows)
            self._agent_count_var.set(f"{running} running · {total} total")
        except Exception:
            pass

    # ── FILES panel — recently-written files ──────────────────────────────────────

    def _refresh_files_panel(self):
        """Pull the recent-files registry and render it. Reschedules itself."""
        try:
            try:
                from actions.file_controller import list_recent_written
                recent = list_recent_written(15)
            except Exception:
                recent = []

            paths_now = [r["path"] for r in recent]
            if paths_now != self._files_known:
                # Rebuild only when the list actually changed.
                for child in list(self._files_inner.winfo_children()):
                    try:
                        child.destroy()
                    except Exception:
                        pass

                if not recent:
                    tk.Label(
                        self._files_inner,
                        text="No files written yet this session.",
                        fg=_TEXT_DIM, bg=_PANEL_BG,
                        font=("Segoe UI", 9, "italic"),
                        padx=10, pady=10,
                    ).pack(anchor="w")
                    self._files_count_var.set("none yet")
                else:
                    for entry in recent:
                        self._build_file_row(entry)
                    self._files_count_var.set(f"{len(recent)} files")

                self._files_known = paths_now
        except Exception:
            pass
        finally:
            # Steady refresh — light enough to be unnoticeable.
            self.root.after(1500, self._refresh_files_panel)

    def _build_file_row(self, entry: dict):
        path = entry.get("path", "")
        name = entry.get("name", "?")
        ext  = (entry.get("ext") or "").lower()
        ts   = entry.get("ts", "")

        row = tk.Frame(self._files_inner, bg=_PANEL_BG, pady=2)
        row.pack(fill="x", padx=6, pady=1)

        # Name + path (truncate path for display)
        info = tk.Frame(row, bg=_PANEL_BG)
        info.pack(side="left", fill="x", expand=True)

        tk.Label(
            info, text=name, fg=_TEXT_1, bg=_PANEL_BG,
            font=("Segoe UI", 9, "bold"), anchor="w",
        ).pack(anchor="w", fill="x")

        short_path = path
        if len(short_path) > 60:
            short_path = "…" + short_path[-58:]
        tk.Label(
            info, text=f"{short_path}   ·   {ts.split('T')[-1] if 'T' in ts else ts}",
            fg=_TEXT_DIM, bg=_PANEL_BG,
            font=("Segoe UI", 8), anchor="w",
        ).pack(anchor="w", fill="x")

        # Action buttons
        btns = tk.Frame(row, bg=_PANEL_BG)
        btns.pack(side="right", padx=(8, 0))

        if ext == ".py":
            tk.Button(
                btns, text="▶ Run",
                command=lambda p=path: self._run_file(p),
                bg=_PANEL_BG, fg=_EMERALD_SOFT,
                activebackground=_EMERALD_DIM, activeforeground=_EMERALD_SOFT,
                font=("Segoe UI", 8, "bold"), relief="flat",
                padx=8, pady=0, cursor="hand2", bd=0,
            ).pack(side="right", padx=(4, 0))

        tk.Button(
            btns, text="📁",
            command=lambda p=path: self._open_file_location(p),
            bg=_PANEL_BG, fg=_TEXT_DIM,
            activebackground="#0a1830", activeforeground=_EMERALD_SOFT,
            font=("Segoe UI", 9), relief="flat",
            padx=6, pady=0, cursor="hand2", bd=0,
        ).pack(side="right")

        tk.Button(
            btns, text="📋",
            command=lambda p=path: self._copy_path(p),
            bg=_PANEL_BG, fg=_TEXT_DIM,
            activebackground="#0a1830", activeforeground=_EMERALD_SOFT,
            font=("Segoe UI", 9), relief="flat",
            padx=6, pady=0, cursor="hand2", bd=0,
        ).pack(side="right")

    def _run_file(self, path: str):
        """Run a saved script in a background thread and stream output."""
        import threading
        def _runner():
            try:
                from agent.executor import run_script
                self._enqueue(self._append_output_impl,
                              f"\n▶ Running {Path(path).name}...", "info")
                result = run_script(path)
                self._enqueue(self._append_output_impl, str(result), "ok")
            except Exception as e:
                self._enqueue(self._append_output_impl,
                              f"Error running {path}: {e}", "error")
        threading.Thread(target=_runner, daemon=True).start()

    def _open_file_location(self, path: str):
        """Open the folder containing the file in the OS file manager."""
        try:
            import subprocess
            target = Path(path).expanduser().resolve()
            folder = str(target.parent)
            if os.name == "nt":
                # Use explorer with /select to highlight the file
                subprocess.Popen(["explorer", "/select,", str(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(target)])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            self._append_output_impl(f"Could not open location: {e}", "error")

    def _copy_path(self, path: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self._append_output_impl(f"Copied path: {path}", "info")
        except Exception:
            pass

    # ── Public API — output panel ──────────────────────────────────────────────────

    def append_output(self, text: str, color: str = "normal"):
        self._enqueue(self._append_output_impl, text, color)

    def _append_output_impl(self, text: str, tag: str):
        try:
            self.output_box.configure(state="normal")
            self.output_box.insert(tk.END, text + "\n", tag)
            self.output_box.see(tk.END)
            self.output_box.configure(state="disabled")
        except Exception:
            pass

    def _copy_output(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.output_box.get("1.0", tk.END).strip())
        except Exception:
            pass

    def _clear_output(self):
        try:
            self.output_box.configure(state="normal")
            self.output_box.delete("1.0", tk.END)
            self.output_box.configure(state="disabled")
        except Exception:
            pass

    # ── Draft popup ───────────────────────────────────────────────────────────────

    def show_draft_popup(self, draft_text: str):
        def _make():
            popup = tk.Toplevel(self.root)
            popup.title("Sam — Draft Reply")
            popup.geometry("540x260")
            popup.configure(bg=_BG)
            popup.resizable(True, True)
            popup.lift()
            popup.focus_force()

            tk.Label(popup, text="Draft — copy and edit as needed:",
                     fg=_EMERALD_SOFT, bg=_BG,
                     font=("Segoe UI", 11)).pack(pady=(14, 4), padx=16, anchor="w")

            txt = tk.Text(popup, height=6, wrap="word",
                          font=("Segoe UI", 11), fg=_TEXT_1, bg=_PANEL_BG,
                          insertbackground=_EMERALD_SOFT, relief="flat", pady=6, padx=10)
            txt.insert("1.0", draft_text)
            txt.pack(padx=16, fill="both", expand=True)
            txt.focus_set()
            txt.tag_add("sel", "1.0", "end")

            def _copy_close():
                self.root.clipboard_clear()
                self.root.clipboard_append(draft_text)
                popup.destroy()

            bf = tk.Frame(popup, bg=_BG)
            bf.pack(pady=10)
            tk.Button(bf, text="Copy & Close", command=_copy_close,
                      bg=_EMERALD_DIM, fg=_EMERALD_SOFT,
                      font=("Segoe UI", 10), relief="flat", padx=14, pady=4,
                      ).pack(side="left", padx=6)
            tk.Button(bf, text="Close", command=popup.destroy,
                      bg="#1F2937", fg=_TEXT_2,
                      font=("Segoe UI", 10), relief="flat", padx=14, pady=4,
                      ).pack(side="left", padx=6)

        self._enqueue(_make)

    # ── First-run setup ───────────────────────────────────────────────────────────

    def _show_setup_ui(self, api_file: Path):
        frame = tk.Frame(self.root, bg="#0A0C12",
                         highlightbackground=_EMERALD, highlightthickness=1)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="SAM SETUP", fg=_EMERALD_SOFT, bg="#0A0C12",
                 font=("Segoe UI", 14, "bold")).pack(pady=(18, 12))

        fields: dict[str, tk.Entry] = {}
        for label_text, key in [
            ("OpenRouter API Key", "openrouter_api_key"),
            ("SerpAPI Key  (optional)", "serpapi_api_key"),
        ]:
            tk.Label(frame, text=label_text, fg=_TEXT_2, bg="#0A0C12",
                     font=("Segoe UI", 10)).pack(pady=(8, 2))
            e = tk.Entry(frame, width=50, fg=_TEXT_1, bg="#111318",
                         insertbackground=_EMERALD_SOFT, borderwidth=0,
                         font=("Segoe UI", 10), show="•")
            e.pack(pady=(0, 4))
            fields[key] = e

        def _save():
            data = {k: e.get().strip() for k, e in fields.items()}
            if not data.get("openrouter_api_key"):
                return
            api_file.parent.mkdir(parents=True, exist_ok=True)
            api_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
            frame.destroy()
            self.write_log("API keys saved. Starting Sam...")

        tk.Button(frame, text="SAVE & CONTINUE", command=_save,
                  bg=_EMERALD_DIM, fg=_EMERALD_SOFT,
                  font=("Segoe UI", 10), relief="flat", padx=16, pady=8,
                  ).pack(pady=(12, 18))
