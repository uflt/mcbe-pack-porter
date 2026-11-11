# -*- coding: utf-8 -*-
"""
GUI @ufltRP: перетащи пак в окно.
Режимы: → Bedrock, → Java, только описание.

Всё рисуется заранее (Pillow) в реальном разрешении экрана, поэтому интерфейс чёткий на любом
масштабе Windows. Блики короткие и проигрываются только при переключении режима и успехе —
в простое окно не нагружает процессор.
"""
import json
import math
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from PIL import Image, ImageDraw, ImageFilter, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

import core
import porter
import vanilla

# ---------------------------------------------------------------- оформление
W, H = 600, 640                       # логические пиксели (масштабируются под DPI)
GOLD_TOP, GOLD_BOT = (255, 214, 120), (214, 150, 38)
TEXT, MUTED, DIM = "#f4f1ea", "#b9b3a8", "#7d776d"
ON_GOLD = "#201608"
OK_COL, ERR_COL, WORK_COL = "#8ee39c", "#ff8a80", "#ffd26e"
FONT, FONT_SEMI = "Segoe UI", "Segoe UI Semibold"

TEXTS = {
    "bedrock": ("Перетащите Java-пак сюда", "Java (.zip или папка) → Bedrock .mcpack · или нажмите на картинку"),
    "java": ("Перетащите Bedrock-пак сюда", "Bedrock .mcpack → Java .zip · или нажмите на картинку"),
    "desc": ("Перетащите .mcpack сюда", "описание поменяется на ваше · или нажмите на картинку"),
}
MODES = (("bedrock", "→ Bedrock", 128), ("java", "→ Java", 112), ("desc", "Только описание", 168))
RGB = "Радуга"   # описание всегда переливается всеми цветами

ZONE = (20, 20, 580, 528)      # пунктирная рамка поверх картинки
TOP = (90, 34, 510, 76)        # капсула с режимами
TITLE = (40, 428, 560, 512)    # полоса с надписью внизу рамки
PANEL = (20, 540, 580, 620)    # нижняя панель: статус и настройки режима
SS = 3   # сглаживание: рисуем в 3 раза крупнее и уменьшаем


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return Path(base) / rel


def enable_dpi_awareness():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- рисование (Pillow)
def rr_mask(w, h, r):
    m = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), r * SS, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def vgrad(w, h, top, bottom):
    g = Image.linear_gradient("L").resize((max(1, w), max(1, h)))
    return Image.composite(Image.new("RGBA", g.size, bottom), Image.new("RGBA", g.size, top), g)


def _colored(mask, color):
    out = Image.new("RGBA", mask.size, color[:3] + (0,))
    out.putalpha(mask.point(lambda v: v * color[3] // 255))
    return out


def ring(w, h, r, width, color):
    m = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), r * SS,
                                        outline=255, width=max(1, int(width * SS)))
    return _colored(m.resize((w, h), Image.LANCZOS), color)


def dashed_ring(w, h, r, width, dash, gap, color):
    """Пунктирная скруглённая рамка (dash/gap — в логических пикселях * масштаб)."""
    big = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(big)
    lw = max(1, int(width * SS))
    o = lw / 2
    bw, bh, R = w * SS - lw, h * SS - lw, r * SS
    pts = []

    def arc(cx, cy, a0):
        for i in range(0, 91, 3):
            t = math.radians(a0 + i)
            pts.append((cx + R * math.cos(t), cy + R * math.sin(t)))

    pts.append((o + R, o))
    pts.append((o + bw - R, o)); arc(o + bw - R, o + R, -90)
    pts.append((o + bw, o + bh - R)); arc(o + bw - R, o + bh - R, 0)
    pts.append((o + R, o + bh)); arc(o + R, o + bh - R, 90)
    pts.append((o, o + R)); arc(o + R, o + R, 180)
    left, draw_on = dash * SS, True
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while pos < seg:
            step = min(left, seg - pos)
            if draw_on and seg:
                a, b = pos / seg, (pos + step) / seg
                d.line((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a,
                        x0 + (x1 - x0) * b, y0 + (y1 - y0) * b), fill=255, width=lw)
            pos += step
            left -= step
            if left <= 0:
                draw_on = not draw_on
                left = (dash if draw_on else gap) * SS
    return _colored(big.resize((w, h), Image.LANCZOS), color)


