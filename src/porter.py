# -*- coding: utf-8 -*-
"""
Портирование ресурс-паков Java <-> Bedrock (текстуры и метаданные).

Переносится: блоки, предметы, мобы (entity), солнце/луна/облака, цвета травы и листвы,
броня, зелья, HUD (прицел, хотбар, сердца, еда, броня, воздух, опыт), иконка и описание.
НЕ переносится: звуки, инвентарь/контейнеры, меню, частицы, модели, шрифты, шейдеры,
кубическое небо (skybox: в обычной Java его нет).

Принимает .zip / .mcpack или распакованную папку. Направление задаётся явно (target).
"""
import io
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import mappings as mp

# Целевые версии Java:
#   fmt    - pack_format (ресурспак)
#   ranged - писать min_format/max_format (так с 1.21.9)
#   legacy - старая раскладка до 1.13: textures/blocks, textures/items (имена как в Bedrock)
#   armor  - "old": cloth_1/chain_1/iron_1...   "layer": leather_layer_1/chainmail_layer_1...
JAVA_VERSIONS = {
    "1.7.10": {"fmt": 1, "legacy": True, "armor": "old"},
    "1.8.9": {"fmt": 1, "legacy": True, "armor": "layer"},
    "1.16.5": {"fmt": 6},
    "1.21.4": {"fmt": 46},
    "1.21.11": {"fmt": 75, "ranged": True},
    "26.3": {"fmt": 97, "ranged": True},
}
DEFAULT_VERSION = "1.21.4"
HUD_FORMAT = 18         # с этого формата (1.20.2) HUD — отдельные спрайты, раньше общий атлас
EQUIPMENT_FORMAT = 42   # с этого формата броня лежит в entity/equipment/...
ITEM_DEFS_FORMAT = 46   # с этого формата (1.21.4) есть assets/minecraft/items/*.json

TEX = "assets/minecraft/textures/"
HUD = "gui/sprites/hud/"
WATER = (56, 93, 198)   # цвет воды в бутылке (стандартный тон жидкости)
HOTBAR_NAMES = ["hotbar_start_cap"] + [f"hotbar_{i}" for i in range(9)] + ["hotbar_end_cap"]

EDITION_NAMES = {"java": "Java", "bedrock": "Bedrock"}


@dataclass
class PortResult:
    dst: Path
    direction: str
    converted: int = 0                       # сколько текстур перенесено
    renamed: int = 0                         # из них переименовано/собрано по таблице
    cropped: int = 0                         # анимации, сохранённые первым кадром
    passthrough: list = field(default_factory=list)   # перенесены под тем же именем
    skipped: dict = field(default_factory=dict)       # папка -> число файлов
    errors: list = field(default_factory=list)        # (файл, причина)
    notes: list = field(default_factory=list)
    report: Path = None

    def skip(self, rel: str, key: str = None):
        if key is None:
            parts = rel.split("/")
            n = 4 if rel.startswith(TEX) else 3
            key = "/".join(parts[:n]) if len(parts) > n else "/".join(parts[:-1]) or rel
        self.skipped[key] = self.skipped.get(key, 0) + 1


