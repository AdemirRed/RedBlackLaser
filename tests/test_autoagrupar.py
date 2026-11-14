"""Autoagrupar: externo + o que está dentro dele."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AutoagruparTest(unittest.TestCase):
    def test_agrupa_por_contencao(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        for r in ((0, 0, 50, 50), (10, 10, 10, 10), (30, 30, 10, 10), (100, 0, 40, 40), (110, 10, 5, 5),
                  (200, 0, 10, 10)):
            w.create_shape(fm.rect_path(QRectF(*r)), "rect")
        w.select_all()
        self.assertEqual(w.autoagrupar(), 2)
        s = w.canvas.view.shapes()
        grupos = [x for x in s if isinstance(x, ob.GroupShape)]
        self.assertEqual(sorted(len(g.extra.children) for g in grupos), [2, 3])
        self.assertEqual(len(s), 3)                                           # 2 grupos + o solto
        w.undo_stack.undo()
        self.assertEqual(len(w.canvas.view.shapes()), 6)
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
