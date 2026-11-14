"""Preferências de importação: centralizar na mesa e agrupar."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack.geometria import BED_H, BED_W  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
       '<rect x="0" y="0" width="10" height="10"/><circle cx="30" cy="5" r="5"/></svg>')


class ImportarOpcoesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_info = lambda *a: None
        self.w.new_document()
        self.svg = os.path.join(self.tmp.name, "a.svg")
        open(self.svg, "w").write(SVG)

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_padrao_mantem_posicao_e_separa(self):
        self.assertTrue(self.w.import_path(self.svg))
        s = self.w.canvas.view.shapes()
        self.assertEqual(len(s), 2)
        self.assertAlmostEqual(ob.bounds(s).left(), 0, 3)

    def test_centralizar_e_agrupar(self):
        self.w.settings.setValue("importar_centralizar", True)
        self.w.settings.setValue("importar_agrupar", True)
        self.assertTrue(self.w.import_path(self.svg))
        s = self.w.canvas.view.shapes()
        self.assertEqual(len(s), 1)
        self.assertIsInstance(s[0], ob.GroupShape)
        c = ob.bounds(s).center()
        self.assertAlmostEqual(c.x(), BED_W / 2, 3)
        self.assertAlmostEqual(c.y(), BED_H / 2, 3)


if __name__ == "__main__":
    unittest.main()
