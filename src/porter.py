# -*- coding: utf-8 -*-
"""
Портирование ресурс-паков Java <-> Bedrock.

Переносится: блоки, предметы, мобы, солнце/луна/облака, скайбокс, цвета травы и листвы, броня,
зелья (с цветами эффектов), интерфейс (прицел, хотбар, сердца, еда, броня, воздух, опыт,
инвентарь, слоты брони, иконки эффектов), частицы, иконка и описание.
Всегда убираются: «сплеш» от удара (sweep) и частицы удара зачарованным оружием (острота).
НЕ переносится: звуки, меню, модели, шрифты, шейдеры.

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
import parts
import vanilla as vn

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
DEFAULT_VERSION = "1.21.11"
EQUIPMENT_FORMAT = 42   # с этого формата броня лежит в entity/equipment/...
OLD_JARS = ["1.8.9", "1.8.8", "1.8", "1.12.2", "1.7.10"]   # основа атласа частиц для Bedrock

TEX = "assets/minecraft/textures/"
EDITION_NAMES = {"java": "Java", "bedrock": "Bedrock"}
JAVA_POTION_FILES = {"potion", "splash_potion", "lingering_potion", "potion_overlay",
                     "splash_potion_overlay", "lingering_potion_overlay",
                     "potion_bottle_drinkable", "potion_bottle_splash"}


@dataclass
class PortResult:
    dst: Path
    direction: str
    converted: int = 0
    renamed: int = 0
    cropped: int = 0
    passthrough: list = field(default_factory=list)
    skipped: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    report: Path = None

    def skip(self, rel: str, key: str = None):
        if key is None:
            p = rel.split("/")
            n = 4 if rel.startswith(TEX) else 3
            key = "/".join(p[:n]) if len(p) > n else "/".join(p[:-1]) or rel
        self.skipped[key] = self.skipped.get(key, 0) + 1


# ---------------------------------------------------------------- чтение пака
class Source:
    """zip/mcpack или папка. Определяет edition и корень пака."""

    def __init__(self, path):
        path = Path(path)
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
        prefix = marker[: -len(marker.split("/")[-1])]
        self.files = {n[len(prefix):]: r for n, r in readers.items() if n.startswith(prefix)}
        self._lower = {n.lower(): n for n in self.files}

    def read(self, rel):
        return self.files[rel]()

    def get(self, rel):
        real = self._lower.get(rel.lower())
        return self.files[real]() if real else None

    def close(self):
        if self._zip:
            self._zip.close()


# ---------------------------------------------------------------- утилиты
def _image(data: bytes, ext: str, first_frame: bool = False):
    """(png-байты, обрезано_до_первого_кадра). TGA -> PNG."""
    ext = ext.lower()
    if ext == ".png" and not first_frame:
        return data, False
    img = Image.open(io.BytesIO(data))
    img.load()
    cropped = False
    if first_frame and img.width and img.height > img.width and img.height % img.width == 0:
        img = img.crop((0, 0, img.width, img.width))
        cropped = True
    elif ext == ".png":
        return data, False
    return parts.to_png(img), cropped


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
        lines += ["Не перенесено:"]
        lines += [f"  {k}: {v} файл(ов)" for k, v in sorted(res.skipped.items())] + [""]
    if res.errors:
        lines += ["Ошибки:"] + [f"  {f}: {e}" for f, e in res.errors] + [""]
    if res.passthrough:
        lines += ["Перенесены под тем же именем (проверьте, если что-то не применилось в игре):"]
        lines += [f"  {p}" for p in sorted(res.passthrough)]
    res.report = res.dst.with_name(res.dst.stem + "_report.txt")
    res.report.write_text("\n".join(lines), encoding="utf-8")


def _safe(res, label, fn, *a):
    try:
        return fn(*a) or {}
    except Exception as e:  # noqa: BLE001
        res.errors.append((label, str(e)))
        return {}


# ---------------------------------------------------------------- Java -> Bedrock
SKIP_J2B = ("gui/", "particle/", "mob_effect/")   # обрабатываются отдельно


def _java_to_bedrock(src: Source, base: Path, desc: str, mc_dir) -> PortResult:
    dst = base / f"{src.name}_bedrock.mcpack"
    res = PortResult(dst, "Java → Bedrock")
    out = {}

    def jtex(rel):
        return src.get(TEX + rel)

    for rel in sorted(src.files):
        low = rel.lower()
        if rel == "pack.png":
            out["pack_icon.png"] = src.read(rel)
            continue
        if rel == "pack.mcmeta" or low.endswith((".mcmeta", ".properties")):
            continue
        if not rel.startswith(TEX):
            if "/sky/" not in rel:
                res.skip(rel)
            continue

        sub = rel[len(TEX):]
        p = sub.split("/")
        if not low.endswith(".png"):
            res.skip(rel)
            continue
        if sub.startswith(SKIP_J2B):
            continue
        top, name = p[0], p[-1][:-4]

        try:
            if top in ("block", "item", "blocks", "items") and len(p) == 2:
                if name in JAVA_POTION_FILES or name.startswith("empty_armor_slot_"):
                    continue     # зелья и слоты брони — отдельно
                if top in ("blocks", "items"):      # старая Java: имена как в Bedrock
                    bname, folder = name, top
                else:
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

            elif sub.startswith("models/armor/"):
                m = re.fullmatch(r"(\w+?)_layer_([12])", name) or re.fullmatch(r"([a-z]+)_([12])", name)
                if not m:
                    res.skip(rel)
                    continue
                mat = "leather" if m.group(1) == "cloth" else mp.ARMOR.get(m.group(1), m.group(1))
                data = src.read(rel)
                out[f"textures/models/armor/{mat}_{m.group(2)}.png"] = data
                if mat == "leather":
                    out[f"textures/models/armor/cloth_{m.group(2)}.png"] = data
                res.converted += 1
                res.renamed += 1

            elif sub.startswith(("entity/equipment/humanoid/", "entity/equipment/humanoid_leggings/")):
                layer = "2" if "humanoid_leggings" in sub else "1"
                mat = mp.ARMOR.get(name, name)
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

    out.update(_safe(res, "интерфейс", parts.hud_from_java, jtex, res))
    out.update(_safe(res, "зелья", parts.potions_to_bedrock, jtex, res))

    sky = _safe(res, "скайбокс", parts.sky_to_bedrock, set(src.files), src.read)
    if sky:
        out.update(sky)
        res.converted += 1
        res.renamed += 1
        res.notes.append("Скайбокс OptiFine перенесён в textures/environment/overworld_cubemap.")

    old = None
    for v in OLD_JARS:
        old = vn.open_vanilla(v, mc_dir)
        if old:
            break
    try:
        legacy_base = old.read(TEX + "particle/particles.png") if old else None
        out.update(_safe(res, "частицы", parts.particles_to_bedrock, jtex, legacy_base, res))
    finally:
        if old:
            old.close()

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
        res.notes.append("Анимированные текстуры (ленты кадров) сохранены первым кадром.")
    res.notes.append("Мобы переносятся по тем же путям, часть текстур может не совпасть по расположению.")
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- Bedrock -> Java
def _bedrock_to_java(src: Source, base: Path, version_label: str, desc: str, mc_dir) -> PortResult:
    cfg = JAVA_VERSIONS[version_label]
    fmt, ranged, legacy = cfg["fmt"], cfg.get("ranged", False), cfg.get("legacy", False)
    dst = base / f"{src.name}_java.zip"
    res = PortResult(dst, f"Bedrock → Java {version_label}")
    out = {}
    potions, sky = {}, {}

    van = vn.open_vanilla(version_label, mc_dir)
    if van:
        res.notes.append(f"Ванильные текстуры взяты из {van.jar.name}: недостающие части интерфейса "
                         "и частиц остались как в обычной игре.")
    try:
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
            p = sub.split("/")
            stem, ext = os.path.splitext(sub)
            if ext.lower() not in (".png", ".tga"):
                if ext.lower() != ".json":
                    res.skip(rel)
                continue
            top, name = p[0], p[-1][: -len(ext)]

            def put(path, data):
                if ext.lower() == ".png":
                    out[path] = data
                else:
                    out.setdefault(path, data)

            try:
                if top == "items" and len(p) == 2 and parts.is_potion_name(name):
                    potions[name] = parts.open_img(src.read(rel))

                elif top in ("ui", "particle", "gui"):
                    continue    # отдельно ниже

                elif top in ("blocks", "items") and len(p) == 2 and legacy:
                    data, _ = _image(src.read(rel), ext)
                    put(f"{TEX}{top}/{name}.png", data)
                    res.converted += 1

                elif top in ("blocks", "items") and len(p) == 2:
                    table = mp.BEDROCK_TO_JAVA_BLOCKS if top == "blocks" else mp.BEDROCK_TO_JAVA_ITEMS
                    folder = "block" if top == "blocks" else "item"
                    jname = table.get(name)
                    if jname:
                        res.renamed += 1
                    else:
                        jname = name
                        res.passthrough.append(f"{top}/{name}")
                    data, _ = _image(src.read(rel), ext)
                    put(f"{TEX}{folder}/{jname}.png", data)
                    res.converted += 1

                elif sub.startswith("models/armor/"):
                    m = re.fullmatch(r"([a-z]+)_([12])", name)
                    if not m:
                        res.skip(rel)
                        continue
                    bmat = "leather" if m.group(1) == "cloth" else m.group(1)
                    jmat = mp.BEDROCK_TO_JAVA_ARMOR.get(bmat, bmat)
                    data, _ = _image(src.read(rel), ext)
                    if cfg.get("armor") == "old":
                        put(f"{TEX}models/armor/{'cloth' if bmat == 'leather' else bmat}_{m.group(2)}.png", data)
                    else:
                        put(f"{TEX}models/armor/{jmat}_layer_{m.group(2)}.png", data)
                    if fmt >= EQUIPMENT_FORMAT:
                        d = "humanoid" if m.group(2) == "1" else "humanoid_leggings"
                        put(f"{TEX}entity/equipment/{d}/{jmat}.png", data)
                    res.converted += 1
                    res.renamed += 1

                elif top == "environment" and "cubemap" in sub.lower():
                    m = re.search(r"cubemap_(\d)", name)
                    if "overworld" in sub.lower() and m:
                        sky[int(m.group(1))] = parts.open_img(src.read(rel))

                elif top in ("entity", "environment", "colormap"):
                    data, _ = _image(src.read(rel), ext)
                    put(f"{TEX}{stem}.png", data)
                    res.converted += 1
                else:
                    res.skip(rel)
            except Exception as e:  # noqa: BLE001
                res.errors.append((rel, str(e)))

        def ui(n):
            for e in (".png", ".tga"):
                d = src.get(f"textures/ui/{n}{e}")
                if d:
                    return parts.open_img(d)
            return None

        ui_names = sorted({os.path.splitext(r[len("textures/ui/"):])[0] for r in src.files
                           if r.lower().startswith("textures/ui/")
                           and r.lower().endswith((".png", ".tga"))})

        def gui(n):
            return src.get(f"textures/gui/{n}.png")

        out.update(_safe(res, "интерфейс", parts.hud_to_java, ui, cfg, van, res, ui_names, gui))
        if potions:
            out.update(_safe(res, "зелья", parts.potions_to_java, potions, cfg, res))
        atlas = src.get("textures/particle/particles.png")
        out.update(_safe(res, "частицы", parts.particles_to_java, atlas, cfg, van, res))
        if sky:
            out.update(_safe(res, "скайбокс", parts.sky_to_java, sky, cfg))
            res.converted += 1
            res.renamed += 1
            res.notes.append("Скайбокс записан в формате OptiFine: работает с OptiFine, Skyboxify "
                             "(Fabric 1.21+) и Nuit + Nuit Interop.")
    finally:
        if van:
            van.close()

    if not res.converted:
        raise ValueError("В паке нет поддерживаемых текстур (textures/...)")

    pack = {"description": desc}
    if ranged:
        pack.update({"min_format": fmt, "max_format": fmt})
    else:
        pack["pack_format"] = fmt
    out["pack.mcmeta"] = json.dumps({"pack": pack}, ensure_ascii=False, indent=2).encode("utf-8")

    if not van:
        res.notes.append(f"Ванильный клиент {version_label} не найден в .minecraft: части "
                         "интерфейса, которых нет в паке, нарисованы заглушками.")
    res.notes.append("Мобы переносятся по тем же путям, часть текстур может не совпасть по расположению.")
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- публичный API
def port_pack(src_path, target: str, version_label: str = DEFAULT_VERSION,
              description: str = "", mc_dir=None) -> PortResult:
    """
    Портирует пак в формат target ("bedrock" или "java").
    description — описание в результате (всегда заменяет исходное).
    mc_dir — папка .minecraft (если не стандартная), оттуда берутся ванильные текстуры.
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
            res = _java_to_bedrock(src, base, description, mc_dir)
        else:
            res = _bedrock_to_java(src, base, version_label, description, mc_dir)
        _write_report(res)
        return res
    finally:
        src.close()
