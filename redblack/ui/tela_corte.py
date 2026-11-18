"""Tela de corte: só para acompanhar o trabalho na máquina (mesa grande, tempo, Pausar e PARAR grandes).

A edição continua na outra tela (o desenho pode ser mexido durante o trabalho, mas o trabalho em andamento usa o
G-code congelado na hora do Iniciar: a mudança só vale ao começar de novo).
"""
import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import (QFrame, QGraphicsView, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from .. import tempo_trabalho as tt


class VistaCorte(QGraphicsView):
    """A mesma cena da edição, só para ver: mira do cabeçote e o caminho já feito com laser (verde)."""

    def __init__(self, cena):
        super().__init__(cena)
        self.setInteractive(False)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.mesa = QRectF(0, 0, 400, 400)
        self.cabecote, self.laser = None, False
        self.trilha = QPainterPath()

    def mostrar_mesa(self, mesa: QRectF):
        self.mesa = QRectF(mesa)
        self.fitInView(self.mesa.adjusted(-8, -8, 8, 8), Qt.KeepAspectRatio)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fitInView(self.mesa.adjusted(-8, -8, 8, 8), Qt.KeepAspectRatio)

    def limpar_trilha(self):
        self.trilha = QPainterPath()
        self.viewport().update()

    def adicionar_trilha(self, segmentos):
        """Trechos já feitos COM laser (tirados do próprio G-code, na ordem): ficam verdes."""
        if not segmentos:
            return
        caixa = QRectF()
        for a, b in segmentos:
            if self.trilha.elementCount() == 0 or self.trilha.currentPosition() != a:
                self.trilha.moveTo(a)
            self.trilha.lineTo(b)
            caixa = caixa.united(QRectF(a, b).normalized())
        r = self.mapFromScene(caixa).boundingRect().adjusted(-4, -4, 4, 4)
        self.viewport().update(r)

    def definir(self, ponto, laser):
        antes = self.cabecote
        self.cabecote, self.laser = ponto, laser
        lado = 26
        reg = QRegion()
        for c in (antes, ponto):  # só o pedacinho da mira e do trecho novo (a mesa inteira pesa)
            if c is not None:
                q = self.mapFromScene(c)
                reg += QRegion(q.x() - lado, q.y() - lado, 2 * lado, 2 * lado)
        self.viewport().update(reg)

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor("#2a2d33"))
        p.fillRect(self.mesa, QColor("#f3e3c3"))

    def drawForeground(self, p, rect):
        if not self.trilha.isEmpty():
            pen = QPen(QColor(30, 170, 60, 200), 3)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(self.trilha)
        if self.cabecote is not None:
            esc = self.transform().m11() or 1.0
            c, raio = self.cabecote, 10 / esc
            pen = QPen(QColor("#ff2a2a"), 2)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(QColor(255, 42, 42, 150) if self.laser else Qt.NoBrush)
            p.drawEllipse(c, raio, raio)
            p.drawLine(QPointF(c.x() - 2 * raio, c.y()), QPointF(c.x() + 2 * raio, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 2 * raio), QPointF(c.x(), c.y() + 2 * raio))


def _rotulo(texto, tam, negrito=False, cor="#e6e8ec"):
    lb = QLabel(texto)  # tamanho pelo estilo: o tema do programa passa por cima do setFont
    lb.setStyleSheet(f"color:{cor}; font-size:{tam}pt; font-weight:{'bold' if negrito else 'normal'}")
    return lb


class TelaCorte(QWidget):
    """Mesa à esquerda; à direita o estado, os tempos grandes e os botões grandes."""

    def __init__(self, cena):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.vista = VistaCorte(cena)
        h.addWidget(self.vista, 1)
        lado = QWidget()
        lado.setMinimumWidth(340)
        lado.setStyleSheet("background:#1d2026")
        v = QVBoxLayout(lado)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(8)
        self.estado = _rotulo("Nenhum trabalho", 20, True)
        self.estado.setWordWrap(True)
        v.addWidget(self.estado)
        self.camada = _rotulo("", 11, cor="#9aa3b2")
        self.camada.setWordWrap(True)
        v.addWidget(self.camada)
        v.addSpacing(10)
        self.tempos = {}
        for chave, titulo in (("decorrido", "Tempo decorrido"), ("restante", "Tempo restante"),
                              ("termino", "Termina às")):
            v.addWidget(_rotulo(titulo, 10, cor="#9aa3b2"))
            lb = _rotulo("—", 26, True, "#ffffff" if chave != "restante" else "#ffd27a")
            self.tempos[chave] = lb
            v.addWidget(lb)
        self.barra = QProgressBar()
        self.barra.setRange(0, 1000)
        self.barra.setMinimumHeight(30)
        self.barra.setFormat("%p%")
        v.addWidget(self.barra)
        self.linhas = _rotulo("", 9, cor="#9aa3b2")
        v.addWidget(self.linhas)
        v.addStretch(1)
        self.btn_pausar = QPushButton("⏸  PAUSAR")
        self.btn_pausar.setMinimumHeight(70)
        self.btn_pausar.setStyleSheet("QPushButton{background:#d79b00;color:#111;font-size:20px;font-weight:bold;"
                                      "border-radius:8px} QPushButton:disabled{background:#4a4a4a;color:#888}")
        v.addWidget(self.btn_pausar)
        self.btn_parar = QPushButton("⏹  PARAR")
        self.btn_parar.setMinimumHeight(90)
        self.btn_parar.setStyleSheet("QPushButton{background:#c62828;color:white;font-size:24px;font-weight:bold;"
                                     "border-radius:8px} QPushButton:disabled{background:#4a4a4a;color:#888}")
        self.btn_parar.setToolTip("Para tudo na hora: o laser apaga e o movimento para (reset)")
        v.addWidget(self.btn_parar)
        self.btn_ar = QPushButton("💨  Air assist")
        self.btn_ar.setCheckable(True)
        self.btn_ar.setMinimumHeight(40)
        v.addWidget(self.btn_ar)
        self.btn_voltar = QPushButton("✎  Voltar para a edição (F9)")
        self.btn_voltar.setMinimumHeight(40)
        v.addWidget(self.btn_voltar)
        rolagem = QScrollArea()  # telas baixas: os botões grandes rolam em vez de esticar a janela
        rolagem.setWidget(lado)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setFixedWidth(356)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        h.addWidget(rolagem)

    def mostrar(self, estado, decorrido=None, restante=None, progresso=0.0, camada="", linhas=""):
        self.estado.setText(estado)
        self.camada.setText(camada)
        self.tempos["decorrido"].setText(tt.fmt(decorrido) if decorrido is not None else "—")
        self.tempos["restante"].setText(tt.fmt(restante) if restante is not None else "—")
        fim = (datetime.datetime.now() + datetime.timedelta(seconds=restante)) if restante is not None else None
        self.tempos["termino"].setText(f"{fim:%H:%M}" if fim else "—")
        self.barra.setValue(int(progresso * 1000))
        self.linhas.setText(linhas)
