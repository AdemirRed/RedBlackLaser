"""Inserir forma com medidas exatas: círculo (diâmetro ou raio), elipse, retângulo (com raio de canto), polígono."""
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout,
)

from .. import geometria as g
from .. import camadas as cm
from .. import formas as fm

TIPOS = (("ellipse", "Círculo"), ("ellipse_wh", "Elipse"), ("rect", "Retângulo"), ("polygon", "Polígono"),
         ("star", "Estrela"))


def _mm(lo=0.0, hi=10000.0, val=0.0):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(3)
    s.setSuffix(" mm")
    s.setValue(val)
    s.setKeyboardTracking(False)
    return s


class FormaDialog(QDialog):
    def __init__(self, parent, camada="C01"):
        super().__init__(parent)
        self.setWindowTitle("Forma com medidas exatas")
        v = QVBoxLayout(self)
        f = self.form = QFormLayout()
        self.tipo = QComboBox()
        for k, t in TIPOS:
            self.tipo.addItem(t, k)
        self.diametro, self.raio = _mm(0.01, 10000, 50), _mm(0.005, 5000, 25)
        self.diametro.setToolTip("Ø — o raio acompanha (metade)")
        self.largura, self.altura = _mm(0.01, 10000, 60), _mm(0.01, 10000, 40)
        self.raio_canto = _mm(0, 5000, 0)
        self.lados = QSpinBox()
        self.lados.setRange(3, 64)
        self.lados.setValue(6)
        self.cx, self.cy = _mm(-10000, 10000, g.BED_W / 2), _mm(-10000, 10000, g.BED_H / 2)
        self.camada = QComboBox()
        self.camada.addItems(cm.IDS)
        self.camada.setCurrentText(camada)
        f.addRow("Tipo", self.tipo)
        f.addRow("Diâmetro (Ø)", self.diametro)
        f.addRow("Raio", self.raio)
        f.addRow("Largura", self.largura)
        f.addRow("Altura", self.altura)
        f.addRow("Raio dos cantos", self.raio_canto)
        f.addRow("Lados / pontas", self.lados)
        self.razao = QSpinBox()
        self.razao.setRange(5, 95)
        self.razao.setValue(50)
        self.razao.setSuffix(" %")
        self.razao.setToolTip("Raio interno da estrela em % do externo")
        f.addRow("Raio interno", self.razao)
        f.addRow("Centro X", self.cx)
        f.addRow("Centro Y", self.cy)
        f.addRow("Camada", self.camada)
        v.addLayout(f)
        self.info = QLabel()
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)
        self._sync = False
        self.diametro.valueChanged.connect(lambda d: self._par(self.raio, d / 2))
        self.raio.valueChanged.connect(lambda r: self._par(self.diametro, r * 2))
        self.tipo.currentIndexChanged.connect(self._mostrar_campos)
        for w in (self.largura, self.altura, self.raio_canto, self.diametro):
            w.valueChanged.connect(self._mostrar_campos)
        self._mostrar_campos()

    def _par(self, outro, valor):
        if not self._sync:
            self._sync = True
            outro.setValue(valor)
            self._sync = False

    def _mostrar_campos(self, *_):
        k = self.tipo.currentData()
        vis = {self.diametro: k in ("ellipse", "polygon", "star"), self.raio: k in ("ellipse", "polygon", "star"),
               self.largura: k in ("ellipse_wh", "rect"), self.altura: k in ("ellipse_wh", "rect"),
               self.raio_canto: k == "rect", self.lados: k in ("polygon", "star"), self.razao: k == "star"}
        for w, on in vis.items():
            self.form.setRowVisible(w, on)
        txt = {"ellipse": "Círculo: digite o diâmetro OU o raio.",
               "polygon": "Polígono: diâmetro do círculo que passa pelos vértices.",
               "rect": "Raio maior que o possível é limitado à metade do lado menor."}.get(k, "")
        self.info.setText(txt + " Centro em coordenadas da mesa (origem inferior esquerda).")

    def forma(self):
        """(QPainterPath em mm de documento, tipo para o nome, camada)."""
        k = self.tipo.currentData()
        c = QPointF(self.cx.value(), g.BED_H - self.cy.value())
        if k == "star":
            return (fm.star_path(c, self.raio.value(), self.lados.value(), self.razao.value() / 100), "star",
                    self.camada.currentText())
        if k == "polygon":
            return fm.polygon_path(c, self.raio.value(), self.lados.value()), "polygon", self.camada.currentText()
        w, h = (self.diametro.value(),) * 2 if k == "ellipse" else (self.largura.value(), self.altura.value())
        r = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        if k == "rect":
            return fm.arredondar(fm.rect_path(r), self.raio_canto.value())[0], "rect", self.camada.currentText()
        return fm.ellipse_path(r), "ellipse", self.camada.currentText()
