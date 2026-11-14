"""Ações em lote das camadas (menu de clique direito)."""
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


class AcoesCamadasTest(unittest.TestCase):
    def test_lote_e_desfazer(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        for i, lid in enumerate(("C01", "C02", "C03")):
            w.create_shape(fm.rect_path(QRectF(10 * i, 0, 5, 5)), "rect", lid)
        saida = lambda: [c.saida for c in w.layers]
        self.assertTrue(w.acao_camadas("saida_so_esta", "C02"))
        self.assertEqual(saida(), [False, True, False])
        w.acao_camadas("saida_inverter")
        self.assertEqual(saida(), [True, False, True])
        w.acao_camadas("ver_so_esta", "C03")
        vis = {s.layer: s.isVisible() for s in w.canvas.view.shapes()}
        self.assertEqual(vis, {"C01": False, "C02": False, "C03": True})
        w.acao_camadas("ar_todas")
        self.assertTrue(all(c.air for c in w.layers))
        self.assertFalse(w.acao_camadas("ar_todas"))                       # nada muda: sem passo no histórico
        w.undo_stack.undo()
        self.assertFalse(any(c.air for c in w.layers))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
