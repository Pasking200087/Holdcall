"""
ui_about.py — Диалог "О программе"
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont

from config import APP_NAME, APP_VERSION


class _LogoHeader(QWidget):
    H = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.H)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        p.fillRect(0, 0, W, H, QColor("#2C3E50"))

        from ui_splash import draw_logo
        size = 72
        lx = (W - size) // 2
        ly = (H - size) // 2
        draw_logo(p, lx, ly, size)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(380, 370)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Шапка с логотипом
        root.addWidget(_LogoHeader(self))

        # Белая область с информацией
        body = QWidget()
        body.setStyleSheet("background-color: #FFFFFF;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(30, 22, 30, 24)
        bl.setSpacing(0)

        # Название
        name_lbl = QLabel(APP_NAME)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #2C3E50; font-family: 'Segoe UI';"
        )
        bl.addWidget(name_lbl)

        bl.addSpacing(6)

        # Версия
        ver_lbl = QLabel(f"Версия {APP_VERSION}")
        ver_lbl.setAlignment(Qt.AlignCenter)
        ver_lbl.setStyleSheet("font-size: 13px; color: #7F8C8D;")
        bl.addWidget(ver_lbl)

        bl.addSpacing(20)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #E8ECF0;")
        bl.addWidget(line)

        bl.addSpacing(18)

        # Разработчик
        dev_title = QLabel("Разработчик")
        dev_title.setAlignment(Qt.AlignCenter)
        dev_title.setStyleSheet("font-size: 11px; color: #95A5A6; letter-spacing: 1px;")
        bl.addWidget(dev_title)

        bl.addSpacing(6)

        dev_name = QLabel("Кирилл Pasking Брус")
        dev_name.setAlignment(Qt.AlignCenter)
        dev_name.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #2C3E50; font-family: 'Segoe UI';"
        )
        bl.addWidget(dev_name)

        bl.addSpacing(20)

        # Copyright
        copy_lbl = QLabel("© 2025 HoldCall. Все права защищены.")
        copy_lbl.setAlignment(Qt.AlignCenter)
        copy_lbl.setStyleSheet("font-size: 11px; color: #BDC3C7;")
        bl.addWidget(copy_lbl)

        bl.addSpacing(20)

        # Кнопка ОК
        btn = QPushButton("ОК")
        btn.setFixedHeight(38)
        btn.clicked.connect(self.accept)
        bl.addWidget(btn)

        root.addWidget(body)
