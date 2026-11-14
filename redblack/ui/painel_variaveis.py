"""Painel do texto variável: planilha CSV, linha atual, contador e lote."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

AJUDA = ("Num texto marcado como <b>variável</b>, use: <b>{n}</b> número de série · <b>{n:3}</b> com 3 dígitos "
         "(001) · <b>{data}</b> · <b>{hora}</b> · <b>{linha}</b> · <b>{Coluna}</b> valor da coluna da planilha "
         "(ex.: {Nome}). Marcador desconhecido aparece como {?…} na peça.")


class PainelVariaveis(QWidget):
    linhaEscolhida = Signal(int)
    contadorAlterado = Signal(int, int)  # contador, incremento
    avancarPedido = Signal()
    limparPedido = Signal()

    def __init__(self):
        super().__init__()
        self._sync = False
        v = QVBoxLayout(self)
        ajuda = QLabel(AJUDA)
        ajuda.setWordWrap(True)
        v.addWidget(ajuda)

        topo = QHBoxLayout()
        self.btn_csv = QPushButton("Carregar planilha CSV…")
        self.btn_csv.setToolTip("Primeira linha = nomes das colunas; separador ; , ou tabulação (Excel: CSV)")
        topo.addWidget(self.btn_csv)
        self.btn_limpar = QPushButton("Remover planilha")
        self.btn_limpar.clicked.connect(self.limparPedido)
        topo.addWidget(self.btn_limpar)
        v.addLayout(topo)
        self.lbl_info = QLabel("Sem planilha.")
        self.lbl_info.setWordWrap(True)
        v.addWidget(self.lbl_info)
        self.lbl_aviso = QLabel()
        self.lbl_aviso.setObjectName("banner")
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.hide()
        v.addWidget(self.lbl_aviso)

        self.tabela = QTableWidget(0, 0)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setAccessibleName("Linhas da planilha")
        self.tabela.setMinimumHeight(120)
        self.tabela.itemSelectionChanged.connect(self._linha_clicada)
        v.addWidget(self.tabela, 1)

        nav = QHBoxLayout()
        self.btn_ant = QPushButton("◀ Anterior")
        self.btn_ant.clicked.connect(lambda: self.linhaEscolhida.emit(self._atual - 1))
        self.btn_prox = QPushButton("Próxima ▶")
        self.btn_prox.clicked.connect(lambda: self.linhaEscolhida.emit(self._atual + 1))
        self.lbl_linha = QLabel("")
        nav.addWidget(self.btn_ant)
        nav.addWidget(self.lbl_linha, 1)
        nav.addWidget(self.btn_prox)
        v.addLayout(nav)

        form = QFormLayout()
        self.contador = QSpinBox()
        self.contador.setRange(-999999, 999999)
        self.contador.setKeyboardTracking(False)
        self.contador.setToolTip("Valor atual de {n}")
        self.incremento = QSpinBox()
        self.incremento.setRange(-1000, 1000)
        self.incremento.setKeyboardTracking(False)
        for sb in (self.contador, self.incremento):
            sb.editingFinished.connect(self._contador_editado)
        form.addRow("Número atual {n}", self.contador)
        form.addRow("Incremento", self.incremento)
        self.quantidade = QSpinBox()
        self.quantidade.setRange(1, 1000)
        self.quantidade.setValue(10)
        self.quantidade.setToolTip("Quantas peças gerar no lote quando não há planilha (contador muda a cada uma)")
        form.addRow("Peças no lote (sem planilha)", self.quantidade)
        v.addLayout(form)

        rodape = QHBoxLayout()
        self.btn_avancar = QPushButton("Avançar (próxima peça)")
        self.btn_avancar.setToolTip("Próxima linha da planilha e contador + incremento")
        self.btn_avancar.clicked.connect(self.avancarPedido)
        rodape.addWidget(self.btn_avancar)
        self.btn_lote = QPushButton("Exportar G-code em lote…")
        self.btn_lote.setToolTip("Um arquivo .gcode por linha da planilha (ou por número de série). "
                                 "Nada é enviado à máquina.")
        rodape.addWidget(self.btn_lote)
        v.addLayout(rodape)
        self._atual = 0

    def set_dados(self, d, faltando=(), n_textos=0, por_mesa=1, sem_dados=0):
        self._sync = True
        self._atual = d.linha_atual
        self.tabela.setColumnCount(len(d.colunas))
        self.tabela.setHorizontalHeaderLabels(list(d.colunas))
        self.tabela.setRowCount(len(d.linhas))
        for r, linha in enumerate(d.linhas):
            for c, valor in enumerate(linha):
                self.tabela.setItem(r, c, QTableWidgetItem(valor))
        if d.linhas:
            self.tabela.selectRow(d.linha_atual)
        self.tabela.resizeColumnsToContents()
        if d.linhas:
            self.lbl_info.setText(f"Planilha: {d.arquivo or '(sem nome)'} — {len(d.linhas)} linha(s); colunas: "
                                  + ", ".join(d.colunas))
            self.lbl_linha.setText(f"Linha {d.linha_atual + 1} de {len(d.linhas)}")
        else:
            self.lbl_info.setText("Sem planilha (só {n}, {data} e {hora}).")
            self.lbl_linha.setText("")
        self.lbl_info.setText(self.lbl_info.text() + f" · {n_textos} texto(s) variável(is) no projeto.")
        self.btn_ant.setEnabled(d.linha_atual > 0)
        self.btn_prox.setEnabled(d.linha_atual < len(d.linhas) - 1)
        self.btn_limpar.setEnabled(bool(d.linhas))
        self.contador.setValue(d.contador)
        self.incremento.setValue(d.incremento)
        self.quantidade.setEnabled(not d.linhas)
        avisos = ["Marcadores sem valor: " + ", ".join("{" + f + "}" for f in faltando)] if faltando else []
        if sem_dados:
            avisos.append(f"{sem_dados} peça(s) do gabarito sem linha na planilha: ficam fora do G-code.")
        self.lbl_aviso.setText("\n".join(avisos))
        self.lbl_aviso.setVisible(bool(avisos))
        self.btn_avancar.setText(f"Próxima mesa ({por_mesa} peças)" if por_mesa > 1 else "Avançar (próxima peça)")
        self._sync = False

    def _linha_clicada(self):
        if self._sync:
            return
        rows = self.tabela.selectionModel().selectedRows()
        if rows and rows[0].row() != self._atual:
            self.linhaEscolhida.emit(rows[0].row())

    def _contador_editado(self):
        if not self._sync:
            self.contadorAlterado.emit(self.contador.value(), self.incremento.value())
