# -*- coding: utf-8 -*-
"""
Портирование ресурс-паков Java <-> Bedrock (только текстуры и метаданные).

Что переносится:
  блоки, предметы, мобы (entity), окружение (солнце/луна/облака), цвета травы/листвы,
  броня, иконка и описание пака.
Что НЕ переносится: звуки, интерфейс (GUI), частицы, модели, шрифты, шейдеры, языки.

Edition определяется автоматически: pack.mcmeta -> Java, manifest.json -> Bedrock.
Принимает .zip / .mcpack или распакованную папку.
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

# метка версии -> (pack_format, использовать min_format/max_format как в 1.21.9+)
JAVA_VERSIONS = {
    "1.20.1": (15, False),
    "1.21.1": (34, False),
    "1.21.4": (46, False),
    "1.21.8": (64, False),
    "26.1": (84, True),
}
DEFAULT_VERSION = "26.1"
EQUIPMENT_FORMAT = 42  # с этого формата броня лежит в entity/equipment/...

TEX = "assets/minecraft/textures/"


@dataclass
class PortResult:
    dst: Path
    direction: str
    converted: int = 0                       # сколько текстур перенесено
    renamed: int = 0                         # из них переименовано по таблице
    cropped: int = 0                         # анимации, сохранённые первым кадром
    passthrough: list = field(default_factory=list)   # перенесены под тем же именем
    skipped: dict = field(default_factory=dict)       # папка -> число файлов
    errors: list = field(default_factory=list)        # (файл, причина)
    notes: list = field(default_factory=list)
    report: Path = None

    def skip(self, rel: str):
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
def _flatten_text(d):
    """Описание Java может быть строкой, словарём или списком JSON-компонентов."""
    if isinstance(d, str):
        return d
    if isinstance(d, list):
        return "".join(_flatten_text(x) for x in d)
    if isinstance(d, dict):
        return str(d.get("text", "")) + _flatten_text(d.get("extra", []))
    return ""


def _load_json_loose(raw: bytes):
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r"(?m)^\s*//.*$", "", text)  # комментарии //
        return json.loads(text)


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
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")
    return buf.getvalue(), cropped


def _write_zip(dst: Path, files: dict):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


def _write_report(res: PortResult):
    lines = [f"Порт пака: {res.direction}", f"Результат: {res.dst.name}", "",
             f"Текстур перенесено: {res.converted}",
             f"  переименовано по таблице: {res.renamed}",
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


# ---------------------------------------------------------------- Java -> Bedrock
def _java_to_bedrock(src: Source, base: Path) -> PortResult:
    dst = base / f"{src.name}_bedrock.mcpack"
    res = PortResult(dst, "Java → Bedrock")
    out = {}

    meta = {}
    if "pack.mcmeta" in src.files:
        try:
            meta = _load_json_loose(src.read("pack.mcmeta"))
        except Exception:  # noqa: BLE001
            res.notes.append("pack.mcmeta не удалось прочитать — описание оставлено пустым")
    desc = _flatten_text(meta.get("pack", {}).get("description", ""))

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
                table = mp.JAVA_TO_BEDROCK_BLOCKS if top == "block" else mp.JAVA_TO_BEDROCK_ITEMS
                folder = "blocks" if top == "block" else "items"
                name = parts[1][:-4]
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
                m = re.fullmatch(r"(\w+?)_layer_([12])", parts[-1][:-4])
                if not m:
                    res.skip(rel)
                    continue
                mat = mp.ARMOR.get(m.group(1), m.group(1))
                out[f"textures/models/armor/{mat}_{m.group(2)}.png"] = src.read(rel)
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
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- Bedrock -> Java
def _resolve_lang(desc: str, src: Source) -> str:
    """Описание в Bedrock может быть ключом локализации (pack.description)."""
    if not re.fullmatch(r"[\w.]+", desc or "") or "." not in desc:
        return desc
    for rel in src.files:
        if rel.lower() == "texts/en_us.lang":
            for line in src.read(rel).decode("utf-8-sig").splitlines():
                key, sep, val = line.partition("=")
                if sep and key.strip() == desc:
                    return val.split("\t#")[0].strip()
    return desc


def _bedrock_to_java(src: Source, base: Path, version_label: str) -> PortResult:
    fmt, ranged = JAVA_VERSIONS[version_label]
    dst = base / f"{src.name}_java.zip"
    res = PortResult(dst, f"Bedrock → Java {version_label}")
    out = {}

    desc = ""
    try:
        header = _load_json_loose(src.read("manifest.json")).get("header", {})
        desc = _resolve_lang(str(header.get("description", "")), src)
    except Exception:  # noqa: BLE001
        res.notes.append("manifest.json не удалось прочитать — описание оставлено пустым")

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
            if top in ("blocks", "items") and len(parts) == 2:
                table = mp.BEDROCK_TO_JAVA_BLOCKS if top == "blocks" else mp.BEDROCK_TO_JAVA_ITEMS
                folder = "block" if top == "blocks" else "item"
                name = parts[1][: -len(ext)]
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
                m = re.fullmatch(r"([a-z]+)_([12])", parts[-1][: -len(ext)])
                if not m:
                    res.skip(rel)
                    continue
                bmat = "leather" if m.group(1) == "cloth" else m.group(1)
                jmat = mp.BEDROCK_TO_JAVA_ARMOR.get(bmat, bmat)
                data, _ = _image(src.read(rel), ext)
                put(f"{TEX}models/armor/{jmat}_layer_{m.group(2)}.png", data)
                if fmt >= EQUIPMENT_FORMAT:
                    sub_dir = "humanoid" if m.group(2) == "1" else "humanoid_leggings"
                    put(f"{TEX}entity/equipment/{sub_dir}/{jmat}.png", data)
                res.converted += 1
                res.renamed += 1

            elif top in ("entity", "environment", "colormap"):
                data, _ = _image(src.read(rel), ext)
                put(f"{TEX}{stem}.png", data)
                res.converted += 1

            else:
                res.skip(rel)
        except Exception as e:  # noqa: BLE001
            res.errors.append((rel, str(e)))

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
    res.notes.append("Анимированные текстуры (flipbook) копируются как есть, без .mcmeta.")
    res.notes.append("Мобы переносятся по тем же путям, часть текстур может не совпасть по расположению.")
    _write_zip(dst, out)
    return res


# ---------------------------------------------------------------- публичный API
def port_pack(src_path, version_label: str = DEFAULT_VERSION) -> PortResult:
    """Определяет edition пака и портирует его в противоположный. Пишет отчёт рядом."""
    src_path = Path(src_path)
    src = Source(src_path)
    try:
        base = src_path.parent
        if src.edition == "java":
            res = _java_to_bedrock(src, base)
        else:
            res = _bedrock_to_java(src, base, version_label)
        _write_report(res)
        return res
    finally:
        src.close()
