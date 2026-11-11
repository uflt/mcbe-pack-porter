# -*- coding: utf-8 -*-
"""
GUI @ufltRP: перетащи пак в окно.
Режимы: » Bedrock, » Java, только описание.

Всё рисуется заранее (Pillow) в реальном разрешении экрана. Текст — шрифтом Minecraft
(assets/minecraft.ttf): рисуется в родном размере 8 px без сглаживания и увеличивается блоками,
с тенью, как в игре.
Анимаций в простое нет: короткие блики проигрываются только при переключении режима и успехе.
"""
import colorsys
import json
import math
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

import core
import porter
import vanilla

# ---------------------------------------------------------------- оформление
W, H = 600, 636                       # логические пиксели (масштабируются под DPI)
GOLD_TOP, GOLD_BOT = (255, 214, 120), (214, 150, 38)
TEXT, MUTED = (244, 241, 234), (196, 191, 182)
ON_GOLD = (46, 30, 8)
OK_COL, ERR_COL, WORK_COL = (142, 227, 156), (255, 138, 128), (255, 210, 110)
LINK_COL = (138, 200, 255)
TG_URL, TG_LABEL = "https://t.me/ufltRP", "t.me/ufltRP"

TEXTS = {
    "bedrock": ("Перетащите Java-пак сюда", "Java .zip или папка » Bedrock .mcpack"),
    "java": ("Перетащите Bedrock-пак сюда", "Bedrock .mcpack » Java .zip"),
    "desc": ("Перетащите .mcpack сюда", "описание поменяется на ваше"),
}
HINT = "  ·  или нажмите на мопса"
MODES = (("bedrock", "» Bedrock", 128), ("java", "» Java", 112), ("desc", "Только описание", 168))
SWATCH = {"Золотой": (255, 170, 0), "Жёлтый": (255, 255, 85), "Красный": (255, 85, 85),
          "Зелёный": (85, 255, 85), "Голубой": (85, 255, 255), "Синий": (85, 85, 255),
          "Розовый": (255, 85, 255)}

ZONE = (20, 20, 580, 520)      # рамка поверх картинки
TOP = (90, 34, 510, 76)        # капсула с режимами
TITLE = (40, 424, 560, 504)    # полоса с надписью и статусом
PANEL = (20, 532, 580, 620)    # нижняя панель: цвет + тгк, настройки режима
ZONE_R = 26
SS = 3                         # сглаживание фигур: рисуем в 3 раза крупнее и уменьшаем

MC_FONT = "assets/minecraft.ttf"   # шрифт Minecraft: сетка 8 px (128 единиц на пиксель)
FALLBACK_FONTS = ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"]
_font_cache = {}


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


# ---------------------------------------------------------------- пиксельный текст
def _font():
    """Шрифт Minecraft в родном размере 8 px; если файла нет — системный шрифт."""
    if "f" not in _font_cache:
        for path in [str(resource_path(MC_FONT))] + FALLBACK_FONTS:
            try:
                _font_cache["f"] = ImageFont.truetype(path, 8 if path.endswith(MC_FONT.split("/")[-1]) else 9)
                break
            except OSError:
                continue
        else:
            _font_cache["f"] = ImageFont.load_default(8)
    return _font_cache["f"]


