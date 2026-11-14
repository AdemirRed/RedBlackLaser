"""Os testes foram escritos para uma mesa de 400 x 400 mm; a bancada padrão do programa é 365 x 370 (RedBlack).
Importar este módulo fixa a mesa dos testes em 400 x 400 (janela nova e módulos de geometria)."""
from redblack import geometria as g
from redblack.ui.main_window import MainWindow

MainWindow.MAQUINA_PADRAO = {**MainWindow.MAQUINA_PADRAO, "largura": 400.0, "altura": 400.0}
g.definir_mesa(400.0, 400.0, "inf_esq")

# A compensação do eixo X vem LIGADA no programa; os testes antigos conferem velocidades e tempos sem ela
# (a compensação tem os testes próprios em test_calibracao_xy.py, que liga/desliga explicitamente).
from redblack import gcode as _gc  # noqa: E402
from redblack.ui import dialogo_calibracao_xy as _cxy  # noqa: E402

_cxy.PADRAO["ativo"] = False
_gc.definir_comp_x(0.0, 150.0)
