"""Encaixar na caixa: o selecionado vai para dentro da 1ª peça clicada (cabe, só diminui ou estica)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QIODevice, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import importar_imagem as imgimp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class EncaixarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.new_document()
        self.v = self.w.canvas.view

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def add(self, item):
        self.w._edit("t", lambda: self.v.scene().addItem(item))
        return next(s for s in self.v.shapes() if s.name == item.name)

    def selecionar(self, caixa, *dentro):
        self.v.scene().clearSelection()
        self.v.ordem_sel = []
        for s in (caixa, *dentro):
            s.setSelected(True)
            self.v.ordem_sel.append(s)

    def r(self, s):
        q = ob.geom_rect(s)
        return tuple(round(x, 4) for x in (q.left(), q.top(), q.width(), q.height()))

    def test_tres_modos(self):
        caixa = self.add(ob.Shape(fm.rect_path(QRectF(100, 100, 80, 40)), "Caixa", "C01", "#2f6bff"))
        logo = self.add(ob.Shape(fm.ellipse_path(QRectF(10, 10, 20, 10)), "Logo", "C02", "#e0313b"))
        self.selecionar(caixa, logo)
        self.assertTrue(self.w.encaixar_na_caixa({"modo": "diminuir", "margem": 0}))
        self.assertEqual(self.r(logo), (130, 115, 20, 10))  # coube: só centralizou
        self.assertTrue(self.w.encaixar_na_caixa({"modo": "caber", "margem": 5}))
        self.assertEqual(self.r(logo), (110, 105, 60, 30))  # proporcional (2:1) até a altura útil de 30
        self.assertTrue(self.w.encaixar_na_caixa({"modo": "esticar", "margem": 0}))
        self.assertEqual(self.r(logo), (100, 100, 80, 40))  # deformou para preencher
        self.assertEqual(self.r(caixa), (100, 100, 80, 40))  # a caixa não muda
        self.w.undo_stack.undo()  # o desfazer recria as peças: busca pelo nome
        self.assertEqual(self.r(next(s for s in self.v.shapes() if s.name == "Logo")), (110, 105, 60, 30))

    def test_imagem_grande_so_diminui_e_varios_itens_juntos(self):
        img = QImage(400, 200, QImage.Format_RGB32)
        img.fill(QColor("gray"))
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        res = imgimp.from_bytes(bytes(buf.data()), "foto.png")
        foto = self.add(ob.ImageShape(res.imagem, 200, 100, "Foto"))
        caixa = self.add(ob.Shape(fm.rect_path(QRectF(0, 0, 50, 50)), "Caixa", "C01", "#2f6bff"))
        texto = self.add(ob.Shape(fm.rect_path(QRectF(0, 120, 200, 10)), "Legenda", "C01", "#2f6bff"))
        self.selecionar(caixa, foto, texto)
        self.assertTrue(self.w.encaixar_na_caixa({"modo": "diminuir", "margem": 0}))
        b = ob.bounds([foto, texto])
        self.assertAlmostEqual(b.width(), 50, places=4)  # o conjunto (200 × 130) diminuiu junto
        self.assertAlmostEqual(b.height(), 50 * 130 / 200, places=4)
        self.assertAlmostEqual(b.center().y(), 25, places=4)

    def test_precisa_de_duas_pecas(self):
        caixa = self.add(ob.Shape(fm.rect_path(QRectF(0, 0, 50, 50)), "Caixa", "C01", "#2f6bff"))
        self.selecionar(caixa)
        self.assertFalse(self.w.encaixar_na_caixa({"modo": "caber", "margem": 0}))
        self.assertIn(self.w.act_encaixar, self.w._menu_contexto)


if __name__ == "__main__":
    unittest.main()
