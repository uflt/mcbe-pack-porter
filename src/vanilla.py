# -*- coding: utf-8 -*-
"""
Поиск ванильного клиента Minecraft (.jar) на компьютере.

Из него берутся ванильные атласы (icons.png, widgets.png, inventory.png, particles.png),
чтобы при переносе не пропадали части интерфейса, которых нет в паке.
Ничего не скачивается и не копируется в репозиторий: файлы читаются с компьютера пользователя.
"""
import os
import sys
import zipfile
from pathlib import Path


def minecraft_dirs(extra=None):
    """Возможные папки .minecraft (обычный лаунчер, TLauncher и т.п.)."""
    dirs = []
    if extra:
        dirs.append(Path(extra))
    appdata = os.environ.get("APPDATA")
    home = Path.home()
    if appdata:
        dirs += [Path(appdata) / ".minecraft", Path(appdata) / ".tlauncher" / "legacy" / "Minecraft" / "game"]
    dirs += [home / ".minecraft", home / "Library" / "Application Support" / "minecraft"]
    return [d for d in dirs if d.is_dir()]


def find_jar(version, extra_dir=None):
    for d in minecraft_dirs(extra_dir):
        versions = d / "versions"
        exact = versions / version / f"{version}.jar"
        if exact.is_file():
            return exact
        if versions.is_dir():   # сборки вроде "1.8.9-OptiFine" содержат ванильный .jar рядом не всегда
            for sub in sorted(versions.iterdir()):
                jar = sub / f"{sub.name}.jar"
                if sub.name.startswith(version) and jar.is_file() and zipfile.is_zipfile(jar):
                    try:
                        with zipfile.ZipFile(jar) as z:
                            if any(n.startswith("assets/minecraft/textures/") for n in z.namelist()[:5000]):
                                return jar
                    except OSError:
                        continue
    return None


class Vanilla:
    """Чтение текстур из ванильного .jar."""

    def __init__(self, jar):
        self.jar = Path(jar)
        self._zip = zipfile.ZipFile(self.jar)
        self._names = set(self._zip.namelist())

    def read(self, rel):
        return self._zip.read(rel) if rel in self._names else None

    def close(self):
        self._zip.close()


def open_vanilla(version, extra_dir=None):
    jar = find_jar(version, extra_dir)
    if not jar:
        return None
    try:
        return Vanilla(jar)
    except (OSError, zipfile.BadZipFile):
        return None


def settings_path():
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "ufltRP" / "settings.json"


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "1.8.9"
    print(find_jar(v))
