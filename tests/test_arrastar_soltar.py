"""Arrastar e soltar arquivos na janela: SVG entra onde foi solto; .rbl abre; tipo estranho avisa."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QMimeData, QPointF, QSettings, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
       '<rect x="0" y="0" width="40" height="20" fill="none" stroke="#000"/></svg>')


def mime(*arquivos):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(a) for a in arquivos])
    return md


class ArrastarSoltarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.erros = []
        self.w.show_error = lambda t, m: self.erros.append(t)
        self.w.new_document()  # sem os objetos de exemplo

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_svg_entra_onde_foi_solto_e_rbl_abre(self):
        arq = os.path.join(self.tmp.name, "caixa.svg")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(SVG)
        self.assertTrue(self.w.soltar(mime(arq), QPointF(150, 100)))
        formas = self.w.canvas.view.shapes()
        self.assertEqual(len(formas), 1)
        r = ob.bounds(formas)
        self.assertAlmostEqual(r.center().x(), 150, delta=0.5)
        self.assertAlmostEqual(r.center().y(), 100, delta=0.5)
        self.assertAlmostEqual(r.width(), 40, delta=1.0)
        projeto = os.path.join(self.tmp.name, "p.rbl")
        self.assertTrue(self.w.save_to(projeto))
        self.w.new_document()
        self.assertTrue(self.w.soltar(mime(projeto)))
        self.assertEqual(len(self.w.canvas.view.shapes()), 1)
        txt = os.path.join(self.tmp.name, "nota.txt")
        open(txt, "w").close()
        self.assertFalse(self.w.soltar(mime(txt)))
        self.assertEqual(self.erros, ["Arquivo não suportado"])


if __name__ == "__main__":
    unittest.main()
