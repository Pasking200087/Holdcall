"""
config.py — Конфигурация приложения
"""
import os
import sys

APP_NAME = "База контактов"
APP_VERSION = "3.0"

GITHUB_REPO = "Pasking200087/Holdcall"  # owner/repo

# Путь к папке с данными (рядом с exe или рядом со скриптом)
if getattr(sys, "frozen", False):
    # Запуск из .exe (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Папка обновлений (рядом с exe на NAS) — используется только для legacy пути
UPDATE_DIR          = os.path.join(BASE_DIR, "update")
UPDATE_EXE_PATH     = os.path.join(UPDATE_DIR, "baza.exe")
UPDATE_VERSION_PATH = os.path.join(UPDATE_DIR, "version.txt")

# Локальный файл сессии (на машине пользователя, не на NAS)
_local_app_dir = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "baza"
)
SESSION_PATH   = os.path.join(_local_app_dir, "session.json")
# Если обновление не смогло перезаписать exe на сетевом диске — запускается
# локальная копия, а путь к данным передаётся через этот файл-указатель
DATA_PTR_PATH  = os.path.join(_local_app_dir, "datapath.txt")

def _resolve_data_dir() -> str:
    """Читаем путь к сетевой папке из datapath.txt. Пустая строка — не настроено."""
    try:
        with open(DATA_PTR_PATH, encoding="utf-8") as _f:
            _ptr = _f.read().strip()
        if _ptr and os.path.isdir(_ptr):
            return _ptr
    except Exception:
        pass
    return ""


def set_data_dir(path: str) -> None:
    """Сохранить путь к папке с базой и обновить модульные константы."""
    global DATA_DIR, DB_PATH, KEY_PATH
    os.makedirs(os.path.dirname(DATA_PTR_PATH), exist_ok=True)
    with open(DATA_PTR_PATH, "w", encoding="utf-8") as _f:
        _f.write(path)
    DATA_DIR = path
    DB_PATH  = os.path.join(path, "baza.db")
    KEY_PATH = os.path.join(path, "baza.key")


DATA_DIR = _resolve_data_dir()
DB_PATH  = os.path.join(DATA_DIR, "baza.db") if DATA_DIR else ""
KEY_PATH = os.path.join(DATA_DIR, "baza.key") if DATA_DIR else ""

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
STATUS_NEW         = "new"
STATUS_CALLED      = "called"
STATUS_CALLBACK    = "callback"
STATUS_DONE        = "done"
STATUS_PRODUCTIVE  = "productive"
STATUS_IRRELEVANT  = "irrelevant"
STATUS_NO_ANSWER   = "no_answer"
STATUS_RUDE        = "rude"

STATUS_LABELS = {
    STATUS_NEW:        "Новый",
    STATUS_CALLED:     "Обзвонен",
    STATUS_CALLBACK:   "Перезвонить",
    STATUS_DONE:       "Завершён",
    STATUS_PRODUCTIVE: "Результативный",
    STATUS_IRRELEVANT: "Не актуален",
    STATUS_NO_ANSWER:  "Не отвечает",
    STATUS_RUDE:       "Грубый",
}

# Зелёный — успех, жёлтый — в работе, красный — негатив/отказ
STATUS_COLORS = {
    STATUS_NEW:        "#FFFFFF",
    STATUS_CALLED:     "#FFF3CD",
    STATUS_CALLBACK:   "#FFF3CD",
    STATUS_DONE:       "#D4EDDA",
    STATUS_PRODUCTIVE: "#A8D5B5",
    STATUS_IRRELEVANT: "#F8D7DA",
    STATUS_NO_ANSWER:  "#F8D7DA",
    STATUS_RUDE:       "#F8D7DA",
}

# Статусы скрытые от менеджеров и специалистов
STATUS_HIDDEN_FROM_MANAGERS = {STATUS_IRRELEVANT, STATUS_NO_ANSWER, STATUS_RUDE}

