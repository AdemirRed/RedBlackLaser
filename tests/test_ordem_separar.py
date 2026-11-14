"""Desagrupar/separar objetos compostos (frisos) e ordem de corte dos objetos."""
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
from redblack import frisos as fr  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.show_error = lambda t, m: None
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def nomes(self):
        return [s.name for s in self.win.canvas.view.shapes()]

    def sel(self, *nomes):
        for s in self.win.canvas.view.shapes():
            s.setSelected(s.name in nomes)
        app.processEvents()


class SepararTest(Base):
    def test_subcaminhos_mantem_curvas(self):
        p = fm.ellipse_path(QRectF(0, 0, 10, 10))
        p.addRect(QRectF(20, 0, 5, 5))
        a, b = fm.subcaminhos(p)
        self.assertEqual(a, fm.ellipse_path(QRectF(0, 0, 10, 10)))
        self.assertEqual(b.boundingRect(), QRectF(20, 0, 5, 5))
        self.assertEqual(fm.n_contornos(p), 2)

    def test_frisos_separados_no_lugar(self):
        self.win.create_shape(fm.rect_path(QRectF(0, 0, 5, 5)), "rect")       # antes
        f = fr.Frisos(60.09, 50, 19, 0.3, 0, 20, 20)
        self.win.inserir_frisos(f, None, "C02")
        self.win.create_shape(fm.rect_path(QRectF(300, 0, 5, 5)), "rect")     # depois
        self.sel("Frisos (19 × 0,3 mm)")
        self.assertTrue(self.win.act_ungroup.isEnabled())
        self.win.ungroup_selected()
        n = self.nomes()
        self.assertEqual(len(n), 2 + 19)
        self.assertEqual(n[0], "Retângulo 1")
        self.assertEqual(n[1], "Frisos (19 × 0,3 mm) 001")
        self.assertEqual(n[-1], "Retângulo 2")                                  # partes no lugar do original
        partes = self.win.canvas.view.shapes()[1:-1]
        self.assertTrue(all(s.layer == "C02" and s.isSelected() for s in partes))
        self.assertAlmostEqual(ob.bounds([partes[0]]).center().x(), f.centros()[0], 6)
        self.win.undo_stack.undo()
        self.assertEqual(len(self.nomes()), 3)

    def test_grupo_desagrupa_no_lugar(self):
        for x in (0, 20, 40):
            self.win.create_shape(fm.rect_path(QRectF(x, 0, 5, 5)), "rect")
        self.sel("Retângulo 1", "Retângulo 2")
        self.win.group_selected()
        self.win.mover_ordem("primeiro")
        self.win.ungroup_selected()
        self.assertEqual(self.nomes(), ["Retângulo 1", "Retângulo 2", "Retângulo 3"])


class OrdemTest(Base):
    def test_subir_descer_primeiro_ultimo_e_corte(self):
        for x in (0, 50, 100, 150):
            self.win.create_shape(fm.rect_path(QRectF(x, 0, 10, 10)), "rect")
        self.sel("Retângulo 3")
        self.assertTrue(self.win.mover_ordem("subir"))
        self.assertEqual(self.nomes(), ["Retângulo 1", "Retângulo 3", "Retângulo 2", "Retângulo 4"])
        self.win.mover_ordem("primeiro")
        self.assertEqual(self.nomes()[0], "Retângulo 3")
        self.assertFalse(self.win.mover_ordem("subir"))                        # já é o primeiro
        self.win.mover_ordem("ultimo")
        self.assertEqual(self.nomes()[-1], "Retângulo 3")
        self.win.mover_ordem("subir")
        self.assertEqual(self.nomes(), ["Retângulo 1", "Retângulo 2", "Retângulo 3", "Retângulo 4"])
        self.sel("Retângulo 1")
        self.win.mover_ordem("descer")
        snaps = [s.snapshot() for s in self.win.canvas.view.shapes()]
        cortes = [t for t in pc.gerar(snaps, self.win.layers).trechos if t.tipo == "corte"]
        self.assertEqual(round(min(p[0] for p in cortes[0].pontos)), 50)        # corta na nova ordem
        self.assertEqual(round(min(p[0] for p in cortes[1].pontos)), 0)
        self.assertTrue(self.win.canvas.view.shapes()[1].isSelected())        # seleção mantida
        self.win.undo_stack.undo()
        self.assertEqual(self.nomes()[0], "Retângulo 1")

    def test_ancora_sobrevive_a_ordem(self):
        for x in (0, 50):
            self.win.create_shape(fm.rect_path(QRectF(x, 0, 10, 10)), "rect")
        a, b = self.win.canvas.view.shapes()
        self.sel("Retângulo 1")
        b.setSelected(True)
        app.processEvents()
        self.win.prender_ancora()
        self.sel("Retângulo 2")
        self.win.mover_ordem("primeiro")
        self.assertEqual(self.win.doc_state()[5], ((0, 1),))                   # preso continua preso


if __name__ == "__main__":
    unittest.main()
