"""
make_icon.py — Генерирует icon.ico из логотипа приложения.
Запускать перед сборкой: python make_icon.py
"""
import struct
import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice

# Нужен QApplication для отрисовки
_app = QApplication.instance() or QApplication(sys.argv)

from ui_splash import draw_logo


def _render(size: int) -> bytes:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_logo(p, 0, 0, size)
    p.end()

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def save_ico(sizes, out_path):
    images = [_render(s) for s in sizes]

    # ICO header: reserved=0, type=1, count
    data = struct.pack("<HHH", 0, 1, len(images))

    # Directory entries (16 bytes each)
    offset = 6 + 16 * len(images)
    for s, img in zip(sizes, images):
        w = s if s < 256 else 0
        data += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(img), offset)
        offset += len(img)

    # Image data
    for img in images:
        data += img

    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Сохранён: {out_path}  ({len(images)} размеров: {sizes})")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "icon.ico")
    save_ico([16, 24, 32, 48, 64, 128, 256], out)
