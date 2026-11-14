"""Modelos de projeto, exportar/importar preferências e converter em bitmap."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = self.nova()
        self.win.new_document()

    def nova(self, nome="t.ini"):
        w = MainWindow(QSettings(os.path.join(self.tmp.name, nome), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_error = lambda *a: None
        w.pasta_modelos = lambda: os.path.join(self.tmp.name, "modelos")
        return w

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()


class ModelosTest(Base):
    def test_salvar_e_usar_modelo(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 30, 20)), "rect")
        self.assertTrue(self.win.salvar_modelo("Chaveiro MDF"))
        self.assertFalse(self.win.undo_stack.isClean())                      # o projeto aberto continua "não salvo"
        self.assertEqual(self.win.modelos(), ["Chaveiro_MDF.rbl"])
        self.win.new_document()
        self.assertTrue(self.win.novo_de_modelo("Chaveiro_MDF.rbl"))
        self.assertEqual(len(self.win.canvas.view.shapes()), 1)
        self.assertIsNone(self.win.file_path)                                 # sem nome: não sobrescreve o modelo
        self.assertFalse(self.win.salvar_modelo("   "))


class PreferenciasArquivoTest(Base):
    def test_exportar_importar(self):
        self.win.settings.setValue("passo_seta_mm", 0.25)
        self.win.settings.setValue("atalhos/Duplicar", "Ctrl+J")
        arq = os.path.join(self.tmp.name, "p.json")
        self.assertTrue(self.win.exportar_preferencias(arq))
        w2 = self.nova("outra.ini")
        self.assertTrue(w2.importar_preferencias(arq))
        self.assertEqual(w2.canvas.view.passo_seta, 0.25)
        from redblack.ui.dialogo_atalhos import chave
        self.assertEqual({chave(a): a for a in w2.todas_acoes()}["Duplicar"].shortcut().toString(), "Ctrl+J")
        with open(arq, "w", encoding="utf-8") as f:
            f.write('{"formato": "outro"}')
        self.assertFalse(w2.importar_preferencias(arq))
        w2.close()


class BitmapTest(Base):
    def test_converter(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 20, 10)), "rect")
        self.assertTrue(self.win.converter_em_bitmap(dpi=254))
        s = self.win.canvas.view.shapes()[0]
        self.assertIsInstance(s, ob.ImageShape)
        self.assertEqual(ob.geom_rect(s), QRectF(10, 10, 20, 10))
        self.assertEqual(s.extra.qimage.width(), 200)                         # 254 dpi = 10 px/mm
        c = cm.alterar(cm.nova("C00", imagem=True), modo_imagem="limiar", intervalo_mm=0.5)
        p = pc.gerar([s.snapshot()], [c])
        self.assertAlmostEqual(p.comprimento_corte, 20 * 20, delta=1)       # retângulo preto cheio
        self.win.undo_stack.undo()
        self.assertNotIsInstance(self.win.canvas.view.shapes()[0], ob.ImageShape)


if __name__ == "__main__":
    unittest.main()
