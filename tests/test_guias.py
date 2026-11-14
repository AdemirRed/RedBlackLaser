"""Guias (pontes) nos contornos da camada."""
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
from redblack import percurso as pc  # noqa: E402
from redblack import projeto as pj  # noqa: E402

app = QApplication.instance() or QApplication([])


class GuiasTest(unittest.TestCase):
    def test_quatro_guias_num_quadrado(self):
        snap = (fm.rect_path(QRectF(10, 10, 40, 40)), QTransform(), "x", "C01", "#fff", None)
        c = cm.alterar(cm.nova("C01"), guias_qtd=4, guias_mm=2)
        p = pc.gerar([snap], [c], internas_primeiro=False)
        cortes = [t for t in p.trechos if t.tipo == "corte"]
        self.assertEqual(len(cortes), 4)
        self.assertAlmostEqual(p.comprimento_corte, 160 - 4 * 2, 6)          # 4 pontes de 2 mm sem corte
        for t in cortes:
            self.assertAlmostEqual(t.comprimento, 38, 6)

    def test_sem_guias_curto_e_aberto(self):
        self.assertEqual(len(pc.com_guias([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)], 4, 2)), 1)  # curto demais
        self.assertEqual(pc.com_guias([(0, 0), (10, 0)], 2, 1), [[(0, 0), (10, 0)]])         # aberto
        with self.assertRaises(ValueError):
            cm.alterar(cm.nova("C01"), guias_qtd=2.5)

    def test_projeto_antigo(self):
        d = pj.to_dict([], [cm.Camada("C01", "c", guias_qtd=3)])
        self.assertEqual(pj.layers_from_dict(d)[0].guias_qtd, 3)
        del d["camadas"][0]["guias_qtd"], d["camadas"][0]["guias_mm"]
        self.assertEqual(pj.layers_from_dict(d)[0].guias_qtd, 0)



class GuiasComSobrecorteTest(unittest.TestCase):
    def test_guias_valem_mesmo_com_sobrecorte(self):
        snap = (fm.rect_path(QRectF(10, 10, 40, 40)), QTransform(), "x", "C01", "#fff", None)
        c = cm.alterar(cm.nova("C01"), guias_qtd=4, guias_mm=2, sobrecorte_mm=3)
        p = pc.gerar([snap], [c], internas_primeiro=False)
        self.assertEqual(len([t for t in p.trechos if t.tipo == "corte"]), 4)
        self.assertAlmostEqual(p.comprimento_corte, 160 - 8, 6)


if __name__ == "__main__":
    unittest.main()
