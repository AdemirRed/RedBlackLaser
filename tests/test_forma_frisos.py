"""Forma com medidas exatas e frisos para dobra (projeto porta-canetas Ø100 × 150)."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import frisos as fr  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.geometria import BED_H  # noqa: E402
from redblack.ui.dialogo_forma import FormaDialog  # noqa: E402
from redblack.ui.dialogo_frisos import FrisosDialog  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class FrisosTest(unittest.TestCase):
    def test_valores_do_blueprint(self):
        L = fr.desenvolvimento(100, 3, 0.8)
        self.assertAlmostEqual(L, 330.4955, 4)                            # π × 105,20
        f = fr.Frisos(L, 150, 109, 0.30)
        self.assertAlmostEqual(f.passo, 3.004505, 6)                      # L / 110
        c = f.centros()
        self.assertEqual(len(c), 109)
        self.assertAlmostEqual(c[0] - f.x_mm, f.passo)
        self.assertAlmostEqual(f.x_mm + L - c[-1], f.passo)              # simétrico
        b = f.frisos().boundingRect()
        self.assertAlmostEqual(b.height(), 150)
        self.assertEqual(f.frisos().elementCount(), 109 * 5)             # 109 retângulos
        self.assertEqual(fr.erros(f, 400, 400), [])

    def test_recusas(self):
        for ruim in (fr.Frisos(quantidade=0), fr.Frisos(largura_friso_mm=3.1), fr.Frisos(margem_mm=75),
                     fr.Frisos(x_mm=80)):
            self.assertTrue(fr.erros(ruim, 400, 400), ruim)


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(m)
        self.win.show_info = lambda t, m: None
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_circulo_por_diametro_ou_raio(self):
        dlg = FormaDialog(self.win)
        dlg.diametro.setValue(99.6)
        self.assertAlmostEqual(dlg.raio.value(), 49.8)                    # raio acompanha
        dlg.raio.setValue(49.8)
        dlg.cx.setValue(100)
        dlg.cy.setValue(80)
        path, kind, layer = dlg.forma()
        self.win.create_shape(path, kind, layer)
        b = ob.bounds(self.win._sel())
        self.assertAlmostEqual(b.width(), 99.6, 9)
        self.assertAlmostEqual(b.height(), 99.6, 9)
        self.assertAlmostEqual(b.center().x(), 100)
        self.assertAlmostEqual(BED_H - b.center().y(), 80)
        self.assertAlmostEqual(self.win.fields["w"].value(), 99.6)        # barra de propriedades mostra 99,60

    def test_retangulo_com_raio_e_poligono_na_camada(self):
        dlg = FormaDialog(self.win)
        dlg.tipo.setCurrentIndex(dlg.tipo.findData("rect"))
        dlg.largura.setValue(60.09)
        dlg.altura.setValue(50)
        dlg.raio_canto.setValue(5)
        dlg.camada.setCurrentText("C03")
        path, kind, layer = dlg.forma()
        self.assertEqual((kind, layer), ("rect", "C03"))
        self.assertAlmostEqual(path.boundingRect().width(), 60.09)
        self.assertGreater(path.elementCount(), 5)                        # cantos curvos
        dlg.tipo.setCurrentIndex(dlg.tipo.findData("polygon"))
        dlg.diametro.setValue(40)
        dlg.lados.setValue(8)
        path, kind, _ = dlg.forma()
        self.assertEqual(kind, "polygon")
        self.assertTrue(dlg.form.isRowVisible(dlg.lados))
        self.assertFalse(dlg.form.isRowVisible(dlg.largura))

    def test_frisos_no_documento(self):
        self.win.create_shape(FormaDialog(self.win).forma()[0], "ellipse", "C01")  # C01 já existe antes
        f = fr.Frisos(fr.desenvolvimento(100, 3, 0.8), 150, 109, 0.30)
        self.assertTrue(self.win.inserir_frisos(f, "C01", "C02"))
        ids = [c.id for c in self.win.layers]
        self.assertLess(ids.index("C02"), ids.index("C01"))               # frisos antes do recorte
        self.assertEqual(self.win.layer("C02").modo, "preenchimento")
        nomes = sorted(s.name for s in self.win._sel())
        self.assertEqual(nomes, ["Contorno 330,50 × 150 mm", "Frisos (109 × 0,3 mm)"])
        perc = pc.gerar([s.snapshot() for s in self.win.canvas.view.shapes()], self.win.layers)
        self.assertTrue(gc.analisar(gc.gerar(perc, self.win.layers))["dentro_da_area"])
        self.win.undo_stack.undo()                                        # um só passo desfaz tudo
        self.assertNotIn("C02", [c.id for c in self.win.layers])
        self.assertEqual(len(self.win.canvas.view.shapes()), 1)
        self.assertFalse(self.win.inserir_frisos(f, "C02", "C02"))

    def test_dialogo_calcula_comprimento(self):
        dlg = FrisosDialog(self.win)
        dlg.calc.setChecked(True)
        self.assertAlmostEqual(dlg.largura.value(), 330.4955, 4)
        self.assertIn("3,004505", dlg.info.text())
        dlg.t.setValue(4)
        self.assertAlmostEqual(dlg.largura.value(), math.pi * 107.2, 3)
        dlg.w.setValue(5)
        self.assertFalse(dlg.botoes.button(dlg.botoes.StandardButton.Ok).isEnabled())


if __name__ == "__main__":
    unittest.main()
