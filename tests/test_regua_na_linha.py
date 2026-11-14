"""Régua: medida sempre em cima da linha e encaixe em qualquer ponto dos contornos (não só nos cantos)."""
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

from redblack import encaixe as enc  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap_de(path):
    return ob.Shape(path, "s", "C01", "#fff").snapshot()


class PontoNaLinhaTest(unittest.TestCase):
    def test_meio_da_reta_e_da_curva(self):
        quad = snap_de(fm.rect_path(QRectF(0, 0, 100, 50)))
        a = enc.ponto_na_linha([quad], 37.3, 1.2, 3)
        self.assertEqual((a.tipo, round(a.x, 6), round(a.y, 6)), ("linha", 37.3, 0))  # projeta na borda de cima
        self.assertIsNone(enc.ponto_na_linha([quad], 50, 25, 3))  # longe de tudo
        circ = QPainterPath()
        circ.addEllipse(QPointF(200, 200), 40, 40)
        b = enc.ponto_na_linha([snap_de(circ)], 200 + 41 * math.cos(0.7), 200 + 41 * math.sin(0.7), 3)
        self.assertAlmostEqual(math.hypot(b.x - 200, b.y - 200), 40, delta=0.01)  # sobre o círculo

    def test_grupo_e_matriz(self):
        quad = ob.Shape(fm.rect_path(QRectF(0, 0, 10, 10)), "q", "C01", "#fff")
        quad.setPos(100, 100)
        g = ob.group([quad]).snapshot()
        a = enc.ponto_na_linha([g], 105, 99, 2)
        self.assertEqual((round(a.x, 6), round(a.y, 6)), (105, 100))


class ReguaJanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.view = self.w.canvas.view
        self.ret = next(s for s in self.view.shapes() if "Retângulo" in s.name)  # (40, 40) 60 × 30

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_snap_canto_tem_prioridade_e_linha_no_meio(self):
        v = self.view
        p = v.snap(QPointF(40.2, 40.3))
        self.assertEqual((v.snap_ind.alvo.tipo, p), ("canto", QPointF(40, 40)))
        p = v.snap(QPointF(71.3, 40.4))  # meio da borda de cima
        self.assertEqual(v.snap_ind.alvo.tipo, "linha")
        self.assertAlmostEqual(p.y(), 40, places=6)
        self.assertAlmostEqual(p.x(), 71.3, places=6)
        p = v.snap(QPointF(71.3, 40.4), Qt.AltModifier)  # Alt desliga
        self.assertEqual(p, QPointF(71.3, 40.4))

    def test_medir_de_linha_a_linha(self):
        self.w.act_medidas.setChecked(False)  # mesmo com "Mostrar medidas" desligado
        self.w.tools["measure"].setChecked(True)
        vp = self.view.viewport()

        def ev(kind, pt, b, bs):
            pos = self.view.mapFromScene(pt)
            app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), b, bs, Qt.NoModifier))
            app.processEvents()
        ev(QEvent.MouseButtonPress, QPointF(55.2, 40.3), Qt.LeftButton, Qt.LeftButton)  # borda de cima
        ev(QEvent.MouseMove, QPointF(55.4, 69.6), Qt.NoButton, Qt.LeftButton)  # borda de baixo (y = 70)
        ev(QEvent.MouseButtonRelease, QPointF(55.4, 69.6), Qt.LeftButton, Qt.NoButton)
        linha = self.view.medidas.itens["medida"]
        self.assertAlmostEqual(linha.p1().y(), 40, places=6)
        self.assertAlmostEqual(linha.p2().y(), 70, places=6)
        self.assertEqual(len(self.view.medidas.textos()), 1)
        self.view.grab()  # pinta (tracinhos e rótulo) sem erro


if __name__ == "__main__":
    unittest.main()
