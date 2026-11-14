"""Associar formas: juntar linhas soltas (ex.: DXF com um LINE por lado)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import booleanas as bo  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def seg(a, b):
    return fm.polyline_path([QPointF(*a), QPointF(*b)])


class JuntarTest(unittest.TestCase):
    def test_quatro_lados_viram_um_quadrado_fechado(self):
        lados = [seg((0, 0), (10, 0)), seg((10, 10), (10, 0)), seg((10, 10), (0, 10)), seg((0, 0.02), (0, 10))]
        paths, unioes = fm.juntar_abertos(lados, tol=0.05)
        self.assertEqual((len(paths), unioes), (1, 3))
        self.assertFalse(fm.aberto(paths[0]))
        self.assertTrue(bo.fechado(paths[0]))

    def test_longe_nao_junta_e_fechado_passa(self):
        paths, unioes = fm.juntar_abertos([seg((0, 0), (5, 0)), seg((6, 0), (9, 0))], tol=0.05)
        self.assertEqual((len(paths), unioes), (2, 0))
        q = fm.polyline_path([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1)], closed=True)
        self.assertEqual(fm.juntar_abertos([q])[1], 0)

    def test_na_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 10)), ((10, 10), (0, 0))):
            w.create_shape(seg(a, b), "line")
        w.select_all()
        self.assertEqual(w.juntar_formas(), 2)
        s = w.canvas.view.shapes()
        self.assertEqual(len(s), 1)
        self.assertFalse(fm.tem_aberto(s[0].path()))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
