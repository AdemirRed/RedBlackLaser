"""Escolher o melhor quadrado de uma matriz já gravada e salvá-lo como material."""
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from .. import matriz as mz


def _fmt(v):
    return f"{v:g}".replace(".", ",")


class ResultadoMatrizDialog(QDialog):
    def __init__(self, parent, m: mz.Matriz, nome="", espessura=0.0):
        super().__init__(parent)
        self.setWindowTitle("Salvar material da matriz de testes")
        self.m, self.escolha = m, None
        v = QVBoxLayout(self)
        topo = QHBoxLayout()
        self.lbl_matriz = QLabel()
        self.lbl_matriz.setWordWrap(True)
        topo.addWidget(self.lbl_matriz, 1)
        self.btn_arquivo = QPushButton("Abrir outra matriz (.gcode)…")
        self.btn_arquivo.setToolTip("Lê os parâmetros gravados no cabeçalho de um G-code de matriz do RedBlack")
        self.btn_arquivo.clicked.connect(self._abrir_arquivo)
        topo.addWidget(self.btn_arquivo)
        v.addLayout(topo)
        v.addWidget(QLabel("Clique no quadrado que ficou melhor na peça gravada (mesma posição da grade):"))
        self.area = QWidget()
        self.grade = QGridLayout(self.area)
        self.grade.setSpacing(3)
        v.addWidget(self.area)
        self.lbl_escolha = QLabel("Nenhum quadrado escolhido.")
        v.addWidget(self.lbl_escolha)
        form = QFormLayout()
        self.nome = QLineEdit(nome)
        self.nome.setPlaceholderText("ex.: MDF cru da loja X")
        self.nome.setMaxLength(80)
        self.espessura = QDoubleSpinBox()
        self.espessura.setRange(0, 100)
        self.espessura.setDecimals(1)
        self.espessura.setSuffix(" mm")
        self.espessura.setValue(espessura)
        self.espessura.setToolTip("0 = gravação de superfície")
        self.nota = QLineEdit()
        self.nota.setPlaceholderText("opcional (ex.: foco, lote do material, resultado)")
        self.nota.setMaxLength(200)
        form.addRow("Nome do material", self.nome)
        form.addRow("Espessura", self.espessura)
        form.addRow("Observação", self.nota)
        v.addLayout(form)
        self.botoes = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.btn_ok = self.botoes.addButton("Salvar material", QDialogButtonBox.AcceptRole)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        v.addWidget(self.botoes)
        self.nome.textChanged.connect(self._atualizar)
        self.grupo = None
        self._montar(m)

    def _montar(self, m):
        self.m, self.escolha = m, None
        while self.grade.count():
            self.grade.takeAt(0).widget().deleteLater()
        tipo = "corte/contorno" if m.modo == "linha" else "gravação"
        self.lbl_matriz.setText(f"Matriz: {tipo}, {m.passadas} passada(s), air assist "
                                f"{'ligado' if m.air else 'desligado'}"
                                + (f", intervalo {_fmt(m.intervalo_mm)} mm" if m.modo != "linha" else "") + ".")
        self.grade.addWidget(QLabel(f"{m.unidade_linhas()} \\ %"), 0, 0)
        for c, pot in enumerate(m.potencias()):
            self.grade.addWidget(QLabel(_fmt(pot)), 0, c + 1)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        for r, val in enumerate(m.valores_linhas()):
            self.grade.addWidget(QLabel(_fmt(val)), r + 1, 0)
            for c, pot in enumerate(m.potencias()):
                b = QToolButton()
                b.setCheckable(True)
                b.setFixedSize(30, 30)
                dica = f"{_fmt(pot)} % · {_fmt(val)} {m.unidade_linhas()}"
                b.setToolTip(dica)
                b.setAccessibleName(f"Quadrado linha {r + 1}, coluna {c + 1}: {dica}")
                b.setStyleSheet("QToolButton{background:#3a2a1a;border:1px solid #6b5a48}"
                                "QToolButton:checked{background:#e0313b;border:2px solid #fff}")
                self.grupo.addButton(b, r * m.colunas + c)
                self.grade.addWidget(b, r + 1, c + 1)
        for k in range(self.grade.columnCount() + 1):
            self.grade.setColumnStretch(k, 0)
        self.grade.setColumnStretch(m.colunas + 1, 1)  # sobra de espaço à direita: grade junto dos rótulos
        self.grupo.idClicked.connect(self.escolher)
        self.lbl_escolha.setText("Nenhum quadrado escolhido.")
        self._atualizar()

    def escolher(self, ident):
        r, c = divmod(ident, self.m.colunas)
        self.escolha = (r, c)
        self.grupo.button(ident).setChecked(True)
        vel, pot, pas, itv = self.m.parametros(r, c)
        self.lbl_escolha.setText(f"Escolhido: {_fmt(pot)} % · {_fmt(vel)} mm/min · {pas} passada(s) · intervalo "
                                 f"{_fmt(itv)} mm (linha {r + 1}, coluna {c + 1}).")
        self._atualizar()

    def _atualizar(self, *_):
        self.btn_ok.setEnabled(self.escolha is not None and bool(self.nome.text().strip()))

    def pedir_arquivo(self) -> str:
        """Substituível nos testes."""
        return QFileDialog.getOpenFileName(self, "Abrir matriz de testes", "", "G-code (*.gcode *.nc *.gc)")[0]

    def _abrir_arquivo(self):
        path = self.pedir_arquivo()
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                cabeca = "".join(f.readline() for _ in range(20))
            self._montar(mz.de_gcode(cabeca))
        except (OSError, ValueError) as e:
            self.lbl_escolha.setText(f"Não foi possível ler a matriz: {e}")

    def resultado(self):
        """(linha, coluna, nome, espessura, observação)."""
        r, c = self.escolha
        return r, c, self.nome.text(), self.espessura.value(), self.nota.text()
