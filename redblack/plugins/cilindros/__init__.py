"""Plugin Cilindros e copos: circunferência, largura útil da arte (com alça e repetições), distorção e foco no copo
cônico, molde em leque e ligação com o rotativo. Abre numa janela própria."""

NOME = "Cilindros e copos (cálculo da gravação)…"


def registrar(janela, menu):
    from .janela import JanelaCilindros
    estado = {"janela": None}

    def abrir():
        if estado["janela"] is None:
            estado["janela"] = JanelaCilindros(janela, janela)
        w = estado["janela"]
        w.carregar_estado()  # parâmetros salvos deste projeto + arte atual do projeto
        w.show()
        w.raise_()
        w.activateWindow()
        return w

    acao = menu.addAction(NOME)
    acao.setToolTip("Copos e cilindros no rotativo: tamanho da arte, alça, repetições, cone e molde em leque")
    acao.triggered.connect(abrir)
    janela.plugin_cilindros = {"abrir": abrir, "estado": estado}
