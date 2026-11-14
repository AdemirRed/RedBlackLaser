"""Pesquisa de comandos (F4): digite parte do nome de qualquer comando dos menus/barras e tecle Enter."""
import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


def _limpo(txt: str) -> str:
    """Minúsculo e sem acento ("Configurações" acha com "configuracoes")."""
    t = unicodedata.normalize("NFD", txt.replace("&", "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def coletar_comandos(janela) -> list:
    """[(texto, caminho do menu, ação)] de todos os comandos dos menus e barras (sem repetir)."""
    vistos, out, vivos = set(), [], []

    def visitar(acoes, caminho):
        for a in acoes:
            vivos.append(a)  # mantém o objeto vivo: senão o id() é reaproveitado e um comando some da pesquisa
            if a.isSeparator():
                continue
            sub = a.menu()
            texto = a.text().replace("&", "").split("\t")[0].strip()
            if sub is not None:
                visitar(sub.actions(), caminho + [texto])
            elif texto and id(a) not in vistos:
                vistos.add(id(a))
                out.append((texto, " › ".join(caminho), a))

    visitar(janela.menuBar().actions(), [])
    for titulo, acoes in getattr(janela, "grupos_barra", []):  # ferramentas agrupadas nas barras
        visitar(acoes, ["Barra", titulo])
    for barra in getattr(janela, "toolbars", []):
        visitar(barra.actions(), [barra.windowTitle()])
    return out


class DialogoPesquisa(QDialog):
    def __init__(self, janela):
        super().__init__(janela)
        self.setWindowTitle("Pesquisar comando")
        self.resize(560, 460)
        self.comandos = coletar_comandos(janela)
        v = QVBoxLayout(self)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Digite o que procura (ex.: bolear, grupo, caixa, G-code…) e tecle Enter")
        v.addWidget(self.busca)
        self.lista = QListWidget()
        v.addWidget(self.lista, 1)
        v.addWidget(QLabel("↑ ↓ escolhe · Enter executa · Esc fecha"))
        self.busca.textChanged.connect(self.filtrar)
        self.busca.returnPressed.connect(self.executar)
        self.lista.itemActivated.connect(lambda _: self.executar())
        self.busca.installEventFilter(self)
        self.escolhida = None
        self.filtrar("")

    def filtrar(self, txt):
        palavras = _limpo(txt).split()
        self.lista.clear()
        for texto, caminho, acao in self.comandos:
            alvo = _limpo(f"{texto} {caminho} {acao.toolTip()} {acao.statusTip()}")  # nome, menu e descrição
            if all(p in alvo for p in palavras):
                atalho = acao.shortcut().toString()
                it = QListWidgetItem(f"{texto}" + (f"   ({atalho})" if atalho else "") + (f"   — {caminho}" if caminho else ""))
                it.setData(Qt.UserRole, acao)
                if not acao.isEnabled():
                    it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                self.lista.addItem(it)
        for i in range(self.lista.count()):  # primeira habilitada já marcada
            if self.lista.item(i).flags() & Qt.ItemIsEnabled:
                self.lista.setCurrentRow(i)
                break

    def eventFilter(self, obj, ev):
        if obj is self.busca and ev.type() == ev.Type.KeyPress and ev.key() in (Qt.Key_Down, Qt.Key_Up):
            self.lista.setFocus()
            self.lista.keyPressEvent(ev)
            self.busca.setFocus()
            return True
        return super().eventFilter(obj, ev)

    def executar(self):
        it = self.lista.currentItem()
        if it is None or not it.flags() & Qt.ItemIsEnabled:
            return
        self.escolhida = it.data(Qt.UserRole)
        self.accept()
