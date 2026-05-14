"""
ui_main.py — Главное окно приложения
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox, QLabel,
    QAbstractItemView, QMessageBox, QStatusBar,
    QAction, QMenuBar, QMenu, QFrame, QSizePolicy, QCheckBox,
    QSystemTrayIcon, QApplication,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QBrush

from config import (
    APP_NAME, STATUS_LABELS, STATUS_COLORS,
    STATUS_NEW, STATUS_CALLED, STATUS_CALLBACK, STATUS_DONE, STATUS_PRODUCTIVE,
    STATUS_IRRELEVANT, STATUS_HIDDEN_FROM_MANAGERS,
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


class DataLoader(QThread):
    """Загружает контакты из БД в фоне, не блокируя UI."""
    loaded = pyqtSignal(list)

    def __init__(self, search: str, status_filter: str, type_filter: str,
                 hide_irrelevant: bool = False, parent=None):
        super().__init__(parent)
        self._search = search
        self._status = status_filter
        self._type = type_filter
        self._hide_irrelevant = hide_irrelevant

    def run(self):
        try:
            import database as db
            contacts = db.get_contacts(
                search=self._search,
                status_filter=self._status,
                type_filter=self._type,
                hide_irrelevant=self._hide_irrelevant,
            )
            self.loaded.emit(contacts)
        except Exception:
            self.loaded.emit([])


class UpdateChecker(QThread):
    update_found = pyqtSignal(str)
    no_update    = pyqtSignal()
    check_error  = pyqtSignal(str)

    def __init__(self, parent=None, silent: bool = True):
        super().__init__(parent)
        self._silent = silent

    def run(self):
        try:
            import updater
            new_ver = updater.check_update()
            if new_ver:
                self.update_found.emit(new_ver)
            elif not self._silent:
                self.no_update.emit()
        except Exception as e:
            if not self._silent:
                self.check_error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}")
        self.setMinimumSize(1100, 600)
        self.resize(1280, 720)
        self._contacts: list[dict] = []
        self._force_quit = False
        self._loader = None

        from ui_splash import make_app_icon
        self._icon = make_app_icon(64)
        self.setWindowIcon(self._icon)
        QApplication.instance().setWindowIcon(self._icon)

        # Таймеры нужно создать до _build_ui и _refresh, которые их используют
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(60_000)

        self._build_menu()
        self._build_ui()
        self._build_tray()
        self._refresh()

        # Проверка обновлений: сразу при открытии и затем каждые 10 минут
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._check_update_bg)
        self._update_timer.start(10 * 60 * 1000)
        self._update_checker = None
        self._check_update_bg()

    # ─── ТРЕЙ ────────────────────────────────────────────────────────────────

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._icon, self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        act_show = QAction("Открыть", self)
        act_show.triggered.connect(self._tray_show)
        act_exit = QAction("Выход", self)
        act_exit.triggered.connect(self._quit_app)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_exit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._tray_show()

    def _quit_app(self):
        self._force_quit = True
        self.close()

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

            act_bitrix = QAction("Экспорт завершённых в Битрикс24...", self)
            act_bitrix.triggered.connect(self._on_export_bitrix)
            m_file.addAction(act_bitrix)
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

            m_admin.addSeparator()
            act_dbpath = QAction("Изменить путь к базе...", self)
            act_dbpath.triggered.connect(self._on_change_db_path)
            m_admin.addAction(act_dbpath)

        # Аккаунт
        m_acc = mb.addMenu("Аккаунт")
        act_chpw = QAction("Сменить пароль...", self)
        act_chpw.triggered.connect(self._on_change_password)
        m_acc.addAction(act_chpw)

        # Справка
        m_help = mb.addMenu("Справка")
        act_check_upd = QAction("Проверить обновление", self)
        act_check_upd.triggered.connect(self._on_check_update_manual)
        m_help.addAction(act_check_upd)
        m_help.addSeparator()
        act_about = QAction("О программе...", self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    # ─── ИНТЕРФЕЙС ───────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Панель инструментов ───────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet(
            "QFrame { background-color: #FFFFFF;"
            " border-bottom: 1px solid #DDE1E7; }"
        )
        toolbar.setFixedHeight(56)
        top = QHBoxLayout(toolbar)
        top.setContentsMargins(12, 8, 12, 8)
        top.setSpacing(8)

        # Поиск
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍  Поиск по имени, телефону, компании...")
        self.edit_search.setMinimumWidth(280)
        self.edit_search.setFixedHeight(36)
        self.edit_search.textChanged.connect(
            lambda: self._search_timer.start(350)
        )
        top.addWidget(self.edit_search)

        # Фильтр по статусу
        self.combo_status = QComboBox()
        self.combo_status.addItem("Все статусы", "")
        for k, v in STATUS_LABELS.items():
            if k in STATUS_HIDDEN_FROM_MANAGERS and not auth.Session.is_admin_or_above():
                continue
            self.combo_status.addItem(v, k)
        self.combo_status.setMinimumWidth(150)
        self.combo_status.setFixedHeight(36)
        self.combo_status.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.combo_status)

        # Фильтр по типу контакта
        self.combo_type = QComboBox()
        self.combo_type.addItem("Все типы", "")
        for k, v in CONTACT_TYPE_LABELS.items():
            self.combo_type.addItem(v, k)
        self.combo_type.setMinimumWidth(120)
        self.combo_type.setFixedHeight(36)
        self.combo_type.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.combo_type)

        top.addStretch()

        # Кнопки (зависят от роли)
        if auth.Session.is_admin_or_above():
            btn_smart = QPushButton("Умный импорт")
            btn_smart.setFixedHeight(36)
            btn_smart.clicked.connect(self._on_smart_import)
            top.addWidget(btn_smart)

        if auth.Session.can_add_contact():
            btn_add = QPushButton("＋  Добавить")
            btn_add.setObjectName("success")
            btn_add.setFixedHeight(36)
            btn_add.clicked.connect(self._on_add)
            top.addWidget(btn_add)

        if auth.Session.is_admin_or_above():
            self.btn_delete = QPushButton("Удалить")
            self.btn_delete.setObjectName("danger")
            self.btn_delete.setFixedHeight(36)
            self.btn_delete.clicked.connect(self._on_delete)
            self.btn_delete.setEnabled(False)
            top.addWidget(self.btn_delete)

            btn_import = QPushButton("Импорт")
            btn_import.setFixedHeight(36)
            btn_import.clicked.connect(self._on_import)
            top.addWidget(btn_import)

            btn_export = QPushButton("Экспорт")
            btn_export.setFixedHeight(36)
            btn_export.clicked.connect(self._on_export)
            top.addWidget(btn_export)

            btn_bitrix = QPushButton("⭳ В Битрикс")
            btn_bitrix.setFixedHeight(36)
            btn_bitrix.setToolTip("Экспорт завершённых контактов в формате Битрикс24")
            btn_bitrix.clicked.connect(self._on_export_bitrix)
            top.addWidget(btn_bitrix)

        # Кнопка "Отметить звонок" — для всех
        self.btn_call = QPushButton("✓  Отметить звонок")
        self.btn_call.setObjectName("success")
        self.btn_call.setFixedHeight(36)
        self.btn_call.clicked.connect(self._on_mark_call)
        self.btn_call.setEnabled(False)
        top.addWidget(self.btn_call)

        root.addWidget(toolbar)

        # Баннер обновления (скрыт по умолчанию)
        self._update_bar = QFrame()
        self._update_bar.setStyleSheet(
            "QFrame { background: #FEF9E7; border-bottom: 2px solid #F9CA24;"
            " border-top: none; border-left: none; border-right: none; }"
        )
        ub_layout = QHBoxLayout(self._update_bar)
        ub_layout.setContentsMargins(16, 6, 12, 6)
        self._update_bar_label = QLabel()
        self._update_bar_label.setStyleSheet("font-weight: bold; color: #7D6608; font-size: 13px;")
        ub_layout.addWidget(self._update_bar_label)
        ub_layout.addStretch()
        btn_do_update = QPushButton("Обновить сейчас")
        btn_do_update.setFixedHeight(30)
        btn_do_update.setObjectName("success")
        btn_do_update.clicked.connect(self._on_apply_update)
        ub_layout.addWidget(btn_do_update)
        btn_later = QPushButton("Позже")
        btn_later.setFixedHeight(30)
        btn_later.clicked.connect(self._update_bar.hide)
        ub_layout.addWidget(btn_later)
        self._update_bar.hide()
        root.addWidget(self._update_bar)

        # ── Контент (отступы вокруг таблицы) ─────────────────────────────
        content = QWidget()
        content.setStyleSheet("background-color: #F0F2F5;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(10, 8, 10, 4)
        cl.setSpacing(0)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.setStyleSheet(
            "QTableWidget { border-radius: 8px; border: 1px solid #DDE1E7; }"
        )

        hh = self.table.horizontalHeader()
        for i, w in enumerate(COL_WIDTHS):
            self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(COL_RESULT, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_ID, QHeaderView.Fixed)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_row_double_click)

        cl.addWidget(self.table)
        root.addWidget(content)

        # Строка статуса
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

        # Инфо пользователя справа в статусбаре
        lbl_user = QLabel(
            f"  {auth.Session.full_name}  |  {auth.Session.display_role()}  "
        )
        lbl_user.setStyleSheet("color: #718096; font-size: 12px;")
        self.status_bar.addPermanentWidget(lbl_user)

    # ─── ДАННЫЕ ──────────────────────────────────────────────────────────────

    def _refresh(self):
        self._search_timer.stop()
        search = self.edit_search.text().strip()
        status_filter = self.combo_status.currentData()
        type_filter = self.combo_type.currentData()
        hide_irrelevant = not auth.Session.is_admin_or_above()

        self._loader = DataLoader(search, status_filter, type_filter, hide_irrelevant, self)
        self._loader.loaded.connect(self._on_data_loaded)
        self._loader.start()

    def _on_data_loaded(self, contacts: list):
        self._contacts = contacts
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
            row_h = 52 if "\n" in phone_val else 32

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

    def _on_export_bitrix(self):
        from excel import export_to_bitrix
        from PyQt5.QtWidgets import QFileDialog
        from ui_dialogs import DateRangeDialog
        from config import STATUS_DONE, STATUS_PRODUCTIVE

        # Выбор периода
        dlg = DateRangeDialog(self)
        if dlg.exec_() != DateRangeDialog.Accepted:
            return
        date_from, date_to = dlg.get_range()

        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт для Битрикс24",
            f"битрикс_{date_from}_{date_to}.xlsx", "Excel файлы (*.xlsx)"
        )
        if not path:
            return
        try:
            # Берём завершённые и результативные за выбранный период
            contacts = []
            for st in (STATUS_DONE, STATUS_PRODUCTIVE):
                contacts += db.get_contacts(
                    status_filter=st, date_from=date_from, date_to=date_to
                )
            # Убираем дубли (на случай если статусы пересекутся) и сортируем по дате
            seen = set()
            unique = []
            for c in contacts:
                if c["id"] not in seen:
                    seen.add(c["id"])
                    unique.append(c)
            unique.sort(key=lambda x: x.get("call_date", ""), reverse=True)

            if not unique:
                QMessageBox.information(
                    self, "Экспорт в Битрикс24",
                    f"За период {date_from} – {date_to} нет завершённых\nили результативных контактов."
                )
                return
            export_to_bitrix(unique, path)
            db.log_action(auth.Session.user_id, "EXPORT_BITRIX",
                          f"файл={path}, период={date_from}:{date_to}, записей={len(unique)}")
            QMessageBox.information(
                self, "Экспорт в Битрикс24",
                f"Сохранено {len(unique)} контактов за период\n{date_from} – {date_to}.\n\n"
                "Как импортировать в Битрикс24:\n"
                "CRM → Лиды → ••• → Импорт"
            )
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

    def _on_change_db_path(self):
        import config
        from ui_setup import SetupDialog
        dlg = SetupDialog(current_path=config.DATA_DIR, parent=self)
        if dlg.exec_() == 1:
            QMessageBox.information(
                self, "Путь изменён",
                f"Новый путь сохранён:\n{config.DATA_DIR}\n\n"
                "Перезапустите программу, чтобы изменения вступили в силу."
            )

    def _on_change_password(self):
        from ui_dialogs import ChangePasswordDialog
        dlg = ChangePasswordDialog(self)
        dlg.exec_()

    def _on_about(self):
        from ui_about import AboutDialog
        AboutDialog(self).exec_()

    def _on_logout(self):
        db.log_action(auth.Session.user_id, "LOGOUT", "Выход из системы")
        auth.logout()
        self._timer.stop()
        self._update_timer.stop()
        self.close()

        # Показать снова окно логина
        from main import restart_login
        restart_login()

    # ─── ОБНОВЛЕНИЕ ──────────────────────────────────────────────────────────

    def _check_update_bg(self):
        if self._update_checker and self._update_checker.isRunning():
            return
        self._update_checker = UpdateChecker(self, silent=True)
        self._update_checker.update_found.connect(self._on_update_found)
        self._update_checker.start()

    def _on_check_update_manual(self):
        if self._update_checker and self._update_checker.isRunning():
            QMessageBox.information(self, "Обновление", "Проверка уже выполняется...")
            return
        self._update_checker = UpdateChecker(self, silent=False)
        self._update_checker.update_found.connect(self._on_update_found)
        self._update_checker.no_update.connect(
            lambda: QMessageBox.information(self, "Обновление", "У вас последняя версия.")
        )
        self._update_checker.check_error.connect(
            lambda e: QMessageBox.warning(self, "Ошибка", f"Не удалось проверить обновление:\n{e}")
        )
        self._update_checker.start()

    def _on_update_found(self, new_ver: str):
        self._update_bar_label.setText(
            f"Доступна новая версия {new_ver}. "
            "После обновления программа перезапустится автоматически."
        )
        self._update_bar.show()

    def _on_apply_update(self):
        import updater
        try:
            updater.apply_update()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка обновления",
                                f"Не удалось применить обновление:\n{e}")

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
        tray_ok = hasattr(self, "_tray") and self._tray.isVisible()
        if tray_ok and not self._force_quit:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                APP_NAME,
                "Программа свёрнута в трей. Для выхода щёлкните правой кнопкой на иконке.",
                QSystemTrayIcon.Information,
                3000,
            )
            return
        self._timer.stop()
        self._update_timer.stop()
        if hasattr(self, "_tray"):
            self._tray.hide()
        event.accept()
