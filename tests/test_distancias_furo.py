"""Furo dentro da peça: o clique pega o furo; linhas de distância até a borda; digitar 3 mm posiciona."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import encaixe as enc  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap_rect(x, y, w, h):
    return ob.Shape(fm.rect_path(QRectF(x, y, w, h)), "r", "C01", "#fff").snapshot()


class DistanciasPurasTest(unittest.TestCase):
    def test_furo_dentro_da_peca(self):
        base = snap_rect(100, 100, 200, 100)
        d = enc.distancias_lados((110, 150, 120, 156), [base], 400, 400)  # furo 10 × 6 perto da esquerda
        self.assertAlmostEqual(d["esq"][0], 10)   # até a borda esquerda da base (não da mesa)
        self.assertAlmostEqual(d["dir"][0], 180)
        self.assertAlmostEqual(d["cima"][0], 50)
        self.assertAlmostEqual(d["baixo"][0], 44)
        self.assertEqual(d["esq"][2], (100, 153))  # a linha sai do meio do lado

    def test_sem_vizinho_vai_ate_a_mesa(self):
        d = enc.distancias_lados((10, 20, 30, 40), [], 400, 300)
        self.assertEqual({k: v[0] for k, v in d.items()}, {"esq": 10, "dir": 370, "cima": 20, "baixo": 260})

    def test_deslocamento(self):
        self.assertEqual(enc.deslocamento_para("esq", 10, 3), (-7, 0))
        self.assertEqual(enc.deslocamento_para("dir", 10, 3), (7, 0))
        self.assertEqual(enc.deslocamento_para("cima", 10, 3), (0, -7))
        self.assertEqual(enc.deslocamento_para("baixo", 10, 3), (0, 7))


class FuroNaJanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view
        furo = ob.Shape(fm.rect_path(QRectF(110, 150, 10, 6)), "Furo", "C02", "#e0313b")
        base = ob.Shape(fm.rect_path(QRectF(100, 100, 200, 100)), "Base", "C01", "#2f6bff")

        def por():
            self.view.scene().addItem(furo)
            self.view.scene().addItem(base)  # a base fica POR CIMA do furo (como depois de desagrupar)
        self.w._edit("teste", por)
        self.view.scene().clearSelection()

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def clicar(self, x, y):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(QPointF(x, y))
        for kind, b, bs in ((QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton),
                            (QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)):
            app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), b, bs, Qt.NoModifier))
        app.processEvents()

    def nomes_sel(self):
        return [s.name for s in self.view.selected()]

    def test_clique_no_furo_pega_o_furo_e_fora_pega_a_base(self):
        self.clicar(115, 153)
        self.assertEqual(self.nomes_sel(), ["Furo"])
        self.clicar(250, 200)  # a base se pega pela linha
        self.assertEqual(self.nomes_sel(), ["Base"])

    def test_digitar_3mm_na_linha_da_esquerda(self):
        self.clicar(115, 153)
        self.assertAlmostEqual(self.view.dist["esq"][0], 10, places=6)
        self.assertIn("d_esq", self.view._centros_dist())
        self.assertTrue(self.w.definir_distancia("esq", 3.0))
        furo = next(s for s in self.view.shapes() if s.name == "Furo")
        self.assertAlmostEqual(ob.geom_rect(furo).left(), 103, places=6)
        self.assertAlmostEqual(self.view.dist["esq"][0], 3, places=6)  # as linhas acompanham
        self.w.undo_stack.undo()
        furo = next(s for s in self.view.shapes() if s.name == "Furo")
        self.assertAlmostEqual(ob.geom_rect(furo).left(), 110, places=6)

    def test_clicar_no_numero_abre_a_caixa(self):
        self.clicar(115, 153)
        c = self.view._centros_dist()["d_esq"]
        self.assertEqual(self.view.rotulo_em(c), "d_esq")
        self.view.editar_medida("d_esq")
        self.assertTrue(self.view.editor_medida.isVisible())
        self.assertEqual(self.view.editor_medida.text(), "10,00")
        self.view.editor_medida.setText("3")
        self.view._aplicar_medida()
        furo = next(s for s in self.view.shapes() if s.name == "Furo")
        self.assertAlmostEqual(ob.geom_rect(furo).left(), 103, places=6)


class CaixaEZoomTest(unittest.TestCase):
    """Base com 3 furos: caixa de seleção começando dentro da base e clique no furo com zoom longe."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view
        itens = [ob.Shape(fm.rect_path(QRectF(x, 150, 6, 20)), f"Furo {i}", "C02", "#e0313b")
                 for i, x in enumerate((130, 160, 250), 1)]
        itens.append(ob.Shape(fm.rect_path(QRectF(100, 100, 200, 100)), "Base", "C01", "#2f6bff"))
        self.w._edit("teste", lambda: [self.view.scene().addItem(i) for i in itens])
        self.view.scene().clearSelection()

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def mouse(self, kind, pt, b, bs):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(pt)
        app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), b, bs, Qt.NoModifier))
        app.processEvents()

    def test_caixa_de_dentro_da_base_pega_so_os_furos(self):
        self.view.ajustar_a(QRectF(90, 90, 220, 120))
        app.processEvents()
        self.mouse(QEvent.MouseButtonPress, QPointF(120, 130), Qt.LeftButton, Qt.LeftButton)  # miolo vazio da base
        self.mouse(QEvent.MouseMove, QPointF(150, 160), Qt.NoButton, Qt.LeftButton)
        self.mouse(QEvent.MouseMove, QPointF(180, 185), Qt.NoButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, QPointF(180, 185), Qt.LeftButton, Qt.NoButton)
        self.assertEqual(sorted(s.name for s in self.view.selected()), ["Furo 1", "Furo 2"])
        base = next(s for s in self.view.shapes() if s.name == "Base")
        self.assertEqual(ob.geom_rect(base).topLeft(), QPointF(100, 100))  # a base não foi arrastada

    def test_zoom_longe_clique_no_furo(self):
        self.view.zoom_center(0.25)  # bem longe: o furo vira poucos pixels
        self.view.zoom_center(0.25)
        app.processEvents()
        self.assertLess(6 * self.view.scale_px_mm, 24)  # furo menor que 24 px na tela
        self.mouse(QEvent.MouseButtonPress, QPointF(253, 160), Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, QPointF(253, 160), Qt.LeftButton, Qt.NoButton)
        self.assertEqual([s.name for s in self.view.selected()], ["Furo 3"])


