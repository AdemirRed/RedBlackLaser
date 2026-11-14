"""Editor de teclas de atalho: todos os comandos dos menus, com a tecla atual; mudanças ficam no QSettings."""
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QKeySequenceEdit, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

PREFIXO = "atalhos/"


def chave(acao) -> str:
    """Identificador estável do comando: o texto do menu sem & nem reticências."""
    return acao.text().split("\t")[0].replace("&", "").rstrip("…").strip()


def aplicar_salvos(settings, acoes):
    """Aplica os atalhos guardados (texto vazio = sem atalho)."""
    for a in acoes:
        v = settings.value(PREFIXO + chave(a))
        if v is not None:
            a.setShortcut(QKeySequence(v))


def conflitos(mapa: dict) -> dict:
    """{tecla: [comandos]} para teclas usadas por mais de um comando."""
    usados = {}
    for nome, seq in mapa.items():
        if seq:
            usados.setdefault(seq, []).append(nome)
    return {k: v for k, v in usados.items() if len(v) > 1}


class AtalhosDialog(QDialog):
    def __init__(self, parent, acoes):
        super().__init__(parent)
        self.setWindowTitle("Teclas de atalho")
        self.resize(560, 600)
        self.acoes = sorted({chave(a): a for a in acoes if chave(a)}.values(), key=chave)
        v = QVBoxLayout(self)
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Procurar comando…")
        self.filtro.textChanged.connect(self._filtrar)
        v.addWidget(self.filtro)
        self.tab = QTableWidget(len(self.acoes), 2)
        self.tab.setHorizontalHeaderLabels(["Comando", "Tecla"])
        self.tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tab.verticalHeader().hide()
        self.editores = []
        for i, a in enumerate(self.acoes):
            self.tab.setItem(i, 0, QTableWidgetItem(chave(a)))
            ed = QKeySequenceEdit(a.shortcut())
            ed.setClearButtonEnabled(True)
            ed.keySequenceChanged.connect(self._verificar)
            self.tab.setCellWidget(i, 1, ed)
            self.editores.append(ed)
        v.addWidget(self.tab)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        v.addWidget(self.aviso)
        self.botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        v.addWidget(self.botoes)
        self._verificar()

    def mapa(self) -> dict:
        return {chave(a): e.keySequence().toString(QKeySequence.PortableText)
                for a, e in zip(self.acoes, self.editores)}

    def _verificar(self, *_):
        c = conflitos(self.mapa())
        self.aviso.setText("Teclas repetidas: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in c.items())
                           if c else "")
        self.botoes.button(QDialogButtonBox.Ok).setEnabled(not c)

    def _filtrar(self, txt):
        for i, a in enumerate(self.acoes):
            self.tab.setRowHidden(i, txt.casefold() not in chave(a).casefold())
