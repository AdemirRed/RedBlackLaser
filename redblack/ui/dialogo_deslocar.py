"""Diálogo de deslocar formas (offset)."""
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QVBoxLayout

DIRECOES = (("fora", "Para fora"), ("dentro", "Para dentro"), ("ambos", "Ambos"))
CANTOS = (("redondo", "Redondo"), ("canto", "Canto vivo"), ("bisel", "Bisel"))


class DeslocarDialog(QDialog):
    def __init__(self, parent, inicial=(2.0, "fora", "redondo", False)):
        super().__init__(parent)
        self.setWindowTitle("Deslocar formas")
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.dist = QDoubleSpinBox()
        self.dist.setRange(0.001, 1000)
        self.dist.setDecimals(3)
        self.dist.setSuffix(" mm")
        self.direcao, self.canto = QComboBox(), QComboBox()
        for cb, itens in ((self.direcao, DIRECOES), (self.canto, CANTOS)):
            for k, t in itens:
                cb.addItem(t, k)
        self.apagar = QCheckBox("Excluir as formas originais")
        f.addRow("Distância", self.dist)
        f.addRow("Direção", self.direcao)
        f.addRow("Estilo de canto", self.canto)
        f.addRow(self.apagar)
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)
        d, dr, c, ap = inicial
        self.dist.setValue(d)
        self.direcao.setCurrentIndex(self.direcao.findData(dr))
        self.canto.setCurrentIndex(self.canto.findData(c))
        self.apagar.setChecked(ap)

    def valores(self):
        return self.dist.value(), self.direcao.currentData(), self.canto.currentData(), self.apagar.isChecked()
