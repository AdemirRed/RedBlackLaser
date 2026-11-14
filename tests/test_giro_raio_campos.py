"""Campos Girar e Raio mostram e guardam o valor da peça selecionada (correção pedida pelo usuário)."""
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
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class CamposTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def campo(self, k, v):
        f = self.win.fields[k] if k != "raio" else self.win.raio
        f.setValue(v)
        if k != "raio":
            f.editingFinished.emit()

    def sel(self, s):
        self.win.canvas.scene.clearSelection()
        s.setSelected(True)
        app.processEvents()

    def test_raio_le_troca_e_volta_a_zero(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 60, 40)), "rect")
        s = self.win._sel()[0]
        self.assertEqual(self.win.raio.value(), 0)
        self.campo("raio", 5)
        self.assertAlmostEqual(fm.raio_retangulo(s.path()), 5)
        self.campo("raio", 12)                                       # troca de novo: parte do retângulo
        self.assertAlmostEqual(fm.raio_retangulo(s.path()), 12)
        self.assertAlmostEqual(ob.bounds([s]).width(), 60, 6)
        self.win.canvas.scene.clearSelection()
        app.processEvents()
        self.sel(s)
        self.assertAlmostEqual(self.win.raio.value(), 12)            # valor fica guardado na peça
        self.campo("raio", 0)
        self.assertEqual(fm.raio_retangulo(s.path()), 0.0)           # cantos vivos de novo

    def test_raio_em_peca_redimensionada_e_girada(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 20, 20)), "rect")
        s = self.win._sel()[0]
        self.campo("rot", 30)
        self.campo("raio", 4)
        self.assertAlmostEqual(self.win.raio.value(), 4)
        self.assertAlmostEqual(self.win.fields["rot"].value(), 30)   # giro mantido ao arredondar
        self.win.lock.setChecked(False)
        self.campo("rot", 0)
        self.campo("w", 50)                                          # esticada: raio continua em mm reais
        self.campo("raio", 6)
        self.assertAlmostEqual(self.win.raio.value(), 6)
        self.assertAlmostEqual(ob.bounds([s]).width(), 50, 6)

    def test_giro_fica_salvo_no_campo_e_no_projeto(self):
        self.win.create_shape(fm.rect_path(QRectF(100, 100, 40, 10)), "rect")
        s = self.win._sel()[0]
        self.campo("rot", 45)
        self.assertAlmostEqual(self.win.fields["rot"].value(), 45)
        self.campo("rot", 45)                                        # mesmo valor: não gira de novo
        self.assertAlmostEqual(ob.angulo(s), 45)
        p = os.path.join(self.tmp.name, "g.rbl")
        self.win.save_to(p)
        self.win.new_document()
        self.win.open_path(p)
        self.sel(self.win.canvas.view.shapes()[0])
        self.assertAlmostEqual(self.win.fields["rot"].value(), 45)

    def test_sem_selecao_raio_vale_para_novos(self):
        self.campo("raio", 3)
        self.assertEqual(self.win.canvas.view.raio_canto, 3)


if __name__ == "__main__":
    unittest.main()
