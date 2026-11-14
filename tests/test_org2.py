"""Escala %, contorno elástico, cisalhar e copiar ao longo do caminho."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class Org2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def ret(self, *r):
        self.win.create_shape(fm.rect_path(QRectF(*r)), "rect")
        return self.win._sel()[0]

    def test_escala_percentual(self):
        s = self.ret(100, 100, 40, 20)
        self.win.lock.setChecked(True)
        self.win.fields["wp"].setValue(150)
        self.win.fields["wp"].editingFinished.emit()
        b = ob.geom_rect(s)
        self.assertAlmostEqual((b.width(), b.height())[0], 60, 6)
        self.assertAlmostEqual(b.height(), 30, 6)
        self.assertEqual(self.win.fields["wp"].value(), 100)                 # volta a 100 %
        self.win.lock.setChecked(False)
        self.win.fields["hp"].setValue(50)
        self.win.fields["hp"].editingFinished.emit()
        self.assertAlmostEqual(ob.geom_rect(s).height(), 15, 6)
        self.assertAlmostEqual(ob.geom_rect(s).width(), 60, 6)

    def test_contorno_elastico(self):
        a, b = self.ret(0, 0, 10, 10), self.ret(50, 30, 10, 10)
        a.setSelected(True)
        self.assertTrue(self.win.contorno_elastico())
        novo = self.win._sel()[0]
        self.assertEqual(novo.name, "Contorno elástico")
        self.assertEqual(ob.geom_rect(novo), QRectF(0, 0, 60, 40))
        self.assertEqual(len(fm.nodes(novo.path())), 6)                       # casco convexo de dois quadrados

    def test_cisalhar(self):
        s = self.ret(100, 100, 20, 20)
        self.win.anchor_group.button(4).setChecked(True)
        self.win.cisalhar({"ax": 45.0, "ay": 0.0})
        b = ob.geom_rect(s)
        self.assertAlmostEqual(b.width(), 40, 6)                            # topo e base deslocados ±10
        self.assertAlmostEqual(b.height(), 20, 6)

    def test_copiar_ao_longo_de_linha(self):
        q = self.ret(0, 0, 4, 4)
        self.win.create_shape(fm.polyline_path([QPointF(100, 100), QPointF(200, 100)]), "line")
        linha = self.win._sel()[0]
        self.win.canvas.scene.clearSelection()
        q.setSelected(True)
        app.processEvents()
        linha.setSelected(True)
        app.processEvents()
        self.assertTrue(self.win.copiar_ao_longo({"quantidade": 3, "girar": True, "incrementar": False}))
        centros = sorted(round(ob.geom_rect(s).center().x(), 6) for s in self.win._sel())
        self.assertEqual(centros, [100, 150, 200])


if __name__ == "__main__":
    unittest.main()