def glass(w, h, r, s, tint=(16, 15, 20), alpha=150):
    """Стеклянная панель с объёмом: заливка, верхний блик, внутренняя тень, тонкая кромка."""
    body = vgrad(w, h, tint + (alpha,), tuple(max(0, c - 6) for c in tint) + (min(255, alpha + 30),))
    body.alpha_composite(vgrad(w, max(1, h // 3), (255, 255, 255, 26), (255, 255, 255, 0)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(body, (0, 0), rr_mask(w, h, r))
    out.alpha_composite(ring(w, h, r, s, (255, 255, 255, 34)))
    out.alpha_composite(ring(w - 2 * s, h - 2 * s, max(1, r - s), s, (0, 0, 0, 90)), (s, s))
    return out


def drop_shadow(img, box, r, blur, alpha, dy):
    x0, y0, x1, y1 = box
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((x0, y0 + dy, x1, y1 + dy), r, fill=alpha)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(blur)))
    img.alpha_composite(sh)


def pill(w, h, s, kind):
    """Кнопка-«таблетка». kind: idle | hover | active | ghost | ghost_hover | disabled."""
    r = h // 2
    if kind == "active":
        img = vgrad(w, h, GOLD_TOP + (255,), GOLD_BOT + (255,))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 90), (255, 255, 255, 0)))
        edge = (255, 240, 200, 160)
    elif kind in ("hover", "ghost_hover"):
        img = vgrad(w, h, (255, 255, 255, 70), (255, 255, 255, 34))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 40), (255, 255, 255, 0)))
        edge = (255, 230, 170, 150)
    elif kind == "disabled":
        img = Image.new("RGBA", (w, h), (30, 29, 32, 160))
        edge = (255, 255, 255, 18)
    else:
        img = vgrad(w, h, (255, 255, 255, 34), (255, 255, 255, 14))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 30), (255, 255, 255, 0)))
        edge = (255, 255, 255, 70)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), rr_mask(w, h, r))
    out.alpha_composite(ring(w, h, r, s, edge))
    return out


def knob(d, s, color=(245, 242, 236)):
    """Круглая ручка переключателя с объёмом (блик сверху, затемнение снизу)."""
    pad = 4 * s
    big = d * SS
    circle = Image.new("L", (big, big), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, big - 1, big - 1), fill=255)
    top = tuple(min(255, int(c * 1.08) + 18) for c in color)
    bot = tuple(int(c * 0.7) for c in color)
    disc = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    disc.paste(vgrad(big, big, top + (255,), bot + (255,)), (0, 0), circle)
    hl = Image.new("L", (big, big), 0)
    ImageDraw.Draw(hl).ellipse((big * 0.2, big * 0.06, big * 0.8, big * 0.46), fill=105)
    hl = hl.filter(ImageFilter.GaussianBlur(big * 0.05))
    disc.alpha_composite(_colored(Image.composite(hl, Image.new("L", hl.size, 0), circle),
                                  (255, 255, 255, 255)))
    out = Image.new("RGBA", (d + 2 * pad, d + 2 * pad), (0, 0, 0, 0))
    out.alpha_composite(disc.resize((d, d), Image.LANCZOS), (pad, pad))
    return out


