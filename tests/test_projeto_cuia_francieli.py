"""Cuia Francieli: contornos abertos do PDF fechados com a borda certa, 20 peças, camadas na ordem do dono."""
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import cuia_francieli as cf  # noqa: E402

from redblack import projeto as pj  # noqa: E402


@unittest.skipUnless(os.path.exists(cf.PDF), "PDF da Cuia Francieli não está neste PC")
class CuiaFrancieliTest(unittest.TestCase):
    def test_gera_fechado_e_na_ordem(self):
        destino = os.path.join(tempfile.mkdtemp(), "cuia.rbl")
        _d, c = cf.gerar(cf.PDF, destino)  # gerar() já faz os asserts de quantidade/bordas/área dos rasgos
        self.assertEqual({round(g, 2) for _p, g in c["hex"]}, {63.51})
        self.assertEqual({round(g, 2) for _p, g in c["lateral"]}, {84.0})
        objetos, camadas = pj.load_full(destino)[:2]
        nomes = sorted(s[2].split()[0] for s in objetos)
        self.assertEqual(nomes, sorted([f"{p}{i}" for p in "LAM" for i in range(1, 7)] + ["T01", "B01"]))
        ids = [c.id for c in camadas]
        self.assertEqual(ids, ["C03", "C06", "C02", "C01"])  # grava, peças nas janelas, janelas, contornos
        corte = [c for c in camadas if c.modo == "linha"]
        self.assertTrue(all((c.velocidade_mm_min, c.potencia_max, c.passadas) == (630, 85, 2) for c in corte))
        self.assertTrue(all(c.potencia_max <= 85 for c in camadas))


if __name__ == "__main__":
    unittest.main()
