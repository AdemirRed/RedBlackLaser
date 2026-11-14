"""Otimizar (simplificar) formas e paleta de 30 camadas."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class OtimizarTest(unittest.TestCase):
    def test_simplificar_reta_cheia_de_nos(self):
        pts = [QPointF(x, 0.001 * (x % 2)) for x in range(101)]               # 101 nós quase em linha
        novo, a, d = fm.simplificar(fm.polyline_path(pts), 0.01)
        self.assertEqual((a, d), (101, 2))
        q = fm.polyline_path([QPointF(0, 0), QPointF(5, 0), QPointF(10, 0), QPointF(10, 10), QPointF(0, 10)],
                             closed=True)
        n2, a2, d2 = fm.simplificar(q, 0.01)
        self.assertLess(d2, a2)
        self.assertFalse(fm.aberto(fm.subcaminhos(n2)[0]))                  # continua fechado
        c = fm.ellipse_path(QRectF(0, 0, 10, 10))
        self.assertEqual(fm.simplificar(c, 1)[1:], (c.elementCount(), c.elementCount()))  # curva fica

    def test_na_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.polyline_path([QPointF(x, 50) for x in range(10, 60)]), "line")
        self.assertEqual(w.otimizar_formas(0.01), 48)
        w.undo_stack.undo()
        self.assertEqual(w.canvas.view.shapes()[0].path().elementCount(), 50)
        w.close()
        tmp.cleanup()


class PaletaTest(unittest.TestCase):
    def test_trinta_camadas(self):
        self.assertEqual(len(cm.IDS), 30)
        self.assertEqual(cm.IDS[-1], "C29")
        self.assertEqual(len(set(cm.PALETA)), 30)
        d = pj.to_dict([], [cm.nova("C29")])
        self.assertEqual(pj.layers_from_dict(d)[0].id, "C29")


if __name__ == "__main__":
    unittest.main()
