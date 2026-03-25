"""
ui_main.py — Главное окно приложения
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox, QLabel,
    QAbstractItemView, QMessageBox, QStatusBar,
    QAction, QMenuBar, QMenu, QFrame, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QBrush

from config import (
    APP_NAME, STATUS_LABELS, STATUS_COLORS,
    STATUS_NEW, STATUS_CALLED, STATUS_CALLBACK, STATUS_DONE,
    CONTACT_TYPE_LABELS, CONTACT_PERSON, CONTACT_COMPANY,
)
import auth
import database as db


# Индексы колонок таблицы
COL_ID      = 0
COL_TYPE    = 1
COL_NAME    = 2
COL_PHONE   = 3
COL_COMPANY = 4
COL_POS     = 5
COL_STATUS  = 6
COL_RESULT  = 7
COL_CALLER  = 8
COL_DATE    = 9

HEADERS = ["ID", "Тип", "Имя", "Телефон", "Компания", "Должность", "Статус", "Результат звонка", "Кто звонил", "Дата звонка"]
COL_WIDTHS = [50, 80, 180, 140, 160, 120, 100, 220, 130, 130]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}")
        self.setMinimumSize(1100, 600)
        self.resize(1280, 720)
        self._contacts: list[dict] = []
        self._build_menu()
        self._build_ui()
        self._refresh()

        # Авто-обновление каждые 30 секунд (для второго пользователя)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(30_000)

    # ─── МЕНЮ ────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # Файл
        m_file = mb.addMenu("Файл")
        if auth.Session.is_admin_or_above():
            act_smart = QAction("Умный импорт (из Битрикса)...", self)
            act_smart.triggered.connect(self._on_smart_import)
            m_file.addAction(act_smart)

            act_import = QAction("Обычный импорт Excel...", self)
            act_import.triggered.connect(self._on_import)
            m_file.addAction(act_import)

            act_export = QAction("Экспорт в Excel...", self)
            act_export.triggered.connect(self._on_export)
            m_file.addAction(act_export)
            m_file.addSeparator()

        act_logout = QAction("Выйти из аккаунта", self)
        act_logout.triggered.connect(self._on_logout)
        m_file.addAction(act_logout)

        act_exit = QAction("Закрыть программу", self)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # Управление (только owner)
        if auth.Session.is_owner():
            m_admin = mb.addMenu("Управление")

            act_users = QAction("Пользователи...", self)
            act_users.triggered.connect(self._on_users)
            m_admin.addAction(act_users)

            act_log = QAction("Журнал действий...", self)
            act_log.triggered.connect(self._on_audit)
            m_admin.addAction(act_log)

        # Аккаунт
        m_acc = mb.addMenu("Аккаунт")
        act_chpw = QAction("Сменить пароль...", self)
        act_chpw.triggered.connect(self._on_change_password)
        m_acc.addAction(act_chpw)

    # ─── ИНТЕРФЕЙС ───────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # Верхняя панель
        top = QHBoxLayout()
        top.setSpacing(8)

        # Поиск
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Поиск по имени, телефону, компании...")
        self.edit_search.setMinimumWidth(260)
        self.edit_search.textChanged.connect(self._refresh)
        top.addWidget(self.edit_search)

        # Фильтр по статусу
        self.combo_status = QComboBox()
        self.combo_status.addItem("Все статусы", "")
        for k, v in STATUS_LABELS.items():
            self.combo_status.addItem(v, k)
        self.combo_status.setMinimumWidth(150)
        self.combo_status.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.combo_status)

        # Фильтр по типу контакта
        self.combo_type = QComboBox()
        self.combo_type.addItem("Все типы", "")
        for k, v in CONTACT_TYPE_LABELS.items():
            self.combo_type.addItem(v, k)
        self.combo_type.setMinimumWidth(120)
        self.combo_type.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.combo_type)

        top.addStretch()

        # Кнопки (зависят от роли)
        if auth.Session.is_admin_or_above():
            btn_smart = QPushButton("Умный импорт")
            btn_smart.clicked.connect(self._on_smart_import)
            top.addWidget(btn_smart)

        if auth.Session.can_add_contact():
            btn_add = QPushButton("+ Добавить")
            btn_add.setObjectName("success")
            btn_add.clicked.connect(self._on_add)
            top.addWidget(btn_add)

        if auth.Session.is_admin_or_above():
            self.btn_delete = QPushButton("Удалить")
            self.btn_delete.setObjectName("danger")
            self.btn_delete.clicked.connect(self._on_delete)
            self.btn_delete.setEnabled(False)
            top.addWidget(self.btn_delete)

            btn_import = QPushButton("Импорт Excel")
            btn_import.clicked.connect(self._on_import)
            top.addWidget(btn_import)

            btn_export = QPushButton("Экспорт Excel")
            btn_export.clicked.connect(self._on_export)
            top.addWidget(btn_export)

        # Кнопка "Отметить звонок" — для всех
        self.btn_call = QPushButton("Отметить звонок")
        self.btn_call.setObjectName("success")
        self.btn_call.clicked.connect(self._on_mark_call)
        self.btn_call.setEnabled(False)
        top.addWidget(self.btn_call)

        root.addLayout(top)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setSortingEnabled(True)

        self.table.setWordWrap(True)

        hh = self.table.horizontalHeader()
        for i, w in enumerate(COL_WIDTHS):
            self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(COL_RESULT, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_ID, QHeaderView.Fixed)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_row_double_click)

        root.addWidget(self.table)

        # Строка статуса
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

        # Инфо пользователя справа в статусбаре
        lbl_user = QLabel(
            f"  {auth.Session.full_name}  |  {auth.Session.display_role()}  "
        )
        lbl_user.setStyleSheet("color: #555; font-size: 12px;")
        self.status_bar.addPermanentWidget(lbl_user)

    # ─── ДАННЫЕ ──────────────────────────────────────────────────────────────

    def _refresh(self):
        search = self.edit_search.text().strip()
        status_filter = self.combo_status.currentData()
        type_filter = self.combo_type.currentData()
        self._contacts = db.get_contacts(search=search, status_filter=status_filter,
                                         type_filter=type_filter)
        self._populate_table()
        self._update_status_bar()

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._contacts))

        for row_idx, c in enumerate(self._contacts):
            status = c.get("status", STATUS_NEW)
            bg = QColor(STATUS_COLORS.get(status, "#FFFFFF"))

            def cell(text: str) -> QTableWidgetItem:
                item = QTableWidgetItem(str(text) if text else "")
                item.setBackground(QBrush(bg))
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                return item

            phone_val = c["phone"] or ""
            row_h = 48 if "\n" in phone_val else 28

            ctype = c.get("contact_type", CONTACT_PERSON)
            type_label = CONTACT_TYPE_LABELS.get(ctype, ctype)

            self.table.setItem(row_idx, COL_ID,      cell(c["id"]))
            self.table.setItem(row_idx, COL_TYPE,    cell(type_label))
            self.table.setItem(row_idx, COL_NAME,    cell(c["name"]))
            self.table.setItem(row_idx, COL_PHONE,   cell(phone_val))
            self.table.setItem(row_idx, COL_COMPANY, cell(c["company"]))
            self.table.setItem(row_idx, COL_POS,     cell(c.get("position", "")))
            self.table.setItem(row_idx, COL_STATUS,  cell(STATUS_LABELS.get(status, status)))
            self.table.setItem(row_idx, COL_RESULT,  cell(c.get("call_result", "")))
            caller = c.get("caller_name") or c.get("caller_username") or ""
            self.table.setItem(row_idx, COL_CALLER,  cell(caller))
            self.table.setItem(row_idx, COL_DATE,    cell(c.get("call_date", "")))

            self.table.setRowHeight(row_idx, row_h)

        self.table.setSortingEnabled(True)
        self._on_selection_changed()

    def _selected_contact_ids(self) -> list[int]:
        rows = set(i.row() for i in self.table.selectedItems())
        ids = []
        for r in rows:
            try:
                ids.append(int(self.table.item(r, COL_ID).text()))
            except Exception:
                pass
        return ids

    def _selected_first_contact(self) -> dict | None:
        ids = self._selected_contact_ids()
        if not ids:
            return None
        for c in self._contacts:
            if c["id"] == ids[0]:
                return c
        return None

    def _on_selection_changed(self):
        has_sel = bool(self._selected_contact_ids())
        self.btn_call.setEnabled(has_sel)
        if auth.Session.is_admin_or_above() and hasattr(self, "btn_delete"):
            self.btn_delete.setEnabled(has_sel)

    # ─── ДЕЙСТВИЯ ────────────────────────────────────────────────────────────

    def _on_row_double_click(self, index):
        contact = self._selected_first_contact()
        if not contact:
            return
        if auth.Session.is_admin_or_above():
            self._open_edit_dialog(contact)
        else:
            self._open_call_dialog(contact)

    def _on_add(self):
        from ui_dialogs import ContactDialog
        dlg = ContactDialog(self)
        if dlg.exec_():
            data = dlg.get_data()
            contact_id = db.create_contact(
                data["name"], data["phone"], data["company"],
                data["comment"], auth.Session.user_id,
                data.get("position", ""), data.get("contact_type", "person")
            )
            db.log_action(auth.Session.user_id, "ADD_CONTACT",
                          f"id={contact_id} phone={data['phone']}")
            self._refresh()

    def _open_edit_dialog(self, contact: dict):
        from ui_dialogs import ContactDialog
        dlg = ContactDialog(self, contact=contact)
        if dlg.exec_():
            data = dlg.get_data()
            db.update_contact(
                contact["id"], data["name"], data["phone"],
                data["company"], data["comment"],
                data.get("position", ""), data.get("contact_type", "person")
            )
            db.log_action(auth.Session.user_id, "EDIT_CONTACT",
                          f"id={contact['id']}")
            self._refresh()

    def _on_delete(self):
        ids = self._selected_contact_ids()
        if not ids:
            return
        reply = QMessageBox.question(
            self, "Удаление",
            f"Удалить {len(ids)} контакт(ов)? Это действие необратимо.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            db.delete_contacts_bulk(ids)
            db.log_action(auth.Session.user_id, "DELETE_CONTACTS",
                          f"ids={ids}")
            self._refresh()

    def _on_mark_call(self):
        contact = self._selected_first_contact()
        if not contact:
            return
        self._open_call_dialog(contact)

    def _open_call_dialog(self, contact: dict):
        from ui_dialogs import CallDialog
        dlg = CallDialog(self, contact=contact)
        if dlg.exec_():
            status, result = dlg.get_data()
            db.mark_called(contact["id"], status, result, auth.Session.user_id)
            db.log_action(auth.Session.user_id, "MARK_CALL",
                          f"id={contact['id']} status={status}")
            self._refresh()

    def _on_smart_import(self):
        from ui_parser import ParserDialog
        dlg = ParserDialog(self, user_id=auth.Session.user_id)
        if dlg.exec_():
            self._refresh()

    def _on_import(self):
        from excel import import_from_excel
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл Excel", "", "Excel файлы (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            rows, errors = import_from_excel(path)
            if not rows and errors:
                QMessageBox.warning(self, "Ошибка импорта", "\n".join(errors[:10]))
                return
            count = db.import_contacts_bulk(rows, auth.Session.user_id)
            db.log_action(auth.Session.user_id, "IMPORT_EXCEL",
                          f"файл={path} добавлено={count}")
            msg = f"Импортировано: {count} контактов."
            if errors:
                msg += f"\nПропущено строк: {len(errors)}"
            QMessageBox.information(self, "Импорт завершён", msg)
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать:\n{e}")

    def _on_export(self):
        from excel import export_to_excel
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить как", "контакты.xlsx", "Excel файлы (*.xlsx)"
        )
        if not path:
            return
        try:
            contacts = db.get_contacts()
            export_to_excel(contacts, path)
            db.log_action(auth.Session.user_id, "EXPORT_EXCEL", f"файл={path}")
            QMessageBox.information(self, "Экспорт", f"Сохранено {len(contacts)} записей.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать:\n{e}")

    def _on_users(self):
        from ui_dialogs import UsersDialog
        dlg = UsersDialog(self)
        dlg.exec_()
        self._refresh()

    def _on_audit(self):
        from ui_dialogs import AuditDialog
        dlg = AuditDialog(self)
        dlg.exec_()

    def _on_change_password(self):
        from ui_dialogs import ChangePasswordDialog
        dlg = ChangePasswordDialog(self)
        dlg.exec_()

    def _on_logout(self):
        db.log_action(auth.Session.user_id, "LOGOUT", "Выход из системы")
        auth.logout()
        self._timer.stop()
        self.close()

        # Показать снова окно логина
        from main import restart_login
        restart_login()

    # ─── СТАТУС ──────────────────────────────────────────────────────────────

    def _update_status_bar(self):
        counts = db.get_contacts_count()
        total = sum(counts.values())
        called = counts.get(STATUS_CALLED, 0) + counts.get(STATUS_DONE, 0)
        new = counts.get(STATUS_NEW, 0)
        cb = counts.get(STATUS_CALLBACK, 0)
        self.status_bar.showMessage(
            f"Всего: {total}  |  Новых: {new}  |  Обзвонено: {called}  |  "
            f"Перезвонить: {cb}  |  Показано: {len(self._contacts)}"
        )

    def closeEvent(self, event):
        self._timer.stop()
        event.accept()
