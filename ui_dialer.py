"""
ui_dialer.py — Режим обзвона: очередь контактов, быстрые исходы,
скрипт звонка, шаблоны комментариев и дневная цель.
"""
import json
import os
from datetime import date

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QProgressBar, QCheckBox,
    QDateTimeEdit, QMessageBox, QApplication, QComboBox,
    QSystemTrayIcon,
)
from PyQt5.QtCore import Qt, QDateTime

from config import (
    STATUS_NEW, STATUS_CALLED, STATUS_CALLBACK, STATUS_DONE,
    STATUS_PRODUCTIVE, STATUS_IRRELEVANT, STATUS_NO_ANSWER, STATUS_RUDE,
    STATUS_LABELS, CONTACT_TYPE_LABELS,
)
import auth
import database as db


# ─── ЛОКАЛЬНЫЕ НАСТРОЙКИ: цель на день, скрипт, шаблоны ──────────────────────

_SETTINGS_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "baza", "dialer.json"
)

DEFAULT_DAILY_GOAL = 50

DEFAULT_TEMPLATES = [
    "Отправил КП на почту",
    "Секретарь, ЛПР недоступен",
    "Просили перезвонить позже",
    "Думают, вернуться через неделю",
    "Не заинтересованы",
    "Номер не отвечает / занято",
]

DEFAULT_SCRIPT = (
    "ПРИВЕТСТВИЕ\n"
    "— Добрый день! Меня зовут ___, компания ___. Удобно говорить?\n\n"
    "ЦЕЛЬ ЗВОНКА\n"
    "— Мы помогаем компаниям ___ . Звоню, чтобы ___.\n\n"
    "ВОЗРАЖЕНИЯ\n"
    "«Нам не надо» — Понимаю. Подскажите, а как вы сейчас решаете вопрос ___?\n"
    "«Дорого» — Смотря с чем сравнивать: наши клиенты экономят ___.\n"
    "«Отправьте на почту» — Конечно, отправлю. На какой адрес? И когда удобно\n"
    "созвониться, чтобы обсудить детали?\n\n"
    "ЗАВЕРШЕНИЕ\n"
    "— Спасибо за разговор! Договорились: ___ . Хорошего дня!"
)


def load_dialer_settings() -> dict:
    """Читает локальные настройки обзвона; при любой ошибке — значения по умолчанию."""
    data = {}
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    return {
        "daily_goal": int(data.get("daily_goal", DEFAULT_DAILY_GOAL)),
        "script":     data.get("script", DEFAULT_SCRIPT),
        "templates":  data.get("templates", list(DEFAULT_TEMPLATES)),
    }


def save_dialer_settings(settings: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fetch_my_today_stats() -> tuple[int, int]:
    """(звонков сегодня, результативных сегодня) для текущего пользователя."""
    try:
        today = date.today().isoformat()
        stats = db.get_stats(date_from=today, date_to=today)
        for u in stats.get("by_user", []):
            if u.get("name") == auth.Session.full_name:
                return int(u.get("calls", 0)), int(u.get("productive", 0))
    except Exception:
        pass
    return 0, 0


# ─── БЫСТРЫЕ ИСХОДЫ ──────────────────────────────────────────────────────────

# (статус, цвет кнопки) — порядок: от позитивных к негативным
QUICK_STATUSES = [
    (STATUS_PRODUCTIVE, "#1E8449"),
    (STATUS_DONE,       "#27AE60"),
    (STATUS_CALLED,     "#B7950B"),
    (STATUS_CALLBACK,   "#CA6F1E"),
    (STATUS_NO_ANSWER,  "#7F8C8D"),
    (STATUS_IRRELEVANT, "#C0392B"),
    (STATUS_RUDE,       "#78281F"),
]


def make_quick_button(status: str, color: str) -> QPushButton:
    label = STATUS_LABELS.get(status, status)
    if status == STATUS_CALLBACK:
        label += "…"
    btn = QPushButton(label)
    btn.setFixedHeight(34)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: #FFFFFF;"
        f" border-radius: 6px; font-size: 12px; padding: 4px 10px; min-width: 60px; }}"
        f"QPushButton:hover {{ background-color: {color}; opacity: 0.9; border: 2px solid #1C2833; }}"
    )
    return btn


