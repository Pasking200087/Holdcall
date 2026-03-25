"""
ui_splash.py — Экран приветствия (сплэш-скрин) + общий логотип приложения
"""
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import (QPainter, QColor, QFont, QPen, QPainterPath,
                          QPixmap, QIcon)
from PyQt5.QtCore import Qt, QRectF


def draw_logo(painter: QPainter, x: int, y: int, size: int) -> None:
    """Рисует логотип приложения в заданной области.  Используется в сплэше, трее и заголовке."""
    painter.save()
    painter.setPen(Qt.NoPen)

    # Фоновый круг
    painter.setBrush(QColor("#1A252F"))
    painter.drawEllipse(x, y, size, size)

    # Три яруса цилиндрической БД
    cx = x + size // 2
    cyl_w = int(size * 0.58)
    ey = int(size * 0.105)
    cyl_body_h = int(size * 0.10)
    gap = int(size * 0.035)

    tiers = [
        ("#76D7EA", "#3498DB", "#2471A3"),
        ("#7DCEA0", "#27AE60", "#1E8449"),
        ("#F1948A", "#E74C3C", "#CB4335"),
    ]
    n = len(tiers)
    total_h = n * (ey + cyl_body_h) + (n - 1) * gap
    start_y = y + int((size - total_h) * 0.42)

    for i, (top_c, side_c, bot_c) in enumerate(tiers):
        cy_top = start_y + i * (ey + cyl_body_h + gap)
        rx = cx - cyl_w // 2
        painter.setBrush(QColor(side_c))
        painter.drawRect(rx, cy_top + ey // 2, cyl_w, cyl_body_h)
        painter.setBrush(QColor(bot_c))
        painter.drawEllipse(rx, cy_top + cyl_body_h, cyl_w, ey)
        painter.setBrush(QColor(top_c))
        painter.drawEllipse(rx, cy_top, cyl_w, ey)

    # Бейдж с телефоном
    br = int(size * 0.22)
    bx = x + size - br + 3
    by = y + size - br + 3
    painter.setBrush(QColor("#27AE60"))
    painter.setPen(QPen(QColor("#1A252F"), max(1, size // 45)))
    painter.drawEllipse(bx - br, by - br, br * 2, br * 2)
    painter.setPen(QColor("#FFFFFF"))
    f = QFont("Segoe UI", max(6, int(br * 0.95)))
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(QRectF(bx - br, by - br, br * 2, br * 2), Qt.AlignCenter, "☎")

    painter.restore()


def make_app_icon(size: int = 64) -> QIcon:
    """Возвращает QIcon с логотипом нужного размера."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_logo(p, 0, 0, size)
    p.end()
    return QIcon(pm)


class SplashScreen(QWidget):
    W, H = 500, 280

    def __init__(self, version: str = ""):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self._version = version
        self._progress = 0
        self._status = "Запуск..."
        self._center()

    def _center(self):
        geo = QApplication.primaryScreen().geometry()
        self.move(
            (geo.width() - self.W) // 2,
            (geo.height() - self.H) // 2,
        )

    def set_status(self, text: str, progress: int = -1):
        self._status = text
        if progress >= 0:
            self._progress = min(progress, 100)
        self.update()
        QApplication.processEvents()

    # ── painting ──────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self._draw(p)

    def _draw(self, p: QPainter):
        W, H = self.W, self.H
        TOP_H = 188

        # ── outer shadow ring ─────────────────────────────────────────────
        for i in range(4, 0, -1):
            shadow = QPainterPath()
            shadow.addRoundedRect(QRectF(i, i, W - i * 2, H - i * 2), 14, 14)
            p.fillPath(shadow, QColor(0, 0, 0, 18 * (5 - i)))

        # ── clip to rounded rect ──────────────────────────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, W, H), 14, 14)
        p.setClipPath(clip)

        # ── top section: dark navy ────────────────────────────────────────
        p.fillRect(0, 0, W, TOP_H, QColor("#2C3E50"))

        # ── bottom section: light ─────────────────────────────────────────
        p.fillRect(0, TOP_H, W, H - TOP_H, QColor("#EEF0F3"))

        # ── separator line ────────────────────────────────────────────────
        p.fillRect(0, TOP_H, W, 1, QColor("#1A252F"))

        # ── logo ──────────────────────────────────────────────────────────
        LOGO = 90
        lx = 32
        ly = (TOP_H - LOGO) // 2
        self._draw_logo(p, lx, ly, LOGO)

        # ── app name ──────────────────────────────────────────────────────
        tx = lx + LOGO + 24
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", 22, QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(tx, 34, W - tx - 20, 46),
                   Qt.AlignVCenter | Qt.AlignLeft, "База контактов")

        # ── tagline / version ─────────────────────────────────────────────
        p.setPen(QColor("#8FA8BF"))
        f2 = QFont("Segoe UI", 11)
        p.setFont(f2)
        ver_text = f"Версия {self._version}  •  CRM для управления контактами"
        p.drawText(QRectF(tx, 84, W - tx - 20, 28),
                   Qt.AlignVCenter | Qt.AlignLeft, ver_text)

        # ── divider between text rows ─────────────────────────────────────
        p.setPen(QColor("#3D5166"))
        p.drawLine(tx, 118, W - 24, 118)

        # ── bottom: status text ───────────────────────────────────────────
        p.setPen(QColor("#4A5568"))
        f3 = QFont("Segoe UI", 10)
        p.setFont(f3)
        p.drawText(QRectF(20, TOP_H + 14, W - 40, 22),
                   Qt.AlignVCenter | Qt.AlignLeft, self._status)

        # ── progress bar track ────────────────────────────────────────────
        bar_x, bar_y = 20, TOP_H + 42
        bar_w, bar_h = W - 40, 6
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#CDD1D8"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        # ── progress bar fill ─────────────────────────────────────────────
        fill = int(bar_w * self._progress / 100)
        if fill > 0:
            p.setBrush(QColor("#3498DB"))
            p.drawRoundedRect(bar_x, bar_y, fill, bar_h, 3, 3)

        # ── copyright ─────────────────────────────────────────────────────
        p.setPen(QColor("#A0AAB8"))
        f4 = QFont("Segoe UI", 9)
        p.setFont(f4)
        p.drawText(QRectF(20, H - 26, W - 40, 18),
                   Qt.AlignVCenter | Qt.AlignRight, "© 2025 HoldCall")

    # ─────────────────────────────────────────────────────────────────────

    def _draw_logo(self, p: QPainter, x: int, y: int, size: int):
        draw_logo(p, x, y, size)
