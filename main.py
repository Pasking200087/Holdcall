"""
main.py — Точка входа. Инициализация БД, окно логина, главное окно.
"""
import sys
import os

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

from config import STYLE_SHEET, APP_NAME, DB_PATH


_app: QApplication = None
_main_window = None


def _check_update():
    """Проверить обновление и предложить пользователю установить."""
    import updater
    new_ver = updater.check_update()
    if not new_ver:
        return
    from config import APP_VERSION
    reply = QMessageBox.question(
        None,
        "Доступно обновление",
        f"Доступна новая версия программы: {new_ver}\n"
        f"Текущая версия: {APP_VERSION}\n\n"
        f"Обновить сейчас?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )
    if reply == QMessageBox.Yes:
        try:
            updater.apply_update()
        except Exception as e:
            QMessageBox.warning(
                None, "Ошибка обновления",
                f"Не удалось применить обновление:\n{e}"
            )


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


def main():
    global _app

    # Включить High DPI масштабирование
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    _app = QApplication(sys.argv)
    _app.setApplicationName(APP_NAME)
    _app.setStyleSheet(STYLE_SHEET)

    # Инициализация БД
    try:
        import database as db
        db.init_db()
    except Exception as e:
        QMessageBox.critical(
            None, "Ошибка базы данных",
            f"Не удалось инициализировать базу данных:\n{e}\n\n"
            f"Путь: {DB_PATH}"
        )
        sys.exit(1)

    _check_update()
    _show_login()
    sys.exit(_app.exec_())


if __name__ == "__main__":
    main()
