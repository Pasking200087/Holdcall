"""
ui_parser.py — Окно умного импорта / парсера сырых данных

Функции:
  - Открыть грязный Excel из Битрикса
  - Показать все строки с цветовой разметкой по статусу
  - Показать сводку: сколько OK / дублей / без телефона
  - Снять галочки с ненужных строк
  - Импортировать выбранные в базу
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QFrame, QMessageBox, QGroupBox,
    QProgressBar, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

from phone_normalizer import (
    parse_excel, get_importable, summary,
    ParsedRow,
    ROW_OK, ROW_NO_PHONE, ROW_EMPTY, ROW_DUPLICATE, ROW_EXTRACTED,
    ROW_STATUS_LABELS, ROW_STATUS_COLORS,
    detect_contact_type,
)


# Колонки таблицы предпросмотра
_COLS = ["", "#", "Статус", "Имя", "Телефон (норм.)", "Телефон (ориг.)", "Компания", "Должность", "Заметка"]
_COL_CHK  = 0
_COL_NUM  = 1
_COL_STS  = 2
_COL_NAME = 3
_COL_PHONE= 4
_COL_ORIG = 5
_COL_COMP = 6
_COL_POS  = 7
_COL_NOTE = 8

_COL_WIDTHS = [28, 42, 110, 190, 145, 145, 200, 130, 160]


class ParseWorker(QThread):
    """Парсинг в отдельном потоке чтобы не блокировать UI."""
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            rows = parse_excel(self.path)
            self.done.emit(rows)
        except Exception as e:
            self.error.emit(str(e))


class ParserDialog(QDialog):
    def __init__(self, parent=None, user_id: int = None):
        super().__init__(parent)
        self._user_id = user_id
        self._rows: list[ParsedRow] = []
        self._worker = None

        self.setWindowTitle("Умный импорт — подготовка данных")
        self.setMinimumSize(1150, 680)
        self.setModal(True)
        self._build_ui()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Верхняя панель: открыть файл
        top = QHBoxLayout()
        self.lbl_file = QLabel("Файл не выбран")
        self.lbl_file.setStyleSheet("color:#555; font-size:12px;")
        btn_open = QPushButton("Открыть Excel...")
        btn_open.clicked.connect(self._on_open)
        top.addWidget(QLabel("Источник:"))
        top.addWidget(self.lbl_file, 1)
        top.addWidget(btn_open)
        root.addLayout(top)

        # Сводка
        self.grp_summary = QGroupBox("Сводка")
        self.grp_summary.setVisible(False)
        sum_layout = QHBoxLayout(self.grp_summary)
        sum_layout.setSpacing(20)

        self.lbl_total    = self._make_stat_label("Всего строк", "0", "#2C3E50")
        self.lbl_ok       = self._make_stat_label("Готово к импорту", "0", "#27AE60")
        self.lbl_extracted= self._make_stat_label("Телефон извлечён", "0", "#2980B9")
        self.lbl_dup      = self._make_stat_label("Дубликаты", "0", "#E67E22")
        self.lbl_nophone  = self._make_stat_label("Нет телефона", "0", "#C0392B")
        self.lbl_empty    = self._make_stat_label("Пустые/мусор", "0", "#999999")

        for w in [self.lbl_total, self.lbl_ok, self.lbl_extracted,
                  self.lbl_dup, self.lbl_nophone, self.lbl_empty]:
            sum_layout.addWidget(w)
        sum_layout.addStretch()
        root.addWidget(self.grp_summary)

        # Прогресс
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        root.addWidget(self.progress)

        # Фильтры (чекбоксы показа)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(16)
        filter_row.addWidget(QLabel("Показать:"))

        self.chk_show_ok   = QCheckBox("OK")
        self.chk_show_ok.setChecked(True)
        self.chk_show_ext  = QCheckBox("Телефон извлечён")
        self.chk_show_ext.setChecked(True)
        self.chk_show_dup  = QCheckBox("Дубликаты")
        self.chk_show_dup.setChecked(True)
        self.chk_show_np   = QCheckBox("Без телефона")
        self.chk_show_np.setChecked(True)
        self.chk_show_emp  = QCheckBox("Пустые")
        self.chk_show_emp.setChecked(False)

        for chk in [self.chk_show_ok, self.chk_show_ext,
                    self.chk_show_dup, self.chk_show_np, self.chk_show_emp]:
            chk.stateChanged.connect(self._apply_filter)
            filter_row.addWidget(chk)

        filter_row.addStretch()
        btn_check_all   = QPushButton("Выбрать все OK")
        btn_check_all.clicked.connect(self._select_all_ok)
        btn_uncheck_all = QPushButton("Снять все")
        btn_uncheck_all.clicked.connect(self._uncheck_all)
        filter_row.addWidget(btn_check_all)
        filter_row.addWidget(btn_uncheck_all)
        root.addLayout(filter_row)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        hh = self.table.horizontalHeader()
        for i, w in enumerate(_COL_WIDTHS):
            self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(_COL_COMP, QHeaderView.Stretch)

        root.addWidget(self.table, 1)

        # Нижняя панель
        bottom = QHBoxLayout()
        self.lbl_selected = QLabel("Выбрано: 0")
        self.lbl_selected.setStyleSheet("font-size:12px; color:#555;")

        self.btn_import = QPushButton("Импортировать выбранные →")
        self.btn_import.setObjectName("success")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._on_import)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.reject)

        bottom.addWidget(self.lbl_selected)
        bottom.addStretch()
        bottom.addWidget(btn_close)
        bottom.addWidget(self.btn_import)
        root.addLayout(bottom)

        # Легенда
        legend = QHBoxLayout()
        legend.setSpacing(12)
        legend.addWidget(QLabel("Цвета:"))
        for status, label in ROW_STATUS_LABELS.items():
            if status == ROW_EMPTY:
                continue
            dot = QLabel(f"  {label}  ")
            dot.setStyleSheet(
                f"background:{ROW_STATUS_COLORS[status]}; "
                f"border:1px solid #ccc; border-radius:3px; "
                f"font-size:11px; padding:1px 4px;"
            )
            legend.addWidget(dot)
        legend.addStretch()
        root.addLayout(legend)

    def _make_stat_label(self, title: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ border:1px solid #ddd; border-radius:6px; "
            f"background:#fff; padding:4px 10px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"font-size:22px; font-weight:bold; color:{color};")
        val_lbl.setAlignment(Qt.AlignCenter)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet("font-size:11px; color:#888;")
        ttl_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(val_lbl)
        layout.addWidget(ttl_lbl)

        # Сохранить ссылку на лейбл значения
        frame._val_label = val_lbl
        return frame

    # ─── ЛОГИКА ──────────────────────────────────────────────────────────────

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл Excel", "", "Excel (*.xlsx *.xls)"
        )
        if not path:
            return

        self.lbl_file.setText(path)
        self.table.setRowCount(0)
        self.grp_summary.setVisible(False)
        self.btn_import.setEnabled(False)
        self.progress.setVisible(True)
        self._rows = []

        self._worker = ParseWorker(path)
        self._worker.done.connect(self._on_parse_done)
        self._worker.error.connect(self._on_parse_error)
        self._worker.start()

    def _on_parse_done(self, rows: list[ParsedRow]):
        self.progress.setVisible(False)
        self._rows = rows
        self._update_summary()
        self._populate_table()
        self.grp_summary.setVisible(True)
        self.btn_import.setEnabled(True)

    def _on_parse_error(self, msg: str):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Ошибка чтения", f"Не удалось прочитать файл:\n{msg}")

    def _update_summary(self):
        s = summary(self._rows)
        self.grp_summary.setTitle(f"Сводка — {self.lbl_file.text().split('/')[-1].split(chr(92))[-1]}")
        self.lbl_total._val_label.setText(str(s["total"]))
        self.lbl_ok._val_label.setText(str(s["importable"]))
        self.lbl_extracted._val_label.setText(str(s["extracted"]))
        self.lbl_dup._val_label.setText(str(s["duplicate"]))
        self.lbl_nophone._val_label.setText(str(s["no_phone"]))
        self.lbl_empty._val_label.setText(str(s["empty"]))

    def _populate_table(self):
        show_statuses = set()
        if self.chk_show_ok.isChecked():
            show_statuses.add(ROW_OK)
        if self.chk_show_ext.isChecked():
            show_statuses.add(ROW_EXTRACTED)
        if self.chk_show_dup.isChecked():
            show_statuses.add(ROW_DUPLICATE)
        if self.chk_show_np.isChecked():
            show_statuses.add(ROW_NO_PHONE)
        if self.chk_show_emp.isChecked():
            show_statuses.add(ROW_EMPTY)

        visible = [r for r in self._rows if r.status in show_statuses]

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible))

        for i, row in enumerate(visible):
            bg = QColor(ROW_STATUS_COLORS.get(row.status, "#FFFFFF"))
            br = QBrush(bg)

            importable = row.status in (ROW_OK, ROW_EXTRACTED)

            # Чекбокс
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if importable else Qt.Unchecked)
            if not importable:
                chk.setFlags(Qt.ItemIsEnabled)  # нельзя включить
            chk.setBackground(br)
            self.table.setItem(i, _COL_CHK, chk)

            def cell(text: str, bold=False) -> QTableWidgetItem:
                item = QTableWidgetItem(str(text) if text else "")
                item.setBackground(br)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if bold:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                return item

            status_lbl = ROW_STATUS_LABELS.get(row.status, row.status)
            dup_hint = f" (= строка {row.dup_of})" if row.dup_of else ""

            self.table.setItem(i, _COL_NUM,  cell(row.row_num))
            self.table.setItem(i, _COL_STS,  cell(status_lbl + dup_hint))
            self.table.setItem(i, _COL_NAME, cell(row.name))
            self.table.setItem(i, _COL_PHONE,cell(row.phone, bold=bool(row.phone)))
            self.table.setItem(i, _COL_ORIG, cell(row.phone_raw))
            self.table.setItem(i, _COL_COMP, cell(row.company))
            self.table.setItem(i, _COL_POS,  cell(row.position))
            self.table.setItem(i, _COL_NOTE, cell(row.call_note))

            self.table.setRowHeight(i, 24)

        self.table.itemChanged.connect(self._on_check_changed)
        self._update_selected_count()

    def _apply_filter(self):
        # Отключить сигнал на время перерисовки
        try:
            self.table.itemChanged.disconnect(self._on_check_changed)
        except Exception:
            pass
        self._populate_table()

    def _on_check_changed(self, item):
        if item.column() == _COL_CHK:
            self._update_selected_count()

    def _update_selected_count(self):
        count = 0
        for i in range(self.table.rowCount()):
            chk = self.table.item(i, _COL_CHK)
            if chk and chk.checkState() == Qt.Checked:
                count += 1
        self.lbl_selected.setText(f"Выбрано к импорту: {count}")

    def _select_all_ok(self):
        try:
            self.table.itemChanged.disconnect(self._on_check_changed)
        except Exception:
            pass
        for i in range(self.table.rowCount()):
            chk = self.table.item(i, _COL_CHK)
            if chk and (chk.flags() & Qt.ItemIsUserCheckable):
                status_item = self.table.item(i, _COL_STS)
                if status_item:
                    st = status_item.text()
                    if "OK" in st or "извлечён" in st:
                        chk.setCheckState(Qt.Checked)
        self.table.itemChanged.connect(self._on_check_changed)
        self._update_selected_count()

    def _uncheck_all(self):
        try:
            self.table.itemChanged.disconnect(self._on_check_changed)
        except Exception:
            pass
        for i in range(self.table.rowCount()):
            chk = self.table.item(i, _COL_CHK)
            if chk and (chk.flags() & Qt.ItemIsUserCheckable):
                chk.setCheckState(Qt.Unchecked)
        self.table.itemChanged.connect(self._on_check_changed)
        self._update_selected_count()

    # ─── ИМПОРТ ──────────────────────────────────────────────────────────────

    def _on_import(self):
        if self._user_id is None:
            QMessageBox.warning(self, "Ошибка", "Не определён пользователь для импорта")
            return

        # Собрать отмеченные строки (по row_num)
        checked_row_nums = set()
        for i in range(self.table.rowCount()):
            chk = self.table.item(i, _COL_CHK)
            num = self.table.item(i, _COL_NUM)
            if chk and chk.checkState() == Qt.Checked and num:
                try:
                    checked_row_nums.add(int(num.text()))
                except Exception:
                    pass

        if not checked_row_nums:
            QMessageBox.information(self, "", "Не выбрано ни одной строки")
            return

        to_import = [r for r in self._rows if r.row_num in checked_row_nums]

        # Финальная дедупликация перед импортом (на случай если выбрали оба дубля)
        seen = set()
        unique_rows = []
        for r in to_import:
            key = r.phone.split("\n")[0]  # дедупликация по первому номеру
            if key not in seen:
                seen.add(key)
                unique_rows.append(r)

        skipped_dups = len(to_import) - len(unique_rows)

        reply = QMessageBox.question(
            self, "Подтверждение импорта",
            f"Будет импортировано: {len(unique_rows)} контактов.\n"
            + (f"Пропущено дублей: {skipped_dups}\n" if skipped_dups else "")
            + "\nПроверка дубликатов с уже существующими записями также выполняется.\n\nПродолжить?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        # Конвертировать в формат для database.import_contacts_bulk
        import database as db
        import auth

        rows_for_db = []
        for r in unique_rows:
            rows_for_db.append({
                "name":         r.name,
                "phone":        r.phone,
                "company":      r.company,
                "position":     r.position,
                "contact_type": r.contact_type,
                "comment":      r.call_note,   # старые заметки → комментарий
            })

        # Проверка на дубли с БД (сравниваем по первому номеру)
        existing = db.get_contacts()
        existing_phones = set()
        for c in existing:
            for p in c["phone"].split("\n"):
                existing_phones.add(p.strip())
        rows_for_db = [r for r in rows_for_db if r["phone"].split("\n")[0] not in existing_phones]
        db_dups = len(unique_rows) - len(rows_for_db)

        try:
            count = db.import_contacts_bulk(rows_for_db, self._user_id)
            db.log_action(self._user_id, "SMART_IMPORT",
                          f"импортировано={count} пропущено_дублей={skipped_dups + db_dups}")

            msg = f"Успешно импортировано: {count} контактов."
            if skipped_dups + db_dups:
                msg += f"\nПропущено дублей: {skipped_dups + db_dups}"
            QMessageBox.information(self, "Импорт завершён", msg)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))
