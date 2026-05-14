"""
ui_setup.py — Диалог выбора сетевой папки с базой данных (первый запуск / смена пути).
"""
import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt


class SetupDialog(QDialog):
    """Показывается при первом запуске или при смене пути к базе."""

    def __init__(self, current_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка пути к базе данных")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui(current_path)

    def _build_ui(self, current_path: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Укажите папку с базой данных")
        title.setObjectName("title")
        layout.addWidget(title)

        hint = QLabel(
            "База данных хранится на сетевом диске и общая для всех пользователей.\n"
            "Укажите путь к папке, где лежит (или будет создан) файл baza.db.\n"
            "Пример: \\\\SERVER\\share\\baza  или  Z:\\baza"
        )
        hint.setWordWrap(True)
        hint.setObjectName("subtitle")
        layout.addWidget(hint)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(current_path)
        self._path_edit.setPlaceholderText("Путь к сетевой папке...")
        self._path_edit.setMinimumWidth(320)
        browse_btn = QPushButton("Обзор...")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Сохранить")
        ok_btn.setFixedWidth(120)
        ok_btn.setObjectName("success")
        ok_btn.clicked.connect(self._accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с базой данных", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(os.path.normpath(path))

    def _accept(self):
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к папке.")
            return
        if not os.path.isdir(path):
            ans = QMessageBox.question(
                self, "Папка не найдена",
                f"Папка не существует или недоступна:\n{path}\n\nСохранить всё равно?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return
        import config
        config.set_data_dir(path)
        self.accept()

    def selected_path(self) -> str:
        return self._path_edit.text().strip()
