"""Menu Editar: recortar, colar no lugar, inverter seleção, selecionar formas, fechar, duplicados, direção."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class EditarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.new_document()
        self.view = self.win.canvas.view
        self.win.create_shape(fm.rect_path(QRectF(0, 0, 100, 100)), "rect")
        self.win.create_shape(fm.ellipse_path(QRectF(10, 10, 20, 20)), "ellipse")
        self.win.create_shape(fm.polyline_path([QPointF(50, 50), QPointF(80, 50), QPointF(80, 80), QPointF(50, 80),
                                                QPointF(50, 50.3)]), "line")
        self.ret, self.circ, self.lin = self.view.shapes()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def sel(self, *itens):
        self.win.canvas.scene.clearSelection()
        for it in itens:
            it.setSelected(True)

    def test_recortar_colar_no_lugar_e_inverter(self):
        self.sel(self.circ)
        self.win.cut()
        self.assertEqual(len(self.view.shapes()), 2)
        self.win.paste_in_place()
        novo = self.win._sel()[0]
        self.assertEqual(ob.geom_rect(novo), QRectF(10, 10, 20, 20))         # mesmo lugar
        self.win.inverter_selecao()
        self.assertEqual(sorted(s.name for s in self.win._sel()), ["Linha 1", "Retângulo 1"])

    def test_selecionar_formas(self):
        self.assertEqual([s.name for s in self.win.selecionar_abertas()], ["Linha 1"])
        self.assertEqual([s.name for s in self.win.selecionar_circulos()], ["Elipse 1"])
        self.sel(self.ret)
        self.assertEqual(sorted(s.name for s in self.win.selecionar_contidas()), ["Elipse 1", "Linha 1"])
        self.sel(self.ret)
        self.assertEqual(len(self.win.selecionar_menores()), 2)
        self.win.set_layer_field("C01", "modo", "preenchimento")
        self.assertEqual(len(self.win.selecionar_abertas(True)), 1)

    def test_fechar_com_tolerancia(self):
        self.sel(self.lin)
        self.assertEqual(self.win.fechar_caminhos(0.1), 0)                   # vão de 0,3 > 0,1
        self.assertEqual(self.win.fechar_caminhos(0.5), 1)
        self.assertFalse(fm.tem_aberto(self.lin.path()))
        p = self.lin.path()
        fim = p.elementAt(p.elementCount() - 1)
        self.assertEqual((fim.x, fim.y), (50, 50))                           # emendado no próprio início
        self.win.undo_stack.undo()
        self.assertTrue(fm.tem_aberto(self.view.shapes()[2].path()))

    def test_duplicados_e_direcao(self):
        self.sel(self.circ)
        self.win.copy()
        self.win.paste_in_place()
        self.win.paste_in_place()
        self.assertEqual(self.win.eliminar_duplicados(), 2)
        self.assertEqual(len(self.view.shapes()), 3)
        self.sel(self.view.shapes()[2])
        antes = self.view.shapes()[2].path().elementAt(0)
        self.win.inverter_direcao()
        depois = self.view.shapes()[2].path().elementAt(0)
        self.assertEqual((depois.x, depois.y), (50, 50.3))
        self.assertNotEqual((antes.x, antes.y), (depois.x, depois.y))


if __name__ == "__main__":
    unittest.main()
