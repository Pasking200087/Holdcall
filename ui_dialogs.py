"""
ui_dialogs.py — Диалоги: контакт, звонок, пользователи, журнал, смена пароля
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox,
    QGroupBox, QCheckBox, QSizePolicy, QDialogButtonBox,
    QFrame, QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt, QDate, QDateTime
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QDateEdit, QDateTimeEdit

from config import (
    ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_SPECIALIST, ROLE_LABELS,
    STATUS_LABELS, STATUS_NEW, STATUS_CALLED, STATUS_CALLBACK, STATUS_DONE,
    STATUS_COLORS, CONTACT_TYPE_LABELS, CONTACT_PERSON,
)
import auth
import database as db


# ─── КОНТАКТ: добавить / редактировать ───────────────────────────────────────

class ContactDialog(QDialog):
    def __init__(self, parent=None, contact: dict = None):
        super().__init__(parent)
        self._contact = contact
        title = "Редактировать контакт" if contact else "Добавить контакт"
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)
        self._build_ui()
        if contact:
            self._fill(contact)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.edit_name     = QLineEdit()
        self.edit_phone    = QLineEdit()
        self.edit_company  = QLineEdit()
        self.edit_position = QLineEdit()
        self.edit_comment  = QTextEdit()
        self.edit_comment.setFixedHeight(70)

        self.combo_type = QComboBox()
        for k, v in CONTACT_TYPE_LABELS.items():
            self.combo_type.addItem(v, k)

        self.edit_name.setPlaceholderText("ФИО контакта")
        self.edit_phone.setPlaceholderText("+7 (999) 123-45-67")
        self.edit_company.setPlaceholderText("Название компании")
        self.edit_position.setPlaceholderText("Должность")

        form.addRow("Тип:", self.combo_type)
        form.addRow("Имя:", self.edit_name)
        form.addRow("Телефон *:", self.edit_phone)
        form.addRow("Компания:", self.edit_company)
        form.addRow("Должность:", self.edit_position)
        form.addRow("Комментарий:", self.edit_comment)
        layout.addLayout(form)

        # Кнопки
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("Сохранить")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _fill(self, c: dict):
        ctype = c.get("contact_type", CONTACT_PERSON)
        idx = self.combo_type.findData(ctype)
        if idx >= 0:
            self.combo_type.setCurrentIndex(idx)
        self.edit_name.setText(c.get("name", ""))
        self.edit_phone.setText(c.get("phone", ""))
        self.edit_company.setText(c.get("company", ""))
        self.edit_position.setText(c.get("position", ""))
        self.edit_comment.setPlainText(c.get("comment", ""))

    def _on_ok(self):
        if not self.edit_phone.text().strip():
            QMessageBox.warning(self, "Ошибка", "Телефон обязателен")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":         self.edit_name.text().strip(),
            "phone":        self.edit_phone.text().strip(),
            "company":      self.edit_company.text().strip(),
            "position":     self.edit_position.text().strip(),
            "contact_type": self.combo_type.currentData(),
            "comment":      self.edit_comment.toPlainText().strip(),
        }


# ─── ОТМЕТИТЬ ЗВОНОК ─────────────────────────────────────────────────────────

class CallDialog(QDialog):
    def __init__(self, parent=None, contact: dict = None):
        super().__init__(parent)
        self._contact = contact or {}
        self.setWindowTitle("Результат звонка")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Информация о контакте
        grp = QGroupBox("Контакт")
        grp_layout = QFormLayout(grp)
        grp_layout.setSpacing(6)
        grp_layout.addRow("Имя:",     QLabel(self._contact.get("name", "—")))
        grp_layout.addRow("Телефон:", QLabel(self._contact.get("phone", "—")))
        grp_layout.addRow("Компания:",QLabel(self._contact.get("company", "—")))
        layout.addWidget(grp)

        # Быстрые исходы — один клик выбирает статус
        from ui_dialer import QUICK_STATUSES, make_quick_button
        from PyQt5.QtWidgets import QGridLayout
        quick = QGridLayout()
        quick.setSpacing(6)
        for i, (status, color) in enumerate(QUICK_STATUSES):
            btn = make_quick_button(status, color)
            btn.clicked.connect(lambda _, s=status: self._select_status(s))
            quick.addWidget(btn, i // 4, i % 4)
        layout.addLayout(quick)

        # Статус
        lbl_s = QLabel("Статус звонка:")
        layout.addWidget(lbl_s)
        self.combo_status = QComboBox()
        for k, v in STATUS_LABELS.items():
            self.combo_status.addItem(v, k)
        cur = self._contact.get("status", STATUS_CALLED)
        idx = self.combo_status.findData(cur)
        if idx >= 0:
            self.combo_status.setCurrentIndex(idx)
        self.combo_status.currentIndexChanged.connect(self._on_status_changed)
        layout.addWidget(self.combo_status)

        # Блок даты перезвона (видим только при статусе callback)
        self._cb_frame = QFrame()
        cb_form = QFormLayout(self._cb_frame)
        cb_form.setContentsMargins(0, 4, 0, 0)
        cb_form.setSpacing(6)
        self.dt_callback = QDateTimeEdit()
        self.dt_callback.setCalendarPopup(True)
        self.dt_callback.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.dt_callback.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        cb_form.addRow("Перезвонить в:", self.dt_callback)
        layout.addWidget(self._cb_frame)
        self._cb_frame.setVisible(cur == STATUS_CALLBACK)

        # Результат
        lbl_r = QLabel("Результат / комментарий:")
        layout.addWidget(lbl_r)
        self.edit_result = QTextEdit()
        self.edit_result.setFixedHeight(80)
        self.edit_result.setPlaceholderText("Краткий итог разговора...")
        self.edit_result.setPlainText(self._contact.get("call_result", ""))
        layout.addWidget(self.edit_result)

        # Шаблоны комментариев
        from ui_dialer import load_dialer_settings, make_template_combo
        self._dialer_settings = load_dialer_settings()
        layout.addWidget(make_template_combo(self._dialer_settings["templates"], self.edit_result))

        # Скрипт разговора (сворачиваемый)
        self._btn_script = QPushButton("Скрипт разговора  ▾")
        self._btn_script.setFixedHeight(28)
        self._btn_script.clicked.connect(self._toggle_script)
        layout.addWidget(self._btn_script)
        self._script_view = QTextEdit()
        self._script_view.setReadOnly(True)
        self._script_view.setPlainText(self._dialer_settings["script"])
        self._script_view.setFixedHeight(150)
        self._script_view.hide()
        layout.addWidget(self._script_view)

        # Кнопки
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Сохранить")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _select_status(self, status: str):
        idx = self.combo_status.findData(status)
        if idx >= 0:
            self.combo_status.setCurrentIndex(idx)

    def _toggle_script(self):
        show = self._script_view.isHidden()
        self._script_view.setVisible(show)
        self._btn_script.setText("Скрыть скрипт  ▴" if show else "Скрипт разговора  ▾")
        # Меняем высоту окна вместе со скриптом, чтобы поля не сжимались
        delta = 150
        h = self.height() + (delta if show else -delta)
        self.resize(self.width(), max(h, self.minimumSizeHint().height()))

    def _on_status_changed(self):
        self._cb_frame.setVisible(self.combo_status.currentData() == STATUS_CALLBACK)

    def get_data(self) -> tuple[str, str, str]:
        status = self.combo_status.currentData()
        result = self.edit_result.toPlainText().strip()
        cb_dt = ""
        if status == STATUS_CALLBACK:
            cb_dt = self.dt_callback.dateTime().toString("yyyy-MM-dd HH:mm")
        return status, result, cb_dt


# ─── УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ───────────────────────────────────────────────

class UsersDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пользователи")
        self.setMinimumSize(620, 420)
        self.setModal(True)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Таблица пользователей
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Логин", "Имя", "Роль", "Активен"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 70)
        layout.addWidget(self.table)

        # Кнопки
        btns = QHBoxLayout()
        btn_add = QPushButton("Добавить пользователя")
        btn_add.setObjectName("success")
        btn_add.clicked.connect(self._on_add)
        btn_edit = QPushButton("Редактировать")
        btn_edit.clicked.connect(self._on_edit)
        self.btn_edit = btn_edit
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_add)
        btns.addWidget(btn_edit)
        btns.addStretch()
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _refresh(self):
        users = db.get_all_users()
        self.table.setRowCount(len(users))
        for i, u in enumerate(users):
            def cell(t):
                item = QTableWidgetItem(str(t) if t else "")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                return item
            self.table.setItem(i, 0, cell(u["id"]))
            self.table.setItem(i, 1, cell(u["username"]))
            self.table.setItem(i, 2, cell(u["full_name"]))
            self.table.setItem(i, 3, cell(ROLE_LABELS.get(u["role"], u["role"])))
            self.table.setItem(i, 4, cell("Да" if u["active"] else "Нет"))
            if not u["active"]:
                for col in range(5):
                    item = self.table.item(i, col)
                    if item:
                        item.setForeground(QBrush(QColor("#AAAAAA")))
            self.table.setRowHeight(i, 26)

    def _selected_user_id(self) -> int | None:
        rows = self.table.selectedItems()
        if not rows:
            return None
        row = self.table.currentRow()
        try:
            return int(self.table.item(row, 0).text())
        except Exception:
            return None

    def _on_add(self):
        dlg = UserEditDialog(self)
        if dlg.exec_():
            data = dlg.get_data()
            from auth import hash_password
            pw_hash = hash_password(data["password"])
            try:
                db.create_user(data["username"], pw_hash, data["role"], data["full_name"])
                db.log_action(auth.Session.user_id, "CREATE_USER",
                              f"username={data['username']} role={data['role']}")
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать пользователя:\n{e}")

    def _on_edit(self):
        uid = self._selected_user_id()
        if uid is None:
            QMessageBox.information(self, "", "Выберите пользователя")
            return
        # Найти пользователя
        users = db.get_all_users()
        user = next((u for u in users if u["id"] == uid), None)
        if not user:
            return
        # Нельзя редактировать себя здесь (только через смену пароля)
        dlg = UserEditDialog(self, user=dict(user))
        if dlg.exec_():
            data = dlg.get_data()
            pw_hash = None
            if data.get("password"):
                from auth import hash_password
                pw_hash = hash_password(data["password"])
            db.update_user(uid, data["full_name"], data["role"],
                           1 if data["active"] else 0, pw_hash)
            db.log_action(auth.Session.user_id, "EDIT_USER",
                          f"id={uid} username={user['username']}")
            self._refresh()


class UserEditDialog(QDialog):
    def __init__(self, parent=None, user: dict = None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Редактировать" if user else "Новый пользователь")
        self.setMinimumWidth(360)
        self.setModal(True)
        self._build_ui()
        if user:
            self._fill(user)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.edit_username  = QLineEdit()
        self.edit_fullname  = QLineEdit()
        self.edit_password  = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.combo_role     = QComboBox()
        self.chk_active     = QCheckBox("Активен")
        self.chk_active.setChecked(True)

        for role_key, role_label in ROLE_LABELS.items():
            self.combo_role.addItem(role_label, role_key)

        pw_hint = "(оставьте пустым чтобы не менять)" if self._user else ""
        self.edit_password.setPlaceholderText(pw_hint or "Минимум 4 символа")

        form.addRow("Логин *:",      self.edit_username)
        form.addRow("Имя:",          self.edit_fullname)
        form.addRow("Пароль *:",     self.edit_password)
        form.addRow("Роль:",         self.combo_role)
        form.addRow("",              self.chk_active)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Сохранить")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self._on_ok)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _fill(self, u: dict):
        self.edit_username.setText(u.get("username", ""))
        self.edit_username.setReadOnly(True)  # логин не меняем
        self.edit_fullname.setText(u.get("full_name", ""))
        idx = self.combo_role.findData(u.get("role", ROLE_SPECIALIST))
        if idx >= 0:
            self.combo_role.setCurrentIndex(idx)
        self.chk_active.setChecked(bool(u.get("active", 1)))

    def _on_ok(self):
        if not self.edit_username.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите логин")
            return
        if not self._user and not self.edit_password.text():
            QMessageBox.warning(self, "Ошибка", "Введите пароль для нового пользователя")
            return
        if self.edit_password.text() and len(self.edit_password.text()) < 4:
            QMessageBox.warning(self, "Ошибка", "Пароль — минимум 4 символа")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "username":  self.edit_username.text().strip(),
            "full_name": self.edit_fullname.text().strip(),
            "password":  self.edit_password.text(),
            "role":      self.combo_role.currentData(),
            "active":    self.chk_active.isChecked(),
        }


# ─── ЖУРНАЛ ДЕЙСТВИЙ ─────────────────────────────────────────────────────────

class AuditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал действий")
        self.setMinimumSize(780, 500)
        self.setModal(True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Дата/Время", "Логин", "Имя", "Действие", "Детали"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 140)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _load(self):
        rows = db.get_audit_log(500)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            def cell(t):
                item = QTableWidgetItem(str(t) if t else "")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                return item
            self.table.setItem(i, 0, cell(r["ts"]))
            self.table.setItem(i, 1, cell(r["username"]))
            self.table.setItem(i, 2, cell(r["full_name"]))
            self.table.setItem(i, 3, cell(r["action"]))
            self.table.setItem(i, 4, cell(r["details"]))
            self.table.setRowHeight(i, 24)


# ─── ВЫБОР ДИАПАЗОНА ДАТ (ЭКСПОРТ БИТРИКС) ──────────────────────────────────

class DateRangeDialog(QDialog):
    """Диалог выбора диапазона дат для экспорта в Битрикс24."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Экспорт в Битрикс24 — период")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Выберите период по дате звонка:"))

        form = QFormLayout()
        form.setSpacing(8)

        today = QDate.currentDate()

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(today.addDays(-30))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        form.addRow("С:", self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(today)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        form.addRow("По:", self.date_to)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Экспорт")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self._validate)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _validate(self):
        if self.date_from.date() > self.date_to.date():
            QMessageBox.warning(self, "Ошибка", "Дата «С» не может быть позже даты «По»")
            return
        self.accept()

    def get_range(self) -> tuple[str, str]:
        """Возвращает (date_from, date_to) в формате YYYY-MM-DD."""
        return (
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
        )


# ─── СМЕНА ПАРОЛЯ ────────────────────────────────────────────────────────────

class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Смена пароля")
        self.setMinimumWidth(340)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.edit_old = QLineEdit()
        self.edit_old.setEchoMode(QLineEdit.Password)
        self.edit_new = QLineEdit()
        self.edit_new.setEchoMode(QLineEdit.Password)
        self.edit_new2 = QLineEdit()
        self.edit_new2.setEchoMode(QLineEdit.Password)

        form.addRow("Текущий пароль:", self.edit_old)
        form.addRow("Новый пароль:",   self.edit_new)
        form.addRow("Повтор:",         self.edit_new2)
        layout.addLayout(form)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color: #C0392B; font-size: 12px;")
        layout.addWidget(self.lbl_err)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Сохранить")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self._on_ok)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _on_ok(self):
        old = self.edit_old.text()
        new = self.edit_new.text()
        new2 = self.edit_new2.text()

        if new != new2:
            self.lbl_err.setText("Новые пароли не совпадают")
            return

        ok, msg = auth.change_password(auth.Session.user_id, old, new)
        if ok:
            QMessageBox.information(self, "Готово", "Пароль успешно изменён")
            self.accept()
        else:
            self.lbl_err.setText(msg)


# ─── СТАТИСТИКА ───────────────────────────────────────────────────────────────

class StatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Статистика звонков")
        self.setMinimumSize(620, 460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Период
        period_row = QHBoxLayout()
        period_row.setSpacing(8)
        period_row.addWidget(QLabel("Период:"))

        today = QDate.currentDate()
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(today.addDays(-30))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        period_row.addWidget(self.date_from)

        period_row.addWidget(QLabel("—"))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(today)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        period_row.addWidget(self.date_to)

        # Быстрые кнопки периода
        for label, days in [("Сегодня", 0), ("7 дней", 6), ("Месяц", 29)]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, d=days: self._set_period(d))
            period_row.addWidget(btn)

        period_row.addStretch()
        btn_load = QPushButton("Показать")
        btn_load.setObjectName("success")
        btn_load.setFixedHeight(28)
        btn_load.clicked.connect(self._load)
        period_row.addWidget(btn_load)
        layout.addLayout(period_row)

        # Сводные карточки
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._lbl_total      = self._make_card(cards_row, "Всего звонков", "#2C3E50")
        self._lbl_productive = self._make_card(cards_row, "Результативных", "#27AE60")
        self._lbl_callback   = self._make_card(cards_row, "Перезвонить",   "#E67E22")
        layout.addLayout(cards_row)

        # Таблица по сотрудникам
        layout.addWidget(QLabel("По сотрудникам:"))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Сотрудник", "Всего", "Результативных", "Перезвонить"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(btn_close)
        layout.addLayout(h)

        self._load()

    def _make_card(self, parent_layout, title: str, color: str) -> QLabel:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {color}; border-radius: 8px; }}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(2)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
        fl.addWidget(lbl_title)
        lbl_val = QLabel("—")
        lbl_val.setStyleSheet("color: #FFFFFF; font-size: 28px; font-weight: bold;")
        fl.addWidget(lbl_val)
        parent_layout.addWidget(frame)
        return lbl_val

    def _set_period(self, days: int):
        today = QDate.currentDate()
        self.date_from.setDate(today.addDays(-days))
        self.date_to.setDate(today)
        self._load()

    def _load(self):
        import database as db
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to   = self.date_to.date().toString("yyyy-MM-dd")
        try:
            data = db.get_stats(date_from, date_to)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить статистику:\n{e}")
            return

        self._lbl_total.setText(str(data.get("total", 0)))
        self._lbl_productive.setText(str(data.get("productive", 0)))
        self._lbl_callback.setText(str(data.get("callback", 0)))

        by_user = data.get("by_user", [])
        self.table.setRowCount(len(by_user))
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        for i, u in enumerate(by_user):
            for col, val in enumerate([u["name"], u["calls"], u["productive"], u["callback"]]):
                item = QTableWidgetItem(str(val))
                item.setFlags(flags)
                if col > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, col, item)


