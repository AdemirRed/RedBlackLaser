"""Gerador de frisos para dobra, com cálculo do comprimento planificado a partir do diâmetro."""
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QSpinBox,
    QVBoxLayout,
)

from .. import geometria as g
from .. import camadas as cm
from .. import frisos as fr


def _mm(lo, hi, val, dec=3):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSuffix(" mm")
    s.setValue(val)
    return s


class FrisosDialog(QDialog):
    def __init__(self, parent, inicial: fr.Frisos = fr.Frisos()):
        super().__init__(parent)
        self.setWindowTitle("Frisos para dobra")
        v = QVBoxLayout(self)
        aviso = QLabel("Painel com rebaixos paralelos para curvar o material. A profundidade NÃO vem do desenho: "
                       "calibre potência/velocidade da camada dos frisos com a matriz de testes e cupons.")
        aviso.setWordWrap(True)
        v.addWidget(aviso)

        calc = QGroupBox("Calcular o comprimento pelo diâmetro (cilindro)")
        calc.setCheckable(True)
        calc.setChecked(False)
        fc = QFormLayout(calc)
        self.di, self.t, self.e = _mm(1, 2000, 100, 2), _mm(0.1, 50, 3, 2), _mm(0, 50, 0.8, 2)
        fc.addRow("Diâmetro interno (Di)", self.di)
        fc.addRow("Espessura do material (t)", self.t)
        fc.addRow("Pele que sobra no friso (e)", self.e)
        self.lbl_calc = QLabel()
        fc.addRow(self.lbl_calc)
        self.calc = calc
        v.addWidget(calc)

        grp = QGroupBox("Painel e frisos")
        f = QFormLayout(grp)
        self.largura, self.altura = _mm(1, 10000, inicial.largura_mm, 4), _mm(1, 10000, inicial.altura_mm)
        self.qtd = QSpinBox()
        self.qtd.setRange(1, fr.MAX_FRISOS)
        self.qtd.setValue(inicial.quantidade)
        self.w = _mm(0.01, 50, inicial.largura_friso_mm)
        self.margem = _mm(0, 5000, inicial.margem_mm)
        self.margem.setToolTip("0 = frisos de ponta a ponta na altura")
        self.x, self.y = _mm(0, 10000, inicial.x_mm, 2), _mm(0, 10000, g.BED_H - inicial.y_mm, 2)
        f.addRow("Comprimento planificado", self.largura)
        f.addRow("Altura", self.altura)
        f.addRow("Quantidade de frisos", self.qtd)
        f.addRow("Largura do friso", self.w)
        f.addRow("Margem em cima e embaixo", self.margem)
        f.addRow("X do canto superior esquerdo", self.x)
        f.addRow("Y do canto superior esquerdo", self.y)
        v.addWidget(grp)

        cam = QGroupBox("Camadas")
        fl = QFormLayout(cam)
        self.contorno = QCheckBox("Incluir o contorno (recorte externo)")
        self.contorno.setChecked(True)
        self.cam_contorno, self.cam_frisos = QComboBox(), QComboBox()
        self.cam_contorno.addItems(cm.IDS)
        self.cam_frisos.addItems(cm.IDS)
        self.cam_contorno.setCurrentText("C01")
        self.cam_frisos.setCurrentText("C02")
        fl.addRow(self.contorno)
        fl.addRow("Camada do contorno (corte)", self.cam_contorno)
        fl.addRow("Camada dos frisos (preenchimento)", self.cam_frisos)
        v.addWidget(cam)

        self.info = QLabel()
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        self.botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        v.addWidget(self.botoes)
        for s in (self.di, self.t, self.e):
            s.valueChanged.connect(self._calcular)
        calc.toggled.connect(self._calcular)
        for s in (self.largura, self.altura, self.qtd, self.w, self.margem, self.x, self.y):
            s.valueChanged.connect(self._atualizar)
        for c in (self.cam_contorno, self.cam_frisos):
            c.currentIndexChanged.connect(self._atualizar)
        self.contorno.toggled.connect(self._atualizar)
        self._calcular()

    def _calcular(self, *_):
        L = fr.desenvolvimento(self.di.value(), self.t.value(), self.e.value())
        self.lbl_calc.setText(f"L = π × (Di + 2t − e) = {L:.4f} mm".replace(".", ","))
        self.largura.setEnabled(not self.calc.isChecked())
        if self.calc.isChecked():
            self.largura.setValue(L)
        self._atualizar()

    def frisos(self) -> fr.Frisos:
        return fr.Frisos(self.largura.value(), self.altura.value(), self.qtd.value(), self.w.value(),
                         self.margem.value(), self.x.value(), g.BED_H - self.y.value())

    def resultado(self):
        """(Frisos, camada do contorno ou None, camada dos frisos)."""
        return (self.frisos(), self.cam_contorno.currentText() if self.contorno.isChecked() else None,
                self.cam_frisos.currentText())

    def _atualizar(self, *_):
        f = self.frisos()
        e = fr.erros(f, g.BED_W, g.BED_H)
        if self.contorno.isChecked() and self.cam_contorno.currentText() == self.cam_frisos.currentText():
            e.append("contorno e frisos precisam de camadas diferentes")
        txt = f"Passo entre centros: {f.passo:.6f} mm.".replace(".", ",") if not e else ""
        self.info.setText(txt + ("; ".join(e)).capitalize())
        self.botoes.button(QDialogButtonBox.Ok).setEnabled(not e)