# Стили Qt
STYLE_SHEET = """
/* ── Общий фон ───────────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #F0F2F5;
    font-family: "Segoe UI", Arial, sans-serif;
}

/* ── Меню-бар ────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #2C3E50;
    color: #FFFFFF;
    font-size: 13px;
    padding: 2px 4px;
    spacing: 2px;
}
QMenuBar::item {
    padding: 6px 14px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #3D5166;
}
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #D5DAE0;
    border-radius: 6px;
    padding: 4px 0;
    font-size: 13px;
}
QMenu::item {
    padding: 8px 22px 8px 14px;
}
QMenu::item:selected {
    background-color: #EBF5FB;
    color: #1A252F;
    border-radius: 4px;
}
QMenu::separator {
    height: 1px;
    background: #E8ECF0;
    margin: 4px 8px;
}

/* ── Кнопки ──────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #2C3E50;
    color: #FFFFFF;
    border: none;
    padding: 7px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-family: "Segoe UI", Arial;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #34495E;
}
QPushButton:pressed {
    background-color: #1A252F;
}
QPushButton:disabled {
    background-color: #C8CDD4;
    color: #96A0AB;
}
QPushButton#danger {
    background-color: #E74C3C;
}
QPushButton#danger:hover {
    background-color: #C0392B;
}
QPushButton#danger:pressed {
    background-color: #962D22;
}
QPushButton#success {
    background-color: #27AE60;
}
QPushButton#success:hover {
    background-color: #219A52;
}
QPushButton#success:pressed {
    background-color: #1A7A41;
}

/* ── Поля ввода ──────────────────────────────────────────────────────── */
QLineEdit, QComboBox, QTextEdit {
    border: 1.5px solid #CDD2D8;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    background-color: #FFFFFF;
    color: #1C2833;
    selection-background-color: #AED6F1;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1.5px solid #2980B9;
    background-color: #FAFCFF;
}
QComboBox:focus {
    border: 1.5px solid #2980B9;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #D5DAE0;
    border-radius: 6px;
    selection-background-color: #EBF5FB;
    selection-color: #1A252F;
    padding: 2px;
}

/* ── Таблица ─────────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #FFFFFF;
    gridline-color: #EAEcF0;
    font-size: 13px;
    selection-background-color: #D6EAF8;
    selection-color: #1C2833;
    border: none;
    outline: none;
    alternate-background-color: #F7F9FC;
}
QTableWidget::item:selected {
    background-color: #D6EAF8;
    color: #1C2833;
}
QHeaderView::section {
    background-color: #2C3E50;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 12px;
    padding: 8px 8px;
    border: none;
    border-right: 1px solid #3D5166;
}
QHeaderView::section:last {
    border-right: none;
}

/* ── Полосы прокрутки ────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #F0F2F5;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #B2BEC9;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #8796A5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: #F0F2F5;
    height: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #B2BEC9;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: #8796A5;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Метки ───────────────────────────────────────────────────────────── */
QLabel {
    font-size: 13px;
    color: #2D3748;
    font-family: "Segoe UI", Arial;
}
QLabel#title {
    font-size: 22px;
    font-weight: bold;
    color: #2C3E50;
}
QLabel#subtitle {
    font-size: 11px;
    color: #7F8C8D;
}

/* ── GroupBox ────────────────────────────────────────────────────────── */
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1.5px solid #E2E8F0;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 8px;
    background-color: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #4A5568;
}

/* ── Строка статуса ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #F7F8FA;
    border-top: 1px solid #E2E8F0;
    font-size: 12px;
    color: #718096;
}

/* ── Подсказки ───────────────────────────────────────────────────────── */
QToolTip {
    background-color: #2C3E50;
    color: #FFFFFF;
    border: none;
    padding: 5px 9px;
    border-radius: 5px;
    font-size: 12px;
    opacity: 220;
}

/* ── Чекбоксы ────────────────────────────────────────────────────────── */
QCheckBox {
    font-size: 13px;
    color: #2D3748;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #B2BEC9;
    border-radius: 3px;
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #2C3E50;
    border-color: #2C3E50;
}
QCheckBox::indicator:hover {
    border-color: #2980B9;
}
"""
