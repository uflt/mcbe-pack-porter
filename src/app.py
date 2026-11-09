# -*- coding: utf-8 -*-
"""GUI: перетащи .mcpack в окно — описание станет ярким."""
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageDraw, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

import core

W, H = 560, 560
ZONE = (36, 36, W - 36, 440)      # область "перетащи сюда"
BAR = (36, 452, W - 36, H - 24)   # нижняя панель со статусом
BORDER = "#ffffff"
BORDER_HOVER = "#ffd23f"
FONT = "Segoe UI"


def resource_path(rel: str) -> Path:
    """Путь к ресурсу и в исходниках, и внутри собранного .exe (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return Path(base) / rel


def make_background() -> Image.Image:
    """Картинка пака + затемнение + полупрозрачные панели под текст."""
    img = Image.open(resource_path("assets/background.jpg")).convert("RGB")
    img = img.resize((W, H), Image.LANCZOS)
    img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), 0.30).convert("RGBA")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(ZONE, radius=24, fill=(0, 0, 0, 70))
    d.rounded_rectangle(BAR, radius=18, fill=(0, 0, 0, 170))
    d.rounded_rectangle((ZONE[0] + 10, ZONE[1] + 10, ZONE[2] - 10, 128), radius=16,
                        fill=(0, 0, 0, 150))
    return Image.alpha_composite(img, layer).convert("RGB")


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Смена описания .mcpack — @ufltRP")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(str(resource_path("assets/icon.ico")))
        except Exception:
            pass

        self.busy = False
        self.last_dir = None
        self.bg = ImageTk.PhotoImage(make_background())

        self.canvas = tk.Canvas(self.root, width=W, height=H, highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.bg, anchor="nw")
        self.canvas.create_rectangle(*ZONE, outline=BORDER, width=3, dash=(10, 7),
                                     tags="border")

        cx = W // 2
        self.text(cx, 68, "Перетащите .mcpack сюда", 24, "bold")
        self.text(cx, 104, "или нажмите, чтобы выбрать файл", 13)
        self.status_id = self.text(cx, 478, "Готов к работе", 12, color="#dddddd",
                                   outline=False)
        self.build_controls()

        self.canvas.bind("<Button-1>", self.on_click)
        for w in (self.root, self.canvas, self.bar):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)
            w.dnd_bind("<<DropEnter>>", self.on_enter)
            w.dnd_bind("<<DropLeave>>", self.on_leave)

        # файл можно также перетащить прямо на .exe
        if len(sys.argv) > 1:
            self.root.after(300, self.run, sys.argv[1:])

    # ---------- интерфейс ----------
    def text(self, x, y, s, size, weight="normal", color="white", outline=True):
        font = (FONT, size, weight)
        if outline:  # чёрная обводка, чтобы текст читался на любом фоне
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                self.canvas.create_text(x + dx, y + dy, text=s, font=font, fill="black")
        return self.canvas.create_text(x, y, text=s, font=font, fill=color,
                                       width=W - 100, justify="center")

    def build_controls(self):
        bg = "#101010"
        self.bar = tk.Frame(self.root, bg=bg)
        tk.Label(self.bar, text="Цвет:", bg=bg, fg="white",
                 font=(FONT, 10)).pack(side="left", padx=(0, 4))

        self.color = tk.StringVar(value="Радуга")
        ttk.Combobox(self.bar, textvariable=self.color, values=list(core.COLORS),
                     state="readonly", width=9).pack(side="left", padx=(0, 12))

        self.bump = tk.BooleanVar(value=True)
        tk.Checkbutton(self.bar, text="Повысить версию", variable=self.bump, bg=bg,
                       fg="white", selectcolor="#333333", activebackground=bg,
                       activeforeground="white", font=(FONT, 10)).pack(side="left", padx=(0, 12))

        self.open_btn = tk.Button(self.bar, text="Открыть папку", state="disabled",
                                  command=self.open_folder, font=(FONT, 10))
        self.open_btn.pack(side="left")
        self.canvas.create_window(W // 2, 516, window=self.bar)

    def set_status(self, s, color="#dddddd"):
        self.canvas.itemconfig(self.status_id, text=s, fill=color)

    def on_enter(self, event):
        self.canvas.itemconfig("border", outline=BORDER_HOVER, width=5)
        return event.action

    def on_leave(self, event):
        self.canvas.itemconfig("border", outline=BORDER, width=3)
        return event.action

    # ---------- события ----------
    def on_click(self, event):
        x1, y1, x2, y2 = ZONE
        if x1 <= event.x <= x2 and y1 <= event.y <= y2 and not self.busy:
            files = filedialog.askopenfilenames(
                title="Выберите .mcpack",
                filetypes=[("Minecraft pack", "*.mcpack *.zip"), ("Все файлы", "*.*")])
            if files:
                self.run(files)

    def on_drop(self, event):
        self.on_leave(event)
        self.run(self.root.tk.splitlist(event.data))
        return event.action

    # ---------- обработка ----------
    def run(self, paths):
        if self.busy:
            return
        self.busy = True
        self.set_status("Обработка…", "#ffd23f")
        color, bump = self.color.get(), self.bump.get()
        results, state = [], {"done": False}

        def work():
            for p in paths:
                try:
                    results.append((Path(p), core.process(p, color, True, bump), None))
                except Exception as e:  # noqa: BLE001
                    results.append((Path(p), None, str(e)))
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self.poll(results, state)

    def poll(self, results, state):
        if not state["done"]:
            self.root.after(100, self.poll, results, state)
            return
        self.busy = False
        ok = [r for r in results if r[1]]
        bad = [r for r in results if r[2]]
        if ok:
            self.last_dir = ok[0][1].parent
            self.open_btn.config(state="normal")
        if ok and not bad:
            msg = (f"✓ Готово: {ok[0][1].name}" if len(ok) == 1
                   else f"✓ Готово: обработано файлов — {len(ok)}")
            self.set_status(msg, "#7CFC8A")
        elif bad:
            first = bad[0]
            msg = f"✗ {first[0].name}: {first[2]}"
            if ok:
                msg = f"Готово: {len(ok)}, ошибок: {len(bad)}. " + msg
            self.set_status(msg, "#ff6b6b")

    def open_folder(self):
        if not self.last_dir:
            return
        if sys.platform == "win32":
            os.startfile(self.last_dir)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(self.last_dir)])
        else:
            subprocess.Popen(["xdg-open", str(self.last_dir)])

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
