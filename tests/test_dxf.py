"""DXF: importar subconjunto e exportar R12."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import dxf  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def grupos(*pares):
    return "\n".join(f"{c}\n{v}" for c, v in pares) + "\n"


AMOSTRA = grupos(
    (0, "SECTION"), (2, "HEADER"), (9, "$INSUNITS"), (70, 4), (0, "ENDSEC"),
    (0, "SECTION"), (2, "ENTITIES"),
    (0, "LINE"), (8, 0), (10, 0), (20, 0), (11, 50), (21, 0),
    (0, "CIRCLE"), (8, 0), (10, 100), (20, 100), (40, 49.8),
    (0, "ARC"), (8, 0), (10, 200), (20, 100), (40, 10), (50, 0), (51, 90),
    (0, "LWPOLYLINE"), (8, 0), (90, 4), (70, 1), (10, 0), (20, 0), (42, 0), (10, 40), (20, 0), (42, 1),
    (10, 40), (20, 20), (42, 0), (10, 0), (20, 20),
    (0, "TEXT"), (8, 0), (1, "oi"),
    (0, "ENDSEC"), (0, "EOF"))


def caixa(p):
    b = p.boundingRect()
    return tuple(round(v, 3) for v in (b.left(), b.top(), b.width(), b.height()))


class DxfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "a.dxf")
        with open(self.arq, "w") as f:
            f.write(AMOSTRA)

    def tearDown(self):
        self.tmp.cleanup()

    def test_importar(self):
        r = dxf.load(self.arq, 400)
        c = {n.split()[0]: caixa(p) for n, p in r.objetos}
        self.assertEqual(c["Line"], (0, 400, 50, 0))                       # y_doc = 400 − y
        self.assertEqual(c["Circle"], (50.2, 250.2, 99.6, 99.6))
        self.assertEqual(c["Arc"], (200, 290, 10, 10))                      # quarto de círculo de 0° a 90°
        self.assertEqual(c["Lwpolyline"], (0, 380, 50, 20))                 # bulge 1 = meia-volta de raio 10
        self.assertEqual(dict(r.ignorados), {"TEXT": 1})
        self.assertEqual(r.avisos, [])

    def test_polegadas_e_sem_unidade(self):
        with open(self.arq, "w") as f:
            f.write(AMOSTRA.replace("$INSUNITS\n70\n4", "$INSUNITS\n70\n1"))
        c = {n.split()[0]: caixa(p) for n, p in dxf.load(self.arq, 400).objetos}
        self.assertEqual(c["Line"][2], 1270)                               # 50 pol
        with open(self.arq, "w") as f:
            f.write(AMOSTRA.replace("9\n$INSUNITS\n70\n4\n", ""))
        self.assertTrue(dxf.load(self.arq, 400).avisos)

    def test_invalido(self):
        with open(self.arq, "w") as f:
            f.write("nada aqui")
        with self.assertRaises(dxf.DxfInvalido):
            dxf.load(self.arq, 400)

    def test_exportar_e_reimportar(self):
        w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_info = lambda *a: None
        w.new_document()
        w.create_shape(fm.ellipse_path(QRectF(10, 10, 99.6, 99.6)), "ellipse")
        w.create_shape(fm.rect_path(QRectF(150, 20, 40, 30)), "rect")
        saida = os.path.join(self.tmp.name, "b.dxf")
        self.assertTrue(w.exportar_dxf(saida))
        r = dxf.load(saida, 400)
        self.assertEqual(sorted(caixa(p)[2:] for _, p in r.objetos), [(40, 30), (99.6, 99.6)])
        self.assertEqual(sorted(caixa(p)[:2] for _, p in r.objetos), [(10, 10), (150, 20)])  # mesma posição
        w.new_document()
        self.assertTrue(w.import_path(saida))
        self.assertEqual(len(w.canvas.view.shapes()), 2)
        self.assertAlmostEqual(ob.bounds(w.canvas.view.shapes()).width(), 180, 3)
        w.close()


if __name__ == "__main__":
    unittest.main()
