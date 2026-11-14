"""Gera redblack/ui/app.ico e app.png: ícone próprio do RedBlack Laser (losango vermelho e preto + feixe).

Executar: python tools/gerar_icone.py
"""
import os
import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPolygonF

DEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "redblack", "ui")


def desenhar(n: int) -> QImage:
    img = QImage(n, n, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(n / 256, n / 256)
    fundo = QPainterPath()
    fundo.addRoundedRect(8, 8, 240, 240, 48, 48)
    p.fillPath(fundo, QColor("#16181c"))
    # losango: metade esquerda vermelha, direita preta com borda
    esq = QPolygonF([QPointF(128, 40), QPointF(40, 128), QPointF(128, 216)])
    dir_ = QPolygonF([QPointF(128, 40), QPointF(216, 128), QPointF(128, 216)])
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#e0313b"))
    p.drawPolygon(esq)
    p.setBrush(QColor("#000000"))
    p.drawPolygon(dir_)
    p.setPen(QPen(QColor("#e0313b"), 6))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(128, 40), QPointF(216, 128), QPointF(128, 216), QPointF(40, 128)]))
    # feixe do laser descendo até um ponto brilhante
    p.setPen(QPen(QColor("#ffcc33"), 10, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(128, 24), QPointF(128, 128))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffcc33"))
    p.drawEllipse(QPointF(128, 128), 16, 16)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    ok = desenhar(256).save(os.path.join(DEST, "app.ico")) and desenhar(256).save(os.path.join(DEST, "app.png"))
    print("ok" if ok else "falhou")
    sys.exit(0 if ok else 1)
