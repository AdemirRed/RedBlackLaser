"""Ajustar imagem (Alt+I): original ao lado de como o laser vai gravar, com brilho, contraste, gama, modo e inverter.
Os valores ficam na camada da imagem (valem para as imagens dessa camada)."""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from .. import camadas as cm
from .. import raster

MODOS = [("limiar", "Limiar (preto e branco)"), ("pontilhado", "Pontilhado ordenado"), ("jarvis", "Jarvis"),
         ("stucki", "Stucki"), ("atkinson", "Atkinson"), ("cinza", "Escala de cinza"), ("meio_tom", "Meio-tom")]
PREVIA_PONTOS = 250_000


class _Quadro(QWidget):
    def __init__(self, titulo):
        super().__init__()
        self.titulo, self.img = titulo, None
        self.setMinimumSize(380, 340)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#bfbfbf"))
        p.setPen(QColor("#222"))
        p.drawText(QRectF(8, 4, self.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, self.titulo)
        if self.img is not None and not self.img.isNull():
            r = QRectF(self.rect()).adjusted(10, 26, -10, -10)
            esc = min(r.width() / self.img.width(), r.height() / self.img.height())
            w, h = self.img.width() * esc, self.img.height() * esc
            alvo = QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)
            p.fillRect(alvo, QColor("white"))
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)  # ver os pontos do pontilhado
            p.drawImage(alvo, self.img)
        p.end()


class DialogoAjustarImagem(QDialog):
    def __init__(self, imagem, largura_mm, altura_mm, camada: cm.Camada, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar imagem")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.imagem, self.larg, self.alt, self.base = imagem, largura_mm, altura_mm, camada
        self.modo = QComboBox()
        for k, t in MODOS:
            self.modo.addItem(t, k)
        self.modo.setCurrentIndex(max(0, [k for k, _ in MODOS].index(camada.modo_imagem)
                                      if camada.modo_imagem in dict(MODOS) else 0))
        self.brilho = self._num(-100, 100, camada.brilho_pct, " %", "Mais alto = mais claro (grava menos)")
        self.contraste = self._num(-100, 100, camada.contraste_pct, " %", "Mais alto = separa mais claro e escuro")
        self.gama = self._num(0.1, 5, camada.gama, "", "Acima de 1 clareia os meios-tons; abaixo de 1 escurece", 2)
        self.limiar = self._num(0, 100, camada.limiar_pct, " %", "Só no modo Limiar: ponto de corte preto/branco")
        self.intervalo = self._num(0.02, 2, camada.intervalo_mm, " mm", "Distância entre linhas (resolução)", 3)
        self.negativo = QCheckBox("Inverter imagem")
        self.negativo.setChecked(camada.negativo)
        form = QFormLayout()
        form.addRow("Modo", self.modo)
        form.addRow("Brilho", self.brilho)
        form.addRow("Contraste", self.contraste)
        form.addRow("Gama", self.gama)
        form.addRow("Limiar", self.limiar)
        form.addRow("Intervalo", self.intervalo)
        form.addRow(self.negativo)
        aviso = QLabel(f"Os ajustes ficam na camada {camada.id} e valem para as imagens dela.")
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color:#7a808a")
        self.dpi = QLabel()
        self.dpi.setStyleSheet("color:#7a808a")
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        lado = QVBoxLayout()
        lado.addLayout(form)
        lado.addWidget(self.dpi)
        lado.addWidget(aviso)
        lado.addStretch(1)
        lado.addWidget(botoes)
        self.original, self.processada = _Quadro("Original"), _Quadro("Como o laser vai gravar")
        self.original.img = imagem
        corpo = QHBoxLayout(self)
        corpo.addWidget(self.original, 1)
        corpo.addWidget(self.processada, 1)
        corpo.addLayout(lado)
        self.resize(1200, 600)
        self._timer = QTimer(self, singleShot=True, interval=120, timeout=self._refazer)
        for w in (self.brilho, self.contraste, self.gama, self.limiar, self.intervalo):
            w.valueChanged.connect(lambda *_: self._timer.start())
        self.modo.currentIndexChanged.connect(lambda *_: self._timer.start())
        self.negativo.toggled.connect(lambda *_: self._timer.start())
        self._refazer()

    @staticmethod
    def _num(a, b, v, suf, dica, casas=1):
        s = QDoubleSpinBox()
        s.setRange(a, b)
        s.setDecimals(casas)
        s.setValue(v)
        s.setSuffix(suf)
        s.setToolTip(dica)
        return s

    def campos(self):
        return dict(modo_imagem=self.modo.currentData(), brilho_pct=self.brilho.value(),
                    contraste_pct=self.contraste.value(), gama=self.gama.value(), limiar_pct=self.limiar.value(),
                    intervalo_mm=self.intervalo.value(), negativo=self.negativo.isChecked())

    def _refazer(self):
        c = cm.alterar(self.base, **self.campos())
        self.limiar.setEnabled(c.modo_imagem == "limiar")
        self.processada.img = raster.imagem_processada(self.imagem, self.larg, self.alt, c, PREVIA_PONTOS)
        self.dpi.setText(f"{25.4 / c.intervalo_mm:.0f} DPI · {self.larg:.1f} × {self.alt:.1f} mm".replace(".", ","))
        self.processada.update()
