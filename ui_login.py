"""
ui_login.py — Окно входа в систему
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

from config import APP_NAME, APP_VERSION
import auth


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Вход")
        self.setFixedSize(380, 320)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(0)

        # Заголовок
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("subtitle")
        ver.setAlignment(Qt.AlignCenter)
        root.addWidget(ver)

        root.addSpacing(24)

        # Поля
        lbl_user = QLabel("Логин")
        root.addWidget(lbl_user)
        root.addSpacing(4)
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("Введите логин")
        self.edit_user.returnPressed.connect(self._on_login)
        root.addWidget(self.edit_user)

        root.addSpacing(12)

        lbl_pw = QLabel("Пароль")
        root.addWidget(lbl_pw)
        root.addSpacing(4)
        self.edit_pw = QLineEdit()
        self.edit_pw.setEchoMode(QLineEdit.Password)
        self.edit_pw.setPlaceholderText("Введите пароль")
        self.edit_pw.returnPressed.connect(self._on_login)
        root.addWidget(self.edit_pw)

        root.addSpacing(6)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #C0392B; font-size: 12px;")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_error)

        root.addSpacing(16)

        btn = QPushButton("Войти")
        btn.setObjectName("success")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._on_login)
        root.addWidget(btn)

        # Подсказка для первого запуска
        hint = QLabel("При первом запуске: owner / owner")
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        self.edit_user.setFocus()

    def _on_login(self):
        self.lbl_error.setText("")
        username = self.edit_user.text().strip()
        password = self.edit_pw.text()

        ok, msg = auth.verify_login(username, password)
        if ok:
            self.accept()
        else:
            self.lbl_error.setText(msg)
            self.edit_pw.clear()
            self.edit_pw.setFocus()