def pixel_text(text, big, k, color, bold=False, shadow=True):
    """
    Текст как в Minecraft: глиф 8 px без сглаживания, увеличенный блоками (k — размер «пикселя»,
    big — крупный заголовок, на один пиксель крупнее). Жирный — двойная прорисовка со сдвигом
    на пиксель, тень — затемнённый цвет со сдвигом вправо-вниз, как в игре.
    """
    font = _font()
    if sum(color[:3]) < 200:          # тёмный текст на светлой кнопке — без тени
        shadow = False
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    probe.fontmode = "1"
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font)
    w, h = x1 - x0 + 2 + bold, y1 - y0 + 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    offsets = [(0, 0), (1, 0)] if bold else [(0, 0)]
    if shadow:
        sh = tuple(c // 4 for c in color[:3]) + (230,)
        for dx, dy in offsets:
            d.text((1 + dx - x0, 1 + dy - y0), text, font=font, fill=sh)
    for dx, dy in offsets:
        d.text((dx - x0, dy - y0), text, font=font, fill=tuple(color[:3]) + (255,))
    scale = k + 1 if big else k
    return img.resize((w * scale, h * scale), Image.NEAREST)


def caret(k, color):
    """Пиксельная стрелочка вниз ▾ (5x3) для выпадающего списка."""
    img = Image.new("RGBA", (5, 3), (0, 0, 0, 0))
    for y, row in enumerate(["#####", ".###.", "..#.."]):
        for x, ch in enumerate(row):
            if ch == "#":
                img.putpixel((x, y), tuple(color[:3]) + (255,))
    return img.resize((5 * k, 3 * k), Image.NEAREST)


# ---------------------------------------------------------------- фигуры
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


def rounded_path(w, h, r, inset):
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset
    pts = []

    def arc(cx, cy, a0):
        for i in range(0, 91, 2):
            t = math.radians(a0 + i)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))

    arc(x1 - r, y0 + r, -90)
    arc(x1 - r, y1 - r, 0)
    arc(x0 + r, y1 - r, 90)
    arc(x0 + r, y0 + r, 180)
    pts.append(pts[0])
    return pts


def dash_mask(w, h, r, width, dash, gap, inset):
    """Пунктир со скруглёнными концами; штрихи повторяют изгиб углов, стык без «обрубка»."""
    big = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(big)
    lw = max(2, int(width * SS))
    pts = rounded_path(w * SS, h * SS, r * SS, inset * SS)
    per = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    n = max(4, round(per / ((dash + gap) * SS)))
    step = per / n
    on_len = step * dash / (dash + gap)

    def point_at(dist):
        for a, b in zip(pts, pts[1:]):
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            if dist <= seg:
                k = dist / seg if seg else 0
                return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
            dist -= seg
        return pts[-1]

    rad = lw / 2
    for i in range(n):
        sub = [point_at(i * step + on_len * t / 6) for t in range(7)]
        d.line(sub, fill=255, width=lw, joint="curve")
        for x, y in (sub[0], sub[-1]):
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=255)
    return big.resize((w, h), Image.LANCZOS)


