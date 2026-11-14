"""Deslocar formas, solda, união, subtrair, interseção e cortar formas."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import booleanas as bo  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class GeometriaTest(unittest.TestCase):
    def test_deslocar(self):
        r = fm.rect_path(QRectF(0, 0, 20, 10))
        self.assertEqual(bo.deslocar(r, 2, "fora").boundingRect(), QRectF(-2, -2, 24, 14))
        self.assertAlmostEqual(bo.deslocar(r, 2, "dentro").boundingRect().width(), 16, 6)
        self.assertEqual(len(bo.deslocar(r, 2, "ambos").toSubpathPolygons()), 2)
        self.assertTrue(bo.deslocar(r, 6, "dentro").isEmpty())               # some: peça menor que 2×6
        c = bo.deslocar(fm.ellipse_path(QRectF(0, 0, 99.6, 99.6)), 0.1, "fora")
        self.assertAlmostEqual(c.boundingRect().width(), 99.8, 3)
        with self.assertRaises(ValueError):
            bo.deslocar(r, 0)

    def test_furo_e_booleanas(self):
        d = QPainterPath()
        d.setFillRule(Qt.OddEvenFill)
        d.addRect(QRectF(0, 0, 50, 50))
        d.addRect(QRectF(20, 20, 10, 10))
        larguras = sorted(round(q.boundingRect().width(), 4) for q in bo.deslocar(d, 1).toSubpathPolygons())
        self.assertEqual(larguras, [8.0, 52.0])                              # furo encolhe, borda cresce
        a, b = fm.ellipse_path(QRectF(0, 0, 20, 20)), fm.ellipse_path(QRectF(10, 0, 20, 20))
        self.assertAlmostEqual(bo.uniao([a, b]).boundingRect().width(), 30, 3)
        self.assertAlmostEqual(bo.subtrair(a, [b]).boundingRect().width(), 15, 2)
        self.assertAlmostEqual(bo.intersecao([a, b]).boundingRect().width(), 10, 2)
        partes = bo.cortar(fm.rect_path(QRectF(0, 0, 40, 10)), fm.rect_path(QRectF(10, -5, 10, 20)))
        self.assertEqual([round(p.boundingRect().width(), 4) for p in partes], [10.0, 40.0])
        self.assertTrue(bo.fechado(a))
        self.assertFalse(bo.fechado(fm.polyline_path([QPointF(0, 0), QPointF(5, 5)])))


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(m)
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def criar(self, *rects):
        out = []
        for r in rects:
            self.win.create_shape(fm.rect_path(QRectF(*r)), "rect")
            out.append(self.win._sel()[0])
        return out

    def selecionar(self, *itens):
        self.win.canvas.scene.clearSelection()
        for it in itens:
            it.setSelected(True)
            app.processEvents()

    def test_solda_e_desfazer(self):
        a, b = self.criar((0, 0, 20, 20), (10, 10, 20, 20))
        self.selecionar(a, b)
        self.assertTrue(self.win.booleana("solda"))
        s = self.win.canvas.view.shapes()
        self.assertEqual(len(s), 1)
        self.assertEqual(ob.bounds(s).width(), 30)
        self.win.undo_stack.undo()
        self.assertEqual(len(self.win.canvas.view.shapes()), 2)

    def test_subtrair_usa_ordem_de_clique(self):
        a, b = self.criar((0, 0, 20, 20), (10, 0, 20, 20))
        self.selecionar(b, a)                                               # b primeiro: b − a
        self.win.booleana("subtrair")
        r = ob.bounds(self.win.canvas.view.shapes())
        self.assertEqual((r.left(), r.width()), (20, 10))

    def test_cortar_mantem_cortador(self):
        alvo, cortador = self.criar((0, 0, 40, 10), (10, -5, 10, 20))
        self.selecionar(alvo, cortador)
        self.win.booleana("cortar")
        nomes = sorted(s.name for s in self.win.canvas.view.shapes())
        self.assertEqual(nomes, ["Retângulo 1 (1)", "Retângulo 1 (2)", "Retângulo 2"])

    def test_linha_aberta_recusada(self):
        a, = self.criar((0, 0, 20, 20))
        self.win.create_shape(fm.polyline_path([QPointF(0, 0), QPointF(30, 30)]), "line")
        self.selecionar(a, self.win.canvas.view.shapes()[1])
        self.assertFalse(self.win.booleana("uniao"))
        self.assertIn("fechadas", self.msgs[-1])

    def test_deslocar_mantem_ou_apaga_original(self):
        a, = self.criar((10, 10, 20, 10))
        self.assertTrue(self.win.deslocar_formas((2, "fora", "redondo", False)))
        s = self.win.canvas.view.shapes()
        self.assertEqual(len(s), 2)
        self.assertEqual(ob.bounds([s[1]]), QRectF(8, 8, 24, 14))
        self.selecionar(s[0])
        self.win.deslocar_formas((1, "dentro", "canto", True))
        self.assertEqual([round(ob.bounds([x]).width(), 6) for x in self.win.canvas.view.shapes()], [24, 18])


if __name__ == "__main__":
    unittest.main()