def make_template_combo(templates: list, target_edit: QTextEdit) -> QComboBox:
    """Комбо «Вставить шаблон…»: выбор добавляет текст в поле результата."""
    combo = QComboBox()
    combo.addItem("Вставить шаблон…", "")
    for t in templates:
        combo.addItem(t, t)

    def _on_pick(idx: int):
        text = combo.itemData(idx)
        if not text:
            return
        cur = target_edit.toPlainText().strip()
        target_edit.setPlainText(f"{cur}. {text}" if cur else text)
        combo.setCurrentIndex(0)

    combo.activated.connect(_on_pick)
    return combo


# ─── РЕДАКТИРОВАНИЕ СКРИПТА И ШАБЛОНОВ ───────────────────────────────────────

class ScriptEditDialog(QDialog):
    """Редактор скрипта звонка и шаблонов комментариев (по одному на строку)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Скрипт и шаблоны")
        self.setMinimumSize(560, 520)
        self.setModal(True)
        self._settings = load_dialer_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Скрипт разговора:"))
        self.edit_script = QTextEdit()
        self.edit_script.setPlainText(self._settings["script"])
        layout.addWidget(self.edit_script, stretch=3)

        layout.addWidget(QLabel("Шаблоны комментариев (по одному на строку):"))
        self.edit_templates = QTextEdit()
        self.edit_templates.setPlainText("\n".join(self._settings["templates"]))
        layout.addWidget(self.edit_templates, stretch=1)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Сохранить")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self._on_save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _on_save(self):
        templates = [t.strip() for t in self.edit_templates.toPlainText().splitlines() if t.strip()]
        save_dialer_settings({
            "daily_goal": self._settings["daily_goal"],
            "script":     self.edit_script.toPlainText(),
            "templates":  templates or list(DEFAULT_TEMPLATES),
        })
        self.accept()


# ─── РЕЖИМ ОБЗВОНА ───────────────────────────────────────────────────────────

class DialerDialog(QDialog):
    """Конвейер обзвона: показывает по одному контакту из очереди
    (сначала просроченные перезвоны, затем новые) и сохраняет исход одним кликом."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Режим обзвона")
        self.setMinimumSize(680, 680)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint)

        self._settings = load_dialer_settings()
        self._idx = 0
        self._session_calls = 0
        self._daily_calls, self._daily_productive = fetch_my_today_stats()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._queue = self._build_queue()
        finally:
            QApplication.restoreOverrideCursor()

        self._build_ui()
        self._show_current()

    # ── Очередь ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_queue() -> list[dict]:
        try:
            contacts = db.get_contacts_raw(
                hide_irrelevant=not auth.Session.is_admin_or_above()
            )
        except Exception:
            return []
        now = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm")
        due = sorted(
            (c for c in contacts
             if c.get("status") == STATUS_CALLBACK
             and (c.get("callback_datetime") or "")
             and c["callback_datetime"][:16] <= now),
            key=lambda c: c["callback_datetime"],
        )
        fresh = sorted(
            (c for c in contacts if c.get("status") == STATUS_NEW),
            key=lambda c: c["id"],
        )
        return due + fresh

    def has_queue(self) -> bool:
        return bool(self._queue)

    def _current(self) -> dict | None:
        if 0 <= self._idx < len(self._queue):
            return self._queue[self._idx]
        return None

    # ── Интерфейс ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Шапка: дневная цель + очередь
        head = QHBoxLayout()
        self.lbl_goal = QLabel()
        self.lbl_goal.setStyleSheet("font-size: 14px; font-weight: bold; color: #2C3E50;")
        head.addWidget(self.lbl_goal)
        head.addStretch()
        self.lbl_queue = QLabel()
        self.lbl_queue.setStyleSheet("font-size: 12px; color: #718096;")
        head.addWidget(self.lbl_queue)
        layout.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border: 1px solid #CDD2D8; border-radius: 7px; background: #FFFFFF; }"
            "QProgressBar::chunk { background-color: #27AE60; border-radius: 6px; }"
        )
        layout.addWidget(self.progress)

        # Карточка контакта
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 1.5px solid #DDE1E7; border-radius: 10px; }"
        )
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(16, 12, 16, 12)
        card_l.setSpacing(4)

        self.lbl_name = QLabel()
        self.lbl_name.setStyleSheet("font-size: 19px; font-weight: bold; color: #1C2833; border: none;")
        self.lbl_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_name.setMinimumHeight(28)
        card_l.addWidget(self.lbl_name)

        phone_row = QHBoxLayout()
        self.lbl_phone = QLabel()
        self.lbl_phone.setStyleSheet("font-size: 22px; font-weight: bold; color: #2980B9; border: none;")
        self.lbl_phone.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_phone.setMinimumHeight(34)
        phone_row.addWidget(self.lbl_phone)
        btn_copy = QPushButton("⧉")
        btn_copy.setFixedSize(30, 30)
        btn_copy.setToolTip("Скопировать телефон")
        btn_copy.clicked.connect(self._copy_phone)
        phone_row.addWidget(btn_copy)
        phone_row.addStretch()
        card_l.addLayout(phone_row)

        self.lbl_company = QLabel()
        self.lbl_company.setStyleSheet("font-size: 13px; color: #4A5568; border: none;")
        self.lbl_company.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_company.setMinimumHeight(20)
        card_l.addWidget(self.lbl_company)

        self.lbl_history = QLabel()
        self.lbl_history.setStyleSheet("font-size: 12px; color: #718096; border: none;")
        self.lbl_history.setWordWrap(True)
        self.lbl_history.setMinimumHeight(48)
        self.lbl_history.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        card_l.addWidget(self.lbl_history)
        card.setMinimumHeight(170)
        layout.addWidget(card)

        # Скрипт разговора (сворачиваемый)
        script_row = QHBoxLayout()
        self.btn_script = QPushButton("Скрипт разговора  ▾")
        self.btn_script.setFixedHeight(30)
        self.btn_script.clicked.connect(self._toggle_script)
        script_row.addWidget(self.btn_script)
        btn_edit_script = QPushButton("✎")
        btn_edit_script.setFixedSize(30, 30)
        btn_edit_script.setToolTip("Изменить скрипт и шаблоны")
        btn_edit_script.clicked.connect(self._edit_script)
        script_row.addWidget(btn_edit_script)
        script_row.addStretch()
        layout.addLayout(script_row)

        self.script_view = QTextEdit()
        self.script_view.setReadOnly(True)
        self.script_view.setPlainText(self._settings["script"])
        self.script_view.setFixedHeight(160)
        self.script_view.hide()
        layout.addWidget(self.script_view)

        # Результат + шаблоны
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Результат / комментарий:"))
        res_row.addStretch()
        layout.addLayout(res_row)

        self.edit_result = QTextEdit()
        self.edit_result.setFixedHeight(64)
        self.edit_result.setPlaceholderText("Краткий итог разговора...")
        layout.addWidget(self.edit_result)

        self.combo_templates = make_template_combo(self._settings["templates"], self.edit_result)
        layout.addWidget(self.combo_templates)

        # Быстрые исходы
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (status, color) in enumerate(QUICK_STATUSES):
            btn = make_quick_button(status, color)
            btn.clicked.connect(lambda _, s=status: self._on_quick(s))
            grid.addWidget(btn, i // 4, i % 4)
        layout.addLayout(grid)

        # Блок даты перезвона (появляется по кнопке «Перезвонить…»)
        self._cb_frame = QFrame()
        cb_l = QHBoxLayout(self._cb_frame)
        cb_l.setContentsMargins(0, 0, 0, 0)
        cb_l.addWidget(QLabel("Перезвонить в:"))
        self.dt_callback = QDateTimeEdit()
        self.dt_callback.setCalendarPopup(True)
        self.dt_callback.setDisplayFormat("dd.MM.yyyy HH:mm")
        cb_l.addWidget(self.dt_callback)
        btn_cb_ok = QPushButton("Сохранить перезвон")
        btn_cb_ok.setObjectName("success")
        btn_cb_ok.clicked.connect(self._on_cb_confirm)
        cb_l.addWidget(btn_cb_ok)
        cb_l.addStretch()
        self._cb_frame.hide()
        layout.addWidget(self._cb_frame)

        # Нижняя панель
        bottom = QHBoxLayout()
        self.chk_ontop = QCheckBox("Поверх окон")
        self.chk_ontop.toggled.connect(self._toggle_on_top)
        bottom.addWidget(self.chk_ontop)
        bottom.addStretch()

        self.btn_skip = QPushButton("Пропустить →")
        self.btn_skip.clicked.connect(self._advance)
        bottom.addWidget(self.btn_skip)

        btn_hide = QPushButton("Скрыть окно")
        btn_hide.setToolTip("Свернуть обзвон в трей. Вернуться — двойной клик по иконке в трее.")
        btn_hide.clicked.connect(self._hide_to_tray)
        bottom.addWidget(btn_hide)

        btn_finish = QPushButton("Завершить обзвон")
        btn_finish.setObjectName("danger")
        btn_finish.clicked.connect(self.accept)
        bottom.addWidget(btn_finish)
        layout.addLayout(bottom)

    # ── Отображение ──────────────────────────────────────────────────────

    def _update_header(self):
        goal = self._settings["daily_goal"]
        self.lbl_goal.setText(
            f"Сегодня: {self._daily_calls} из {goal} звонков  |  "
            f"результативных: {self._daily_productive}"
        )
        self.progress.setMaximum(max(goal, 1))
        self.progress.setValue(min(self._daily_calls, goal))
        left = len(self._queue) - self._idx
        due_left = sum(
            1 for c in self._queue[self._idx:] if c.get("status") == STATUS_CALLBACK
        )
        self.lbl_queue.setText(f"В очереди: {max(left, 0)} (перезвонить: {due_left})")

    def _show_current(self):
        self._update_header()
        c = self._current()
        enabled = c is not None
        self.btn_skip.setEnabled(enabled)
        self.edit_result.setEnabled(enabled)
        self.combo_templates.setEnabled(enabled)
        if not c:
            self.lbl_name.setText("Очередь пуста 🎉")
            self.lbl_phone.setText("")
            self.lbl_company.setText("Все перезвоны и новые контакты обработаны.")
            self.lbl_history.setText("")
            return

        ctype = CONTACT_TYPE_LABELS.get(c.get("contact_type", ""), "")
        name = c.get("name") or "Без имени"
        self.lbl_name.setText(f"{name}" + (f"  ({ctype})" if ctype else ""))
        self.lbl_phone.setText(c.get("phone", ""))

        parts = [p for p in (c.get("company", ""), c.get("position", "")) if p]
        self.lbl_company.setText(" — ".join(parts) if parts else "")

        history = []
        if c.get("status") == STATUS_CALLBACK:
            history.append(f"⏰ Перезвон был назначен на {c.get('callback_datetime', '')}")
        if c.get("call_result"):
            history.append(f"Прошлый итог: {c['call_result']}")
        if c.get("comment"):
            history.append(f"Комментарий: {c['comment']}")
        self.lbl_history.setText("\n".join(history))

        self.edit_result.setPlainText(c.get("call_result", "") if c.get("status") == STATUS_CALLBACK else "")
        self.dt_callback.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self._cb_frame.hide()

    # ── Действия ─────────────────────────────────────────────────────────

    def _copy_phone(self):
        QApplication.clipboard().setText(self.lbl_phone.text())

    def _toggle_script(self):
        show = self.script_view.isHidden()
        self.script_view.setVisible(show)
        self.btn_script.setText("Скрыть скрипт  ▴" if show else "Скрипт разговора  ▾")
        # Меняем высоту окна вместе со скриптом, чтобы ничего не сжималось
        delta = self.script_view.height() or 160
        h = self.height() + (delta if show else -delta)
        self.resize(self.width(), max(h, self.minimumHeight()))

    def _edit_script(self):
        dlg = ScriptEditDialog(self)
        if dlg.exec_():
            self._settings = load_dialer_settings()
            self.script_view.setPlainText(self._settings["script"])
            old = self.combo_templates
            self.combo_templates = make_template_combo(self._settings["templates"], self.edit_result)
            self.layout().replaceWidget(old, self.combo_templates)
            old.deleteLater()

    def _toggle_on_top(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()

    def _hide_to_tray(self):
        self.hide()
        parent = self.parent()
        tray = getattr(parent, "_tray", None)
        if tray is not None and tray.isVisible():
            tray.showMessage(
                "Режим обзвона",
                "Обзвон свёрнут. Двойной клик по иконке — вернуться к звонкам.",
                QSystemTrayIcon.Information,
                4000,
            )

    def _on_quick(self, status: str):
        if self._current() is None:
            return
        if status == STATUS_CALLBACK:
            self._cb_frame.setVisible(True)
            return
        self._save(status, "")

    def _on_cb_confirm(self):
        cb_dt = self.dt_callback.dateTime().toString("yyyy-MM-dd HH:mm")
        self._save(STATUS_CALLBACK, cb_dt)

    def _save(self, status: str, cb_dt: str):
        c = self._current()
        if c is None:
            return
        result = self.edit_result.toPlainText().strip()
        try:
            db.mark_called(c["id"], status, result, auth.Session.user_id, cb_dt)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить результат:\n{e}")
            return
        db.log_action(auth.Session.user_id, "MARK_CALL",
                      f"id={c['id']} status={status} (обзвон)")
        self._session_calls += 1
        self._daily_calls += 1
        if status in (STATUS_PRODUCTIVE, STATUS_DONE):
            self._daily_productive += 1
        self._advance()

    def _advance(self):
        self._idx += 1
        self._show_current()
