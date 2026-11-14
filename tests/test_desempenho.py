"""Desempenho com muitos objetos: seleção em massa e comandos não podem ficar quadráticos."""
import os
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class DesempenhoTest(unittest.TestCase):
    def test_quinhentos_objetos(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()

        def add():
            for i in range(500):
                w.canvas.scene.addItem(ob.Shape(fm.rect_path(QRectF((i % 25) * 15, (i // 25) * 15, 10, 10)),
                                                f"R{i}", "C01", "#2f6bff"))
        w._edit("x", add)
        t0 = time.perf_counter()
        w.select_all()
        w.duplicate()
        w.undo_stack.undo()
        w.inverter_selecao()
        w.select_all()
        w.canvas.view.nudge(1, 0)
        app.processEvents()
        self.assertLess(time.perf_counter() - t0, 5.0)                      # antes: mais de 60 s
        self.assertEqual(len(w._sel()), 500)
        self.assertEqual(sum(n.isSelected() for _, n in w._tree_map.values()), 500)  # lista Objetos em dia
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
