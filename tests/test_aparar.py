"""Ferramenta Aparar formas (tesoura)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import aparar as ap  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AlgoritmoTest(unittest.TestCase):
    def test_quadrado_cortado_por_circulo(self):
        q, c = fm.rect_path(QRectF(0, 0, 20, 20)), fm.ellipse_path(QRectF(10, -5, 20, 30))
        novo, rem = ap.aparar(q, [c], QPointF(20, 10), 0.5)
        self.assertAlmostEqual(rem.boundingRect().left(), 12.548, 2)
        self.assertAlmostEqual(novo.boundingRect().width(), 12.548, 2)
        self.assertIsNone(ap.aparar(q, [c], QPointF(10, 10), 0.5))           # longe do contorno

    def test_linha_aberta_e_sem_cruzamento(self):
        q = fm.rect_path(QRectF(0, 0, 20, 20))
        linha = fm.polyline_path([QPointF(-10, 5), QPointF(40, 5)])
        novo, rem = ap.aparar(linha, [q], QPointF(10, 5), 0.5)
        self.assertEqual(rem.boundingRect(), QRectF(0, 5, 20, 0))
        self.assertEqual(len(novo.toSubpathPolygons()), 2)                 # sobram as duas pontas
        self.assertTrue(ap.aparar(q, [], QPointF(0, 10), 0.5)[0].isEmpty())  # sem cruzar: some inteiro

    def test_linha_que_so_encosta_tambem_divide(self):
        q = fm.rect_path(QRectF(0, 0, 20, 20))
        a = fm.polyline_path([QPointF(-10, 3), QPointF(0, 3)])     # termina em cima da borda (junta em "T")
        b = fm.polyline_path([QPointF(-10, 7), QPointF(0.1, 7)])   # passa 0,1 mm: ainda encosta
        novo, rem = ap.aparar(q, [a, b], QPointF(0, 5), 0.5)
        self.assertAlmostEqual(rem.length(), 4.0, 1)  # só o pedaço entre as duas juntas, não o quadrado todo
        self.assertAlmostEqual(novo.length(), 76.0, 1)
        # a própria linha termina em cima de si mesma (contorno que encosta nele mesmo)
        laco = fm.polyline_path([QPointF(-10, 10), QPointF(0, 10), QPointF(0, 0), QPointF(10, 0), QPointF(10, 20),
                                 QPointF(0, 20), QPointF(0, 10)])  # volta e termina em cima do próprio começo
        c = fm.polyline_path([QPointF(-10, 15), QPointF(0, 15)])  # outra linha encostando no lado esquerdo
        _, rem = ap.aparar(laco, [c], QPointF(0, 12), 0.5)
        self.assertAlmostEqual(rem.length(), 5.0, 1)  # de (0, 15) até a ponta em (0, 10), não o laço inteiro

    def test_outro_contorno_do_mesmo_objeto_corta(self):
        p = fm.rect_path(QRectF(0, 0, 20, 20))
        p.addPath(fm.polyline_path([QPointF(10, -5), QPointF(10, 25)]))
        novo, rem = ap.aparar(p, [], QPointF(20, 10), 0.5)
        self.assertAlmostEqual(rem.boundingRect().left(), 10, 6)


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.win.new_document()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_clicar_com_a_tesoura(self):
        self.win.create_shape(fm.rect_path(QRectF(100, 100, 40, 40)), "rect")
        self.win.create_shape(fm.ellipse_path(QRectF(120, 90, 40, 60)), "ellipse")
        self.win.tools["trim"].setChecked(True)
        vp = self.view.viewport()
        pos = self.view.mapFromScene(QPointF(140, 120))                   # lado direito do quadrado
        QTest.mouseMove(vp, pos)
        self.assertFalse(self.view._realce.path().isEmpty())               # trecho realçado antes do clique
        QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, pos)
        quad = next(s for s in self.view.shapes() if s.name.startswith("Retângulo"))
        self.assertLess(ob.bounds([quad]).width(), 40)
        self.win.undo_stack.undo()
        quad = next(s for s in self.view.shapes() if s.name.startswith("Retângulo"))
        self.assertAlmostEqual(ob.bounds([quad]).width(), 40, 6)
        self.win.tools["select"].setChecked(True)
        self.assertTrue(self.view._realce.path().isEmpty())


if __name__ == "__main__":
    unittest.main()
