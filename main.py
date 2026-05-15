"""
main.py — Точка входа. Инициализация БД, окно логина, главное окно.
"""
import sys
import os
import time
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QEventLoop

import config
from config import STYLE_SHEET, APP_NAME, APP_VERSION, BASE_DIR


_app: QApplication = None
_main_window = None


def _setup_crash_log():
    log_path = os.path.join(BASE_DIR, "baza_error.log")

    def handle_exception(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n[{datetime.datetime.now()}]\n{msg}\n")
        # Показать диалог если Qt уже запущен
        if _app:
            QMessageBox.critical(None, "Критическая ошибка",
                                 f"Программа завершилась с ошибкой.\n\n{msg}\n\nЛог: {log_path}")
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle_exception


def restart_login():
    """Показать окно логина снова (после logout)."""
    _show_login()


def _show_login():
    global _main_window
    import auth
    if auth.try_auto_login():
        _show_main()
        return
    from ui_login import LoginDialog
    dlg = LoginDialog()
    result = dlg.exec_()
    if result:
        _show_main()
    else:
        # Пользователь закрыл окно логина — выход
        sys.exit(0)


def _show_main():
    global _main_window
    from ui_main import MainWindow
    _main_window = MainWindow()
    _main_window.show()


def _cleanup_old_mei():
    """Удалить устаревшие папки PyInstaller из прошлых запусков.
    Без этого новый exe может наткнуться на неполный _MEI* и упасть с
    'Failed to load Python DLL'."""
    if not getattr(sys, "frozen", False):
        return
    import glob, shutil, tempfile
    current = getattr(sys, "_MEIPASS", None)
    for folder in glob.glob(os.path.join(tempfile.gettempdir(), "_MEI*")):
        if folder == current:
            continue
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass


def main():
    global _app
    _cleanup_old_mei()
    _setup_crash_log()

    # Включить High DPI масштабирование
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    _app = QApplication(sys.argv)
    _app.setApplicationName(APP_NAME)
    _app.setStyleSheet(STYLE_SHEET)

    # ── Настройка пути к базе (первый запуск) ────────────────────────────
    if not config.DATA_DIR:
        from ui_setup import SetupDialog
        dlg = SetupDialog()
        if dlg.exec_() != 1:
            sys.exit(0)

    # ── Экран приветствия ─────────────────────────────────────────────────
    from ui_splash import SplashScreen
    splash = SplashScreen(APP_VERSION)
    splash.show()
    QApplication.processEvents()
    t_start = time.monotonic()

    # Инициализация БД
    splash.set_status("Инициализация базы данных...", 25)
    try:
        import database as db
        db.init_db()
    except Exception as e:
        splash.close()
        QMessageBox.critical(
            None, "Ошибка базы данных",
            f"Не удалось инициализировать базу данных:\n{e}\n\n"
            f"Путь: {config.DB_PATH}"
        )
        sys.exit(1)

    splash.set_status("Проверка авторизации...", 70)
    QApplication.processEvents()

    # Гарантируем минимальное время показа сплэша (0.6 с)
    splash.set_status("Готово", 100)
    QApplication.processEvents()
    remaining_ms = int(max(0.0, 0.6 - (time.monotonic() - t_start)) * 1000)
    if remaining_ms > 0:
        loop = QEventLoop()
        QTimer.singleShot(remaining_ms, loop.quit)
        loop.exec_()

    splash.close()
    # ─────────────────────────────────────────────────────────────────────

    _show_login()
    sys.exit(_app.exec_())


if __name__ == "__main__":
    main()
