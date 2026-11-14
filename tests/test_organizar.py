"""Organizar: matriz em grade/circular, encostar, página, distribuir espaçado, mesma medida, espelhar na linha."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.geometria import BED_H, BED_W  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
GRADE = {"colunas": 3, "linhas": 2, "esp_x": 5.0, "esp_y": 5.0, "centro": False, "desloc_col": 0.0,
         "desloc_lin": 0.0, "espelhar_col": False, "espelhar_lin": False, "agrupar": False, "incrementar": True}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.new_document()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def rets(self, *rs):
        out = []
        for r in rs:
            self.win.create_shape(fm.rect_path(QRectF(*r)), "rect")
            out.append(self.win._sel()[0])
        return out

    def sel(self, *itens):
        self.win.canvas.scene.clearSelection()
        for it in itens:
            it.setSelected(True)
            app.processEvents()

    def caixas(self):
        return sorted((round(b.left(), 6), round(b.top(), 6), round(b.width(), 6), round(b.height(), 6))
                      for b in (ob.geom_rect(s) for s in self.view.shapes()))


class MatrizesTest(Base):
    def test_grade_e_texto_variavel(self):
        self.win.create_text(tx.TextoParams("Nº {n}", "Arial", 5, variavel=True), QPointF(20, 20))
        self.assertTrue(self.win.matriz_grade(GRADE))
        textos = self.view.shapes()
        self.assertEqual(len(textos), 6)
        self.assertEqual(sorted(t.params.peca for t in textos), [0, 1, 2, 3, 4, 5])
        b0, b1 = ob.geom_rect(textos[0]), ob.geom_rect(textos[1])
        self.assertAlmostEqual(b1.left() - b0.right(), 5, 6)                 # vão de 5 mm entre bordas
        self.win.undo_stack.undo()
        self.assertEqual(len(self.view.shapes()), 1)

    def test_grade_centro_a_centro_agrupada_e_espelhada(self):
        self.rets((10, 10, 10, 5))
        self.win.matriz_grade({**GRADE, "centro": True, "esp_x": 30.0, "esp_y": 20.0, "colunas": 2, "linhas": 1,
                               "agrupar": True, "espelhar_col": True})
        c = self.caixas()
        self.assertEqual(c, [(10, 10, 10, 5), (40, 10, 10, 5)])

    def test_circular(self):
        self.rets((95, 50, 10, 10))
        v = {"quantidade": 4, "raio": 50.0, "angulo": 360.0, "girar": True, "agrupar": False, "incrementar": False}
        self.assertTrue(self.win.matriz_circular(v))
        centros = sorted((round(ob.geom_rect(s).center().x(), 6), round(ob.geom_rect(s).center().y(), 6))
                         for s in self.view.shapes())
        self.assertEqual(centros, [(50, 105), (100, 55), (100, 155), (150, 105)])


class PosicaoTest(Base):
    def test_encostar(self):
        a, b = self.rets((10, 10, 20, 20), (100, 15, 10, 10))
        self.sel(b)
        self.win.encostar("esquerda")
        self.assertEqual(ob.geom_rect(b).left(), 30)                          # encosta no outro
        self.win.encostar("cima")
        self.assertEqual(ob.geom_rect(b).top(), 0)                            # sem obstáculo: borda da mesa
        self.win.encostar("baixo")
        self.assertEqual(ob.geom_rect(b).bottom(), BED_H)

    def test_mover_para_pagina(self):
        a, = self.rets((10, 10, 20, 10))
        self.win.mover_para_pagina(4)
        self.assertEqual(ob.geom_rect(a).center(), QPointF(BED_W / 2, BED_H / 2))
        self.win.mover_para_pagina(8)
        self.assertEqual(ob.geom_rect(a).bottomRight(), QPointF(BED_W, BED_H))

    def test_distribuir_espacado_e_mesma_medida(self):
        a, b, c = self.rets((0, 0, 10, 10), (15, 0, 30, 10), (100, 0, 10, 10))
        self.sel(a, b, c)
        self.win.distribuir_espacado(True)
        self.assertEqual(self.caixas(), [(0, 0, 10, 10), (40, 0, 30, 10), (100, 0, 10, 10)])  # vãos de 30
        self.win.lock.setChecked(False)
        self.sel(b, a)                                                       # b é a referência
        self.win.mesma_medida(True)
        self.assertAlmostEqual(ob.geom_rect(a).width(), 30, 6)
        self.assertAlmostEqual(ob.geom_rect(a).height(), 10, 6)

    def test_alinhar_centros_e_espelhar_na_linha(self):
        a, b = self.rets((0, 0, 10, 10), (50, 50, 20, 20))
        self.sel(a, b)
        self.win.alinhar_centros()
        self.assertEqual(ob.geom_rect(a).center(), ob.geom_rect(b).center())
        q, = self.rets((10, 100, 10, 10))
        self.win.create_shape(fm.polyline_path([QPointF(0, 130), QPointF(200, 130)]), "line")
        linha = self.win._sel()[0]
        self.sel(q, linha)
        self.assertTrue(self.win.espelhar_na_linha())
        self.assertEqual(ob.geom_rect(q), QRectF(10, 150, 10, 10))           # 100..110 → 150..160


if __name__ == "__main__":
    unittest.main()
