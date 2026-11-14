"""Dimensionar/rotacionar por dois pontos: a referência vai exatamente para o alvo, o ponto fixo não se move."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class DoisPontosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.rect = next(s for s in self.view.shapes() if "Retângulo" in s.name)  # (40, 40) 60 × 30
        self.view.scene().clearSelection()
        self.rect.setSelected(True)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def clicar(self, x, y):
        pos = self.view.mapFromScene(QPointF(x, y))
        for kind, b, bs in ((QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton),
                            (QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)):
            app.sendEvent(self.view.viewport(), QMouseEvent(kind, QPointF(pos),
                                                            QPointF(self.view.viewport().mapToGlobal(pos)), b, bs,
                                                            Qt.NoModifier))
        app.processEvents()

    def test_gira_90_e_dobra(self):
        # canto sup. esq. fixo; canto sup. dir. (100, 40) vai para (40, 160): +90° (horário na tela) e ×2
        self.assertTrue(self.win.aplicar_dois_pontos(QPointF(40, 40), QPointF(100, 40), QPointF(40, 160)))
        r = ob.geom_rect(self.win._sel()[0])
        for got, exp in zip(r.getCoords(), (-20, 40, 40, 160)):
            self.assertAlmostEqual(got, exp, places=6)

    def test_tres_cliques_com_encaixe(self):
        self.assertTrue(self.win.dois_pontos())
        self.clicar(40.3, 40.2)    # perto do canto: gruda em (40, 40)
        self.clicar(99.8, 40.1)    # gruda em (100, 40)
        self.clicar(130, 40)       # mesmo rumo, 1,5× mais longe (ponto livre)
        self.assertIsNone(self.view.coleta)
        r = ob.geom_rect(next(s for s in self.view.shapes() if "Retângulo" in s.name))
        # o 3º clique é livre (sem encaixe): o mouse dá pixels inteiros, então ~0,5 px de erro no alvo
        tol = 1.0 / self.view.scale_px_mm * 3
        self.assertAlmostEqual(r.top(), 40, delta=tol)  # o fixo (canto que grudou) não se moveu
        self.assertAlmostEqual(r.left(), 40, delta=tol)
        self.assertAlmostEqual(r.width(), 90, delta=tol)
        self.assertAlmostEqual(r.height(), 45, delta=tol)
        self.win.undo_stack.undo()
        r = ob.geom_rect(next(s for s in self.view.shapes() if "Retângulo" in s.name))
        self.assertAlmostEqual(r.width(), 60, places=6)

    def test_esc_cancela_e_pontos_iguais(self):
        self.win.dois_pontos()
        self.clicar(40, 40)
        app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.assertIsNone(self.view.coleta)
        self.assertFalse(self.win.aplicar_dois_pontos(QPointF(1, 1), QPointF(1, 1), QPointF(5, 5)))
        self.view.scene().clearSelection()
        self.assertFalse(self.win.dois_pontos())  # sem seleção


if __name__ == "__main__":
    unittest.main()
