"""Plugin Plano de corte: lista de peças por material → peças posicionadas nas chapas → abas no RedBlack.

Abre numa janela própria (Qt), sem mexer no layout da janela principal. "Enviar ao RedBlack" cria uma aba por
chapa no projeto aberto, com os retângulos das peças na camada escolhida e a borda da chapa numa camada que não
corta.
"""
import os

from PySide6.QtCore import QRectF, QStandardPaths

from ... import camadas as cm
from ... import formas as fm
from ... import objetos as ob

CAMADA_CHAPA = "C29"  # borda da chapa: referência na tela, Saída desligada
NOME = "Plano de corte (lista de materiais)…"


def aplicar_plano(janela, chapas, camada) -> int:
    """Cria uma aba por chapa no projeto aberto. Devolve quantas abas foram criadas."""
    if camada not in cm.IDS or camada == CAMADA_CHAPA:
        raise ValueError("camada inválida")
    for ch in chapas:
        janela.adicionar_pagina(False)
        janela.renomear_pagina(janela.pagina_atual, ch["nome"])
        borda = ob.Shape(fm.rect_path(QRectF(0, 0, ch["largura"], ch["altura"])),
                         f"Chapa {ch['largura']:g} × {ch['altura']:g} (referência)", CAMADA_CHAPA, cm.cor(CAMADA_CHAPA))
        itens = [borda] + [ob.Shape(fm.rect_path(QRectF(p["x"], p["y"], p["largura"], p["altura"])), p["nome"],
                                    camada, cm.cor(camada)) for p in ch["pecas"]]
        janela._edit("Plano de corte", lambda itens=itens: [janela.canvas.scene.addItem(i) for i in itens])
    c = janela.layer(CAMADA_CHAPA)
    if c is not None and c.saida:
        janela.set_layer_fields(CAMADA_CHAPA, {"saida": False, "nome": "Chapa (referência — não corta)"},
                                "Camada da chapa")
    janela.canvas.view.fit()
    return len(chapas)


def registrar(janela, menu):
    from .janela import JanelaPlanoCorte
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
    arquivo = os.path.join(base, "plano_corte", "lista.json")
    estado = {"janela": None}

    def abrir():
        if estado["janela"] is None:
            estado["janela"] = JanelaPlanoCorte(lambda chapas, camada: aplicar_plano(janela, chapas, camada), arquivo,
                                                janela)
        w = estado["janela"]
        w.show()
        w.raise_()
        w.activateWindow()
        return w

    acao = menu.addAction(NOME)
    acao.setToolTip("Lista de peças por material, encaixe automático nas chapas e envio ao projeto (abas)")
    acao.triggered.connect(abrir)
    janela.plugin_plano_corte = {"abrir": abrir, "estado": estado}
