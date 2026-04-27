import os
import json
import time
import math
import random
import tkinter as tk
from queue import Queue, Empty
from PIL import Image, ImageTk, ImageDraw, ImageFilter
from tkinter.scrolledtext import ScrolledText
import sys
from pathlib import Path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE = CONFIG_DIR / "api_keys.json"

# ── Colours ──────────────────────────────────────────────────────────────────
_CYAN       = "#8ffcff"
_BG         = "#000000"
_PANEL_BG   = "#050810"
_PANEL_EDGE = "#0a1520"
_YELLOW     = "#f0c040"
_GREEN      = "#00e080"
_RED        = "#ff4444"
_DIM        = "#334455"


class SamUI:
    def __init__(self, face_path, size=(700, 700)):
        self.root = tk.Tk()
        self.root.title("SAM")
        self.root.resizable(True, True)
        # Two-panel: left orb (580) + right dashboard (540) = 1120 wide
        self.root.geometry("1120x760")
        self.root.configure(bg=_BG)
        self.root.minsize(700, 640)

        self.size = size
        self.cx = size[0] // 2
        self.cy = size[1] // 2

        # ── Left container (orb + chat) ───────────────────────────────────────
        self.left_frame = tk.Frame(self.root, bg=_BG, width=580)
        self.left_frame.pack(side="left", fill="y", expand=False)
        self.left_frame.pack_propagate(False)

        # Canvas for the animated orb + particles
        self.canvas = tk.Canvas(
            self.left_frame,
            width=size[0],
            height=size[1],
            bg=_BG,
            highlightthickness=0
        )
        self.canvas.place(relx=0.5, rely=0.38, anchor="center")

        # Load and prepare the face image
        raw = Image.open(face_path).convert("RGBA").resize(size, Image.LANCZOS)
        self.face_base = self._make_transparent(raw)
        self.halo_base = self._create_halo(size, radius=240, y_offset=0)

        # Animation state
        self.speaking        = False
        self.shake_intensity = 0.0
        self.scale           = 1.0
        self.target_scale    = 1.0
        self.halo_alpha      = 70.0
        self.target_halo_alpha = 70.0
        self.last_target_time  = time.time()
        self.frame_count       = 0

        # Particle system
        self.particles = self._init_particles()

        # Transcription label
        self.transcription_var = tk.StringVar(value="")
        self.transcription_label = tk.Label(
            self.left_frame,
            textvariable=self.transcription_var,
            fg=_CYAN,
            bg=_BG,
            font=("Consolas", 11),
            wraplength=540,
            justify="center",
            pady=6
        )
        self.transcription_label.place(relx=0.5, rely=0.76, anchor="center")

        # Chat log
        self.text_box = ScrolledText(
            self.left_frame,
            fg=_CYAN,
            bg=_BG,
            insertbackground=_CYAN,
            height=6,
            borderwidth=0,
            wrap="word",
            font=("Consolas", 10),
            padx=12,
            pady=8
        )
        self.text_box.place(relx=0.5, rely=0.88, anchor="center", relwidth=0.95)
        self.text_box.configure(state="disabled")

        # Typed input
        self._typed_input_queue = None
        self._input_placeholder = "Type a message..."

        self.input_frame = tk.Frame(self.left_frame, bg="#111111", pady=3)
        self.input_frame.place(relx=0.5, rely=0.97, anchor="center", relwidth=0.92)

        self.text_entry = tk.Entry(
            self.input_frame,
            bg="#1a1a1a",
            fg="#555555",
            insertbackground="white",
            font=("Segoe UI", 11),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2a2a2a",
            highlightcolor="#444444",
        )
        self.text_entry.pack(fill="x", padx=4, pady=3)
        self.text_entry.insert(0, self._input_placeholder)
        self.text_entry.bind("<FocusIn>",  self._clear_placeholder)
        self.text_entry.bind("<FocusOut>", self._restore_placeholder)
        self.text_entry.bind("<Return>",   self._submit_text)

        # ── Right panel ───────────────────────────────────────────────────────
        self.right_frame = tk.Frame(self.root, bg=_PANEL_BG, width=540)
        self.right_frame.pack(side="right", fill="both", expand=True)
        self.right_frame.pack_propagate(False)

        # Vertical separator line
        sep = tk.Frame(self.root, bg=_PANEL_EDGE, width=1)
        sep.pack(side="left", fill="y")

        self._build_right_panel()

        # ── First-run setup ───────────────────────────────────────────────────
        if not self._api_keys_exist():
            self._show_setup_ui()

        # ── Thread-safe queue ─────────────────────────────────────────────────
        self._command_queue = Queue()
        self.root.after(20, self._process_command_queue)

        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    # ─────────────────────────────────────────────
    #  Right panel construction
    # ─────────────────────────────────────────────

    def _build_right_panel(self):
        rf = self.right_frame

        # ── AGENTS section ────────────────────────────────────────────────────
        agents_hdr = tk.Frame(rf, bg=_PANEL_BG)
        agents_hdr.pack(fill="x", padx=10, pady=(12, 4))

        tk.Label(
            agents_hdr, text="● AGENTS",
            fg=_CYAN, bg=_PANEL_BG,
            font=("Consolas", 11, "bold")
        ).pack(side="left")

        self._agent_count_var = tk.StringVar(value="0 running")
        tk.Label(
            agents_hdr, textvariable=self._agent_count_var,
            fg=_DIM, bg=_PANEL_BG,
            font=("Consolas", 9)
        ).pack(side="right")

        # Agent list container (fixed height, scrollable)
        agent_list_wrap = tk.Frame(rf, bg=_PANEL_BG, height=240)
        agent_list_wrap.pack(fill="x", padx=10, pady=(0, 4))
        agent_list_wrap.pack_propagate(False)

        self._agent_canvas = tk.Canvas(
            agent_list_wrap, bg=_PANEL_BG, highlightthickness=0
        )
        agent_scroll = tk.Scrollbar(
            agent_list_wrap, orient="vertical",
            command=self._agent_canvas.yview,
            bg=_PANEL_BG, troughcolor=_PANEL_BG,
            width=8
        )
        self._agent_canvas.configure(yscrollcommand=agent_scroll.set)
        agent_scroll.pack(side="right", fill="y")
        self._agent_canvas.pack(side="left", fill="both", expand=True)

        self._agent_inner = tk.Frame(self._agent_canvas, bg=_PANEL_BG)
        self._agent_canvas_window = self._agent_canvas.create_window(
            (0, 0), window=self._agent_inner, anchor="nw"
        )
        self._agent_inner.bind("<Configure>", self._on_agent_inner_resize)
        self._agent_canvas.bind("<Configure>", self._on_agent_canvas_resize)

        self._agent_rows = {}   # task_id → (frame, name_var, status_var, status_label)

        # Horizontal divider
        tk.Frame(rf, bg=_PANEL_EDGE, height=1).pack(fill="x", padx=6, pady=4)

        # ── OUTPUT section ────────────────────────────────────────────────────
        out_hdr = tk.Frame(rf, bg=_PANEL_BG)
        out_hdr.pack(fill="x", padx=10, pady=(4, 4))

        tk.Label(
            out_hdr, text="● OUTPUT",
            fg=_CYAN, bg=_PANEL_BG,
            font=("Consolas", 11, "bold")
        ).pack(side="left")

        copy_btn = tk.Button(
            out_hdr, text="copy",
            command=self._copy_output,
            bg=_PANEL_BG, fg=_DIM,
            activebackground="#0a1830",
            font=("Consolas", 9),
            relief="flat", padx=6, pady=0,
            cursor="hand2"
        )
        copy_btn.pack(side="right")

        clear_btn = tk.Button(
            out_hdr, text="clear",
            command=self._clear_output,
            bg=_PANEL_BG, fg=_DIM,
            activebackground="#0a1830",
            font=("Consolas", 9),
            relief="flat", padx=6, pady=0,
            cursor="hand2"
        )
        clear_btn.pack(side="right", padx=(0, 4))

        self.output_box = tk.Text(
            rf,
            bg="#020a14", fg="#ccddee",
            insertbackground=_CYAN,
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=10, pady=8,
            state="disabled",
        )
        self.output_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Configure text tags for coloured output
        self.output_box.tag_configure("info",   foreground=_CYAN)
        self.output_box.tag_configure("ok",     foreground=_GREEN)
        self.output_box.tag_configure("warn",   foreground=_YELLOW)
        self.output_box.tag_configure("error",  foreground=_RED)
        self.output_box.tag_configure("normal", foreground="#ccddee")
        self.output_box.tag_configure("dim",    foreground=_DIM)

        # Output scrollbar
        out_scroll = tk.Scrollbar(rf, command=self.output_box.yview,
                                  bg=_PANEL_BG, troughcolor=_PANEL_BG, width=8)
        self.output_box.configure(yscrollcommand=out_scroll.set)

    def _on_agent_inner_resize(self, event):
        self._agent_canvas.configure(scrollregion=self._agent_canvas.bbox("all"))

    def _on_agent_canvas_resize(self, event):
        self._agent_canvas.itemconfig(self._agent_canvas_window, width=event.width)

    # ─────────────────────────────────────────────
    #  Image helpers
    # ─────────────────────────────────────────────

    def _make_transparent(self, img: Image.Image) -> Image.Image:
        data = img.getdata()
        new_data = []
        for r, g, b, a in data:
            if r > 220 and g > 220 and b > 220:
                new_data.append((r, g, b, 0))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
        return img

    def _create_halo(self, size, radius, y_offset):
        w, h = size
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = w // 2, h // 2 + y_offset
        for r in range(radius, 0, -10):
            alpha = int(80 * (1 - r / radius))
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 180, 255, alpha))
        return img.filter(ImageFilter.GaussianBlur(28))

    # ─────────────────────────────────────────────
    #  Particle system
    # ─────────────────────────────────────────────

    def _init_particles(self):
        particles = []
        total = 65
        for i in range(total):
            angle = (i / total) * 2 * math.pi + random.uniform(-0.15, 0.15)
            if i < 22:
                base_r = random.uniform(210, 255)
                size   = random.uniform(1.5, 3.5)
                alpha  = random.randint(50, 120)
            elif i < 48:
                base_r = random.uniform(255, 305)
                size   = random.uniform(2.0, 5.0)
                alpha  = random.randint(80, 160)
            else:
                base_r = random.uniform(305, 355)
                size   = random.uniform(1.0, 3.0)
                alpha  = random.randint(30, 90)
            particles.append({
                'angle':       angle,
                'base_r':      base_r,
                'r':           base_r,
                'size':        size,
                'phase':       random.uniform(0, 2 * math.pi),
                'phase_speed': random.uniform(0.008, 0.035),
                'drift':       random.uniform(-0.002, 0.002),
                'base_alpha':  alpha,
            })
        return particles

    def _update_particles(self):
        for p in self.particles:
            p['phase'] += p['phase_speed']
            p['angle'] += p['drift']

    # ─────────────────────────────────────────────
    #  Animation loop
    # ─────────────────────────────────────────────

    def _animate(self):
        now = time.time()
        self.frame_count += 1

        interval = 0.18 if self.speaking else 0.65
        if now - self.last_target_time > interval:
            if self.speaking:
                self.target_scale      = random.uniform(1.03, 1.12)
                self.target_halo_alpha = random.uniform(130, 165)
            else:
                self.target_scale      = random.uniform(1.002, 1.010)
                self.target_halo_alpha = random.uniform(55, 80)
            self.last_target_time = now

        ss = 0.50 if self.speaking else 0.22
        hs = 0.45 if self.speaking else 0.22
        self.scale      += (self.target_scale - self.scale) * ss
        self.halo_alpha += (self.target_halo_alpha - self.halo_alpha) * hs

        if self.speaking:
            self.shake_intensity = min(self.shake_intensity + 0.25, 1.0)
        else:
            self.shake_intensity = max(self.shake_intensity - 0.10, 0.0)

        self._update_particles()

        w, h = self.size
        frame = Image.new("RGBA", self.size, (0, 0, 0, 255))

        halo = self.halo_base.copy()
        halo.putalpha(int(self.halo_alpha))
        frame.alpha_composite(halo)

        face_w = int(w * self.scale)
        face_h = int(h * self.scale)
        face   = self.face_base.resize((face_w, face_h), Image.LANCZOS)
        fx = (w - face_w) // 2
        fy = (h - face_h) // 2
        if self.shake_intensity > 0.05:
            mag = int(self.shake_intensity * 7)
            fx += random.randint(-mag, mag)
            fy += random.randint(-mag, mag)
        frame.alpha_composite(face, (fx, fy))

        draw = ImageDraw.Draw(frame)
        for p in self.particles:
            breathe = math.sin(p['phase']) * 14
            r_now   = p['base_r'] + breathe
            x = self.cx + math.cos(p['angle']) * r_now
            y = self.cy + math.sin(p['angle']) * r_now
            if self.shake_intensity > 0.05:
                shake = self.shake_intensity * 10
                x += random.uniform(-shake, shake)
                y += random.uniform(-shake, shake)
            s = p['size']
            if self.speaking:
                alpha = min(255, int(p['base_alpha'] * 1.6))
                s = s * 1.35
            else:
                alpha = int(p['base_alpha'] * (0.6 + 0.4 * (math.sin(p['phase']) * 0.5 + 0.5)))
            draw.ellipse(
                [x - s, y - s, x + s, y + s],
                fill=(0x8f, 0xfc, 0xff, alpha)
            )

        img = ImageTk.PhotoImage(frame)
        self.canvas.delete("all")
        self.canvas.create_image(w // 2, h // 2, image=img)
        self.canvas.image = img

        self.root.after(16, self._animate)

    # ─────────────────────────────────────────────
    #  Thread-safe queue
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    #  Public API — chat log (thread-safe)
    # ─────────────────────────────────────────────

    def write_log(self, text: str):
        self._enqueue(self._write_log_impl, text)

    def _write_log_impl(self, text: str):
        try:
            self.text_box.configure(state="normal")
            self.text_box.insert(tk.END, text + "\n")
            self.text_box.see(tk.END)
            self.text_box.configure(state="disabled")
        except Exception:
            pass

    def start_speaking(self):
        self._enqueue(self._set_speaking, True)

    def stop_speaking(self):
        self._enqueue(self._set_speaking, False)

    def _set_speaking(self, value: bool):
        self.speaking = value

    def set_transcription(self, text: str):
        self._enqueue(self._set_transcription_impl, text)

    def _set_transcription_impl(self, text: str):
        try:
            self.transcription_var.set(text)
        except Exception:
            pass

    def clear_transcription(self):
        self._enqueue(self._set_transcription_impl, "")

    # ─────────────────────────────────────────────
    #  Public API — Agent panel (thread-safe)
    # ─────────────────────────────────────────────

    def add_agent_task(self, task_id: str, name: str, status: str = "running"):
        """Add a new row to the AGENTS panel."""
        self._enqueue(self._add_agent_task_impl, task_id, name, status)

    def _add_agent_task_impl(self, task_id: str, name: str, status: str):
        try:
            row = tk.Frame(self._agent_inner, bg=_PANEL_BG, pady=2)
            row.pack(fill="x", padx=4)

            dot_color = _YELLOW if status == "running" else (_GREEN if status == "done" else _RED)
            dot = tk.Canvas(row, width=8, height=8, bg=_PANEL_BG, highlightthickness=0)
            dot.create_oval(1, 1, 7, 7, fill=dot_color, outline="")
            dot.pack(side="left", padx=(0, 6))

            name_var   = tk.StringVar(value=name[:30])
            status_var = tk.StringVar(value=status)

            tk.Label(row, textvariable=name_var,
                     fg="#aaccdd", bg=_PANEL_BG,
                     font=("Consolas", 9), anchor="w"
                     ).pack(side="left", fill="x", expand=True)

            status_lbl = tk.Label(row, textvariable=status_var,
                                  fg=dot_color, bg=_PANEL_BG,
                                  font=("Consolas", 9))
            status_lbl.pack(side="right")

            self._agent_rows[task_id] = (row, name_var, status_var, status_lbl, dot)
            self._refresh_agent_count()
        except Exception:
            pass

    def update_agent_task(self, task_id: str, status: str):
        """Update the status of an existing agent row."""
        self._enqueue(self._update_agent_task_impl, task_id, status)

    def _update_agent_task_impl(self, task_id: str, status: str):
        try:
            row_data = self._agent_rows.get(task_id)
            if not row_data:
                return
            _, name_var, status_var, status_lbl, dot = row_data
            color = _YELLOW if status == "running" else (_GREEN if status == "done" else _RED)
            status_var.set(status)
            status_lbl.configure(fg=color)
            dot.delete("all")
            dot.create_oval(1, 1, 7, 7, fill=color, outline="")
            self._refresh_agent_count()
        except Exception:
            pass

    def _refresh_agent_count(self):
        try:
            running = sum(
                1 for (_, _, sv, _, _) in self._agent_rows.values()
                if sv.get() == "running"
            )
            total = len(self._agent_rows)
            self._agent_count_var.set(f"{running} running / {total} total")
        except Exception:
            pass

    # ─────────────────────────────────────────────
    #  Public API — Output panel (thread-safe)
    # ─────────────────────────────────────────────

    def append_output(self, text: str, color: str = "normal"):
        """
        Add a line to the OUTPUT panel.

        color: 'normal' | 'info' | 'ok' | 'warn' | 'error' | 'dim'
        """
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
            content = self.output_box.get("1.0", tk.END).strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
        except Exception:
            pass

    def _clear_output(self):
        try:
            self.output_box.configure(state="normal")
            self.output_box.delete("1.0", tk.END)
            self.output_box.configure(state="disabled")
        except Exception:
            pass

    # ─────────────────────────────────────────────
    #  Typed input field
    # ─────────────────────────────────────────────

    def set_typed_input_queue(self, q):
        self._typed_input_queue = q

    def highlight_text_input(self):
        self._enqueue(self._highlight_text_input_impl)

    def unhighlight_text_input(self):
        self._enqueue(self._unhighlight_text_input_impl)

    def _highlight_text_input_impl(self):
        try:
            self.text_entry.configure(
                highlightbackground="#f59e0b",
                highlightcolor="#f59e0b",
                fg="#ffffff",
            )
        except Exception:
            pass

    def _unhighlight_text_input_impl(self):
        try:
            current = self.text_entry.get()
            fg = "#555555" if current == self._input_placeholder else "#ffffff"
            self.text_entry.configure(
                highlightbackground="#2a2a2a",
                highlightcolor="#444444",
                fg=fg,
            )
        except Exception:
            pass

    def _clear_placeholder(self, event=None):
        try:
            if self.text_entry.get() == self._input_placeholder:
                self.text_entry.delete(0, tk.END)
                self.text_entry.configure(fg="#ffffff")
        except Exception:
            pass

    def _restore_placeholder(self, event=None):
        try:
            if not self.text_entry.get().strip():
                self.text_entry.delete(0, tk.END)
                self.text_entry.insert(0, self._input_placeholder)
                self.text_entry.configure(fg="#555555")
                self._unhighlight_text_input_impl()
        except Exception:
            pass

    def _submit_text(self, event=None):
        try:
            text = self.text_entry.get().strip()
            if text and text != self._input_placeholder and self._typed_input_queue is not None:
                self._typed_input_queue.put(text)
                self.text_entry.delete(0, tk.END)
                self._restore_placeholder()
                self._unhighlight_text_input_impl()
        except Exception:
            pass

    def show_draft_popup(self, draft_text: str):
        def _make_popup():
            popup = tk.Toplevel(self.root)
            popup.title("Sam's Draft Reply")
            popup.geometry("520x250")
            popup.configure(bg=_BG)
            popup.resizable(True, True)
            popup.lift()
            popup.focus_force()

            tk.Label(
                popup, text="Draft reply — copy and edit as needed:",
                fg=_CYAN, bg=_BG, font=("Consolas", 11)
            ).pack(pady=(12, 4), padx=16, anchor="w")

            txt = tk.Text(
                popup, height=6, wrap="word",
                font=("Consolas", 11), fg="#ffffff", bg="#111111",
                insertbackground="white", relief="flat", pady=6, padx=8
            )
            txt.insert("1.0", draft_text)
            txt.pack(padx=16, fill="both", expand=True)
            txt.focus_set()
            txt.tag_add("sel", "1.0", "end")

            def copy_and_close():
                self.root.clipboard_clear()
                self.root.clipboard_append(draft_text)
                popup.destroy()

            btn_frame = tk.Frame(popup, bg=_BG)
            btn_frame.pack(pady=10)
            tk.Button(btn_frame, text="Copy & Close", command=copy_and_close,
                      bg="#0077aa", fg="white", font=("Consolas", 10),
                      relief="flat", padx=12, pady=4
                      ).pack(side="left", padx=6)
            tk.Button(btn_frame, text="Close", command=popup.destroy,
                      bg="#333333", fg="white", font=("Consolas", 10),
                      relief="flat", padx=12, pady=4
                      ).pack(side="left", padx=6)

        self._enqueue(_make_popup)

    # ─────────────────────────────────────────────
    #  First-run API setup wizard
    # ─────────────────────────────────────────────

    def _api_keys_exist(self):
        return os.path.exists(API_FILE)

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(
            self.root,
            bg="#050505",
            highlightbackground="#00cfff",
            highlightthickness=1
        )
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            self.setup_frame, text="SAM SETUP",
            fg=_CYAN, bg="#050505", font=("Consolas", 14, "bold")
        ).pack(pady=(15, 10))

        self.openrouter_entry = self._setup_entry("OpenRouter API Key")
        self.serpapi_entry    = self._setup_entry("SerpAPI Key")

        tk.Button(
            self.setup_frame, text="SAVE & CONTINUE",
            command=self._save_api_keys,
            bg=_BG, fg=_CYAN, activebackground="#003344",
            font=("Consolas", 10), borderwidth=0
        ).pack(pady=15)

    def _setup_entry(self, label_text):
        tk.Label(
            self.setup_frame, text=label_text,
            fg=_CYAN, bg="#050505", font=("Consolas", 10)
        ).pack(pady=(8, 2))
        entry = tk.Entry(
            self.setup_frame,
            width=46,
            fg=_CYAN, bg=_BG,
            insertbackground=_CYAN,
            borderwidth=0, font=("Consolas", 10)
        )
        entry.pack(pady=(0, 6))
        return entry

    def _save_api_keys(self):
        openrouter_key = self.openrouter_entry.get().strip()
        serpapi_key    = self.serpapi_entry.get().strip()
        if not openrouter_key:
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(API_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"openrouter_api_key": openrouter_key, "serpapi_api_key": serpapi_key},
                f, indent=4
            )
        self.setup_frame.destroy()
        self.write_log("API keys saved.")
