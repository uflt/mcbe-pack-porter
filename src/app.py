# -*- coding: utf-8 -*-
"""GUI: перетащи пак в окно. Режимы: -> Bedrock, -> Java, только смена описания."""
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
import porter

W, H = 560, 560
ZONE = (36, 36, W - 36, 440)      # область "перетащи сюда"
HEAD_BOTTOM = 152                 # нижний край верхней тёмной полосы
BAR = (36, 452, W - 36, H - 24)   # нижняя панель со статусом
BORDER = "#ffffff"
BORDER_HOVER = "#ffd23f"
FONT = "Segoe UI"

TEXTS = {
    "bedrock": ("Перетащите Java-пак сюда",
                "Java (.zip или папка) → Bedrock .mcpack, описание ставится моё"),
    "java": ("Перетащите Bedrock-пак сюда",
             "Bedrock (.mcpack) → Java .zip, описание ставится моё"),
    "desc": ("Перетащите .mcpack сюда", "описание пака поменяется на моё"),
}
MODES = (("bedrock", "→ Bedrock"), ("java", "→ Java"), ("desc", "Только описание"))


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
    d.rounded_rectangle((ZONE[0] + 10, ZONE[1] + 10, ZONE[2] - 10, HEAD_BOTTOM), radius=16,
                        fill=(0, 0, 0, 160))
    return Image.alpha_composite(img, layer).convert("RGB")


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Пак-тулза — @ufltRP")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(str(resource_path("assets/icon.ico")))
        except Exception:
            pass

        self.busy = False
        self.last_dir = None
        self.mode = tk.StringVar(value="bedrock")
        self.bg = ImageTk.PhotoImage(make_background())

        self.canvas = tk.Canvas(self.root, width=W, height=H, highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.bg, anchor="nw")
        self.canvas.create_rectangle(*ZONE, outline=BORDER, width=3, dash=(10, 7),
                                     tags="border")

        cx = W // 2
        title, sub = TEXTS["bedrock"]
        self.text(cx, 66, title, 22, "bold", tag="title")
        self.text(cx, 98, sub, 11, tag="subtitle")
        self.status_id = self.text(cx, 478, "Готов к работе", 12, color="#dddddd",
                                   outline=False)
        self.build_mode_switch(cx, 128)
        self.build_controls()
        self.on_mode()

        self.canvas.bind("<Button-1>", self.on_click)
        for w in (self.root, self.canvas, self.bar, self.mode_bar):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)
            w.dnd_bind("<<DropEnter>>", self.on_enter)
            w.dnd_bind("<<DropLeave>>", self.on_leave)

        # файл можно также перетащить прямо на .exe
        if len(sys.argv) > 1:
            self.root.after(300, self.run, sys.argv[1:])

    # ---------- интерфейс ----------
    def text(self, x, y, s, size, weight="normal", color="white", outline=True, tag=None):
        font = (FONT, size, weight)
        tags = (tag,) if tag else ()
        if outline:  # чёрная обводка, чтобы текст читался на любом фоне
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                self.canvas.create_text(x + dx, y + dy, text=s, font=font, fill="black",
                                        width=W - 100, justify="center", tags=tags)
        return self.canvas.create_text(x, y, text=s, font=font, fill=color,
                                       width=W - 100, justify="center", tags=tags)

    def build_mode_switch(self, cx, y):
        bg = "#101010"
        self.mode_bar = tk.Frame(self.root, bg=bg)
        for value, label in MODES:
            tk.Radiobutton(self.mode_bar, text=label, value=value, variable=self.mode,
                           indicatoron=False, command=self.on_mode, bg="#2a2a2a", fg="white",
                           selectcolor="#c77d00", activebackground="#3a3a3a",
                           activeforeground="white", font=(FONT, 10, "bold"),
                           padx=14, pady=3, bd=0, relief="flat", cursor="hand2"
                           ).pack(side="left", padx=2)
        self.canvas.create_window(cx, y, window=self.mode_bar)

    def build_controls(self):
        bg = "#101010"
        self.bar = tk.Frame(self.root, bg=bg)

        # цвет описания — во всех режимах
        tk.Label(self.bar, text="Цвет:", bg=bg, fg="white",
                 font=(FONT, 10)).pack(side="left", padx=(0, 4))
        self.color = tk.StringVar(value="Радуга")
        ttk.Combobox(self.bar, textvariable=self.color, values=list(core.COLORS),
                     state="readonly", width=9).pack(side="left", padx=(0, 10))

        # дополнительные опции — зависят от режима
        self.extra = tk.Frame(self.bar, bg=bg)
        self.extra.pack(side="left")

        self.extra_desc = tk.Frame(self.extra, bg=bg)
        self.bump = tk.BooleanVar(value=True)
        tk.Checkbutton(self.extra_desc, text="Повысить версию", variable=self.bump, bg=bg,
                       fg="white", selectcolor="#333333", activebackground=bg,
                       activeforeground="white", font=(FONT, 10)).pack(side="left")

        self.extra_bedrock = tk.Frame(self.extra, bg=bg)
        tk.Button(self.extra_bedrock, text="Папка…", command=self.pick_folder,
                  font=(FONT, 10)).pack(side="left")

        self.extra_java = tk.Frame(self.extra, bg=bg)
        tk.Label(self.extra_java, text="Java:", bg=bg, fg="white",
                 font=(FONT, 10)).pack(side="left", padx=(0, 4))
        self.java_ver = tk.StringVar(value=porter.DEFAULT_VERSION)
        ttk.Combobox(self.extra_java, textvariable=self.java_ver,
                     values=list(porter.JAVA_VERSIONS), state="readonly",
                     width=8).pack(side="left", padx=(0, 8))
        tk.Button(self.extra_java, text="Папка…", command=self.pick_folder,
                  font=(FONT, 10)).pack(side="left")

        self.open_btn = tk.Button(self.bar, text="Открыть папку", state="disabled",
                                  command=self.open_folder, font=(FONT, 10))
        self.open_btn.pack(side="left", padx=(10, 0))
        self.canvas.create_window(W // 2, 516, window=self.bar)

    def on_mode(self):
        mode = self.mode.get()
        title, sub = TEXTS[mode]
        self.canvas.itemconfig("title", text=title)
        self.canvas.itemconfig("subtitle", text=sub)
        for f in (self.extra_desc, self.extra_bedrock, self.extra_java):
            f.pack_forget()
        {"desc": self.extra_desc, "bedrock": self.extra_bedrock,
         "java": self.extra_java}[mode].pack()
        self.set_status("Готов к работе")

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
                title="Выберите пак",
                filetypes=[("Minecraft pack", "*.mcpack *.zip"), ("Все файлы", "*.*")])
            if files:
                self.run(files)

    def pick_folder(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title="Выберите папку с паком")
        if folder:
            self.run([folder])

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
        mode = self.mode.get()
        color, bump, ver = self.color.get(), self.bump.get(), self.java_ver.get()
        description = core.build_description(color, True)  # моё описание — всегда
        results, state = [], {"done": False}

        def work():
            for p in paths:
                try:
                    if mode == "desc":
                        dst = core.process(p, color, True, bump)
                        results.append((Path(p), dst, None, None))
                    else:
                        res = porter.port_pack(p, mode, ver, description)
                        results.append((Path(p), res.dst, None, res))
                except Exception as e:  # noqa: BLE001
                    results.append((Path(p), None, str(e), None))
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self.poll(results, state, mode)

    def poll(self, results, state, mode):
        if not state["done"]:
            self.root.after(100, self.poll, results, state, mode)
            return
        self.busy = False
        ok = [r for r in results if r[1]]
        bad = [r for r in results if r[2]]
        if ok:
            self.last_dir = ok[0][1].parent
            self.open_btn.config(state="normal")
        if ok and not bad:
            if len(ok) > 1:
                msg = f"✓ Готово: обработано файлов — {len(ok)}"
            elif mode != "desc":
                res = ok[0][3]
                msg = f"✓ {res.direction}: {res.dst.name} ({res.converted} текстур)"
            else:
                msg = f"✓ Готово: {ok[0][1].name}"
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