def glass(w, h, r, s, tint=(16, 15, 20), alpha=150):
    """Стеклянная панель с объёмом: заливка, верхний блик, внутренняя тень, тонкая кромка."""
    body = vgrad(w, h, tint + (alpha,), tuple(max(0, c - 6) for c in tint) + (min(255, alpha + 30),))
    body.alpha_composite(vgrad(w, max(1, h // 3), (255, 255, 255, 26), (255, 255, 255, 0)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(body, (0, 0), rr_mask(w, h, r))
    out.alpha_composite(ring(w, h, r, s, (255, 255, 255, 34)))
    out.alpha_composite(ring(w - 2 * s, h - 2 * s, max(1, r - s), s, (0, 0, 0, 90)), (s, s))
    return out


def pill(w, h, s, kind):
    """Кнопка-«таблетка». kind: idle | hover | active."""
    r = h // 2
    if kind == "active":
        img = vgrad(w, h, GOLD_TOP + (255,), GOLD_BOT + (255,))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 90), (255, 255, 255, 0)))
        edge = (255, 240, 200, 160)
    elif kind == "hover":
        img = vgrad(w, h, (255, 255, 255, 70), (255, 255, 255, 34))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 40), (255, 255, 255, 0)))
        edge = (255, 230, 170, 150)
    else:
        img = vgrad(w, h, (255, 255, 255, 34), (255, 255, 255, 14))
        img.alpha_composite(vgrad(w, max(1, h // 2), (255, 255, 255, 30), (255, 255, 255, 0)))
        edge = (255, 255, 255, 70)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), rr_mask(w, h, r))
    out.alpha_composite(ring(w, h, r, s, edge))
    return out


def ball(d, s, color, selected=False, hover=False):
    """Круглый образец цвета с объёмом. color=None — радуга."""
    pad = 3 * s
    size = d + 2 * pad
    big = d * SS
    circle = Image.new("L", (big, big), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, big - 1, big - 1), fill=255)
    if color is None:
        n = 32
        small = Image.new("RGB", (n, n))
        px = small.load()
        for y in range(n):
            for x in range(n):
                hue = (math.atan2(y - n / 2, x - n / 2) / (2 * math.pi)) % 1.0
                r_, g_, b_ = colorsys.hsv_to_rgb(hue, 0.72, 1.0)
                px[x, y] = (int(r_ * 255), int(g_ * 255), int(b_ * 255))
        fill = small.resize((big, big), Image.BICUBIC).convert("RGBA")
        fill.alpha_composite(vgrad(big, big, (0, 0, 0, 0), (0, 0, 0, 70)))
    else:
        top = tuple(min(255, int(c * 1.08) + 18) for c in color)
        bot = tuple(int(c * 0.62) for c in color)
        fill = vgrad(big, big, top + (255,), bot + (255,))
    disc = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    disc.paste(fill, (0, 0), circle)
    hl = Image.new("L", (big, big), 0)
    ImageDraw.Draw(hl).ellipse((big * 0.2, big * 0.06, big * 0.8, big * 0.46), fill=105)
    hl = hl.filter(ImageFilter.GaussianBlur(big * 0.05))
    disc.alpha_composite(_colored(Image.composite(hl, Image.new("L", hl.size, 0), circle),
                                  (255, 255, 255, 255)))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(disc.resize((d, d), Image.LANCZOS), (pad, pad))
    if selected or hover:
        e = Image.new("L", (size * SS, size * SS), 0)
        ImageDraw.Draw(e).ellipse((SS, SS, size * SS - SS - 1, size * SS - SS - 1),
                                  outline=255, width=max(1, int(1.6 * s * SS)))
        col = (255, 255, 255, 255) if selected else (255, 255, 255, 110)
        out.alpha_composite(_colored(e.resize((size, size), Image.LANCZOS), col))
    return out


