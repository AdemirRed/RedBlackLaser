"""Estrela e polígonos prontos (triângulo, pentágono, octógono)."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack.ui.dialogo_forma import FormaDialog  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class EstrelaTest(unittest.TestCase):
    def test_geometria(self):
        p = fm.star_path(QPointF(0, 0), 10, 5, 0.4)
        pts = p.toSubpathPolygons()[0]
        self.assertEqual(len(pts), 11)                                       # 10 vértices + fechamento
        raios = sorted({round(math.hypot(q.x(), q.y()), 6) for q in pts})
        self.assertEqual(raios, [4.0, 10.0])
        self.assertAlmostEqual(pts[0].y(), -10)                              # ponta no topo
        with self.assertRaises(ValueError):
            fm.star_path(QPointF(0, 0), 10, 2)

    def test_ferramenta_e_presets(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.resize(1400, 900)
        w.show()
        app.processEvents()
        w.new_document()
        w._poligono_preset(5, "star")  # agora é forma pronta: não mexe nas ferramentas Estrela/Polígono
        self.assertTrue(w.tools["preset"].isChecked())
        self.assertEqual(w.canvas.view.forma_pronta, "Estrela de 5 pontas")
        v, vp = w.canvas.view, w.canvas.view.viewport()
        a, b = v.mapFromScene(QPointF(100, 100)), v.mapFromScene(QPointF(130, 70))  # arrasta a caixa
        QTest.mousePress(vp, Qt.LeftButton, Qt.AltModifier, a)
        QTest.mouseMove(vp, b)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.AltModifier, b)
        s = v.shapes()[0]
        self.assertTrue(s.name.startswith("Estrela"))
        self.assertEqual(s.path().elementCount(), 11)
        w._poligono_preset(3)
        self.assertEqual(v.forma_pronta, "Triângulo")
        self.assertEqual((v.polygon_sides, v.star_pontas), (6, 5))  # o triângulo não estraga Polígono/Estrela
        w.tools["star"].trigger()
        self.assertEqual((w.lb_lados.text().strip(), w.sides.value()), ("Pontas", 5))
        w.sides.setValue(7)
        self.assertEqual((v.star_pontas, v.polygon_sides), (7, 6))
        w.tools["polygon"].trigger()
        self.assertEqual((w.lb_lados.text().strip(), w.sides.value()), ("Lados", 6))
        dlg = FormaDialog(w)
        dlg.tipo.setCurrentIndex(dlg.tipo.findData("star"))
        dlg.diametro.setValue(40)
        dlg.lados.setValue(6)
        path, kind, _ = dlg.forma()
        self.assertEqual((kind, path.elementCount()), ("star", 13))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
