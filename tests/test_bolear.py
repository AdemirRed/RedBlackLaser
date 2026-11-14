"""Bolear: arredondar todos os cantos, um só (mesmo com curvas na forma) e pontas totalmente redondas (pega)."""
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
from redblack import nos  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def curvas(p):
    return sum(p.elementAt(i).type == QPainterPath.CurveToElement for i in range(p.elementCount()))


def area(p):
    from PySide6.QtGui import QTransform
    poly = p.toFillPolygon(QTransform.fromScale(20, 20))  # o Qt achata curvas em ~1 unidade: amplia antes
    return abs(sum(poly[i].x() * poly[i + 1].y() - poly[i + 1].x() * poly[i].y()
                   for i in range(len(poly) - 1))) / 2 / 400


class BolearTest(unittest.TestCase):
    def setUp(self):
        self.ret = fm.rect_path(QRectF(0, 0, 100, 40))

    def test_todos_os_cantos(self):
        novo, n = nos.bolear(self.ret, 5)
        self.assertEqual((n, curvas(novo)), (4, 4))
        r = novo.boundingRect()
        self.assertEqual((round(r.width(), 6), round(r.height(), 6)), (100, 40))  # medida externa igual
        self.assertAlmostEqual(area(novo), 100 * 40 - (4 - math.pi) * 25, delta=0.2)
        self.assertFalse(novo.contains(QPointF(0.5, 0.5)))  # o canto foi cortado

    def test_um_canto_e_depois_os_outros(self):
        cantos = nos.cantos_boleaveis(self.ret)
        self.assertEqual(len(cantos), 4)
        c0 = next(c for c in cantos if c[2] == (0, 0))
        novo, n = nos.bolear(self.ret, 8, [c0[:2]])
        self.assertEqual((n, curvas(novo)), (1, 1))
        self.assertFalse(novo.contains(QPointF(1, 1)))
        self.assertTrue(novo.contains(QPointF(99, 39)))  # os outros cantos continuam vivos
        self.assertEqual(len(nos.cantos_boleaveis(novo)), 3)  # forma com curva: ainda dá para bolear os outros
        novo2, n2 = nos.bolear(novo, 8)
        self.assertEqual((n2, curvas(novo2)), (3, 4))

    def test_pontas_totalmente_redondas(self):
        novo, n = nos.bolear(self.ret, 20)  # raio = metade da altura: vira pega
        self.assertEqual(n, 4)
        self.assertTrue(novo.contains(QPointF(1, 20)))   # meio da ponta continua
        self.assertFalse(novo.contains(QPointF(3, 3)))   # cantos sumiram
        lado_reto = [novo.pointAtPercent(t / 400) for t in range(400)]
        self.assertTrue(any(abs(p.x()) < 0.05 for p in lado_reto))  # a ponta encosta em x = 0 só no meio

    def test_linha_aberta_nao_mexe_nas_pontas_e_raio_zero(self):
        p = fm.polyline_path([QPointF(0, 0), QPointF(50, 0), QPointF(50, 30)])
        novo, n = nos.bolear(p, 5)
        self.assertEqual(n, 1)  # só o canto do meio
        self.assertEqual(nos.bolear(p, 0)[1], 0)


class FerramentaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view
        r = ob.Shape(fm.rect_path(QRectF(100, 100, 120, 40)), "Placa", "C01", "#2f6bff")
        self.w._edit("teste", lambda: self.view.scene().addItem(r))
        self.view.ajustar_a(QRectF(80, 80, 160, 80))
        app.processEvents()
        self.w.tools["bolear"].trigger()

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def placa(self):
        return next(s for s in self.view.shapes() if s.name == "Placa")

    def clicar(self, x, y, mods=Qt.NoModifier):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(QPointF(x, y))
        for k, b, bs in ((QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton),
                         (QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)):
            app.sendEvent(vp, QMouseEvent(k, QPointF(pos), QPointF(vp.mapToGlobal(pos)), b, bs, mods))
        app.processEvents()

    def test_clique_no_canto_so_ele(self):
        self.w.raio.setValue(6)
        self.clicar(100.5, 100.5)
        self.assertEqual(curvas(self.placa().path()), 1)
        self.clicar(160, 140)  # na borda de baixo, longe dos cantos: os outros 3
        self.assertEqual(curvas(self.placa().path()), 4)
        self.w.undo_stack.undo()
        self.assertEqual(curvas(self.placa().path()), 1)

    def test_shift_pontas_redondas_e_previa(self):
        self.w._bolear_previa(QPointF(160, 140), True)
        self.assertFalse(self.view._realce.path().isEmpty())  # prévia em vermelho antes do clique
        self.clicar(160, 140, Qt.ShiftModifier)
        p = self.placa().path()
        self.assertTrue(p.contains(QPointF(101, 120)))
        self.assertFalse(p.contains(QPointF(103, 103)))
        r = ob.geom_rect(self.placa())
        self.assertEqual((round(r.width(), 6), round(r.height(), 6)), (120, 40))

    def test_raio_zerado_usa_5mm_e_fora_nao_faz_nada(self):
        self.w.raio.setValue(0)
        self.assertTrue(self.w.bolear_em(QPointF(160, 140)))
        self.assertIn("5,00 mm", self.w.statusBar().currentMessage())
        self.assertFalse(self.w.bolear_em(QPointF(300, 300)))  # vazio


if __name__ == "__main__":
    unittest.main()
