"""Texto ao longo de um caminho."""
import math
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
from redblack import texto_caminho as txc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
P = tx.TextoParams("REDBLACK", "Arial", 5)


class TextoCaminhoTest(unittest.TestCase):
    def test_reta_igual_ao_texto_comum(self):
        reta = fm.polyline_path([QPointF(0, 50), QPointF(200, 50)])
        p = txc.aplicar(P, reta)
        comum = tx.build_path(P).boundingRect()
        b = p.boundingRect()
        self.assertAlmostEqual(b.width(), comum.width(), 1)
        self.assertAlmostEqual(b.height(), comum.height(), 1)
        self.assertAlmostEqual(b.bottom(), 50, 0)                            # letras em cima da linha de base

    def test_circulo_letras_ficam_no_raio(self):
        c = fm.ellipse_path(QRectF(-50, -50, 100, 100))
        p = txc.aplicar(P, c, inicio_pct=0)
        dist = [math.hypot(q.x(), q.y()) for poly in p.toSubpathPolygons() for q in poly]
        self.assertTrue(all(44 <= d <= 56 for d in dist), (min(dist), max(dist)))
        longe = txc.aplicar(P, c, deslocamento_mm=10)
        d2 = [math.hypot(q.x(), q.y()) for poly in longe.toSubpathPolygons() for q in poly]
        self.assertNotAlmostEqual(min(d2), min(dist), 0)

    def test_na_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_text(P, QPointF(50, 50))
        t = w._sel()[0]
        w.create_shape(fm.ellipse_path(QRectF(100, 100, 100, 100)), "ellipse")
        circ = w._sel()[0]
        w.canvas.scene.clearSelection()
        t.setSelected(True)
        app.processEvents()
        circ.setSelected(True)
        app.processEvents()
        self.assertTrue(w.texto_no_caminho({"inicio": 75.0, "deslocamento": 0.0, "inverter": False}))
        nomes = sorted(s.name for s in w.canvas.view.shapes())
        self.assertIn("Elipse 1", nomes)
        self.assertTrue(any(n.endswith("(no caminho)") for n in nomes))
        self.assertFalse(any(isinstance(s, ob.TextShape) for s in w.canvas.view.shapes()))
        w.undo_stack.undo()
        self.assertTrue(any(isinstance(s, ob.TextShape) for s in w.canvas.view.shapes()))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
