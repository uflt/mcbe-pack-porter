# -*- coding: utf-8 -*-
"""
Сложные части переноса Java <-> Bedrock:
  интерфейс (HUD, хотбар, инвентарь, иконки эффектов), частицы, скайбокс, зелья.

Везде, где Java хранит много картинок в одном атласе (icons.png, widgets.png, inventory.png,
particles.png), основа берётся из ванильного .jar (vanilla.py), а поверх кладутся текстуры пака.
Если .jar не найден — недостающие части рисуются простыми заглушками.
"""
import io
import json
import colorsys

from PIL import Image

NEAREST = Image.NEAREST
TEX = "assets/minecraft/textures/"


# ================================================================ утилиты
def open_img(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGBA")


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")
    return buf.getvalue()


def blank_png(w=16, h=16) -> bytes:
    return to_png(Image.new("RGBA", (w, h), (0, 0, 0, 0)))


def fit(img, w, h):
    return img if img.size == (w, h) else img.resize((max(1, w), max(1, h)), NEAREST)


def jdump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def nineslice(piece, w, h, border, out_border):
    """Растягивает картинку-рамку (углы border px) до w x h, углы в результате out_border px."""
    pw, ph = piece.size
    b = max(1, min(border, pw // 2, ph // 2))
    ob = max(1, min(out_border, w // 2, h // 2))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xs_s, ys_s = [0, b, pw - b, pw], [0, b, ph - b, ph]
    xs_d, ys_d = [0, ob, w - ob, w], [0, ob, h - ob, h]
    for i in range(3):
        for j in range(3):
            src = piece.crop((xs_s[i], ys_s[j], xs_s[i + 1], ys_s[j + 1]))
            dw, dh = xs_d[i + 1] - xs_d[i], ys_d[j + 1] - ys_d[j]
            if dw > 0 and dh > 0 and src.width > 0 and src.height > 0:
                out.paste(src.resize((dw, dh), NEAREST), (xs_d[i], ys_d[j]))
    return out


# ================================================================ заглушки (если нет ни пака, ни ванили)
HEART = ["..##.##..", ".#######.", "#########", "#########", "#########",
         ".#######.", "..#####..", "...###...", "....#...."]
ARMOR = [".##...##.", "#########", "#########", ".#######.", ".#######.",
         ".#######.", ".#######.", "..#####..", "........."]
ROUND = ["...###...", ".#######.", ".#######.", "#########", "#########",
         "#########", ".#######.", ".#######.", "...###..."]


def _shape(rows, fill, outline, half=False):
    h, w = len(rows), len(rows[0])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != "#" or (half and x > w // 2):
                continue
            edge = any(not (0 <= x + dx < w and 0 <= y + dy < h and rows[y + dy][x + dx] == "#")
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            col = outline if edge else fill
            if col:
                px[x, y] = col
    return img


def _bar(w, h, fill):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    img.paste(Image.new("RGBA", (w - 2, h - 2), fill), (1, 1))
    return img


def _slot(w=18, h=18):
    img = Image.new("RGBA", (w, h), (139, 139, 139, 255))
    img.paste(Image.new("RGBA", (w - 1, 1), (55, 55, 55, 255)), (0, 0))
    img.paste(Image.new("RGBA", (1, h - 1), (55, 55, 55, 255)), (0, 0))
    img.paste(Image.new("RGBA", (w - 1, 1), (255, 255, 255, 255)), (1, h - 1))
    img.paste(Image.new("RGBA", (1, h - 1), (255, 255, 255, 255)), (w - 1, 1))
    return img


def _button(w, h, fill, edge):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    img.paste(Image.new("RGBA", (w - 2, h - 2), edge), (1, 1))
    img.paste(Image.new("RGBA", (w - 4, h - 4), fill), (2, 2))
    return img


def _crosshair():
    img = Image.new("RGBA", (15, 15), (0, 0, 0, 0))
    for i in range(3, 12):
        img.putpixel((7, i), (255, 255, 255, 255))
        img.putpixel((i, 7), (255, 255, 255, 255))
    return img


def _arrow():
    img = Image.new("RGBA", (22, 15), (0, 0, 0, 0))
    for y in range(5, 10):
        for x in range(0, 14):
            img.putpixel((x, y), (139, 139, 139, 255))
    for i in range(8):
        for y in range(i, 15 - i):
            img.putpixel((14 + i, y), (139, 139, 139, 255))
    return img


BLACK, RED, DARK = (0, 0, 0, 255), (220, 30, 30, 255), (50, 50, 50, 255)
FALLBACK = {
    "crosshair": _crosshair,
    "heart_container": lambda: _shape(HEART, DARK, BLACK),
    "heart_container_blink": lambda: _shape(HEART, DARK, (255, 255, 255, 255)),
    "heart_full": lambda: _shape(HEART, RED, None),
    "heart_half": lambda: _shape(HEART, RED, None, half=True),
    "heart_full_blink": lambda: _shape(HEART, (255, 120, 120, 255), None),
    "heart_half_blink": lambda: _shape(HEART, (255, 120, 120, 255), None, half=True),
    "heart_poison_full": lambda: _shape(HEART, (140, 150, 30, 255), None),
    "heart_poison_half": lambda: _shape(HEART, (140, 150, 30, 255), None, half=True),
    "heart_wither_full": lambda: _shape(HEART, (40, 40, 40, 255), None),
    "heart_wither_half": lambda: _shape(HEART, (40, 40, 40, 255), None, half=True),
    "heart_absorb_full": lambda: _shape(HEART, (230, 200, 40, 255), None),
    "heart_absorb_half": lambda: _shape(HEART, (230, 200, 40, 255), None, half=True),
    "armor_empty": lambda: _shape(ARMOR, None, (60, 60, 60, 255)),
    "armor_half": lambda: _shape(ARMOR, (210, 210, 210, 255), BLACK, half=True),
    "armor_full": lambda: _shape(ARMOR, (210, 210, 210, 255), BLACK),
    "air": lambda: _shape(ROUND, (160, 210, 255, 255), (50, 90, 170, 255)),
    "air_pop": lambda: _shape(ROUND, None, (160, 210, 255, 255)),
    "food_empty": lambda: _shape(ROUND, DARK, BLACK),
    "food_full": lambda: _shape(ROUND, (180, 110, 50, 255), BLACK),
    "food_half": lambda: _shape(ROUND, (180, 110, 50, 255), BLACK, half=True),
    "food_hunger_empty": lambda: _shape(ROUND, (40, 60, 30, 255), BLACK),
    "food_hunger_full": lambda: _shape(ROUND, (110, 150, 60, 255), BLACK),
    "food_hunger_half": lambda: _shape(ROUND, (110, 150, 60, 255), BLACK, half=True),
    "xp_empty": lambda: _bar(182, 5, (25, 50, 25, 255)),
    "xp_full": lambda: _bar(182, 5, (128, 255, 32, 255)),
    "hotbar": lambda: _hotbar_fallback(),
    "hotbar_selection": lambda: _selection_fallback(),
}


def _hotbar_fallback():
    img = Image.new("RGBA", (182, 22), (0, 0, 0, 255))
    for i in range(9):
        img.paste(_slot(20, 20), (1 + i * 20, 1))
    return img


def _selection_fallback():
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for i in range(24):
        for t in (0, 1, 22, 23):
            img.putpixel((i, t), (255, 255, 255, 255))
            img.putpixel((t, i), (255, 255, 255, 255))
    return img


# ================================================================ HUD
# ключ -> (атлас 1.7.10–1.20.1, (u, v, w, h), спрайт 1.20.2+, варианты имён в Bedrock textures/ui)
HUD = {
    "crosshair": ("icons", (0, 0, 15, 15), "hud/crosshair", ["cross_hair"]),
    "heart_container": ("icons", (16, 0, 9, 9), "hud/heart/container",
                        ["heart_background", "heart_container", "heart_empty"]),
    "heart_container_blink": ("icons", (25, 0, 9, 9), "hud/heart/container_blinking",
                              ["heart_background_blink", "heart_blink_background"]),
    "heart_full": ("icons", (52, 0, 9, 9), "hud/heart/full", ["heart", "heart_full"]),
    "heart_half": ("icons", (61, 0, 9, 9), "hud/heart/half", ["heart_half"]),
    "heart_full_blink": ("icons", (70, 0, 9, 9), "hud/heart/full_blinking",
                         ["heart_blink", "heart_flash"]),
    "heart_half_blink": ("icons", (79, 0, 9, 9), "hud/heart/half_blinking",
                         ["heart_half_blink", "heart_half_flash"]),
    "heart_poison_full": ("icons", (88, 0, 9, 9), "hud/heart/poisoned_full",
                          ["poison_heart", "heart_poison"]),
    "heart_poison_half": ("icons", (97, 0, 9, 9), "hud/heart/poisoned_half",
                          ["poison_heart_half", "heart_poison_half"]),
    "heart_wither_full": ("icons", (124, 0, 9, 9), "hud/heart/withered_full",
                          ["wither_heart", "heart_wither"]),
    "heart_wither_half": ("icons", (133, 0, 9, 9), "hud/heart/withered_half",
                          ["wither_heart_half", "heart_wither_half"]),
    "heart_absorb_full": ("icons", (160, 0, 9, 9), "hud/heart/absorbing_full",
                          ["absorption_heart", "heart_absorption"]),
    "heart_absorb_half": ("icons", (169, 0, 9, 9), "hud/heart/absorbing_half",
                          ["absorption_heart_half", "heart_absorption_half"]),
    "armor_empty": ("icons", (16, 9, 9, 9), "hud/armor_empty", ["armor_empty"]),
    "armor_half": ("icons", (25, 9, 9, 9), "hud/armor_half", ["armor_half"]),
    "armor_full": ("icons", (34, 9, 9, 9), "hud/armor_full", ["armor_full"]),
    "air": ("icons", (16, 18, 9, 9), "hud/air", ["bubble"]),
    "air_pop": ("icons", (25, 18, 9, 9), "hud/air_bursting", ["bubble_pop"]),
    "food_empty": ("icons", (16, 27, 9, 9), "hud/food_empty",
                   ["hunger_background", "food_empty", "food_background"]),
    "food_full": ("icons", (52, 27, 9, 9), "hud/food_full", ["hunger_full", "food_full"]),
    "food_half": ("icons", (61, 27, 9, 9), "hud/food_half", ["hunger_half", "food_half"]),
    "food_hunger_empty": ("icons", (133, 27, 9, 9), "hud/food_empty_hunger",
                          ["hunger_effect_background", "hunger_effect_empty"]),
    "food_hunger_full": ("icons", (88, 27, 9, 9), "hud/food_full_hunger", ["hunger_effect_full"]),
    "food_hunger_half": ("icons", (97, 27, 9, 9), "hud/food_half_hunger", ["hunger_effect_half"]),
    "xp_empty": ("icons", (0, 64, 182, 5), "hud/experience_bar_background",
                 ["experiencebarempty", "experience_bar_empty", "experience_bar_empty_blue"]),
    "xp_full": ("icons", (0, 69, 182, 5), "hud/experience_bar_progress",
                ["experiencebarfull", "experience_bar_full", "experience_bar_full_white"]),
    "hotbar": ("widgets", (0, 0, 182, 22), "hud/hotbar", []),
    "hotbar_selection": ("widgets", (0, 22, 24, 24), "hud/hotbar_selection",
                         ["selected_hotbar_slot"]),
}
HOTBAR_NAMES = ["hotbar_start_cap"] + [f"hotbar_{i}" for i in range(9)] + ["hotbar_end_cap"]

# кнопки в widgets.png (если нет ванильного .jar — рисуем заглушки, иначе меню без кнопок)
WIDGET_BUTTONS = [((0, 46, 200, 20), (45, 45, 45, 255), (70, 70, 70, 255)),
                  ((0, 66, 200, 20), (111, 111, 111, 255), (170, 170, 170, 255)),
                  ((0, 86, 200, 20), (126, 136, 191, 255), (190, 200, 255, 255)),
                  ((0, 106, 20, 20), (111, 111, 111, 255), (170, 170, 170, 255)),
                  ((0, 126, 20, 20), (126, 136, 191, 255), (190, 200, 255, 255)),
                  ((0, 146, 20, 20), (45, 45, 45, 255), (70, 70, 70, 255))]

# пустые слоты брони: имя в Bedrock textures/ui/
SLOT_ICONS = ["helmet", "chestplate", "leggings", "boots", "shield"]

# иконки эффектов: Bedrock textures/ui/<имя>, id в Java (mob_effect/), клетка в inventory.png 1.7–1.8
EFFECTS = [
    (["speed_effect"], "speed", (0, 0)),
    (["slowness_effect"], "slowness", (1, 0)),
    (["haste_effect"], "haste", (2, 0)),
    (["mining_fatigue_effect"], "mining_fatigue", (3, 0)),
    (["strength_effect"], "strength", (4, 0)),
    (["weakness_effect"], "weakness", (5, 0)),
    (["poison_effect"], "poison", (6, 0)),
    (["regeneration_effect"], "regeneration", (7, 0)),
    (["invisibility_effect"], "invisibility", (0, 1)),
    (["hunger_effect"], "hunger", (1, 1)),
    (["jump_boost_effect", "jump_effect"], "jump_boost", (2, 1)),
    (["nausea_effect"], "nausea", (3, 1)),
    (["night_vision_effect"], "night_vision", (4, 1)),
    (["blindness_effect"], "blindness", (5, 1)),
    (["resistance_effect"], "resistance", (6, 1)),
    (["fire_resistance_effect"], "fire_resistance", (7, 1)),
    (["water_breathing_effect"], "water_breathing", (0, 2)),
    (["wither_effect"], "wither", (1, 2)),
    (["absorption_effect"], "absorption", (2, 2)),
    (["health_boost_effect"], "health_boost", (7, 2)),
]

INV_W, INV_H = 176, 166


def _inv_layout(legacy: bool):
    """Позиции слотов инвентаря игрока (левый верхний угол рамки 18x18)."""
    slots = [(7, 7 + 18 * i) for i in range(4)]                                  # броня
    slots += [(7 + 18 * c, 83 + 18 * r) for r in range(3) for c in range(9)]     # рюкзак
    slots += [(7 + 18 * c, 141) for c in range(9)]                               # хотбар
    if legacy:   # 1.7–1.8: крафт 2x2 у (88,26), результат (144,36)
        slots += [(87 + 18 * c, 25 + 18 * r) for r in range(2) for c in range(2)]
        result, arrow = (143, 35), (124, 37)
    else:        # 1.12+: крафт (98,18), результат (154,28), левая рука (77,62)
        slots += [(97 + 18 * c, 17 + 18 * r) for r in range(2) for c in range(2)]
        slots += [(76, 61)]
        result, arrow = (153, 27), (134, 29)
    return slots, result, arrow


def _classify_heart(name):
    """Определяет вид сердца по имени файла (heart_half_blink, poison_heart и т.п.)."""
    n = name.lower()
    if "heart" not in n or any(w in n for w in ("hardcore", "frozen", "freeze", "horse", "mount",
                                                 "vehicle", "boss", "health_boost")):
        return None
    if any(w in n for w in ("background", "container", "empty", "outline", "border", "_bg")):
        return "heart_container_blink" if ("blink" in n or "flash" in n) else "heart_container"
    kind = ("poison" if "poison" in n else "wither" if "wither" in n
            else "absorb" if "absor" in n or "gold" in n else "")
    half = "half" in n
    blink = "blink" in n or "flash" in n
    if kind:
        return f"heart_{kind}_{'half' if half else 'full'}"
    if blink:
        return "heart_half_blink" if half else "heart_full_blink"
    return "heart_half" if half else "heart_full"


def _classify_hud(name):
    """Сердца, еда, броня, воздух, опыт — по смыслу имени файла."""
    base = name.lower().rsplit("/", 1)[-1]
    if base.endswith("_effect") or base in ("hunger_effect", "absorption_effect"):
        return None          # это иконки эффектов, не HUD
    heart = _classify_heart(base)
    if heart:
        return heart
    if any(w in base for w in ("hunger", "food", "drumstick", "meat")):
        if any(w in base for w in ("horse", "mount", "saturation_bar")):
            return None
        hunger = "effect" in base or "poison" in base or "rotten" in base
        if any(w in base for w in ("background", "empty", "container", "outline", "_bg")):
            return "food_hunger_empty" if hunger else "food_empty"
        part = "half" if "half" in base else "full"
        return f"food_hunger_{part}" if hunger else f"food_{part}"
    if "armor" in base and "slot" not in base and "stand" not in base and "trim" not in base:
        if any(w in base for w in ("empty", "background", "container", "outline", "_bg")):
            return "armor_empty"
        return "armor_half" if "half" in base else "armor_full"
    if "bubble" in base or "oxygen" in base or base in ("air", "air_full"):
        return "air_pop" if any(w in base for w in ("pop", "burst", "empty")) else "air"
    if ("experience" in base or base.startswith("xp")) and "nub" not in base:
        if "empty" in base or "background" in base:
            return "xp_empty"
        if "full" in base or "progress" in base:
            return "xp_full"
    return None


def find_hud(ui_names, ui):
    """Все элементы HUD, которые удалось опознать по именам файлов в textures/ui."""
    found = {}
    # короткие имена важнее (heart лучше heart_new_v2), файлы в корне ui — важнее подпапок
    for name in sorted(ui_names, key=lambda n: (n.count("/"), len(n))):
        key = _classify_hud(name)
        if key and key not in found:
            img = ui(name)
            if img is not None:
                found[key] = img
    return found


def _ui_lookup(ui, names):
    for n in names:
        img = ui(n)
        if img is not None:
            return img
    return None


def _scale_of(pieces):
    best = 1
    for key, img in pieces.items():
        w = HUD[key][1][2] if key in HUD else 18
        best = max(best, round(img.width / w))
    return best


def _base_atlas(vanilla, rel, s, size=256):
    """Ванильный атлас, увеличенный до масштаба s, или пустой."""
    data = vanilla.read(TEX + rel) if vanilla else None
    if data:
        img = open_img(data)
        k = img.width / size
        if round(k) != s:
            img = img.resize((size * s, int(img.height / k) * s), NEAREST)
        return img, True
    return Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0)), False


def _compose_hotbar(parts):
    imgs = [parts[n] for n in HOTBAR_NAMES]
    h = max(i.height for i in imgs)
    imgs = [i if i.height == h else fit(i, max(1, round(i.width * h / i.height)), h) for i in imgs]
    out = Image.new("RGBA", (sum(i.width for i in imgs), h), (0, 0, 0, 0))
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width
    return out


def _slice_hotbar(img):
    w, h = img.size
    s = max(1, w // 182)
    parts = {"hotbar_start_cap": img.crop((0, 0, s, h)),
             "hotbar_end_cap": img.crop((w - s, 0, w, h))}
    for i in range(9):
        x0 = s + i * 20 * s
        parts[f"hotbar_{i}"] = img.crop((x0, 0, x0 + 20 * s, h))
    return parts


def _draw_inventory(canvas, s, legacy, panel, slot, arrow):
    """Рисует фон инвентаря (176x166) из кусочков Bedrock."""
    pw = panel.width
    piece_scale = max(1, round(pw / 16))
    bg = nineslice(panel, INV_W * s, INV_H * s, 4 * piece_scale, 4 * s)
    canvas.paste(bg, (0, 0))
    slots, result, arrow_pos = _inv_layout(legacy)
    sl = fit(slot if slot is not None else _slot(), 18 * s, 18 * s)
    for x, y in slots + [result]:
        canvas.alpha_composite(sl, (x * s, y * s))
    # окно с моделью игрока
    box = Image.new("RGBA", (51 * s, 72 * s), (0, 0, 0, 255))
    canvas.paste(box, (25 * s, 7 * s))
    ar = arrow if arrow is not None else _arrow()
    k = 15 / ar.height
    canvas.alpha_composite(fit(ar, max(1, round(ar.width * k)) * s, 15 * s),
                           (arrow_pos[0] * s, arrow_pos[1] * s))


def _from_bedrock_atlas(gui, pieces):
    """Старые Bedrock-паки: textures/gui/icons.png (раскладка как у Java) и gui/gui.png (хотбар)."""
    for atlas_name, keys in (("icons", [k for k in HUD if HUD[k][0] == "icons"]),
                             ("gui", ["hotbar", "hotbar_selection"])):
        data = gui(atlas_name)
        if not data:
            continue
        atlas = open_img(data)
        s = max(1, atlas.width // 256)
        for k in keys:
            if k in pieces:
                continue
            u, v, w, h = HUD[k][1]
            if (v + h) * s > atlas.height:
                continue
            img = atlas.crop((u * s, v * s, (u + w) * s, (v + h) * s))
            if img.getbbox() is not None:
                pieces[k] = img


def hud_to_java(ui, cfg, vanilla, res, ui_names=(), gui=None):
    """
    Интерфейс Bedrock (textures/ui) -> Java.
    ui(name) -> Image|None. cfg: настройки версии. vanilla: Vanilla|None. res: PortResult.
    ui_names — все имена файлов в textures/ui; gui(name) -> bytes|None для textures/gui/<name>.png.
    """
    out = {}
    legacy, sprites, fmt = cfg.get("legacy", False), cfg["fmt"] >= 18, cfg["fmt"]

    pieces = {}
    for key, (_, _, _, names) in HUD.items():
        img = _ui_lookup(ui, names)
        if img is not None:
            pieces[key] = img
    for key, img in find_hud(ui_names, ui).items():
        pieces.setdefault(key, img)
    if gui:
        _from_bedrock_atlas(gui, pieces)
    for label, prefix in (("Сердца", "heart_"), ("Еда", "food_")):
        got = sorted(k for k in pieces if k.startswith(prefix))
        if got:
            res.notes.append(f"{label}: перенесено " + ", ".join(got) + ".")
        else:
            res.notes.append(f"{label}: в паке не найдены.")
    if not any(k.startswith(("heart_", "food_")) for k in pieces):
        res.notes.append("Все файлы в textures/ui (пришлите этот список, если сердца/еда не перенеслись): "
                         + (", ".join(ui_names) if ui_names else "папки textures/ui нет") + ".")
    parts = {n: ui(n) for n in HOTBAR_NAMES}
    if all(p is not None for p in parts.values()):
        pieces["hotbar"] = _compose_hotbar(parts)
    elif any(p is not None for p in parts.values()):
        res.notes.append("Хотбар не собран: в паке есть не все его части.")

    if pieces:
        s = _scale_of(pieces)
        if sprites:
            for key, img in pieces.items():
                out[f"{TEX}gui/sprites/{HUD[key][2]}.png"] = to_png(img)
        else:
            for atlas in ("icons", "widgets"):
                keys = [k for k in HUD if HUD[k][0] == atlas]
                if not any(k in pieces for k in keys):
                    continue
                canvas, from_jar = _base_atlas(vanilla, f"gui/{atlas}.png", s)
                for k in keys:
                    u, v, w, h = HUD[k][1]
                    img = pieces.get(k)
                    if img is None and not from_jar:
                        img = FALLBACK[k]()
                    if img is not None:
                        canvas.paste(fit(img, w * s, h * s), (u * s, v * s))
                if atlas == "widgets" and not from_jar:
                    for (u, v, w, h), fill, edge in WIDGET_BUTTONS:
                        canvas.paste(fit(_button(w, h, fill, edge), w * s, h * s), (u * s, v * s))
                if not from_jar:
                    res.notes.append(f"gui/{atlas}.png собран без ванильного .jar: недостающие части "
                                     "нарисованы заглушками, часть элементов может пропасть. "
                                     "Укажите папку .minecraft с этой версией, чтобы было 1-в-1.")
                out[f"{TEX}gui/{atlas}.png"] = to_png(canvas)
        res.converted += len(pieces)
        res.renamed += len(pieces)

    # пустые слоты брони
    for name in SLOT_ICONS:
        img = ui(f"empty_armor_slot_{name}")
        if img is None or (name == "shield" and legacy):
            continue
        if sprites:
            path = f"{TEX}gui/sprites/container/slot/{name}.png"
        elif legacy:
            path = f"{TEX}items/empty_armor_slot_{name}.png"
        else:
            path = f"{TEX}item/empty_armor_slot_{name}.png"
        out[path] = to_png(img)
        res.converted += 1

    # иконки эффектов
    effects = {}
    for names, jid, cell in EFFECTS:
        img = _ui_lookup(ui, names)
        if img is not None:
            effects[jid] = (img, cell)
    if effects and not legacy:
        for jid, (img, _) in effects.items():
            out[f"{TEX}mob_effect/{jid}.png"] = to_png(img)
        res.converted += len(effects)

    # инвентарь
    panel = _ui_lookup(ui, ["dialog_background_opaque", "dialog_background_opaque_override"])
    slot = _ui_lookup(ui, ["cell_image", "cell_image_normal", "item_cell"])
    arrow = _ui_lookup(ui, ["arrow_large", "arrow_icon", "crafting_arrow"])
    need_legacy_effects = legacy and effects
    if panel is not None or need_legacy_effects:
        s = max(1, round(panel.width / 16)) if panel is not None else 1
        if slot is not None:
            s = max(s, round(slot.width / 18))
        canvas, from_jar = _base_atlas(vanilla, "gui/container/inventory.png", s)
        if panel is not None:
            _draw_inventory(canvas, s, legacy, panel, slot, arrow)
            res.converted += 1
            res.renamed += 1
        if need_legacy_effects:
            for jid, (img, (c, r)) in effects.items():
                canvas.paste(fit(img, 18 * s, 18 * s), (c * 18 * s, (198 + r * 18) * s))
            res.converted += len(effects)
        if panel is not None or from_jar:
            out[f"{TEX}gui/container/inventory.png"] = to_png(canvas)
            if not from_jar and (legacy or fmt < 18):
                res.notes.append("inventory.png собран без ванильного .jar: фон эффектов и иконки "
                                 "эффектов, которых нет в паке, будут пустыми.")
        elif need_legacy_effects:
            res.notes.append("Иконки эффектов не перенесены: для этой версии они в inventory.png, "
                             "а ванильный .jar не найден.")
    elif slot is not None:
        res.notes.append("Инвентарь не собран: в паке есть слот, но нет фона окна "
                         "(dialog_background_opaque).")
    return out


def hud_from_java(java, res):
    """
    Интерфейс Java -> Bedrock. java(rel_from_textures) -> bytes|None.
    Понимает и спрайты 1.20.2+, и атласы icons.png/widgets.png (1.7–1.20.1).
    """
    out = {}
    atlases = {}
    for name in ("icons", "widgets"):
        data = java(f"gui/{name}.png")
        if data:
            img = open_img(data)
            atlases[name] = (img, max(1, img.width // 256))

    for key, (atlas, (u, v, w, h), sprite, names) in HUD.items():
        img = None
        data = java(f"gui/sprites/{sprite}.png")
        if data:
            img = open_img(data)
        elif atlas in atlases:
            a, s = atlases[atlas]
            img = a.crop((u * s, v * s, (u + w) * s, (v + h) * s))
            if img.getbbox() is None:   # пустая клетка
                img = None
        if img is None:
            continue
        if key == "hotbar":
            for n, p in _slice_hotbar(img).items():
                out[f"textures/ui/{n}.png"] = to_png(p)
        elif names:
            out[f"textures/ui/{names[0]}.png"] = to_png(img)
        else:
            continue
        res.converted += 1
        res.renamed += 1

    for name in SLOT_ICONS:
        for rel in (f"gui/sprites/container/slot/{name}.png", f"item/empty_armor_slot_{name}.png",
                    f"items/empty_armor_slot_{name}.png"):
            data = java(rel)
            if data:
                out[f"textures/ui/empty_armor_slot_{name}.png"] = data
                res.converted += 1
                break

    inv = java("gui/container/inventory.png")
    inv_img = open_img(inv) if inv else None
    inv_s = max(1, inv_img.width // 256) if inv_img else 1
    for names, jid, (c, r) in EFFECTS:
        data = java(f"mob_effect/{jid}.png")
        if data:
            out[f"textures/ui/{names[0]}.png"] = data
            res.converted += 1
        elif inv_img is not None and inv_img.height >= 256 * inv_s:
            cell = inv_img.crop((c * 18 * inv_s, (198 + r * 18) * inv_s,
                                 (c + 1) * 18 * inv_s, (198 + (r + 1) * 18) * inv_s))
            if cell.getbbox():
                out[f"textures/ui/{names[0]}.png"] = to_png(cell)
                res.converted += 1

    if inv_img is not None:
        s = inv_s
        bg = inv_img.crop((0, 0, INV_W * s, INV_H * s))
        b = 4 * s
        panel = Image.new("RGBA", (16 * s, 16 * s), (0, 0, 0, 0))
        W, H = bg.size
        cx, cy = W // 2, H // 2
        regions = [  # (src box, dst pos) — углы, края и центр
            ((0, 0, b, b), (0, 0)), ((W - b, 0, W, b), (12 * s, 0)),
            ((0, H - b, b, H), (0, 12 * s)), ((W - b, H - b, W, H), (12 * s, 12 * s)),
            ((cx - 4 * s, 0, cx + 4 * s, b), (b, 0)), ((cx - 4 * s, H - b, cx + 4 * s, H), (b, 12 * s)),
            ((0, cy - 4 * s, b, cy + 4 * s), (0, b)), ((W - b, cy - 4 * s, W, cy + 4 * s), (12 * s, b)),
        ]
        for box, pos in regions:
            panel.paste(bg.crop(box), pos)
        fill = bg.getpixel((b + 2 * s, 75 * s))   # фон между слотами
        panel.paste(Image.new("RGBA", (8 * s, 8 * s), fill), (b, b))
        out["textures/ui/dialog_background_opaque.png"] = to_png(panel)
        out["textures/ui/dialog_background_opaque.json"] = jdump(
            {"nineslice_size": 4, "base_size": [16, 16]})
        out["textures/ui/cell_image.png"] = to_png(bg.crop((7 * s, 83 * s, 25 * s, 101 * s)))
        res.converted += 1
        res.renamed += 1
    return out


# ================================================================ частицы
# имя спрайта Java 1.14+ -> номер клетки в атласе particles.png (Java 1.7–1.13 и Bedrock, сетка 16x16)
PARTICLE_INDEX = {f"generic_{i}": i for i in range(8)}
PARTICLE_INDEX.update({f"splash_{i}": 19 + i for i in range(4)})
PARTICLE_INDEX.update({
    "bubble": 32, "flame": 48, "lava": 49, "note": 64, "critical_hit": 65, "enchanted_hit": 66,
    "heart": 80, "angry": 81, "glint": 82, "drip_hang": 112, "drip_fall": 113, "drip_land": 114,
})
PARTICLE_INDEX.update({f"effect_{i}": 128 + i for i in range(8)})
PARTICLE_INDEX.update({f"spell_{i}": 144 + i for i in range(8)})
PARTICLE_INDEX.update({f"spark_{i}": 160 + i for i in range(8)})
PARTICLE_INDEX.update({f"sga_{chr(97 + k)}": 225 + k for k in range(26)})
ENCHANTED_HIT = 66   # синие звёздочки при ударе зачарованным оружием (острота и т.п.)


def _cell_box(idx, cell):
    return ((idx % 16) * cell, (idx // 16) * cell, (idx % 16 + 1) * cell, (idx // 16 + 1) * cell)


def _clear_cell(atlas, idx):
    cell = atlas.width // 16
    atlas.paste(Image.new("RGBA", (cell, cell), (0, 0, 0, 0)), _cell_box(idx, cell)[:2])


def particles_to_java(atlas_bytes, cfg, vanilla, res):
    """particles.png из Bedrock -> Java. Плюс убирает «сплеш» удара и частицы остроты."""
    out = {}
    legacy = cfg.get("legacy", False)
    if legacy:
        data = atlas_bytes or (vanilla.read(TEX + "particle/particles.png") if vanilla else None)
        if data:
            atlas = open_img(data)
            _clear_cell(atlas, ENCHANTED_HIT)
            out[f"{TEX}particle/particles.png"] = to_png(atlas)
            if atlas_bytes:
                res.converted += 1
        else:
            res.notes.append("Частицы остроты не убраны: в этой версии они в общем атласе "
                             "particles.png, а его нет ни в паке, ни в ванильном .jar.")
        return out

    if atlas_bytes:
        atlas = open_img(atlas_bytes)
        cell = atlas.width // 16
        n = 0
        for name, idx in PARTICLE_INDEX.items():
            if (idx // 16 + 1) * cell > atlas.height:
                continue
            sprite = atlas.crop(_cell_box(idx, cell))
            if sprite.getbbox() is not None:
                out[f"{TEX}particle/{name}.png"] = to_png(sprite)
                n += 1
        res.converted += n
        res.renamed += n
    for i in range(8):                       # «сплеш» от удара (атака по площади)
        out[f"{TEX}particle/sweep_{i}.png"] = blank_png(32, 32)
    out[f"{TEX}particle/enchanted_hit.png"] = blank_png(8, 8)
    return out


def particles_to_bedrock(java, legacy_base, res):
    """
    Частицы Java -> Bedrock (общий атлас textures/particle/particles.png).
    java(rel) -> bytes|None; legacy_base — particles.png из старого ванильного .jar (основа атласа).
    """
    src_atlas = java("particle/particles.png")
    sprites = {n: java(f"particle/{n}.png") for n in PARTICLE_INDEX}
    sprites = {n: d for n, d in sprites.items() if d}
    if src_atlas:
        atlas = open_img(src_atlas)
        res.converted += 1
    elif legacy_base:
        atlas = open_img(legacy_base)
        cell = atlas.width // 16
        for name, data in sprites.items():
            atlas.paste(fit(open_img(data), cell, cell), _cell_box(PARTICLE_INDEX[name], cell)[:2])
        res.converted += len(sprites)
        res.renamed += len(sprites)
    else:
        if sprites:
            res.notes.append("Частицы не перенесены: в Bedrock это общий атлас, для сборки нужен "
                             "ванильный .jar 1.8.9 (или другой версии до 1.13) в папке .minecraft.")
        else:
            res.notes.append("Частицы остроты не убраны: для этого нужен ванильный .jar 1.8.9 "
                             "(или другой версии до 1.13) в папке .minecraft.")
        return {}
    _clear_cell(atlas, ENCHANTED_HIT)
    return {"textures/particle/particles.png": to_png(atlas)}


# ================================================================ скайбокс
# Bedrock: cubemap_0..5 = перед(север), право(восток), зад(юг), лево(запад), верх, низ.
# OptiFine: одна картинка 3x2:  [низ | верх | юг] / [запад | север | восток]
SKY_LAYOUT = [(5, 0, 0), (4, 1, 0), (2, 2, 0), (3, 0, 1), (0, 1, 1), (1, 2, 1)]  # (cubemap, col, row)


def sky_to_java(faces, cfg):
    """faces: {0..5: Image}. Возвращает файлы OptiFine-скайбокса (OptiFine, Skyboxify, Nuit Interop)."""
    f = max(img.width for img in faces.values())
    atlas = Image.new("RGBA", (3 * f, 2 * f), (0, 0, 0, 0))
    for idx, col, row in SKY_LAYOUT:
        if idx in faces:
            atlas.paste(fit(faces[idx], f, f), (col * f, row * f))
    folder = "mcpatcher" if cfg.get("legacy") else "optifine"
    base = f"assets/minecraft/{folder}/sky/world0"
    props = "\n".join([
        "# Скайбокс перенесён из Bedrock (@ufltRP)",
        "source=./sky1.png" if cfg.get("legacy") else f"source=minecraft:{folder}/sky/world0/sky1.png",
        "blend=alpha",
        "rotate=false",
        "speed=0",
        "weather=clear rain thunder",
    ]) + "\n"
    return {f"{base}/sky1.png": to_png(atlas), f"{base}/sky1.properties": props.encode("utf-8")}


def _props(text):
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def sky_to_bedrock(files, read):
    """Ищет OptiFine/MCPatcher скайбокс (world0) в Java-паке и режет его на cubemap_0..5."""
    for folder in ("assets/minecraft/optifine/sky/world0/", "assets/minecraft/mcpatcher/sky/world0/"):
        props = sorted((n for n in files if n.startswith(folder) and n.endswith(".properties")
                        and n[len(folder):].startswith("sky")),
                       key=lambda n: int("".join(ch for ch in n[len(folder):] if ch.isdigit()) or 0))
        lower = {n.lower(): n for n in files}
        candidates = []
        for p in props:
            src = _props(read(p).decode("utf-8", "ignore")).get("source", "").replace("\\", "/")
            name = p[:-len(".properties")] + ".png"
            if src:
                src = src.split(":", 1)[-1] if ":" in src else src
                if src.startswith("./"):
                    name = folder + src[2:]
                elif "/" not in src:
                    name = folder + src
                elif src.startswith("assets/"):
                    name = src
                else:
                    name = "assets/minecraft/" + src
                if not name.lower().endswith(".png"):
                    name += ".png"
            candidates.append(name)
        candidates += [n for n in files if n.startswith(folder) and n.lower().endswith(".png")]
        best, best_score = None, -1
        for name in dict.fromkeys(candidates):
            real = lower.get(name.lower())
            if not real:
                continue
            img = open_img(read(real))
            if img.width < 3 or abs(img.width * 2 - img.height * 3) > img.width // 10:
                continue   # не 3x2
            # основной слой — самый непрозрачный и светлый (а не звёзды/облака поверх)
            small = img.resize((48, 32))
            score = sum(a * (r + g + b) for r, g, b, a in small.getdata())
            if score > best_score:
                best, best_score = img, score
        if best is not None:
            f = best.width // 3
            out = {}
            for idx, col, row in SKY_LAYOUT:
                face = best.crop((col * f, row * f, (col + 1) * f, (row + 1) * f))
                bg = Image.new("RGBA", face.size, (0, 0, 0, 255))   # в Bedrock грань непрозрачная
                out[f"textures/environment/overworld_cubemap/cubemap_{idx}.png"] = to_png(
                    Image.alpha_composite(bg, face))
            return out
    return _sky_from_json(files, read)


FACE_INDEX = {"north": 0, "east": 1, "south": 2, "west": 3, "top": 4, "up": 4,
              "bottom": 5, "down": 5}


def _resolve_id(ident, files_lower):
    """'ns:path' или путь -> реальное имя файла в паке."""
    ident = ident.replace("\\", "/")
    ns, _, path = ident.partition(":") if ":" in ident else ("minecraft", "", ident)
    if not path.lower().endswith(".png"):
        path += ".png"
    for cand in (f"assets/{ns}/{path}", f"assets/{ns}/textures/{path}", path):
        real = files_lower.get(cand.lower())
        if real:
            return real
    return None


def _cubemap(faces):
    out = {}
    for idx, img in faces.items():
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        out[f"textures/environment/overworld_cubemap/cubemap_{idx}.png"] = to_png(
            Image.alpha_composite(bg, img))
    return out


def _sky_from_json(files, read):
    """FabricSkyBoxes / Nuit (JSON): шесть текстур граней или одна картинка 3x2."""
    lower = {n.lower(): n for n in files}
    jsons = [n for n in files if n.lower().endswith(".json") and n.startswith("assets/")
             and ("sky" in n.lower().split("/")[2] if len(n.split("/")) > 3 else False)]
    for name in sorted(jsons):
        try:
            data = json.loads(read(name).decode("utf-8-sig"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        tex = data.get("textures")
        if isinstance(tex, dict):
            faces = {}
            for k, v in tex.items():
                idx = FACE_INDEX.get(str(k).lower())
                real = _resolve_id(v, lower) if idx is not None and isinstance(v, str) else None
                if real:
                    faces[idx] = open_img(read(real))
            if len(faces) == 6:
                f = max(i.width for i in faces.values())
                return _cubemap({k: fit(v, f, f) for k, v in faces.items()})
        single = data.get("texture") or data.get("source")
        if isinstance(single, str):
            real = _resolve_id(single, lower)
            if real:
                img = open_img(read(real))
                if abs(img.width * 2 - img.height * 3) <= img.width // 10:
                    f = img.width // 3
                    return _cubemap({idx: img.crop((c * f, r * f, (c + 1) * f, (r + 1) * f))
                                     for idx, c, r in SKY_LAYOUT})
    return {}


# ================================================================ зелья
WATER = (56, 93, 198)
# эффект (как в именах Bedrock) -> цвет жидкости
EFFECT_COLORS = {
    "moveSpeed": 0x7CAFC6, "moveSlowdown": 0x5A6C81, "digSpeed": 0xD9C043, "digSlowdown": 0x4A4217,
    "damageBoost": 0x932423, "heal": 0xF82423, "harm": 0x430A09, "jump": 0x22FF4C,
    "confusion": 0x551D4A, "regeneration": 0xCD5CAB, "resistance": 0x99453A,
    "fireResistance": 0xE49A3A, "waterBreathing": 0x2E5299, "invisibility": 0x7F8392,
    "blindness": 0x1F1F23, "nightVision": 0x1F1FA1, "hunger": 0x587653, "weakness": 0x484D48,
    "poison": 0x4E9331, "wither": 0x352A27, "healthBoost": 0xF87D23, "absorption": 0x2552A5,
    "saturation": 0xF82423, "levitation": 0xCEFFFF, "slowFall": 0xF7F8E0, "turtleMaster": 0x755E7E,
}
_EFFECT_LOWER = {k.lower(): k for k in EFFECT_COLORS}
# тип: (имя в Java, имя в Bedrock, префикс вариантов в Bedrock, старое имя Java 1.7–1.8)
POTION_TYPES = [
    ("potion", "potion_bottle_drinkable", "potion_bottle_", "potion_bottle_drinkable"),
    ("splash_potion", "potion_bottle_splash", "potion_bottle_splash_", "potion_bottle_splash"),
    ("lingering_potion", "potion_bottle_lingering", "potion_bottle_lingering_", None),
]


def is_potion_name(stem: str) -> bool:
    s = stem.lower()
    return s.startswith("potion_bottle_") and s != "potion_bottle_empty"


def _is_outline(px):
    r, g, b, a = px
    _, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return vv < 0.28 or (ss < 0.18 and vv < 0.9)   # тёмный контур, серое/белое стекло, блик


def _lum(px):
    return 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]


def _split_potion(base, variants):
    """
    Цельная бутылка Bedrock -> (стекло с дыркой, серая жидкость, которую окрашивает игра).
    Жидкость — пиксели, цвет которых различается у разных эффектов. Базовая бутылка может
    быть нарисована пустой: жидкость тогда берётся из вариантов.
    """
    w, h = base.size
    bp = base.load()
    vps = [fit(v, w, h).load() for v in variants]
    mask = set()
    if len(vps) >= 2:
        for y in range(h):
            for x in range(w):
                cols = [vp[x, y] for vp in vps if vp[x, y][3] > 16]
                if len(cols) < 2 or all(_is_outline(c) for c in cols):
                    continue
                spread = sum(max(c[i] for c in cols) - min(c[i] for c in cols) for i in range(3))
                if spread > 90:
                    mask.add((x, y))
    elif len(vps) == 1:
        vp = vps[0]
        for y in range(h):
            for x in range(w):
                a, b = bp[x, y], vp[x, y]
                if b[3] > 16 and not _is_outline(b) and (
                        a[3] < 16 or sum(abs(a[i] - b[i]) for i in range(3)) > 60):
                    mask.add((x, y))
    if not mask:   # вариантов нет — ищем «синюю воду» в самой бутылке
        for y in range(h):
            for x in range(w):
                px = bp[x, y]
                if px[3] and not _is_outline(px):
                    hh, ss, _ = colorsys.rgb_to_hsv(px[0] / 255, px[1] / 255, px[2] / 255)
                    if 0.53 <= hh <= 0.72 and ss > 0.3:
                        mask.add((x, y))
        vps = [bp]

    bottle = base.copy()
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if mask:
        # яркость жидкости: среднее по эффектам, нормированное к самому светлому пикселю
        tops = [max(_lum(vp[p]) for p in mask) or 1 for vp in vps]
        btp, op = bottle.load(), overlay.load()
        for p in mask:
            vals = [_lum(vp[p]) / t for vp, t in zip(vps, tops) if vp[p][3] > 16]
            g = min(255, round(sum(vals) / len(vals) * 255)) if vals else 255
            alpha = max(vp[p][3] for vp in vps)
            op[p] = (g, g, g, alpha)
            btp[p] = (0, 0, 0, 0)
    return bottle, overlay


def _tint(overlay, rgb):
    r, g, b, a = overlay.split()
    return Image.merge("RGBA", (r.point(lambda v: v * rgb[0] // 255),
                                g.point(lambda v: v * rgb[1] // 255),
                                b.point(lambda v: v * rgb[2] // 255), a))


def potions_to_java(items, cfg, res):
    """items: {имя_файла_Bedrock_без_расширения: Image} (только зелья). -> файлы Java."""
    out = {}
    legacy, fmt = cfg.get("legacy", False), cfg["fmt"]
    by_lower = {k.lower(): v for k, v in items.items()}
    overlays = {}
    for jname, bname, prefix, old in POTION_TYPES:
        variants = [img for k, img in sorted(by_lower.items())
                    if k.startswith(prefix.lower()) and k[len(prefix):] in _EFFECT_LOWER]
        base = by_lower.get(bname.lower())
        if base is None:
            if not variants:
                continue
            base = variants[0]
        bottle, overlay = _split_potion(base, variants)
        overlays[jname] = overlay
        if legacy:
            if old:
                out[f"{TEX}items/{old}.png"] = to_png(bottle)
        else:
            out[f"{TEX}item/{jname}.png"] = to_png(bottle)
            out[f"{TEX}item/{jname}_overlay.png"] = to_png(overlay)
            out[f"assets/minecraft/models/item/{jname}.json"] = jdump({
                "parent": "minecraft:item/generated",
                "textures": {"layer0": f"minecraft:item/{jname}_overlay",
                             "layer1": f"minecraft:item/{jname}"}})
            if fmt >= 46:
                out[f"assets/minecraft/items/{jname}.json"] = jdump({"model": {
                    "type": "minecraft:model", "model": f"minecraft:item/{jname}",
                    "tints": [{"type": "minecraft:potion", "default": -13083194}]}})
        res.converted += 1
        res.renamed += 1
    if overlays:
        shared = overlays.get("splash_potion") or overlays.get("potion") or next(iter(overlays.values()))
        out[f"{TEX}{'items' if legacy else 'item'}/potion_overlay.png"] = to_png(shared)
        if legacy and len(overlays) > 1:
            res.notes.append("Зелья 1.7–1.8: жидкость у всех бутылок общая (взята от взрывного), "
                             "у обычных зелий она может не совпасть с формой бутылки.")
    return out


def potions_to_bedrock(java, res):
    """Бутылка + жидкость Java -> цельные текстуры Bedrock под каждый эффект."""
    out = {}
    shared = java("item/potion_overlay.png") or java("items/potion_overlay.png")
    for jname, bname, prefix, old in POTION_TYPES:
        data = java(f"item/{jname}.png") or (java(f"items/{old}.png") if old else None)
        if not data:
            continue
        bottle = open_img(data)
        ov = java(f"item/{jname}_overlay.png") or shared
        overlay = fit(open_img(ov), *bottle.size) if ov else None

        def make(rgb):
            if overlay is None:
                return to_png(bottle)
            return to_png(Image.alpha_composite(_tint(overlay, rgb), bottle))

        out[f"textures/items/{bname}.png"] = make(WATER)
        for eff, col in EFFECT_COLORS.items():
            rgb = ((col >> 16) & 255, (col >> 8) & 255, col & 255)
            out[f"textures/items/{prefix}{eff}.png"] = make(rgb)
        res.converted += 1
        res.renamed += 1
    return out
