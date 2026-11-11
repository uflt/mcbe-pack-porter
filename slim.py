"""Перед сборкой: удаляет из tkinterdnd2 библиотеки для Linux/macOS/ARM (в .exe они не нужны)."""
import os
import shutil

import tkinterdnd2

root = os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd")
for name in os.listdir(root):
    path = os.path.join(root, name)
    if os.path.isdir(path) and name != "win-x64":
        shutil.rmtree(path)
        print("удалено:", name)
