"""Diálogo genérico de valores (números, sim/não e listas) para comandos com poucos parâmetros."""
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QSpinBox,
    QVBoxLayout,
)


class ValoresDialog(QDialog):
    """campos: [(chave, rótulo, padrão, opções)] — opções: (min, max, casas, sufixo) para números, None para
    sim/não (padrão bool) ou lista de (valor, texto) para escolha."""

    def __init__(self, parent, titulo, campos, nota=""):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        v = QVBoxLayout(self)
        if nota:
            lb = QLabel(nota)
            lb.setWordWrap(True)
            v.addWidget(lb)
        f = QFormLayout()
        self.w = {}
        for chave, rotulo, padrao, op in campos:
            if isinstance(padrao, str) and not isinstance(op, list):
                w = QLineEdit(padrao)
                w.setMinimumWidth(320)
                f.addRow(rotulo, w)
            elif isinstance(padrao, bool):
                w = QCheckBox(rotulo)
                w.setChecked(padrao)
                f.addRow(w)
            elif isinstance(op, list):
                w = QComboBox()
                for val, txt in op:
                    w.addItem(txt, val)
                w.setCurrentIndex(max(0, w.findData(padrao)))
                f.addRow(rotulo, w)
            else:
                lo, hi, casas, suf = op
                w = QSpinBox() if casas == 0 else QDoubleSpinBox()
                if casas:
                    w.setDecimals(casas)
                w.setRange(lo, hi)
                w.setSuffix(suf)
                w.setValue(padrao)
                f.addRow(rotulo, w)
            self.w[chave] = w
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def valores(self) -> dict:
        out = {}
        for k, w in self.w.items():
            out[k] = (w.isChecked() if isinstance(w, QCheckBox) else w.currentData() if isinstance(w, QComboBox)
                      else w.text() if isinstance(w, QLineEdit) else w.value())
        return out
