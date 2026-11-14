"""Sobrecorte e preencher todas as formas de uma vez."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import frisos as fr  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import percurso as pc  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap(path):
    return (path, QTransform(), "x", "C01", "#fff", None)


class ExtrasTest(unittest.TestCase):
    def test_sobrecorte(self):
        c = cm.alterar(cm.nova("C01"), sobrecorte_mm=3)
        p = pc.gerar([snap(fm.rect_path(QRectF(10, 10, 20, 20)))], [c])
        self.assertAlmostEqual(p.comprimento_corte, 80 + 3, 6)
        corte = [t for t in p.trechos if t.tipo == "corte"][0]
        self.assertAlmostEqual(pc._dist(corte.pontos[-1], corte.pontos[0]), 3, 6)   # passou 3 mm do início
        self.assertEqual(pc.com_sobrecorte([(0, 0), (5, 0)], 3), [(0, 0), (5, 0)])   # aberto: igual

    def test_preencher_juntas_mesmo_corte_menos_ida(self):
        f = fr.Frisos(60.09, 50, 19, 0.3, 0, 20, 20)
        snaps = [snap(sp) for sp in fm.subcaminhos(f.frisos())]              # 19 frisos separados
        base = cm.alterar(cm.nova("C01"), modo="preenchimento", intervalo_mm=0.1)
        sep = pc.gerar(snaps, [base])
        jun = pc.gerar(snaps, [cm.alterar(base, preencher_juntas=True)])
        self.assertAlmostEqual(jun.comprimento_corte, sep.comprimento_corte, 3)
        self.assertNotEqual(len(jun.trechos), 0)
        self.assertTrue(gc.analisar(gc.gerar(jun, [cm.alterar(base, preencher_juntas=True)]))["dentro_da_area"])


if __name__ == "__main__":
    unittest.main()