def glint_band(w, h, pos, width_frac=0.22, strength=70):
    """Диагональная полоса блика; pos 0..1 — положение слева направо."""
    bw = max(2, int(w * width_frac))
    prof = Image.new("L", (bw, 1))
    pp = prof.load()
    for x in range(bw):
        t = 1 - abs(x / (bw - 1) * 2 - 1)
        pp[x, 0] = int(strength * (t ** 1.6))
    rot = prof.resize((bw, h * 2)).rotate(-22, expand=True, resample=Image.BICUBIC)
    canvas = Image.new("L", (w, h), 0)
    canvas.paste(rot, (int(-rot.width + (w + rot.width) * pos), (h - rot.height) // 2))
    return canvas


# ---------------------------------------------------------------- приложение
class App:
    def __init__(self):
        enable_dpi_awareness()
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.s = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.root.title("@ufltRP")
        self.root.configure(bg="#0e0d10")
        self.root.geometry(f"{self.px(W)}x{self.px(H)}")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(str(resource_path("assets/icon.ico")))
        except Exception:  # noqa: BLE001
            pass

        self.busy = False
        st = self.load_settings()
        self.mc_dir = st.get("mc_dir")
        self.mode = st.get("mode") if st.get("mode") in TEXTS else "desc"
        ver = st.get("java_version")
        self.java_ver = ver if ver in porter.JAVA_VERSIONS else porter.DEFAULT_VERSION
        self.bump = bool(st.get("bump", True))
        self._imgs = {}      # ссылки на PhotoImage, чтобы их не собрал сборщик мусора
        self._anim = {}
        self._glint_cache = {}

        self.canvas = tk.Canvas(self.root, width=self.px(W), height=self.px(H),
                                highlightthickness=0, bd=0, bg="#0e0d10")
        self.canvas.pack()
        self.build_static()
        self.build_card()
        self.build_panel()
        self.build_modes()
        self.apply_mode(initial=True)

        for w in (self.root, self.canvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)
            w.dnd_bind("<<DropEnter>>", self.on_enter)
            w.dnd_bind("<<DropLeave>>", self.on_leave)
        self.root.deiconify()
        threading.Thread(target=self.warm_glints, daemon=True).start()
        if len(sys.argv) > 1:
            self.root.after(300, self.run, sys.argv[1:])

    # ---------- утилиты ----------
    def px(self, v):
        return int(round(v * self.s))

    def photo(self, key, img):
        ph = ImageTk.PhotoImage(img)
        self._imgs[key] = ph
        return ph

    def text(self, x, y, s, size, color=TEXT, font=FONT, anchor="center", tag=None, width=None):
        return self.canvas.create_text(self.px(x), self.px(y), text=s, fill=color, font=(font, size),
                                       anchor=anchor, tags=tag, justify="center",
                                       width=self.px(width) if width else 0)

    def hover_cursor(self, on):
        self.canvas.config(cursor="hand2" if on else "")

    def bind(self, tag, enter, leave, click):
        self.canvas.tag_bind(tag, "<Enter>", enter)
        self.canvas.tag_bind(tag, "<Leave>", leave)
        self.canvas.tag_bind(tag, "<Button-1>", click)

    # ---------- фон ----------
    def build_static(self):
        s = self.s
        w, h = self.px(W), self.px(H)
        bg = Image.open(resource_path("assets/background.jpg")).convert("RGB")
        side = max(w, h)
        bg = bg.resize((side, side), Image.LANCZOS).crop(((side - w) // 2, 0, (side - w) // 2 + w, h))
        bg = bg.convert("RGBA")
        vig = Image.new("L", (w, h), 0)                                      # мягкая виньетка по краям
        ImageDraw.Draw(vig).ellipse((-w * 0.4, -h * 0.3, w * 1.4, h * 1.3), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(int(70 * s)))
        bg.alpha_composite(_colored(vig.point(lambda v: 255 - v), (0, 0, 0, 90)))
        # полупрозрачные «стёкла»: картинка под ними немного размыта, чтобы текст читался
        for box, r, tint in ((TOP, 20, 70), (TITLE, 18, 95), (PANEL, 18, 110)):
            pb = tuple(self.px(v) for v in box)
            pw, ph = pb[2] - pb[0], pb[3] - pb[1]
            mask = rr_mask(pw, ph, self.px(r))
            blurred = bg.crop(pb).filter(ImageFilter.GaussianBlur(10 * s))
            bg.paste(blurred, pb[:2], mask)
            bg.alpha_composite(glass(pw, ph, self.px(r), self.px(1), alpha=tint), pb[:2])
        self.canvas.create_image(0, 0, image=self.photo("bg", bg), anchor="nw")

    # ---------- режимы ----------
    def build_modes(self):
        self.mode_items = {}
        x0, y0, x1, y1 = TOP
        gap, pad = 4, 4
        widths = {key: w for key, _, w in MODES}
        total = sum(widths.values())
        scale = (x1 - x0 - 2 * pad - gap * (len(MODES) - 1)) / total
        x, hh = x0 + pad, y1 - y0 - 2 * pad
        for key, label, w in MODES:
            w = w * scale
            imgs = {"idle": Image.new("RGBA", (self.px(w), self.px(hh)), (0, 0, 0, 0)),
                    "hover": pill(self.px(w), self.px(hh), self.px(1), "hover"),
                    "active": pill(self.px(w), self.px(hh), self.px(1), "active")}
            imgs = {k: self.photo(f"mode_{key}_{k}", v) for k, v in imgs.items()}
            tag = f"mode_{key}"
            iid = self.canvas.create_image(self.px(x), self.px(y0 + pad), image=imgs["idle"],
                                           anchor="nw", tags=tag)
            tid = self.text(x + w / 2, y0 + pad + hh / 2, label, 10, TEXT, FONT_SEMI, tag=tag)
            self.mode_items[key] = (iid, tid, imgs, (x, y0 + pad, w, hh))
            self.bind(tag, lambda e, k=key: self.mode_hover(k, True),
                      lambda e, k=key: self.mode_hover(k, False), lambda e, k=key: self.set_mode(k))
            x += w + gap

    def mode_hover(self, key, on):
        self.hover_cursor(on)
        iid, _, imgs, _ = self.mode_items[key]
        if key != self.mode:
            self.canvas.itemconfig(iid, image=imgs["hover" if on else "idle"])

    def set_mode(self, key):
        if self.busy or key == self.mode:
            return
        self.mode = key
        self.apply_mode()
        self.play_glint(f"mode_{key}")

    def apply_mode(self, initial=False):
        for key, (iid, tid, imgs, _) in self.mode_items.items():
            active = key == self.mode
            self.canvas.itemconfig(iid, image=imgs["active" if active else "idle"])
            self.canvas.itemconfig(tid, fill=ON_GOLD if active else TEXT)
        title, sub = TEXTS[self.mode]
        self.canvas.itemconfig(self.title_id, text=title)
        self.canvas.itemconfig(self.sub_id, text=sub)
        for name in self.mode_rows:
            self.canvas.itemconfig(f"row_{name}", state="normal" if name == self.mode else "hidden")
        self.set_status(self.ready_text())
        if not initial:
            self.save_settings()

    # ---------- карточка «перетащите сюда» ----------
    def build_card(self):
        x0, y0, x1, y1 = ZONE
        dw, dh = self.px(x1 - x0), self.px(y1 - y0)
        self.dash_idle = self.photo("dash_idle", dashed_ring(dw, dh, self.px(26), 2.5 * self.s,
                                                             12 * self.s, 9 * self.s, (255, 255, 255, 200)))
        self.dash_hover = self.photo("dash_hover", dashed_ring(dw, dh, self.px(26), 4 * self.s,
                                                               12 * self.s, 9 * self.s, GOLD_TOP + (255,)))
        self.canvas.create_rectangle(self.px(x0), self.px(y0), self.px(x1), self.px(y1),
                                     outline="", fill="", tags="card")
        self.dash_id = self.canvas.create_image(self.px(x0), self.px(y0), image=self.dash_idle,
                                                anchor="nw", tags="card")
        tx0, ty0, tx1, _ = TITLE
        self.title_id = self.text(W / 2, ty0 + 32, "", 19, TEXT, FONT_SEMI, tag="card")
        self.sub_id = self.text(W / 2, ty0 + 60, "", 9, MUTED, tag="card", width=tx1 - tx0 - 30)
        self.bind("card", lambda e: self.card_hover(True), lambda e: self.card_hover(False),
                  lambda e: self.pick_files())

    def card_hover(self, on):
        self.hover_cursor(on)
        self.canvas.itemconfig(self.dash_id, image=self.dash_hover if on else self.dash_idle)

    # ---------- нижняя панель ----------
    def build_panel(self):
        _, y0, _, y1 = PANEL
        self.mode_rows = {"bedrock": [], "java": [], "desc": []}
        self.status_id = self.text(W / 2, y0 + 20, "", 10, MUTED, width=W - 80)
        ry = y0 + 54

        self.text(44, ry, "Версия Java", 10, MUTED, anchor="w", tag="row_java")
        self.ver_items = {}
        vx = 156
        for ver in porter.JAVA_VERSIONS:
            w = 18 + len(ver) * 7.2
            imgs = {k: self.photo(f"ver_{ver}_{k}", pill(self.px(w), self.px(26), self.px(1), k))
                    for k in ("idle", "hover", "active")}
            tag = f"ver_{ver}"
            iid = self.canvas.create_image(self.px(vx), self.px(ry - 13), image=imgs["idle"],
                                           anchor="nw", tags=(tag, "row_java"))
            tid = self.text(vx + w / 2, ry, ver, 9, TEXT, FONT_SEMI, tag=(tag, "row_java"))
            self.ver_items[ver] = (iid, tid, imgs)
            self.bind(tag, lambda e, v=ver: self.ver_hover(v, True),
                      lambda e, v=ver: self.ver_hover(v, False), lambda e, v=ver: self.set_ver(v))
            vx += w + 6
        self.refresh_versions()

        self.text(W / 2, ry, "Подойдёт .zip, .mcpack или распакованная папка", 10, MUTED, tag="row_bedrock")
        self.text(44, ry, "Повысить версию пака", 10, MUTED, anchor="w", tag="row_desc")
        self.toggle_imgs = {k: self.photo(f"tg_{k}", self.toggle_img(k)) for k in (True, False)}
        self.toggle_id = self.canvas.create_image(self.px(556), self.px(ry), anchor="e",
                                                  image=self.toggle_imgs[self.bump],
                                                  tags=("toggle", "row_desc"))
        self.bind("toggle", lambda e: self.hover_cursor(True), lambda e: self.hover_cursor(False),
                  lambda e: self.flip_bump())

    def toggle_img(self, on):
        w, h = self.px(44), self.px(24)
        base = pill(w, h, self.px(1), "active" if on else "idle")
        knob_img = knob(h - self.px(10), self.px(1))
        x = w - knob_img.width + self.px(1) if on else -self.px(1)
        base.alpha_composite(knob_img, (max(0, x), (h - knob_img.height) // 2))
        return base

    def ver_hover(self, ver, on):
        self.hover_cursor(on)
        if ver != self.java_ver:
            iid, _, imgs = self.ver_items[ver]
            self.canvas.itemconfig(iid, image=imgs["hover" if on else "idle"])

    def set_ver(self, ver):
        self.java_ver = ver
        self.refresh_versions()
        self.save_settings()
        self.set_status(self.ready_text())

    def refresh_versions(self):
        for v, (iid, tid, imgs) in self.ver_items.items():
            active = v == self.java_ver
            self.canvas.itemconfig(iid, image=imgs["active" if active else "idle"])
            self.canvas.itemconfig(tid, fill=ON_GOLD if active else TEXT)

    def flip_bump(self):
        self.bump = not self.bump
        self.canvas.itemconfig(self.toggle_id, image=self.toggle_imgs[self.bump])
        self.save_settings()

    # ---------- блик ----------
    def glint_specs(self):
        x0, y0, x1, y1 = TITLE
        specs = {"card": ((x0, y0, x1 - x0, y1 - y0), 18, 16, 70)}
        for key, (_, _, _, (x, y, w, h)) in self.mode_items.items():
            specs[f"mode_{key}"] = ((x, y, w, h), h / 2, 10, 110)
        return specs

    def _glint_pil(self, box, radius, frames, strength):
        _, _, w, h = box
        pw, ph = self.px(w), self.px(h)
        mask = rr_mask(pw, ph, self.px(radius))
        empty = Image.new("L", (pw, ph), 0)
        return [_colored(Image.composite(glint_band(pw, ph, i / (frames - 1), strength=strength),
                                         empty, mask), (255, 248, 230, 255)) for i in range(frames)]

    def warm_glints(self):
        """Считает кадры бликов в фоне (только Pillow, без Tk)."""
        for key, spec in self.glint_specs().items():
            self._glint_cache.setdefault(key, self._glint_pil(*spec))

    def play_glint(self, key, interval=16):
        """Короткий блик. В простое ничего не анимируется."""
        if key in self._anim:
            return
        (x, y, _, _), *_ = self.glint_specs()[key]
        if ("glint", key) not in self._imgs:
            frames = self._glint_cache.get(key) or self._glint_pil(*self.glint_specs()[key])
            self._imgs[("glint", key)] = [ImageTk.PhotoImage(f) for f in frames]
        seq = self._imgs[("glint", key)]
        iid = self.canvas.create_image(self.px(x), self.px(y), image=seq[0], anchor="nw",
                                       state="disabled")
        self._anim[key] = iid

        def step(i):
            if i >= len(seq):
                self.canvas.delete(iid)
                self._anim.pop(key, None)
                return
            self.canvas.itemconfig(iid, image=seq[i])
            self.root.after(interval, step, i + 1)

        step(0)

    # ---------- состояние ----------
    def set_status(self, s, color=MUTED):
        self.canvas.itemconfig(self.status_id, text=s, fill=color)

    def ready_text(self):
        if self.mode != "java":
            return "Готов к работе"
        jar = vanilla.find_jar(self.java_ver, self.mc_dir)
        if jar:
            return f"Ванильные текстуры: {jar.name}"
        return (f"Minecraft {self.java_ver} не найден в .minecraft — недостающие части "
                "интерфейса будут заглушками")

    def load_settings(self):
        try:
            return json.loads(vanilla.settings_path().read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def save_settings(self):
        try:
            path = vanilla.settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"mode": self.mode,
                                        "java_version": self.java_ver, "mc_dir": self.mc_dir,
                                        "bump": self.bump}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    # ---------- события ----------
    def on_enter(self, event):
        self.card_hover(True)
        return event.action

    def on_leave(self, event):
        self.card_hover(False)
        return event.action

    def on_drop(self, event):
        self.card_hover(False)
        self.run(self.root.tk.splitlist(event.data))
        return event.action

    def pick_files(self):
        if self.busy:
            return
        files = filedialog.askopenfilenames(
            title="Выберите пак", filetypes=[("Minecraft pack", "*.mcpack *.zip"), ("Все файлы", "*.*")])
        if files:
            self.run(files)

    # ---------- обработка ----------
    def run(self, paths):
        if self.busy:
            return
        self.busy = True
        self.save_settings()
        self.set_status("Обработка…", WORK_COL)
        mode, bump, ver = self.mode, self.bump, self.java_ver
        description = core.build_description(RGB, True)
        results, state = [], {"done": False}

        def work():
            for p in paths:
                try:
                    if mode == "desc":
                        results.append((Path(p), core.process(p, RGB, True, bump), None, None))
                    else:
                        res = porter.port_pack(p, mode, ver, description, self.mc_dir)
                        results.append((Path(p), res.dst, None, res))
                except Exception as e:  # noqa: BLE001
                    results.append((Path(p), None, str(e), None))
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self.poll(results, state, mode)

    def poll(self, results, state, mode):
        if not state["done"]:
            self.root.after(120, self.poll, results, state, mode)
            return
        self.busy = False
        ok = [r for r in results if r[1]]
        bad = [r for r in results if r[2]]
        if ok and not bad:
            if len(ok) > 1:
                msg = f"✓ Готово: обработано файлов — {len(ok)}"
            elif mode != "desc":
                res = ok[0][3]
                msg = f"✓ {res.direction}: {res.dst.name} · {res.converted} текстур"
            else:
                msg = f"✓ Готово: {ok[0][1].name}"
            self.set_status(msg, OK_COL)
            self.play_glint("card")
        elif bad:
            first = bad[0]
            msg = f"✗ {first[0].name}: {first[2]}"
            if ok:
                msg = f"Готово: {len(ok)}, ошибок: {len(bad)}. " + msg
            self.set_status(msg, ERR_COL)

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
