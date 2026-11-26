"""Suporte Armor 27T: 22 peças da lista de corte, contornos fechados, figuras só nas faces externas, 2 chapas."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import suporte_armor27t as sa  # noqa: E402


@unittest.skipUnless(os.path.exists(sa.PDF), "PDF do suporte Armor 27T não está neste PC")
class SuporteArmorTest(unittest.TestCase):
    def test_pecas_e_gravacao(self):
        _d, abas = sa.gerar(sa.PDF, os.path.join(tempfile.mkdtemp(), "armor.rbl"))  # gerar() confere contagem/fecho
        self.assertEqual(len(abas), 2)
        nomes = [s[2] for _n, snaps in abas for s in snaps]
        self.assertEqual(len(nomes), 22)
        gravadas = [n for n in nomes if "face externa gravada" in n]
        self.assertEqual(sorted(n.split()[0] for n in gravadas), ["LD1", "LE1"])  # uma esquerda e uma direita


if __name__ == "__main__":
    unittest.main()
