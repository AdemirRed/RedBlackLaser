"""Duplicar (Ctrl+D) e cantos arredondados — pedidos do usuário. Valores esperados calculados à mão."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def comprimento(path):
    return pc.gerar([ob.Shape(path, "x", "C01", "#fff").snapshot()], [cm.nova("C01")]).comprimento_corte


class GeometriaTest(unittest.TestCase):
    def test_retangulo_arredondado_medidas(self):
        r = 5
        p, n = fm.arredondar(fm.rect_path(QRectF(10, 20, 40, 20)), r)
        self.assertEqual(n, 4)
        self.assertEqual(p.boundingRect().getRect(), (10, 20, 40, 20))     # caixa não muda
        esperado = 2 * (40 + 20) - 8 * r + 2 * math.pi * r                    # perímetro do retângulo arredondado
        self.assertAlmostEqual(comprimento(p), esperado, delta=esperado * 1e-3)
        # o ponto médio de cada arco fica a r do centro do canto: (15,25), (45,25), (45,35), (15,35)
        centros = [(15, 25), (45, 25), (45, 35), (15, 35)]
        curvas = [i for i in range(p.elementCount()) if p.elementAt(i).type == QPainterPath.CurveToElement]
        self.assertEqual(len(curvas), 4)
        for i in curvas:
            a, c1, c2, f = p.elementAt(i - 1), p.elementAt(i), p.elementAt(i + 1), p.elementAt(i + 2)
            x = (a.x + 3 * c1.x + 3 * c2.x + f.x) / 8   # Bézier em t = 0,5
            y = (a.y + 3 * c1.y + 3 * c2.y + f.y) / 8
            d = min(math.hypot(x - cx, y - cy) for cx, cy in centros)
            self.assertAlmostEqual(d, r, delta=r * 3e-4)

    def test_raio_grande_limita_a_metade_do_lado(self):
        p, n = fm.arredondar(fm.rect_path(QRectF(0, 0, 40, 20)), 100)
        self.assertEqual(n, 4)
        self.assertEqual(p.boundingRect().getRect(), (0, 0, 40, 20))
        esperado = 2 * (40 - 20) + math.pi * 20                              # vira "estádio" (raio 10)
        self.assertAlmostEqual(comprimento(p), esperado, delta=esperado * 1e-3)
        for i in range(p.elementCount()):
            e = p.elementAt(i)
            self.assertTrue(math.isfinite(e.x) and math.isfinite(e.y))

    def test_triangulo_linha_aberta_colinear_e_curvas(self):
        tri = fm.polygon_path(QPointF(0, 0), 20, 3)
        self.assertEqual(fm.arredondar(tri, 2)[1], 3)
        aberta = fm.polyline_path([QPointF(0, 0), QPointF(10, 0), QPointF(10, 10)])
        p, n = fm.arredondar(aberta, 3)
        self.assertEqual(n, 1)                                               # extremos não arredondam
        self.assertEqual((p.elementAt(0).x, p.elementAt(0).y), (0.0, 0.0))
        fim = p.elementAt(p.elementCount() - 1)
        self.assertEqual((fim.x, fim.y), (10.0, 10.0))
        reta = fm.polyline_path([QPointF(0, 0), QPointF(5, 0), QPointF(10, 0)])
        self.assertEqual(fm.arredondar(reta, 3)[1], 0)                      # ponto no meio de uma reta
        ell = fm.ellipse_path(QRectF(0, 0, 20, 10))
        p, n = fm.arredondar(ell, 3)
        self.assertEqual(n, 0)
        self.assertEqual(p.boundingRect(), ell.boundingRect())
        self.assertEqual(fm.arredondar(fm.rect_path(QRectF(0, 0, 5, 5)), 0)[1], 0)


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def drag(self, a, b):
        vp = self.view.viewport()
        for kind, p, btn, btns in ((QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton),
                                   (QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton),
                                   (QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)):
            q = self.view.mapFromScene(p)
            app.sendEvent(vp, QMouseEvent(kind, QPointF(q), QPointF(vp.mapToGlobal(q)), btn, btns, Qt.NoModifier))
        app.processEvents()

    def test_duplicar_no_mesmo_lugar_e_desfazer(self):
        self.win.create_shape(fm.rect_path(QRectF(50, 50, 30, 20)), "rect")
        self.win.create_text(tx.TextoParams("Faca", "Arial", 10), QPointF(100, 100))
        self.win.select_all()
        self.win._clipboard = ["marcador"]
        self.win.act_duplicate.trigger()
        shapes = self.view.shapes()
        self.assertEqual(len(shapes), 4)
        copias = self.view.selected()
        self.assertEqual(len(copias), 2)
        self.assertTrue(all(c.name.endswith("(cópia)") for c in copias))
        self.assertEqual({ob.geom_rect(c).getRect() for c in copias},
                         {ob.geom_rect(s).getRect() for s in shapes if s not in copias})   # mesmo lugar
        self.assertTrue(any(isinstance(c, ob.TextShape) for c in copias))                  # texto continua texto
        self.assertEqual(self.win._clipboard, ["marcador"])                                 # área de transferência intacta
        self.assertEqual(self.win.undo_stack.undoText(), "Duplicar")
        self.win.undo_stack.undo()
        self.assertEqual(len(self.view.shapes()), 2)

    def test_ctrl_d_sem_selecao_desabilitado(self):
        self.assertFalse(self.win.act_duplicate.isEnabled())
        self.assertEqual(self.win.act_duplicate.shortcut().toString(), "Ctrl+D")

    def test_retangulo_desenhado_com_raio(self):
        self.win.raio.setValue(4)
        self.win.tools["rect"].setChecked(True)
        self.drag(QPointF(100, 100), QPointF(160, 140))
        s = self.view.selected()[0]
        self.assertEqual(sum(s.path().elementAt(i).type == QPainterPath.CurveToElement
                             for i in range(s.path().elementCount())), 4)
        r = ob.geom_rect(s)
        self.assertAlmostEqual(r.width() / r.height(), 1.5, delta=0.02)

    def test_arredondar_selecao_ignora_curvas_e_texto(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 40, 20)), "rect")
        self.win.create_shape(fm.ellipse_path(QRectF(100, 10, 40, 20)), "ellipse")
        self.win.create_text(tx.TextoParams("A", "Arial", 10), QPointF(200, 50))
        self.win.select_all()
        self.assertTrue(self.win.act_round.isEnabled())
        self.win.raio.setValue(0)
        n_hist = self.win.undo_stack.count()
        self.win.act_round.trigger()
        self.assertIn("Defina o Raio", self.win.statusBar().currentMessage())
        self.assertEqual(self.win.undo_stack.count(), n_hist)                # raio 0: nada muda
        self.win.raio.setValue(5)                                             # com seleção: aplica na hora
        self.assertEqual(self.win.undo_stack.count(), n_hist + 1)
        self.win.act_round.trigger()                                          # mesmo raio: nada novo
        self.assertEqual(self.win.undo_stack.count(), n_hist + 1)
        rect = next(s for s in self.view.shapes() if s.name.startswith("Retângulo"))
        self.assertAlmostEqual(comprimento(rect.sceneTransform().map(rect.path())),
                               2 * 60 - 40 + 10 * math.pi, delta=0.2)
        self.assertIn("4 canto(s) com raio 5 mm em 1 objeto(s)", self.win.statusBar().currentMessage())
        self.assertIn("2 objeto(s) sem cantos retos ignorado(s)", self.win.statusBar().currentMessage())
        self.assertTrue(any(isinstance(s, ob.TextShape) for s in self.view.shapes()))
        self.win.undo_stack.undo()
        rect = next(s for s in self.view.shapes() if s.name.startswith("Retângulo"))
        self.assertEqual(len(fm.nodes(rect.path())), 4)

    def test_raio_em_mm_reais_apos_escalar(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 20, 10)), "rect")
        s = self.view.selected()[0]
        ob.scale([s], 2, 2, QPointF(10, 10))                                 # agora 40×20 na mesa
        self.win.raio.setValue(5)
        self.win.act_round.trigger()
        s = self.view.selected()[0]
        p = s.sceneTransform().map(s.path())
        self.assertEqual(p.boundingRect().getRect(), (10, 10, 40, 20))
        self.assertAlmostEqual(comprimento(p), 120 - 40 + 10 * math.pi, delta=0.2)  # raio 5 mm, não 10


if __name__ == "__main__":
    unittest.main()
