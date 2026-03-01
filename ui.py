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


class SamUI:
    def __init__(self, face_path, size=(700, 700)):
        self.root = tk.Tk()
        self.root.title("SAM")
        self.root.resizable(False, False)
        self.root.geometry("580x760")
        self.root.configure(bg="#000000")

        self.size = size
        self.cx = size[0] // 2
        self.cy = size[1] // 2

        # Canvas for the animated orb + particles
        self.canvas = tk.Canvas(
            self.root,
            width=size[0],
            height=size[1],
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.place(relx=0.5, rely=0.38, anchor="center")

        # Load and prepare the face image
        raw = Image.open(face_path).convert("RGBA").resize(size, Image.LANCZOS)
        # Make white background transparent so it sits on black cleanly
        self.face_base = self._make_transparent(raw)

        self.halo_base = self._create_halo(size, radius=240, y_offset=0)

        # Animation state
        self.speaking = False
        self.shake_intensity = 0.0
        self.scale = 1.0
        self.target_scale = 1.0
        self.halo_alpha = 70.0
        self.target_halo_alpha = 70.0
        self.last_target_time = time.time()
        self.frame_count = 0

        # Particle system
        self.particles = self._init_particles()

        # ── Transcription label (shown below orb when Sam speaks) ──
        self.transcription_var = tk.StringVar(value="")
        self.transcription_label = tk.Label(
            self.root,
            textvariable=self.transcription_var,
            fg="#8ffcff",
            bg="#000000",
            font=("Consolas", 11),
            wraplength=540,
            justify="center",
            pady=6
        )
        self.transcription_label.place(relx=0.5, rely=0.76, anchor="center")

        # ── Logs box ──
        self.text_box = ScrolledText(
            self.root,
            fg="#8ffcff",
            bg="#000000",
            insertbackground="#8ffcff",
            height=8,
            borderwidth=0,
            wrap="word",
            font=("Consolas", 10),
            padx=12,
            pady=8
        )
        self.text_box.place(relx=0.5, rely=0.92, anchor="center")
        self.text_box.configure(state="disabled")

        # First-time API setup
        if not self._api_keys_exist():
            self._show_setup_ui()

        # Command queue for thread-safe UI calls
        self._command_queue = Queue()
        self.root.after(20, self._process_command_queue)

        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    # ─────────────────────────────────────────────
    #  Image helpers
    # ─────────────────────────────────────────────

    def _make_transparent(self, img: Image.Image) -> Image.Image:
        """Replace near-white pixels with transparency so the orb floats on black."""
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

            # Three rings: inner glow, mid orbit, outer corona
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

        # ── Target update ──
        interval = 0.18 if self.speaking else 0.65
        if now - self.last_target_time > interval:
            if self.speaking:
                self.target_scale = random.uniform(1.03, 1.12)
                self.target_halo_alpha = random.uniform(130, 165)
            else:
                self.target_scale = random.uniform(1.002, 1.010)
                self.target_halo_alpha = random.uniform(55, 80)
            self.last_target_time = now

        # ── Lerp ──
        ss = 0.50 if self.speaking else 0.22
        hs = 0.45 if self.speaking else 0.22
        self.scale      += (self.target_scale - self.scale) * ss
        self.halo_alpha += (self.target_halo_alpha - self.halo_alpha) * hs

        # ── Shake ramp ──
        if self.speaking:
            self.shake_intensity = min(self.shake_intensity + 0.25, 1.0)
        else:
            self.shake_intensity = max(self.shake_intensity - 0.10, 0.0)

        self._update_particles()

        # ── Build PIL frame ──
        w, h = self.size
        frame = Image.new("RGBA", self.size, (0, 0, 0, 255))

        # Halo
        halo = self.halo_base.copy()
        halo.putalpha(int(self.halo_alpha))
        frame.alpha_composite(halo)

        # Orb face (scaled + optional shake)
        face_w = int(w * self.scale)
        face_h = int(h * self.scale)
        face = self.face_base.resize((face_w, face_h), Image.LANCZOS)
        fx = (w - face_w) // 2
        fy = (h - face_h) // 2
        if self.shake_intensity > 0.05:
            mag = int(self.shake_intensity * 7)
            fx += random.randint(-mag, mag)
            fy += random.randint(-mag, mag)
        frame.alpha_composite(face, (fx, fy))

        # Particles
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
            # Boost alpha and size when speaking
            if self.speaking:
                alpha = min(255, int(p['base_alpha'] * 1.6))
                s = s * 1.35
            else:
                alpha = int(p['base_alpha'] * (0.6 + 0.4 * (math.sin(p['phase']) * 0.5 + 0.5)))

            draw.ellipse(
                [x - s, y - s, x + s, y + s],
                fill=(0x8f, 0xfc, 0xff, alpha)
            )

        # ── Render to canvas ──
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
    #  Public API (thread-safe)
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
        """Show transcription of what Sam is saying below the orb."""
        self._enqueue(self._set_transcription_impl, text)

    def _set_transcription_impl(self, text: str):
        try:
            self.transcription_var.set(text)
        except Exception:
            pass

    def clear_transcription(self):
        """Clear the transcription line when Sam finishes speaking."""
        self._enqueue(self._set_transcription_impl, "")

    def show_draft_popup(self, draft_text: str):
        """Open a small copyable window showing a drafted message."""
        def _make_popup():
            popup = tk.Toplevel(self.root)
            popup.title("Sam's Draft Reply")
            popup.geometry("520x250")
            popup.configure(bg="#000000")
            popup.resizable(True, True)
            popup.lift()
            popup.focus_force()

            tk.Label(
                popup, text="Draft reply — copy and edit as needed:",
                fg="#8ffcff", bg="#000000", font=("Consolas", 11)
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

            btn_frame = tk.Frame(popup, bg="#000000")
            btn_frame.pack(pady=10)
            tk.Button(
                btn_frame, text="Copy & Close", command=copy_and_close,
                bg="#0077aa", fg="white", font=("Consolas", 10), relief="flat",
                padx=12, pady=4
            ).pack(side="left", padx=6)
            tk.Button(
                btn_frame, text="Close", command=popup.destroy,
                bg="#333333", fg="white", font=("Consolas", 10), relief="flat",
                padx=12, pady=4
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
            self.setup_frame,
            text="SAM SETUP",
            fg="#8ffcff",
            bg="#050505",
            font=("Consolas", 14, "bold")
        ).pack(pady=(15, 10))

        self.openrouter_entry = self._setup_entry("OpenRouter API Key")
        self.serpapi_entry    = self._setup_entry("SerpAPI Key")

        tk.Button(
            self.setup_frame,
            text="SAVE & CONTINUE",
            command=self._save_api_keys,
            bg="#000000",
            fg="#8ffcff",
            activebackground="#003344",
            font=("Consolas", 10),
            borderwidth=0
        ).pack(pady=15)

    def _setup_entry(self, label_text):
        tk.Label(
            self.setup_frame,
            text=label_text,
            fg="#8ffcff",
            bg="#050505",
            font=("Consolas", 10)
        ).pack(pady=(8, 2))
        entry = tk.Entry(
            self.setup_frame,
            width=46,
            fg="#8ffcff",
            bg="#000000",
            insertbackground="#8ffcff",
            borderwidth=0,
            font=("Consolas", 10)
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