# ---------------------------------------------------------------- чтение пака
class Source:
    """Единый интерфейс к zip/mcpack или папке. Определяет edition и корень пака."""

    def __init__(self, path):
        path = Path(path)
        self.path = path
        self._zip = None
        readers = {}
        if path.is_dir():
            self.name = path.name
            for p in path.rglob("*"):
                if p.is_file():
                    readers[p.relative_to(path).as_posix()] = (lambda p=p: p.read_bytes())
        elif path.is_file() and zipfile.is_zipfile(path):
            self.name = path.stem
            self._zip = zipfile.ZipFile(path)
            for n in self._zip.namelist():
                if not n.endswith("/"):
                    readers[n] = (lambda n=n: self._zip.read(n))
        else:
            raise ValueError("Нужен .zip/.mcpack или папка с паком")
        self._rebase(readers)

    def _rebase(self, readers):
        def find(marker):
            c = [n for n in readers if n == marker or n.endswith("/" + marker)]
            return min(c, key=lambda n: n.count("/")) if c else None

        java, bedrock = find("pack.mcmeta"), find("manifest.json")
        if not java and not bedrock:
            raise ValueError("Не найден pack.mcmeta (Java) или manifest.json (Bedrock) — "
                             "это точно ресурс-пак?")
        if java and (not bedrock or java.count("/") <= bedrock.count("/")):
            self.edition, marker = "java", java
        else:
            self.edition, marker = "bedrock", bedrock
        prefix = marker[: -len(marker.split("/")[-1])]  # папка, где лежит маркер
        self.files = {n[len(prefix):]: r for n, r in readers.items() if n.startswith(prefix)}

    def read(self, rel):
        return self.files[rel]()

    def close(self):
        if self._zip:
            self._zip.close()


# ---------------------------------------------------------------- утилиты
def _load_json_loose(raw: bytes):
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r"(?m)^\s*//.*$", "", text)  # комментарии //
        return json.loads(text)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")
    return buf.getvalue()


