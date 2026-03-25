"""
deploy.py -- Публикация новой версии на NAS.
Запускать из папки проекта после сборки: pyinstaller build.spec
"""
import os
import sys
import shutil

# ── НАСТРОЙКА ─────────────────────────────────────────────────────────────────
NAS_MAIN   = r"Z:\Программа для холодных звонков"
NAS_UPDATE = r"Z:\Программа для холодных звонков\update"
# ──────────────────────────────────────────────────────────────────────────────

SRC_EXE  = os.path.join("dist", "baza.exe")
VER_FILE = "version.txt"


def fail(msg):
    print(f"[ОШИБКА] {msg}")
    input("Нажмите Enter для выхода...")
    sys.exit(1)


def main():
    if not os.path.exists(SRC_EXE):
        fail(f"Файл {SRC_EXE} не найден. Сначала запусти: pyinstaller build.spec")

    if not os.path.exists(VER_FILE):
        fail(f"Файл {VER_FILE} не найден.")

    with open(VER_FILE, encoding="utf-8") as f:
        new_ver = f.read().strip()

    print(f"Публикация версии {new_ver}...")

    # 1. Копируем основной exe
    os.makedirs(NAS_MAIN, exist_ok=True)
    dst_main = os.path.join(NAS_MAIN, "baza.exe")
    try:
        shutil.copy2(SRC_EXE, dst_main)
        print(f"[OK] Основной exe обновлён: {dst_main}")
    except Exception as e:
        fail(f"Не удалось скопировать exe в основную папку:\n{e}")

    # 2. Копируем в папку обновлений
    os.makedirs(NAS_UPDATE, exist_ok=True)
    dst_update = os.path.join(NAS_UPDATE, "baza.exe")
    try:
        shutil.copy2(SRC_EXE, dst_update)
    except Exception as e:
        fail(f"Не удалось скопировать exe в папку обновлений:\n{e}")

    ver_path = os.path.join(NAS_UPDATE, "version.txt")
    with open(ver_path, "w", encoding="utf-8") as f:
        f.write(new_ver + "\n")

    print(f"[OK] Папка обновлений: {dst_update}")
    print(f"[OK] version.txt → {new_ver}")
    print()
    print(f"[OK] Версия {new_ver} опубликована. Пользователи получат обновление при следующей проверке.")
    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()
