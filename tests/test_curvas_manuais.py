"""Curvas à mão: linha com clicar-e-arrastar, alças das curvas no Editar nós, L reta/curva, aviso de grupo."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import nos  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def tipos(p):
    return [p.elementAt(i).type for i in range(p.elementCount())]


class FuncoesTest(unittest.TestCase):
    def test_caminho_com_alcas(self):
        pts = [QPointF(0, 0), QPointF(10, 0), QPointF(20, 0)]
        reto = fm.caminho_com_alcas(pts, {})
        self.assertNotIn(QPainterPath.CurveToElement, tipos(reto))
        curvo = fm.caminho_com_alcas(pts, {1: QPointF(3, 4)})
        self.assertEqual(tipos(curvo).count(QPainterPath.CurveToElement), 2)  # os dois trechos do ponto 1
        e = curvo.elementAt(2)  # c2 do 1º trecho = ponto - alça (espelho)
        self.assertEqual((e.x, e.y), (7, -4))

    def test_alternar_reta_curva_mantem_forma(self):
        p = fm.polyline_path([QPointF(0, 0), QPointF(30, 0), QPointF(30, 20)])
        c = nos.alternar_reta_curva(p, 0, 0)
        self.assertIn(QPainterPath.CurveToElement, tipos(c))
        self.assertTrue(c.pointAtPercent(0.25).y() == 0)  # alças na própria reta: forma igual até mexer
        self.assertEqual(tipos(nos.alternar_reta_curva(c, 0, 0)), tipos(p))  # e volta a reta

    def test_move_controle_so_a_alca(self):
        p = QPainterPath()
        p.moveTo(0, 0)
        p.cubicTo(10, 0, 20, 10, 30, 10)
        q = fm.move_controle(p, 2, 5, -5)
        self.assertEqual([(q.elementAt(i).x, q.elementAt(i).y) for i in range(4)],
                         [(0, 0), (10, 0), (25, 5), (30, 10)])
        self.assertEqual(fm.controles(p), [(1, 0), (2, 3)])


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view
        self.view.encaixe_ativo = False  # pontos livres, sem grudar

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def mouse(self, kind, scene_pt, buttons=Qt.LeftButton, button=Qt.LeftButton):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(scene_pt)
        app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), button, buttons,
                                      Qt.NoModifier))
        app.processEvents()

    def clicar(self, p, ate=None):
        self.mouse(QEvent.MouseButtonPress, p)
        if ate is not None:  # arrastar antes de soltar
            self.mouse(QEvent.MouseMove, (p + ate) / 2, Qt.LeftButton, Qt.NoButton)
            self.mouse(QEvent.MouseMove, ate, Qt.LeftButton, Qt.NoButton)
        self.mouse(QEvent.MouseButtonRelease, ate if ate is not None else p, Qt.NoButton)

    def test_linha_com_curva_por_arraste(self):
        self.w.tools["pen"].trigger()
        self.clicar(QPointF(100, 100))
        self.clicar(QPointF(150, 100), ate=QPointF(170, 80))  # este ponto vira curva
        self.clicar(QPointF(200, 100))
        app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        s = self.view.selected()[0]
        t = tipos(s.path())
        self.assertEqual(t.count(QPainterPath.CurveToElement), 2)
        r = ob.geom_rect(s)
        self.assertLess(r.top(), 100 - 1)  # a curva sobe acima da reta dos pontos

    def test_arrastar_alca_no_editar_nos_e_desfazer(self):
        p = QPainterPath()
        p.moveTo(100, 100)
        p.cubicTo(120, 100, 140, 120, 160, 120)
        s = ob.Shape(p, "curva", "C01", "#fff")
        self.w._edit("teste", lambda: self.w.canvas.scene.addItem(s))
        s = self.view.shapes()[0]
        s.setSelected(True)
        self.w.tools["node"].trigger()
        alcas = self.view.node_overlay.handle_points()
        self.assertEqual(len(alcas), 2)
        idx, pt, _ = alcas[0]
        self.mouse(QEvent.MouseButtonPress, pt)
        self.mouse(QEvent.MouseMove, pt + QPointF(0, -30), Qt.LeftButton, Qt.NoButton)
        self.mouse(QEvent.MouseButtonRelease, pt + QPointF(0, -30), Qt.NoButton)
        novo = s.path()
        self.assertAlmostEqual(novo.elementAt(idx).y, 70, delta=1)  # a alça subiu
        self.assertEqual((novo.elementAt(0).x, novo.elementAt(0).y), (100, 100))  # os nós ficaram
        self.assertEqual((novo.elementAt(3).x, novo.elementAt(3).y), (160, 120))
        self.w.undo_stack.undo()
        self.assertAlmostEqual(self.view.shapes()[0].path().elementAt(idx).y, 100, delta=1e-6)

    def test_aviso_de_grupo_e_texto(self):
        a = ob.Shape(fm.polyline_path([QPointF(0, 0), QPointF(10, 0)]), "a", "C01", "#fff")
        b = ob.Shape(fm.polyline_path([QPointF(0, 5), QPointF(10, 5)]), "b", "C01", "#fff")
        self.w._edit("teste", lambda: self.w.canvas.scene.addItem(ob.group([a, b])))
        self.view.shapes()[0].setSelected(True)
        self.assertIn("GRUPO", self.w._aviso_nos())
        self.assertIn("Ctrl+U", self.w._aviso_nos())


if __name__ == "__main__":
    unittest.main()