def _open(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGBA")


def _image(data: bytes, ext: str, first_frame: bool = False):
    """Возвращает (png-байты, обрезано_до_первого_кадра). TGA конвертирует в PNG."""
    ext = ext.lower()
    if ext == ".png" and not first_frame:
        return data, False
    img = Image.open(io.BytesIO(data))
    img.load()
    cropped = False
    if first_frame and img.width and img.height > img.width and img.height % img.width == 0:
        img = img.crop((0, 0, img.width, img.width))  # вертикальная лента -> 1-й кадр
        cropped = True
    elif ext == ".png":
        return data, False
    return _png(img), cropped


def _write_zip(dst: Path, files: dict):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


def _write_report(res: PortResult):
    lines = [f"Порт пака: {res.direction}", f"Результат: {res.dst.name}", "",
             f"Текстур перенесено: {res.converted}",
             f"  переименовано/собрано по таблице: {res.renamed}",
             f"  перенесено под тем же именем: {len(res.passthrough)}",
             f"  анимаций сохранено первым кадром: {res.cropped}", ""]
    if res.notes:
        lines += ["Замечания:"] + [f"  - {n}" for n in res.notes] + [""]
    if res.skipped:
        lines += ["Не перенесено (нет поддержки):"]
        lines += [f"  {k}: {v} файл(ов)" for k, v in sorted(res.skipped.items())] + [""]
    if res.errors:
        lines += ["Ошибки:"] + [f"  {f}: {e}" for f, e in res.errors] + [""]
    if res.passthrough:
        lines += ["Перенесены под тем же именем (проверьте, если что-то не применилось в игре):"]
        lines += [f"  {p}" for p in sorted(res.passthrough)]
    res.report = res.dst.with_name(res.dst.stem + "_report.txt")
    res.report.write_text("\n".join(lines), encoding="utf-8")


def _slice_hotbar(data: bytes) -> dict:
    """Java hotbar.png (182x22 * k) -> Bedrock: крайние части 1 px и 9 ячеек по 20 px."""
    img = _open(data)
    w, h = img.size
    if w % 182:
        raise ValueError(f"hotbar.png: ширина {w} не кратна 182")
    s = w // 182
    parts = {"hotbar_start_cap": img.crop((0, 0, s, h)),
             "hotbar_end_cap": img.crop((w - s, 0, w, h))}
    for i in range(9):
        x0 = s + i * 20 * s
        parts[f"hotbar_{i}"] = img.crop((x0, 0, x0 + 20 * s, h))
    return {k: _png(v) for k, v in parts.items()}


def _compose_hotbar(pieces: dict) -> bytes:
    """Bedrock: начало + 9 ячеек + конец -> один hotbar.png для Java."""
    imgs = [_open(pieces[n]) for n in HOTBAR_NAMES]
    h = max(i.height for i in imgs)
    imgs = [i if i.height == h else
            i.resize((max(1, round(i.width * h / i.height)), h), Image.NEAREST) for i in imgs]
    out = Image.new("RGBA", (sum(i.width for i in imgs), h))
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width
    return _png(out)


def _compose_potion(base: bytes, overlay: bytes = None) -> bytes:
    """Java (бутылка + окрашиваемая жидкость) -> цельная текстура Bedrock."""
    b = _open(base)
    if overlay is None:
        return _png(b)
    o = _open(overlay)
    if o.size != b.size:
        o = o.resize(b.size, Image.NEAREST)
    r, g, bl, a = o.split()
    tinted = Image.merge("RGBA", (r.point(lambda v: v * WATER[0] // 255),
                                  g.point(lambda v: v * WATER[1] // 255),
                                  bl.point(lambda v: v * WATER[2] // 255), a))
    return _png(Image.alpha_composite(tinted, b))


# ---------------------------------------------------------------- Java -> Bedrock
def _java_to_bedrock(src: Source, base: Path, desc: str) -> PortResult:
    dst = base / f"{src.name}_bedrock.mcpack"
    res = PortResult(dst, "Java → Bedrock")
    out = {}
    potion_src = {}   # имя -> байты (потом склеиваем бутылку и жидкость)

    for rel in sorted(src.files):
        low = rel.lower()
        if rel == "pack.png":
            out["pack_icon.png"] = src.read(rel)
            continue
        if rel == "pack.mcmeta" or low.endswith(".mcmeta"):
            continue
        if not rel.startswith(TEX):
            res.skip(rel)
            continue

        sub = rel[len(TEX):]
        parts = sub.split("/")
        stem, ext = os.path.splitext(sub)
        if ext.lower() != ".png":
            res.skip(rel)
            continue
        top = parts[0]

        try:
            if top in ("block", "item") and len(parts) == 2:
                name = parts[1][:-4]
                if top == "item" and (name in mp.POTIONS_JAVA_TO_BEDROCK or name == "potion_overlay"):
                    potion_src[name] = src.read(rel)
                    continue
                table = mp.JAVA_TO_BEDROCK_BLOCKS if top == "block" else mp.JAVA_TO_BEDROCK_ITEMS
                folder = "blocks" if top == "block" else "items"
                bname = table.get(name)
                if bname:
                    res.renamed += 1
                else:
                    bname = name
                    res.passthrough.append(f"{top}/{name}")
                data, cropped = _image(src.read(rel), ".png", first_frame=True)
                res.cropped += cropped
                out[f"textures/{folder}/{bname}.png"] = data
                res.converted += 1

            elif top in ("blocks", "items") and len(parts) == 2:
                # старый формат Java (до 1.13): имена те же, что в Bedrock
                name = parts[1][:-4]
                legacy_potion = {"potion_bottle_drinkable": "potion",
                                 "potion_bottle_splash": "splash_potion"}
                if name == "potion_overlay" or name in legacy_potion:
                    potion_src[legacy_potion.get(name, name)] = src.read(rel)
                    continue
                data, cropped = _image(src.read(rel), ".png", first_frame=True)
                res.cropped += cropped
                out[f"textures/{top}/{name}.png"] = data
                res.converted += 1

            elif sub.startswith(HUD):
                hud = sub[len(HUD):-4]
                if hud == "hotbar":
                    for k, v in _slice_hotbar(src.read(rel)).items():
                        out[f"textures/ui/{k}.png"] = v
                    res.converted += 1
                    res.renamed += 1
                elif hud in mp.UI_JAVA_TO_BEDROCK:
                    out[f"textures/ui/{mp.UI_JAVA_TO_BEDROCK[hud]}.png"] = src.read(rel)
                    res.converted += 1
                    res.renamed += 1
                else:
                    res.skip(rel, "интерфейс (HUD-спрайты без аналога)")

            elif sub.startswith("models/armor/"):
                aname = parts[-1][:-4]
                m = re.fullmatch(r"(\w+?)_layer_([12])", aname) or re.fullmatch(r"([a-z]+)_([12])", aname)
                if not m:
                    res.skip(rel)
                    continue
                jmat, layer = m.group(1), m.group(2)
                mat = "leather" if jmat == "cloth" else mp.ARMOR.get(jmat, jmat)
                data = src.read(rel)
                out[f"textures/models/armor/{mat}_{layer}.png"] = data
                if mat == "leather":  # у кожаной брони в Bedrock встречается и имя cloth_N
                    out[f"textures/models/armor/cloth_{layer}.png"] = data
                res.converted += 1
                res.renamed += 1

            elif sub.startswith(("entity/equipment/humanoid/", "entity/equipment/humanoid_leggings/")):
                layer = "2" if "humanoid_leggings" in sub else "1"
                mat = mp.ARMOR.get(parts[-1][:-4], parts[-1][:-4])
                out.setdefault(f"textures/models/armor/{mat}_{layer}.png", src.read(rel))
                res.converted += 1
                res.renamed += 1

            elif top in ("entity", "environment", "colormap"):
                out[f"textures/{sub}"] = src.read(rel)
                res.converted += 1

            else:
                res.skip(rel)
        except Exception as e:  # noqa: BLE001
            res.errors.append((rel, str(e)))

    # зелья: склеиваем бутылку и окрашенную жидкость
    for jname, bname in mp.POTIONS_JAVA_TO_BEDROCK.items():
        if jname in potion_src:
            try:
                out[f"textures/items/{bname}.png"] = _compose_potion(
                    potion_src[jname], potion_src.get("potion_overlay"))
                res.converted += 1
                res.renamed += 1
            except Exception as e:  # noqa: BLE001
                res.errors.append((f"item/{jname}.png", str(e)))
    if potion_src:
        res.notes.append("Зелья: жидкость окрашена в цвет воды. В Bedrock у каждого эффекта "
                         "своя цельная текстура, а в Java цвет задаётся игрой.")

    if not res.converted:
        raise ValueError("В паке нет поддерживаемых текстур (assets/minecraft/textures/...)")

    out["manifest.json"] = json.dumps({
        "format_version": 2,
        "header": {"name": src.name, "description": desc, "uuid": str(uuid.uuid4()),
                   "version": [1, 0, 0], "min_engine_version": [1, 20, 0]},
        "modules": [{"type": "resources", "uuid": str(uuid.uuid4()),
                     "version": [1, 0, 0], "description": desc}],
    }, ensure_ascii=False, indent=2).encode("utf-8")

    if res.cropped:
        res.notes.append("Анимированные текстуры (вертикальные ленты) сохранены первым кадром, "
                         "чтобы не растягиваться в Bedrock.")
    res.notes.append("Мобы переносятся по тем же путям, часть текстур может не совпасть по расположению.")
    res.notes.append("Инвентарь, контейнеры, меню, звуки и частицы не переносятся.")
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- Bedrock -> Java
def _bedrock_to_java(src: Source, base: Path, version_label: str, desc: str) -> PortResult:
    cfg = JAVA_VERSIONS[version_label]
    fmt, ranged, legacy = cfg["fmt"], cfg.get("ranged", False), cfg.get("legacy", False)
    dst = base / f"{src.name}_java.zip"
    res = PortResult(dst, f"Bedrock → Java {version_label}")
    out = {}
    hotbar = {}          # части хотбара
    potion_ids = set()   # какие зелья переносили (для моделей без окраски)

    for rel in sorted(src.files):
        if rel == "pack_icon.png":
            out["pack.png"] = src.read(rel)
            continue
        if rel == "manifest.json":
            continue
        if not rel.startswith("textures/"):
            res.skip(rel)
            continue

        sub = rel[len("textures/"):]
        parts = sub.split("/")
        stem, ext = os.path.splitext(sub)
        if ext.lower() not in (".png", ".tga"):
            res.skip(rel)
            continue
        top = parts[0]

        def put(path, data):
            # .png важнее .tga, если есть оба
            if ext.lower() == ".png":
                out[path] = data
            else:
                out.setdefault(path, data)

        try:
            if top in ("blocks", "items") and len(parts) == 2 and legacy:
                # до 1.13 Java использует те же имена, что и Bedrock
                data, _ = _image(src.read(rel), ext)
                put(f"{TEX}{top}/{parts[1][: -len(ext)]}.png", data)
                res.converted += 1

            elif top in ("blocks", "items") and len(parts) == 2:
                table = mp.BEDROCK_TO_JAVA_BLOCKS if top == "blocks" else mp.BEDROCK_TO_JAVA_ITEMS
                folder = "block" if top == "blocks" else "item"
                name = parts[1][: -len(ext)]
                jname = table.get(name)
                if top == "items" and not jname and name.startswith("potion_bottle_"):
                    res.skip(rel, "зелья по эффектам (в Java цвет задаёт игра)")
                    continue
                if jname:
                    res.renamed += 1
                else:
                    jname = name
                    res.passthrough.append(f"{top}/{name}")
                if top == "items" and jname in mp.POTIONS_JAVA_TO_BEDROCK:
                    potion_ids.add(jname)
                data, _ = _image(src.read(rel), ext)
                put(f"{TEX}{folder}/{jname}.png", data)
                res.converted += 1

            elif top == "ui" and len(parts) == 2 and fmt < HUD_FORMAT:
                res.skip(rel, "интерфейс (в этой версии HUD — общий атлас icons/widgets.png)")

            elif top == "ui" and len(parts) == 2:
                name = parts[1][: -len(ext)]
                if name in HOTBAR_NAMES:
                    hotbar[name] = _image(src.read(rel), ext)[0]
                elif name in mp.UI_BEDROCK_TO_JAVA:
                    data, _ = _image(src.read(rel), ext)
                    put(f"{TEX}{HUD}{mp.UI_BEDROCK_TO_JAVA[name]}.png", data)
                    res.converted += 1
                    res.renamed += 1
                else:
                    res.skip(rel, "интерфейс (инвентарь, меню и др.)")

            elif sub.startswith("models/armor/"):
                m = re.fullmatch(r"([a-z]+)_([12])", parts[-1][: -len(ext)])
                if not m:
                    res.skip(rel)
                    continue
                bmat = "leather" if m.group(1) == "cloth" else m.group(1)
                jmat = mp.BEDROCK_TO_JAVA_ARMOR.get(bmat, bmat)
                data, _ = _image(src.read(rel), ext)
                if cfg.get("armor") == "old":      # 1.7.10: cloth_1, chain_1, iron_1 ...
                    put(f"{TEX}models/armor/{'cloth' if bmat == 'leather' else bmat}_{m.group(2)}.png", data)
                else:
                    put(f"{TEX}models/armor/{jmat}_layer_{m.group(2)}.png", data)
                if fmt >= EQUIPMENT_FORMAT:
                    sub_dir = "humanoid" if m.group(2) == "1" else "humanoid_leggings"
                    put(f"{TEX}entity/equipment/{sub_dir}/{jmat}.png", data)
                res.converted += 1
                res.renamed += 1

            elif top == "environment" and "cubemap" in sub.lower():
                res.skip(rel, "небо-кубмап (skybox; в обычной Java не поддерживается)")

            elif top in ("entity", "environment", "colormap"):
                data, _ = _image(src.read(rel), ext)
                put(f"{TEX}{stem}.png", data)
                res.converted += 1

            else:
                res.skip(rel)
        except Exception as e:  # noqa: BLE001
            res.errors.append((rel, str(e)))

    # хотбар: собираем из частей
    if hotbar:
        missing = [n for n in HOTBAR_NAMES if n not in hotbar]
        if missing:
            res.notes.append("Хотбар не собран, не хватает частей: " + ", ".join(missing))
        else:
            try:
                out[f"{TEX}{HUD}hotbar.png"] = _compose_hotbar(hotbar)
                res.converted += 1
                res.renamed += 1
            except Exception as e:  # noqa: BLE001
                res.errors.append(("хотбар", str(e)))

    # зелья: без окраски, иначе поверх цельной текстуры Bedrock ложится жидкость Java
    for jid in sorted(potion_ids if not legacy else []):
        out[f"assets/minecraft/models/item/{jid}.json"] = json.dumps({
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"minecraft:item/{jid}"}}, indent=2).encode("utf-8")
        if fmt >= ITEM_DEFS_FORMAT:
            out[f"assets/minecraft/items/{jid}.json"] = json.dumps({
                "model": {"type": "minecraft:model",
                          "model": f"minecraft:item/{jid}"}}, indent=2).encode("utf-8")
    if potion_ids and not legacy:
        res.notes.append("Зелья: взяты цельные текстуры Bedrock без окраски — все зелья одного типа "
                         "выглядят одинаково (в Java цвет эффекта иначе наложится поверх).")
    if legacy:
        res.notes.append("Зелья в старых версиях: бутылка берётся из Bedrock, а цветная жидкость "
                         "рисуется самой игрой поверх, поэтому вид может отличаться.")
        res.notes.append("В старых версиях имена блоков/предметов почти совпадают с Bedrock, поэтому "
                         "переносятся как есть. Блоков и предметов, которых нет в этой версии, просто не будет.")

    if not res.converted:
        raise ValueError("В паке нет поддерживаемых текстур (textures/...)")

    pack = {"description": desc}
    if ranged:
        pack.update({"min_format": fmt, "max_format": fmt})
    else:
        pack["pack_format"] = fmt
    out["pack.mcmeta"] = json.dumps({"pack": pack}, ensure_ascii=False, indent=2).encode("utf-8")

    res.notes.append(f"pack_format выставлен для Java {version_label}. Для другой версии "
                     "поправьте число в pack.mcmeta.")
    if fmt < HUD_FORMAT:
        res.notes.append("Интерфейс (прицел, хотбар, сердца и т.д.) в этой версии Java хранится в общих "
                         "атласах gui/icons.png и gui/widgets.png — не переносится.")
    res.notes.append("Небо: солнце, луна и облака переносятся; кубическое небо в обычной Java "
                     "не работает (нужны OptiFine/Fabric-моды).")
    res.notes.append("Инвентарь и контейнеры не переносятся: в Bedrock они собраны из отдельных "
                     "кусочков, в Java это один атлас.")
    res.notes.append("Анимированные текстуры (flipbook) копируются как есть, без .mcmeta.")
    res.notes.append("Мобы переносятся по тем же путям, часть текстур может не совпасть по расположению.")
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- публичный API
def port_pack(src_path, target: str, version_label: str = DEFAULT_VERSION,
              description: str = "") -> PortResult:
    """
    Портирует пак в формат target ("bedrock" или "java").
    description — описание, которое будет записано в результат (всегда заменяет исходное).
    Рядом с результатом пишется *_report.txt.
    """
    if target not in EDITION_NAMES:
        raise ValueError("target должен быть 'bedrock' или 'java'")
    src_path = Path(src_path)
    src = Source(src_path)
    try:
        if src.edition == target:
            raise ValueError(f"Это уже {EDITION_NAMES[target]}-пак — выберите другое направление")
        base = src_path.parent
        if target == "bedrock":
            res = _java_to_bedrock(src, base, description)
        else:
            res = _bedrock_to_java(src, base, version_label, description)
        _write_report(res)
        return res
    finally:
        src.close()
