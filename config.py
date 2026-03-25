"""
config.py — Конфигурация приложения
"""
import os
import sys

APP_NAME = "База контактов"
APP_VERSION = "1.2"

# Путь к папке с данными (рядом с exe или рядом со скриптом)
if getattr(sys, "frozen", False):
    # Запуск из .exe (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = BASE_DIR  # БД и ключ хранятся рядом с exe (на NAS)
DB_PATH = os.path.join(DATA_DIR, "baza.db")
KEY_PATH = os.path.join(DATA_DIR, "baza.key")

# Папка обновлений (рядом с exe на NAS)
UPDATE_DIR = os.path.join(DATA_DIR, "update")
UPDATE_EXE_PATH = os.path.join(UPDATE_DIR, "baza.exe")
UPDATE_VERSION_PATH = os.path.join(UPDATE_DIR, "version.txt")

# Локальный файл сессии (на машине пользователя, не на NAS)
_local_app_dir = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "baza"
)
SESSION_PATH = os.path.join(_local_app_dir, "session.json")

# Роли
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_SPECIALIST = "specialist"

ROLE_LABELS = {
    ROLE_OWNER: "Собственник",
    ROLE_ADMIN: "Администратор",
    ROLE_MANAGER: "Менеджер",
    ROLE_SPECIALIST: "Специалист",
}

# Типы контактов
CONTACT_PERSON  = "person"
CONTACT_COMPANY = "company"

CONTACT_TYPE_LABELS = {
    CONTACT_PERSON:  "Физ. лицо",
    CONTACT_COMPANY: "Юр. лицо",
}

# Статусы контакта
STATUS_NEW = "new"
STATUS_CALLED = "called"
STATUS_CALLBACK = "callback"
STATUS_DONE = "done"

STATUS_LABELS = {
    STATUS_NEW: "Новый",
    STATUS_CALLED: "Обзвонен",
    STATUS_CALLBACK: "Перезвонить",
    STATUS_DONE: "Завершён",
}

STATUS_COLORS = {
    STATUS_NEW: "#FFFFFF",
    STATUS_CALLED: "#D4EDDA",
    STATUS_CALLBACK: "#FFF3CD",
    STATUS_DONE: "#D1ECF1",
}

# Стили Qt
STYLE_SHEET = """
QMainWindow, QDialog {
    background-color: #F5F5F5;
}
QTableWidget {
    background-color: #FFFFFF;
    gridline-color: #DDDDDD;
    font-size: 13px;
    selection-background-color: #CCE5FF;
    selection-color: #000000;
}
QTableWidget::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #2C3E50;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #3D5166;
}
QPushButton {
    background-color: #2C3E50;
    color: #FFFFFF;
    border: none;
    padding: 7px 18px;
    border-radius: 4px;
    font-size: 13px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #3D5166;
}
QPushButton:pressed {
    background-color: #1A252F;
}
QPushButton:disabled {
    background-color: #AAAAAA;
    color: #DDDDDD;
}
QPushButton#danger {
    background-color: #C0392B;
}
QPushButton#danger:hover {
    background-color: #E74C3C;
}
QPushButton#success {
    background-color: #27AE60;
}
QPushButton#success:hover {
    background-color: #2ECC71;
}
QLineEdit, QComboBox, QTextEdit {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 13px;
    background-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #2C3E50;
}
QLabel {
    font-size: 13px;
    color: #222222;
}
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #2C3E50;
}
QLabel#subtitle {
    font-size: 12px;
    color: #888888;
}
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #2C3E50;
}
QStatusBar {
    font-size: 12px;
    color: #555555;
}
"""
