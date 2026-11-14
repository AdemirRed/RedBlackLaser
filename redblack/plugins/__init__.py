"""Plugins do RedBlack Laser: cada um só acrescenta itens em Ferramentas → Plugins (não mexe no layout).

Um plugin é um subpacote com `registrar(janela, menu)`. A lista é explícita (o empacotador do .exe não acha
módulos carregados por descoberta dinâmica).
"""
import importlib
import sys
import traceback

PLUGINS = ("plano_corte", "colorir_metal", "cilindros", "orcamento")


def carregar(janela, menu) -> list:
    """Registra os plugins no submenu `menu`; um plugin com erro não impede os outros nem o programa."""
    ok = []
    for nome in PLUGINS:
        try:
            importlib.import_module(f"{__name__}.{nome}").registrar(janela, menu)
            ok.append(nome)
        except Exception:  # plugin quebrado: registra no log e segue
            traceback.print_exc(file=sys.stderr)
    return ok
