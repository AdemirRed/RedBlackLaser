"""Plugin Colorir metal: grade de teste (potência × intervalo), leitura das cores pela foto da placa e aplicação
das cores às formas (camadas de Preenchimento configuradas). Abre numa janela própria."""
import os

from PySide6.QtCore import QStandardPaths

NOME = "Colorir metal com laser…"


def registrar(janela, menu):
    from .janela import JanelaColorir
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
    arquivo = os.path.join(base, "colorir_metal", "paletas.json")
    estado = {"janela": None}

    def abrir():
        if estado["janela"] is None:
            estado["janela"] = JanelaColorir(janela, arquivo, janela)
        w = estado["janela"]
        w.show()
        w.raise_()
        w.activateWindow()
        return w

    acao = menu.addAction(NOME)
    acao.setToolTip("Inox/titânio colorido: grade de teste, paleta pela foto da placa e aplicar cores às formas")
    acao.triggered.connect(abrir)
    janela.plugin_colorir_metal = {"abrir": abrir, "estado": estado}
