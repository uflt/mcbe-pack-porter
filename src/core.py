# -*- coding: utf-8 -*-
"""Логика: замена описания в .mcpack. Не зависит от GUI."""
import json
import re
import zipfile
from pathlib import Path

TEXT = "Больше паков в тгк - @ufltRP"

# Коды цветов Minecraft Bedrock
COLORS = {
    "Радуга": None,
    "Золотой": "§6",
    "Жёлтый": "§e",
    "Красный": "§c",
    "Зелёный": "§a",
    "Голубой": "§b",
    "Синий": "§9",
    "Розовый": "§d",
}
RAINBOW = ["§c", "§6", "§e", "§a", "§b", "§9", "§d"]


def build_description(color_name: str = "Радуга", bold: bool = True) -> str:
    b = "§l" if bold else ""
    code = COLORS[color_name]
    if code is None:  # радуга
        out, i = "", 0
        for ch in TEXT:
            if ch == " ":
                out += ch
                continue
            out += f"{RAINBOW[i % len(RAINBOW)]}{b}{ch}"
            i += 1
        return out + "§r"
    return f"{code}{b}{TEXT}§r"


def bump_version(ver):
    """[1, 0, 0] -> [1, 0, 1]; "1.0.0" -> "1.0.1"."""
    if isinstance(ver, list) and len(ver) == 3 and all(isinstance(x, int) for x in ver):
        return [ver[0], ver[1], ver[2] + 1]
    if isinstance(ver, str):
        parts = ver.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
    return ver


def _find_manifest(names):
    candidates = [n for n in names if n.lower().endswith("manifest.json")]
    if not candidates:
        return None
    return min(candidates, key=lambda n: n.count("/"))


def _patch_manifest(raw: bytes, desc: str, bump: bool) -> bytes:
    text = raw.decode("utf-8-sig")
    try:
        data = json.loads(text)
        header = data.setdefault("header", {})
        header["description"] = desc
        if bump and "version" in header:
            header["version"] = bump_version(header["version"])
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    except json.JSONDecodeError:
        # manifest с комментариями — правим регулярками
        pat = re.compile(r'("description"\s*:\s*)"(?:[^"\\]|\\.)*"')
        if not pat.search(text):
            raise ValueError("В manifest.json не найдено поле description")
        new = pat.sub(lambda m: m.group(1) + json.dumps(desc, ensure_ascii=False), text, count=1)
        if bump:
            vpat = re.compile(r'("version"\s*:\s*\[\s*\d+\s*,\s*\d+\s*,\s*)(\d+)(\s*\])')
            new = vpat.sub(lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}", new, count=1)
        return new.encode("utf-8")


def _patch_lang(raw: bytes, desc: str) -> bytes:
    text = raw.decode("utf-8-sig")
    new = re.sub(r"(?m)^(pack\.description\s*=).*$", lambda m: m.group(1) + desc, text)
    return new.encode("utf-8")


def process(src, color_name: str = "Радуга", bold: bool = True, bump: bool = True) -> Path:
    """Создаёт <имя>_ufltRP.mcpack рядом с оригиналом и возвращает путь к нему."""
    src = Path(src)
    if src.suffix.lower() not in (".mcpack", ".zip"):
        raise ValueError("Это не .mcpack файл")
    if not zipfile.is_zipfile(src):
        raise ValueError("Файл повреждён или это не архив")

    desc = build_description(color_name, bold)
    dst = src.with_name(src.stem + "_ufltRP.mcpack")

    with zipfile.ZipFile(src) as zin:
        mf = _find_manifest(zin.namelist())
        if not mf:
            raise ValueError("manifest.json не найден — это точно ресурс-пак?")
        mf_dir = mf[: -len("manifest.json")]

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == mf:
                    data = _patch_manifest(data, desc, bump)
                elif (item.filename.startswith(mf_dir + "texts/")
                      and item.filename.endswith(".lang")
                      and b"pack.description" in data):
                    data = _patch_lang(data, desc)
                zout.writestr(item, data)
    return dst