def plane_icon(size, color):
    """Пиксельный бумажный самолётик (значок Telegram), рисуется по сетке 8x8."""
    grid = ["......##",
            "....####",
            "..###.##",
            "####..#.",
            ".##..##.",
            "..#.#.#.",
            "..##..#.",
            "...#...."]
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == "#":
                img.putpixel((x, y), tuple(color) + (255,))
    return img.resize((size, size), Image.NEAREST)


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
    INTERACTIVE = ("mode_", "ver_", "pop_", "color_btn", "toggle", "link")

    def __init__(self):
        enable_dpi_awareness()
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.s = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.k = max(2, round(2 * self.s))           # размер «пикселя» шрифта
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
        self.color = st.get("color") if st.get("color") in core.COLORS else "Радуга"
        ver = st.get("java_version")
        self.java_ver = ver if ver in porter.JAVA_VERSIONS else porter.DEFAULT_VERSION
        self.bump = bool(st.get("bump", True))
        self._imgs = {}            # ссылки на PhotoImage, чтобы их не собрал сборщик мусора
        self._anim, self._glint_pil = {}, {}
        self.hovering = False

        self.canvas = tk.Canvas(self.root, width=self.px(W), height=self.px(H),
                                highlightthickness=0, bd=0, bg="#0e0d10")
        self.canvas.pack()
        self.build_static()
        self.build_zone()
        self.build_panel()
        self.build_modes()
        self.apply_mode(initial=True)

        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda e: self.set_hover(False, cursor=""))
        self.canvas.bind("<Button-1>", self.on_click)
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

    def label(self, key, x, y, text, size=8, color=TEXT, bold=False, anchor="center", tags=(),
              passive=False):
        """Пиксельная надпись (картинка на canvas). passive — не перехватывает мышь."""
        img = self.photo(("lbl", key), pixel_text(text, size >= 12, self.k, color, bold))
        return self.canvas.create_image(self.px(x), self.px(y), image=img, anchor=anchor,
                                        tags=tuple(tags) + (("passive",) if passive else ()),
                                        state="disabled" if passive else "normal")

    def set_label(self, key, iid, text, size=8, color=TEXT, bold=False):
        self.canvas.itemconfig(iid, image=self.photo(("lbl", key), pixel_text(text, size >= 12, self.k, color, bold)))

    def bind(self, tag, enter, leave, click):
        self.canvas.tag_bind(tag, "<Enter>", enter)
        self.canvas.tag_bind(tag, "<Leave>", leave)
        self.canvas.tag_bind(tag, "<Button-1>", click)

    def in_box(self, e, box):
        x0, y0, x1, y1 = box
        return self.px(x0) <= e.x <= self.px(x1) and self.px(y0) <= e.y <= self.px(y1)

    def over_interactive(self):
        return any(t.startswith(self.INTERACTIVE) for t in self.canvas.gettags("current"))

    # ---------- фон ----------
    def build_static(self):
        s = self.s
        w, h = self.px(W), self.px(H)
        bg = Image.open(resource_path("assets/background.jpg")).convert("RGB")
        side = max(w, h)
        bg = bg.resize((side, side), Image.LANCZOS).crop(((side - w) // 2, 0, (side - w) // 2 + w, h))
        bg = bg.convert("RGBA")
        vig = Image.new("L", (w, h), 0)
        ImageDraw.Draw(vig).ellipse((-w * 0.4, -h * 0.3, w * 1.4, h * 1.3), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(int(70 * s)))
        bg.alpha_composite(_colored(vig.point(lambda v: 255 - v), (0, 0, 0, 90)))
        for box, r, tint in ((TOP, 20, 70), (TITLE, 18, 95), (PANEL, 18, 110)):
            pb = tuple(self.px(v) for v in box)
            pw, ph = pb[2] - pb[0], pb[3] - pb[1]
            blurred = bg.crop(pb).filter(ImageFilter.GaussianBlur(10 * s))
            bg.paste(blurred, pb[:2], rr_mask(pw, ph, self.px(r)))
            bg.alpha_composite(glass(pw, ph, self.px(r), self.px(1), alpha=tint), pb[:2])
        self.canvas.create_image(0, 0, image=self.photo("bg", bg), anchor="nw")

    # ---------- рамка и надписи ----------
    def build_zone(self):
        x0, y0, x1, y1 = ZONE
        w, h, r, s = self.px(x1 - x0), self.px(y1 - y0), self.px(ZONE_R), self.s
        inset = 5 * s
        dash = dash_mask(w, h, r, 2.6 * s, 12 * s, 9 * s, inset)
        glow = Image.new("L", (w * SS, h * SS), 0)
        ImageDraw.Draw(glow).rounded_rectangle((inset * SS, inset * SS, (w - inset) * SS, (h - inset) * SS),
                                               r * SS, outline=255, width=int(3 * s * SS))
        glow = glow.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3 * s))
        self.glow_id = self.canvas.create_image(self.px(x0), self.px(y0), anchor="nw", state="hidden",
                                                image=self.photo("glow", _colored(glow, GOLD_TOP + (190,))))
        self.dash_id = self.canvas.create_image(self.px(x0), self.px(y0), anchor="nw",
                                                image=self.photo("dash", _colored(dash, (255, 255, 255, 225))))
        _, ty0, _, _ = TITLE
        self.title_id = self.label("title", W / 2, ty0 + 28, "", 12, TEXT)
        self.sub_id = self.label("sub", W / 2, ty0 + 58, "", 9, MUTED)

    def set_hover(self, on, cursor=None):
        if cursor is not None:
            self.canvas.config(cursor=cursor)
        if on != self.hovering:
            self.hovering = on
            self.canvas.itemconfig(self.glow_id, state="normal" if on else "hidden")

    def on_motion(self, e):
        interactive = self.over_interactive()
        in_zone = (self.in_box(e, ZONE) and not self.in_box(e, TOP) and not self.popup_open)
        self.set_hover(in_zone, cursor="hand2" if (interactive or in_zone) else "")

    def on_click(self, e):
        tags = self.canvas.gettags("current")
        if self.popup_open:
            if not any(t.startswith(("pop_", "color_btn")) for t in tags):
                self.toggle_popup(False)       # клик мимо списка — просто закрыть его
            return
        if not self.over_interactive() and self.in_box(e, ZONE) and not self.in_box(e, TOP):
            self.pick_files()

    # ---------- режимы ----------
    def build_modes(self):
        self.mode_items = {}
        x0, y0, x1, y1 = TOP
        gap, pad = 4, 4
        scale = (x1 - x0 - 2 * pad - gap * (len(MODES) - 1)) / sum(m[2] for m in MODES)
        x, hh = x0 + pad, y1 - y0 - 2 * pad
        for key, text, w in MODES:
            w = w * scale
            imgs = {"idle": Image.new("RGBA", (self.px(w), self.px(hh)), (0, 0, 0, 0)),
                    "hover": pill(self.px(w), self.px(hh), self.px(1), "hover"),
                    "active": pill(self.px(w), self.px(hh), self.px(1), "active")}
            imgs = {k: self.photo(f"mode_{key}_{k}", v) for k, v in imgs.items()}
            tag = f"mode_{key}"
            iid = self.canvas.create_image(self.px(x), self.px(y0 + pad), image=imgs["idle"],
                                           anchor="nw", tags=tag)
            lid = self.label(f"mode_{key}", x + w / 2, y0 + pad + hh / 2, text, 9, TEXT, passive=True)
            self.mode_items[key] = (iid, lid, imgs, (x, y0 + pad, w, hh), text)
            self.bind(tag, lambda e, k=key: self.mode_hover(k, True),
                      lambda e, k=key: self.mode_hover(k, False), lambda e, k=key: self.set_mode(k))
            x += w + gap

    def mode_hover(self, key, on):
        iid, _, imgs, _, _ = self.mode_items[key]
        if key != self.mode:
            self.canvas.itemconfig(iid, image=imgs["hover" if on else "idle"])

    def set_mode(self, key):
        if not self.busy and key != self.mode:
            self.mode = key
            self.apply_mode()
            self.play_glint(f"mode_{key}")

    def apply_mode(self, initial=False):
        for key, (iid, lid, imgs, _, text) in self.mode_items.items():
            active = key == self.mode
            self.canvas.itemconfig(iid, image=imgs["active" if active else "idle"])
            self.set_label(f"mode_{key}", lid, text, 9, ON_GOLD if active else TEXT)
        title, _ = TEXTS[self.mode]
        self.set_label("title", self.title_id, title, 12, TEXT)
        self.show_hint()
        for name in ("bedrock", "java", "desc"):
            self.canvas.itemconfig(f"row_{name}", state="normal" if name == self.mode else "hidden")
        for iid in self.canvas.find_withtag("passive"):
            if self.canvas.itemcget(iid, "state") != "hidden":
                self.canvas.itemconfig(iid, state="disabled")
        if getattr(self, "popup_open", False):
            self.toggle_popup(False)
        if not initial:
            self.save_settings()

    def show_hint(self):
        sub = TEXTS[self.mode][1]
        if self.mode == "java" and not vanilla.find_jar(self.java_ver, self.mc_dir):
            sub += f"  ·  {self.java_ver} нет в .minecraft"
        else:
            sub += HINT
        self.set_status(sub, MUTED)

    # ---------- нижняя панель ----------
    def build_panel(self):
        _, y0, _, _ = PANEL
        r1, r2 = y0 + 24, y0 + 62

        # цвет описания: кнопка с текущим цветом, по клику — список
        self.label("color_cap", 44, r1, "Цвет", 9, MUTED, anchor="w")
        self.color_btn_pos = (96, r1)
        self.color_btn = self.canvas.create_image(self.px(96), self.px(r1), anchor="w", tags="color_btn")
        self.bind("color_btn", lambda e: self.color_btn_hover(True), lambda e: self.color_btn_hover(False),
                  lambda e: self.toggle_popup())
        self.draw_color_btn(False)
        self.build_popup()

        # ссылка на тгк
        icon = plane_icon(self.px(12), LINK_COL)
        text = pixel_text(TG_LABEL, False, self.k, LINK_COL)
        gap = self.px(6)
        lw, lh = icon.width + gap + text.width + self.px(24), self.px(26)
        for kind in ("idle", "hover"):
            img = pill(lw, lh, self.px(1), kind)
            img.alpha_composite(icon, (self.px(12), (lh - icon.height) // 2))
            img.alpha_composite(text, (self.px(12) + icon.width + gap, (lh - text.height) // 2))
            self.photo(f"link_{kind}", img)
        self.link_id = self.canvas.create_image(self.px(556), self.px(r1), anchor="e",
                                                image=self._imgs["link_idle"], tags="link")
        self.bind("link", lambda e: self.canvas.itemconfig(self.link_id, image=self._imgs["link_hover"]),
                  lambda e: self.canvas.itemconfig(self.link_id, image=self._imgs["link_idle"]),
                  lambda e: webbrowser.open(TG_URL))

        # строка режима
        self.label("ver_cap", 44, r2, "Версия", 9, MUTED, anchor="w", tags=("row_java",))
        self.ver_items = {}
        vx = 120
        for ver in porter.JAVA_VERSIONS:
            w = 20 + len(ver) * 7.4
            imgs = {k: self.photo(f"ver_{ver}_{k}", pill(self.px(w), self.px(24), self.px(1), k))
                    for k in ("idle", "hover", "active")}
            tag = f"ver_{ver}"
            iid = self.canvas.create_image(self.px(vx), self.px(r2 - 12), image=imgs["idle"],
                                           anchor="nw", tags=(tag, "row_java"))
            lid = self.label(f"ver_{ver}", vx + w / 2, r2, ver, 9, TEXT, tags=("row_java",),
                             passive=True)
            self.ver_items[ver] = (iid, lid, imgs)
            self.bind(tag, lambda e, v=ver: self.ver_hover(v, True),
                      lambda e, v=ver: self.ver_hover(v, False), lambda e, v=ver: self.set_ver(v))
            vx += w + 6
        self.refresh_versions()

        self.label("bedrock_cap", W / 2, r2, "Подойдёт .zip, .mcpack или распакованная папка", 9, MUTED,
                   tags=("row_bedrock",))
        self.label("desc_cap", 44, r2, "Повысить версию пака", 9, MUTED, anchor="w", tags=("row_desc",))
        self.toggle_imgs = {k: self.photo(f"tg_{k}", self.toggle_img(k)) for k in (True, False)}
        self.toggle_id = self.canvas.create_image(self.px(556), self.px(r2), anchor="e",
                                                  image=self.toggle_imgs[self.bump],
                                                  tags=("toggle", "row_desc"))
        self.canvas.tag_bind("toggle", "<Button-1>", lambda e: self.flip_bump())

    def toggle_img(self, on):
        w, h = self.px(42), self.px(22)
        base = pill(w, h, self.px(1), "active" if on else "idle")
        knob = ball(h - self.px(8), self.px(1), (245, 242, 236))
        x = w - knob.width + self.px(1) if on else -self.px(1)
        base.alpha_composite(knob, (max(0, x), (h - knob.height) // 2))
        return base

    # ---------- выбор цвета ----------
    def ball_for(self, name, size, **kw):
        col = None if name == "Радуга" else SWATCH.get(name, (200, 200, 200))
        return ball(self.px(size), self.px(1), col, **kw)

    def draw_color_btn(self, hover):
        dot = self.ball_for(self.color, 12)
        text = pixel_text(self.color, False, self.k, TEXT)
        arrow = caret(self.k, MUTED)
        h = self.px(26)
        w = self.px(8) + dot.width + self.px(6) + text.width + self.px(10) + arrow.width + self.px(12)
        img = pill(w, h, self.px(1), "hover" if hover else "idle")
        x = self.px(8)
        img.alpha_composite(dot, (x, (h - dot.height) // 2))
        x += dot.width + self.px(6)
        img.alpha_composite(text, (x, (h - text.height) // 2))
        x += text.width + self.px(10)
        img.alpha_composite(arrow, (x, (h - arrow.height) // 2 + self.px(1)))
        self.canvas.itemconfig(self.color_btn, image=self.photo("color_btn", img))

    def color_btn_hover(self, on):
        self.draw_color_btn(on or self.popup_open)

    def build_popup(self):
        """Список цветов над кнопкой. Рисуется один раз, потом только показывается/прячется."""
        self.popup_open = False
        bx, by = self.color_btn_pos
        row_h, pw, pad = 26, 168, 6
        names = list(core.COLORS)
        ph = pad * 2 + row_h * len(names)
        x0, y1 = bx - 4, by - 18
        y0 = y1 - ph
        self.popup_box = (x0, y0, x0 + pw, y1)
        # фон: тёмное стекло с размытой картинкой не нужно — достаточно плотной панели
        bg = glass(self.px(pw), self.px(ph), self.px(14), self.px(1), alpha=215)
        self.canvas.create_image(self.px(x0), self.px(y0), image=self.photo("popup_bg", bg), anchor="nw",
                                 tags=("popup", "pop_bg"), state="hidden")
        self.pop_rows = {}
        hover_img = self.photo("pop_hover", pill(self.px(pw - 2 * pad), self.px(row_h - 2), self.px(1), "hover"))
        sel_img = self.photo("pop_sel", pill(self.px(pw - 2 * pad), self.px(row_h - 2), self.px(1), "idle"))
        for i, name in enumerate(names):
            ry = y0 + pad + i * row_h
            tag = f"pop_{i}"
            hl = self.canvas.create_image(self.px(x0 + pad), self.px(ry + 1), anchor="nw", image=sel_img,
                                          tags=(tag, "popup"), state="hidden")
            dot = self.photo(f"pop_dot_{i}", self.ball_for(name, 12))
            self.canvas.create_image(self.px(x0 + pad + 8), self.px(ry + row_h / 2), anchor="w", image=dot,
                                     tags=("popup", "passive_pop"), state="hidden")
            self.label(f"pop_{i}", x0 + pad + 34, ry + row_h / 2, name, 9, TEXT, anchor="w",
                       tags=("popup", "passive_pop"))
            self.pop_rows[name] = (hl, tag)
            self.bind(tag, lambda e, n=name: self.pop_hover(n, True),
                      lambda e, n=name: self.pop_hover(n, False), lambda e, n=name: self.pick_color(n))
        self.pop_imgs = {"hover": hover_img, "sel": sel_img}
        self.canvas.itemconfig("popup", state="hidden")

    def toggle_popup(self, show=None):
        show = (not self.popup_open) if show is None else show
        self.popup_open = show
        if show:
            self.canvas.itemconfig("popup", state="normal")
            self.canvas.itemconfig("passive_pop", state="disabled")
            self.refresh_popup()
            self.canvas.tag_raise("popup")
        else:
            self.canvas.itemconfig("popup", state="hidden")
        self.draw_color_btn(show)

    def refresh_popup(self, hover=None):
        """Подложка строки: выбранный цвет — светлее, наведение — с золотой кромкой, остальные — пусто."""
        for name, (hl, _) in self.pop_rows.items():
            if name == hover:
                self.canvas.itemconfig(hl, image=self.pop_imgs["hover"], state="normal")
            elif name == self.color:
                self.canvas.itemconfig(hl, image=self.pop_imgs["sel"], state="normal")
            else:
                self.canvas.itemconfig(hl, image=self._blank_row(), state="normal")

    def _blank_row(self):
        if "pop_blank" not in self._imgs:
            w, h = self._imgs["pop_sel"].width(), self._imgs["pop_sel"].height()
            self.photo("pop_blank", Image.new("RGBA", (w, h), (0, 0, 0, 1)))   # почти прозрачная, ловит мышь
        return self._imgs["pop_blank"]

    def pop_hover(self, name, on):
        if self.popup_open:
            self.refresh_popup(name if on else None)

    def pick_color(self, name):
        self.color = name
        self.save_settings()
        self.toggle_popup(False)

    def ver_hover(self, ver, on):
        if ver != self.java_ver:
            iid, _, imgs = self.ver_items[ver]
            self.canvas.itemconfig(iid, image=imgs["hover" if on else "idle"])

    def set_ver(self, ver):
        self.java_ver = ver
        self.refresh_versions()
        self.save_settings()
        self.show_hint()

    def refresh_versions(self):
        for v, (iid, lid, imgs) in self.ver_items.items():
            active = v == self.java_ver
            self.canvas.itemconfig(iid, image=imgs["active" if active else "idle"])
            self.set_label(f"ver_{v}", lid, v, 9, ON_GOLD if active else TEXT)

    def flip_bump(self):
        self.bump = not self.bump
        self.canvas.itemconfig(self.toggle_id, image=self.toggle_imgs[self.bump])
        self.save_settings()

    # ---------- блики (коротко и только по событию) ----------
    def glint_specs(self):
        x0, y0, x1, y1 = TITLE
        specs = {"title": ((x0, y0, x1 - x0, y1 - y0), 18, 14, 60)}
        for key, (_, _, _, box, _) in self.mode_items.items():
            specs[f"mode_{key}"] = (box, box[3] / 2, 10, 110)
        return specs

    def _make_glint(self, box, radius, frames, strength):
        _, _, w, h = box
        pw, ph = self.px(w), self.px(h)
        mask = rr_mask(pw, ph, self.px(radius))
        empty = Image.new("L", (pw, ph), 0)
        return [_colored(Image.composite(glint_band(pw, ph, i / (frames - 1), strength=strength),
                                         empty, mask), (255, 248, 230, 255)) for i in range(frames)]

    def warm_glints(self):
        for key, spec in self.glint_specs().items():
            self._glint_pil.setdefault(key, self._make_glint(*spec))

    def play_glint(self, key, interval=18):
        if key in self._anim:
            return
        spec = self.glint_specs()[key]
        if ("glint", key) not in self._imgs:
            frames = self._glint_pil.get(key) or self._make_glint(*spec)
            self._imgs[("glint", key)] = [ImageTk.PhotoImage(f) for f in frames]
        seq = self._imgs[("glint", key)]
        x, y = spec[0][:2]
        iid = self.canvas.create_image(self.px(x), self.px(y), image=seq[0], anchor="nw", state="disabled")
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
    def set_status(self, text, color=MUTED):
        if len(text) > 70:
            text = text[:67] + "…"
        self.set_label("sub", self.sub_id, text, 9, color)

    def load_settings(self):
        try:
            return json.loads(vanilla.settings_path().read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def save_settings(self):
        try:
            path = vanilla.settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"mode": self.mode, "color": self.color,
                                        "java_version": self.java_ver, "mc_dir": self.mc_dir,
                                        "bump": self.bump}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    # ---------- события ----------
    def on_enter(self, event):
        self.set_hover(True)
        return event.action

    def on_leave(self, event):
        self.set_hover(False)
        return event.action

    def on_drop(self, event):
        self.set_hover(False)
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
        mode, color, bump, ver = self.mode, self.color, self.bump, self.java_ver
        description = core.build_description(color, True)
        results, state = [], {"done": False}

        def work():
            for p in paths:
                try:
                    if mode == "desc":
                        results.append((Path(p), core.process(p, color, True, bump), None, None))
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
                msg = f"Готово: обработано файлов — {len(ok)}"
            elif mode != "desc":
                msg = f"Готово: {ok[0][1].name} · {ok[0][3].converted} текстур"
            else:
                msg = f"Готово: {ok[0][1].name}"
            self.set_status(msg, OK_COL)
            self.play_glint("title")
        elif bad:
            first = bad[0]
            msg = f"{first[0].name}: {first[2]}"
            if ok:
                msg = f"Готово {len(ok)}, ошибок {len(bad)}. " + msg
            self.set_status(msg, ERR_COL)

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
