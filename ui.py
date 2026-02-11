import os
import json
import time
import random
import tkinter as tk
from collections import deque
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

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE = CONFIG_DIR / "api_keys.json"
class SamUI:
    def __init__(self, face_path, size=(760, 760)):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S")
        self.root.resizable(False, False)
        self.root.geometry("760x900")
        self.root.configure(bg="#000000")

        self.size = size
        self.center_y = 0.42

        self.canvas = tk.Canvas(
            self.root,
            width=size[0],
            height=size[1],
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.place(relx=0.5, rely=self.center_y, anchor="center")

        self.face_base = (
            Image.open(face_path)
            .convert("RGBA")
            .resize(size, Image.LANCZOS)
        )

        self.halo_base = self._create_halo(size, radius=220, y_offset=-50)

        self.speaking = False
        self.scale = 1.0
        self.target_scale = 1.0
        self.halo_alpha = 70
        self.target_halo_alpha = 70
        self.last_target_time = time.time()

        self.text_box = ScrolledText(
            self.root,
            fg="#8ffcff",
            bg="#000000",
            insertbackground="#8ffcff",
            height=12,
            borderwidth=0,
            wrap="word",
            font=("Consolas", 10),
            padx=12,
            pady=12
        )
        self.text_box.place(relx=0.5, rely=0.86, anchor="center")
        self.text_box.configure(state="disabled")

        self.typing_queue = deque()
        self.is_typing = False

        if not self._api_keys_exist():
            self._show_setup_ui()

        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

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

        self.openrouter_entry = self._setup_entry(
            "OpenRouter API Key"
        )
        self.serpapi_entry = self._setup_entry(
            "SerpAPI Key"
        )

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
        serpapi_key = self.serpapi_entry.get().strip()

        if not openrouter_key:
            return  

        os.makedirs(CONFIG_DIR, exist_ok=True)

        with open(API_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "openrouter_api_key": openrouter_key,
                    "serpapi_api_key": serpapi_key
                },
                f,
                indent=4
            )

        self.setup_frame.destroy()
        self.write_log("API keys saved successfully.")

    def _create_halo(self, size, radius, y_offset):
        w, h = size
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = w // 2
        cy = h // 2 + y_offset

        for r in range(radius, 0, -12):
            alpha = int(70 * (1 - r / radius))
            draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                fill=(0, 180, 255, alpha)
            )

        return img.filter(ImageFilter.GaussianBlur(30))

    def write_log(self, text: str):
        self.typing_queue.append(text)
        if not self.is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            return

        self.is_typing = True
        text = self.typing_queue.popleft()

        self.text_box.configure(state="normal")
        self._type_char(text, 0)

    def _type_char(self, text, i):
        if i < len(text):
            self.text_box.insert(tk.END, text[i])
            self.text_box.see(tk.END)
            self.root.after(12, self._type_char, text, i + 1)
        else:
            self.text_box.insert(tk.END, "\n")
            self.text_box.configure(state="disabled")
            self.root.after(40, self._start_typing)


    def start_speaking(self):
        self.speaking = True

    def stop_speaking(self):
        self.speaking = False

    def _animate(self):
        now = time.time()

        if now - self.last_target_time > (0.25 if self.speaking else 0.7):
            if self.speaking:
                self.target_scale = random.uniform(1.02, 1.1)
                self.target_halo_alpha = random.randint(120, 150)
            else:
                self.target_scale = random.uniform(1.004, 1.012)
                self.target_halo_alpha = random.randint(60, 80)

            self.last_target_time = now

        scale_speed = 0.45 if self.speaking else 0.25
        halo_speed = 0.40 if self.speaking else 0.25

        self.scale += (self.target_scale - self.scale) * scale_speed
        self.halo_alpha += (self.target_halo_alpha - self.halo_alpha) * halo_speed

        frame = Image.new("RGBA", self.size, (0, 0, 0, 255))

        halo = self.halo_base.copy()
        halo.putalpha(int(self.halo_alpha))
        frame.alpha_composite(halo)

        w, h = self.size
        face = self.face_base.resize(
            (int(w * self.scale), int(h * self.scale)),
            Image.LANCZOS
        )

        fx = (w - face.size[0]) // 2
        fy = (h - face.size[1]) // 2
        frame.alpha_composite(face, (fx, fy))

        img = ImageTk.PhotoImage(frame)
        self.canvas.delete("all")
        self.canvas.create_image(w // 2, h // 2, image=img)
        self.canvas.image = img

        self.root.after(16, self._animate)
