"""Carregado primeiro pela descoberta de testes: fixa a mesa de 400 x 400 que os testes esperam, e confere que o
PROGRAMA continua com a bancada padrão 365 x 370."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
import redblack.ui.main_window as mw  # noqa: E402

# lido do código-fonte: outro teste pode já ter trocado o valor em memória para 400 x 400
_fonte = open(mw.__file__, encoding="utf-8").read()
PADRAO_DO_PROGRAMA = {"largura": 365.0 if '"largura": 365.0, "altura": 370.0' in _fonte else None,
                      "altura": 370.0 if '"largura": 365.0, "altura": 370.0' in _fonte else None}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401


class BancadaPadraoTest(unittest.TestCase):
    def test_bancada_padrao_da_redblack(self):
        self.assertEqual((PADRAO_DO_PROGRAMA["largura"], PADRAO_DO_PROGRAMA["altura"]), (365.0, 370.0))


if __name__ == "__main__":
    unittest.main()
