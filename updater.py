"""
updater.py — Автообновление программы
"""
import os
import sys
import shutil
import subprocess
import tempfile
from typing import Optional

from config import APP_VERSION, UPDATE_EXE_PATH, UPDATE_VERSION_PATH


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def check_update() -> Optional[str]:
    """
    Проверить наличие обновления.
    Возвращает строку новой версии или None если обновления нет.
    """
    try:
        if not os.path.exists(UPDATE_VERSION_PATH):
            return None
        with open(UPDATE_VERSION_PATH, encoding="utf-8") as f:
            new_ver = f.read().strip()
        if _parse_version(new_ver) > _parse_version(APP_VERSION):
            return new_ver
    except Exception:
        pass
    return None


def apply_update() -> None:
    """
    Скопировать новый exe и перезапустить через bat-скрипт.
    Вызывается только из замороженного exe.
    """
    if not getattr(sys, "frozen", False):
        return

    exe_path = sys.executable                          # напр. \\NAS\baza\baza.exe
    exe_dir  = os.path.dirname(exe_path)
    new_tmp  = os.path.join(exe_dir, "_baza_new.exe")

    # Копируем новый файл рядом с текущим
    shutil.copy2(UPDATE_EXE_PATH, new_tmp)

    # Bat-скрипт: ждём завершения текущего процесса, подменяем exe, запускаем
    bat = (
        "@echo off\n"
        "ping 127.0.0.1 -n 3 >nul\n"
        f"move /y \"{new_tmp}\" \"{exe_path}\"\n"
        f"start \"\" \"{exe_path}\"\n"
        "del \"%~f0\"\n"
    )
    bat_path = os.path.join(tempfile.gettempdir(), "baza_update.bat")
    with open(bat_path, "w", encoding="ascii", errors="replace") as f:
        f.write(bat)

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    sys.exit(0)
