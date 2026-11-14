"""Diálogo de criação/edição de texto (Etapa 7)."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFontComboBox, QFormLayout,
    QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout,
)

from ..texto import ALINHAMENTOS, TextoParams, font_available
from ..variaveis import renderizar, tem_marcadores


class TextDialog(QDialog):
    def __init__(self, parent, initial: TextoParams, ctx=None):
        super().__init__(parent)
        self._ctx = ctx or {}
        self.setWindowTitle("Texto")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        self.text = QPlainTextEdit(initial.texto)
        self.text.setAccessibleName("Conteúdo do texto")
        self.text.setPlaceholderText("Digite o texto (Enter cria nova linha)")
        self.text.setFixedHeight(90)
        v.addWidget(self.text)
        form = QFormLayout()
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(initial.fonte))
        form.addRow("Fonte", self.font)
        self.missing = QLabel()
        self.missing.setObjectName("banner")
        self.missing.setWordWrap(True)
        form.addRow("", self.missing)
        self.height = QDoubleSpinBox()
        self.height.setRange(0.5, 1000)
        self.height.setDecimals(2)
        self.height.setSuffix(" mm")
        self.height.setValue(initial.altura_mm)
        self.height.setToolTip("Altura do X maiúsculo. Acentos e letras como g/ç passam desta medida.")
        form.addRow("Altura (X maiúsculo)", self.height)
        style = QHBoxLayout()
        self.bold, self.italic = QCheckBox("Negrito"), QCheckBox("Itálico")
        self.bold.setChecked(initial.negrito)
        self.italic.setChecked(initial.italico)
        style.addWidget(self.bold)
        style.addWidget(self.italic)
        style.addStretch(1)
        form.addRow("Estilo", style)
        self.align = QComboBox()
        self.align.addItems([a.capitalize() for a in ALINHAMENTOS])
        self.align.setCurrentIndex(ALINHAMENTOS.index(initial.alinhamento))
        form.addRow("Alinhamento", self.align)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(50, 400)
        self.spacing.setDecimals(0)
        self.spacing.setSuffix(" %")
        self.spacing.setValue(initial.espacamento * 100)
        form.addRow("Entrelinha", self.spacing)
        self.variavel = QCheckBox("Texto variável (marcadores {n}, {n:3}, {data}, {hora}, {Coluna})")
        self.variavel.setChecked(initial.variavel)
        self.variavel.setToolTip("Os marcadores são trocados pelo contador, data/hora e valores da planilha "
                                 "(painel Texto variável)")
        form.addRow("", self.variavel)
        self.resultado = QLabel()
        self.resultado.setWordWrap(True)
        form.addRow("Resultado agora", self.resultado)
        v.addLayout(form)
        self.variavel.toggled.connect(self._validate)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok = buttons.button(QDialogButtonBox.Ok)
        v.addWidget(buttons)
        self.text.textChanged.connect(self._validate)
        self._initial_font = initial.fonte
        self._validate()
        self.text.setFocus()

    def _validate(self):
        self.ok.setEnabled(bool(self.text.toPlainText().strip()))
        modelo = self.text.toPlainText()
        if self.variavel.isChecked():
            final, faltando = renderizar(modelo, self._ctx)
            aviso = f"  (sem valor: {', '.join(faltando)})" if faltando else ""
            self.resultado.setText((final or "—").replace("\n", " ⏎ ") + aviso)
        elif tem_marcadores(modelo):
            self.resultado.setText("Há marcadores {…} no texto: marque “Texto variável” para preenchê-los.")
        else:
            self.resultado.setText("(texto fixo)")
        absent = not font_available(self._initial_font)
        self.missing.setVisible(absent)
        if absent:
            self.missing.setText(f"A fonte “{self._initial_font}” não está instalada. Escolha outra fonte.")

    def params(self) -> TextoParams:
        return TextoParams(self.text.toPlainText(), self.font.currentFont().family(), self.height.value(),
                           self.bold.isChecked(), self.italic.isChecked(),
                           ALINHAMENTOS[self.align.currentIndex()], self.spacing.value() / 100,
                           self.variavel.isChecked())