# ─── ДУБЛИКАТЫ ────────────────────────────────────────────────────────────────

class DuplicatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Поиск дубликатов")
        self.setMinimumSize(760, 520)
        self.setModal(True)
        self._groups: list = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.lbl_info = QLabel("Поиск групп контактов с одинаковым номером телефона...")
        layout.addWidget(self.lbl_info)

        # Таблица групп
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "ID", "Имя", "Телефон", "Дата звонка"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 24)
        self.table.setColumnWidth(1, 50)
        layout.addWidget(self.table)

        # Кнопки
        btns = QHBoxLayout()
        self.lbl_sel = QLabel("Выберите дубликаты для удаления (оставьте нужный без галочки)")
        self.lbl_sel.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        btns.addWidget(self.lbl_sel)
        btns.addStretch()
        btn_merge = QPushButton("Удалить выбранные")
        btn_merge.setObjectName("danger")
        btn_merge.clicked.connect(self._on_merge)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_merge)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _load(self):
        import database as db
        try:
            self._groups = db.get_duplicates()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить дубликаты:\n{e}")
            return
        self._populate()

    def _populate(self):
        from config import STATUS_LABELS
        groups = self._groups
        total_dups = sum(len(g) - 1 for g in groups)
        self.lbl_info.setText(
            f"Найдено групп: {len(groups)}  |  Возможных дубликатов: {total_dups}"
            if groups else "Дубликатов не найдено."
        )

        # Собираем строки: разделитель группы + строки контактов
        rows_data = []
        for g in groups:
            rows_data.append(("separator", g))
            for c in g:
                rows_data.append(("contact", c))

        self.table.setRowCount(len(rows_data))
        self._checkboxes: dict[int, QCheckBox] = {}  # row -> checkbox
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        row_idx = 0

        for kind, data in rows_data:
            if kind == "separator":
                # Заголовок группы
                self.table.setSpan(row_idx, 0, 1, 5)
                first_phone = data[0]["phone"].split("\n")[0] if data else ""
                item = QTableWidgetItem(f"  Телефон: {first_phone}  —  {len(data)} контакта(ов)")
                item.setBackground(QBrush(QColor("#EBF5FB")))
                item.setFont(self.table.font())
                item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row_idx, 0, item)
                row_idx += 1
            else:
                c = data
                cb = QCheckBox()
                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.setContentsMargins(4, 0, 0, 0)
                cb_layout.addWidget(cb)
                self.table.setCellWidget(row_idx, 0, cb_widget)
                self._checkboxes[row_idx] = cb

                for col, val in enumerate([c["id"], c["name"], c["phone"], c["call_date"]], start=1):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setFlags(flags)
                    self.table.setItem(row_idx, col, item)
                row_idx += 1

    def _on_merge(self):
        to_delete = []
        for row, cb in self._checkboxes.items():
            if cb.isChecked():
                id_item = self.table.item(row, 1)
                if id_item:
                    try:
                        to_delete.append(int(id_item.text()))
                    except ValueError:
                        pass

        if not to_delete:
            QMessageBox.information(self, "Дубликаты", "Ничего не выбрано.")
            return

        reply = QMessageBox.question(
            self, "Удаление дубликатов",
            f"Удалить {len(to_delete)} контакт(ов)? Это действие необратимо.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        import database as db
        import auth
        try:
            count = db.merge_contacts(0, to_delete)
            db.log_action(auth.Session.user_id, "MERGE_DUPLICATES", f"удалено={count}")
            QMessageBox.information(self, "Готово", f"Удалено {count} дубликат(ов).")
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