class MoverPorDentroTest(CaixaEZoomTest):
    """Peça comum: arrastar por dentro move. Base com furos: clique seleciona; selecionada, arrasta por dentro."""

    def arrastar(self, a, b):
        self.mouse(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseMove, (a + b) / 2, Qt.NoButton, Qt.LeftButton)
        self.mouse(QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)

    def peca(self, nome):
        return next(s for s in self.view.shapes() if s.name == nome)

    def test_peca_comum_arrasta_por_dentro(self):
        self.view.ajustar_a(QRectF(90, 90, 220, 120))
        app.processEvents()
        avulsa = ob.Shape(fm.rect_path(QRectF(320, 100, 60, 40)), "Avulsa", "C01", "#2f6bff")
        self.w._edit("teste", lambda: self.view.scene().addItem(avulsa))
        self.view.ajustar_a(QRectF(90, 90, 300, 120))
        app.processEvents()
        self.arrastar(QPointF(350, 120), QPointF(350, 150))  # meio da peça
        self.assertAlmostEqual(ob.geom_rect(self.peca("Avulsa")).top(), 130, delta=1)

    def test_base_clique_seleciona_e_depois_arrasta_por_dentro(self):
        self.view.ajustar_a(QRectF(90, 90, 220, 120))
        app.processEvents()
        self.mouse(QEvent.MouseButtonPress, QPointF(200, 120), Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, QPointF(200, 120), Qt.LeftButton, Qt.NoButton)
        self.assertEqual([s.name for s in self.view.selected()], ["Base"])
        self.arrastar(QPointF(200, 120), QPointF(220, 120))
        self.assertAlmostEqual(ob.geom_rect(self.peca("Base")).left(), 120, delta=1)

    def test_selecionada_aparece_em_destaque(self):
        self.view.ajustar_a(QRectF(90, 90, 220, 120))
        app.processEvents()
        antes = self.view.viewport().grab().toImage()
        self.peca("Furo 3").setSelected(True)
        app.processEvents()
        depois = self.view.viewport().grab().toImage()
        rosa = lambda img: sum(1 for x in range(0, img.width(), 2) for y in range(0, img.height(), 2)  # noqa: E731
                               if (lambda c: c.red() > 200 and c.green() < 120 and c.blue() > 170)(img.pixelColor(x, y)))
        self.assertGreater(rosa(depois), rosa(antes) + 20)


if __name__ == "__main__":
    unittest.main()
