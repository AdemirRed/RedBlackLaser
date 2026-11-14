"""Exportar vetores para SVG e reimportar sem perda."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import importar_svg as svg  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class ExportarSvgTest(unittest.TestCase):
    def test_ida_e_volta(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.ellipse_path(QRectF(10, 10, 99.6, 99.6)), "ellipse")
        w.create_shape(fm.rect_path(QRectF(150, 20, 40, 30)), "rect", "C02")
        w.fields["rot"].setValue(30)
        w.fields["rot"].editingFinished.emit()                               # matriz aplicada na exportação
        esperado = sorted((round(b.width(), 3), round(b.height(), 3))
                          for b in (ob.geom_rect(s) for s in w.canvas.view.shapes()))
        p = os.path.join(tmp.name, "a.svg")
        self.assertTrue(w.exportar_svg(p))
        res = svg.load(p)
        obtido = sorted((round(path.boundingRect().width(), 3), round(path.boundingRect().height(), 3))
                        for _, path in res.objetos)
        self.assertEqual(obtido, esperado)
        texto = open(p, encoding="utf-8").read()
        self.assertIn('width="400mm"', texto)
        self.assertIn('data-camada="C02"', texto)
        w.canvas.scene.clearSelection()
        w.canvas.view.shapes()[0].setSelected(True)
        self.assertTrue(w.exportar_svg(p, so_selecao=True))
        self.assertEqual(len(svg.load(p).objetos), 1)
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
