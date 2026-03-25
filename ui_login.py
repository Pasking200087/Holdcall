"""
ui_login.py — Окно входа в систему
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QWidget, QFrame,
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFont, QPainter, QPainterPath, QColor

from config import APP_NAME, APP_VERSION
import auth


class _HeaderWidget(QWidget):
    """Тёмная шапка с логотипом и названием приложения."""
    H = 110

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.H)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        # Фон шапки (тёмно-синий)
        p.fillRect(0, 0, W, H, QColor("#2C3E50"))

        # Логотип
        from ui_splash import draw_logo
        logo_size = 60
        lx = 28
        ly = (H - logo_size) // 2
        draw_logo(p, lx, ly, logo_size)

        # Название
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", 18, QFont.Bold)
        p.setFont(f)
        tx = lx + logo_size + 16
        p.drawText(QRectF(tx, 18, W - tx - 16, 38), Qt.AlignVCenter | Qt.AlignLeft, APP_NAME)

        # Версия
        p.setPen(QColor("#8FA8BF"))
        f2 = QFont("Segoe UI", 10)
        p.setFont(f2)
        p.drawText(QRectF(tx, 58, W - tx - 16, 22), Qt.AlignVCenter | Qt.AlignLeft,
                   f"Версия {APP_VERSION}  •  CRM для управления контактами")


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Вход")
        self.setFixedSize(400, 370)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Шапка с логотипом
        root.addWidget(_HeaderWidget(self))

        # Форма
        form = QWidget()
        form.setStyleSheet("background-color: #FFFFFF;")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(36, 26, 36, 24)
        fl.setSpacing(0)

        # Логин
        lbl_user = QLabel("Логин")
        lbl_user.setStyleSheet("font-size: 12px; color: #4A5568; font-weight: bold; margin-bottom: 4px;")
        fl.addWidget(lbl_user)
        fl.addSpacing(4)
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("Введите логин")
        self.edit_user.setFixedHeight(38)
        self.edit_user.returnPressed.connect(self._on_login)
        fl.addWidget(self.edit_user)

        fl.addSpacing(14)

        # Пароль
        lbl_pw = QLabel("Пароль")
        lbl_pw.setStyleSheet("font-size: 12px; color: #4A5568; font-weight: bold; margin-bottom: 4px;")
        fl.addWidget(lbl_pw)
        fl.addSpacing(4)
        self.edit_pw = QLineEdit()
        self.edit_pw.setEchoMode(QLineEdit.Password)
        self.edit_pw.setPlaceholderText("Введите пароль")
        self.edit_pw.setFixedHeight(38)
        self.edit_pw.returnPressed.connect(self._on_login)
        fl.addWidget(self.edit_pw)

        fl.addSpacing(8)

        # Ошибка
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(
            "color: #E74C3C; font-size: 12px; min-height: 18px;"
        )
        self.lbl_error.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.lbl_error)

        fl.addSpacing(10)

        # Кнопка входа
        btn = QPushButton("Войти")
        btn.setObjectName("success")
        btn.setFixedHeight(40)
        btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; border-radius: 6px;"
            " font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #219A52; }"
            "QPushButton:pressed { background-color: #1A7A41; }"
        )
        btn.clicked.connect(self._on_login)
        fl.addWidget(btn)

        fl.addSpacing(10)

        # Подсказка
        hint = QLabel("При первом запуске: owner / owner")
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignCenter)
        fl.addWidget(hint)

        root.addWidget(form)

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
