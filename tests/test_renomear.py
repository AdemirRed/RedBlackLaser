"""Renomear objetos pela lista Objetos (duplo clique / F2)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class RenomearTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.new_document()
        self.win.create_shape(fm.ellipse_path(QRectF(10, 10, 99.6, 99.6)), "ellipse")

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_editar_na_lista_salva_e_desfaz(self):
        node = self.win.obj_tree.topLevelItem(0)
        node.setText(0, "  Fundo   Ø99,60 ")                           # como o editor da lista faz
        app.processEvents()
        s = self.win.canvas.view.shapes()[0]
        self.assertEqual(s.name, "Fundo Ø99,60")
        self.assertEqual(self.win.obj_tree.topLevelItem(0).text(0), "Fundo Ø99,60")
        p = os.path.join(self.tmp.name, "a.rbl")
        self.win.save_to(p)
        self.assertEqual(pj.load(p)[0][2], "Fundo Ø99,60")
        self.win.undo_stack.undo()
        self.assertEqual(self.win.canvas.view.shapes()[0].name, "Elipse 1")

    def test_nome_vazio_recusado_e_f2(self):
        s = self.win.canvas.view.shapes()[0]
        self.assertFalse(self.win.rename_object(s, "   "))
        self.assertEqual(s.name, "Elipse 1")
        self.assertEqual(self.win.act_rename.shortcut().toString(), "F2")
        self.win.rename_selected()                                        # abre o editor sem erro


if __name__ == "__main__":
    unittest.main()
