"""Guias inteligentes ao arrastar (centro com centro, bordas) e menu do botão direito com Desagrupar."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

from redblack import encaixe as enc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class GuiasPurasTest(unittest.TestCase):
    def test_centro_com_centro(self):
        dx, dy, segs = enc.guias_alinhamento((0, 0, 10, 10), [(100, 3.6, 120, 7.6)], tol=1.0)
        self.assertEqual(dx, 0.0)
        self.assertAlmostEqual(dy, 0.6)  # centro 5 -> 5,6
        self.assertIn(((0, 5.6), (120, 5.6)), segs)

    def test_borda_com_borda_e_longe_nada(self):
        dx, dy, segs = enc.guias_alinhamento((0, 0, 10, 10), [(10.4, 50, 20, 60)], tol=1.0)
        self.assertAlmostEqual(dx, 0.4)  # direita encosta na esquerda do outro
        self.assertEqual(dy, 0.0)
        self.assertEqual(segs, [((10.4, 0), (10.4, 60))])
        self.assertEqual(enc.guias_alinhamento((0, 0, 10, 10), [(30, 30, 40, 40)], tol=1.0), (0.0, 0.0, []))

    def test_prefere_o_mais_perto(self):
        dx, _, _ = enc.guias_alinhamento((0, 0, 10, 10), [(10.8, 50, 20, 60), (9.7, 70, 20, 80)], tol=1.0)
        self.assertAlmostEqual(dx, -0.3)  # a direita (10) para a esquerda 9,7 (0,3) ganha da 10,8 (0,8)


class GuiasArrasteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.rect = next(s for s in self.view.shapes() if "Retângulo" in s.name)  # (40, 40) 60 × 30
        self.elipse = next(s for s in self.view.shapes() if "Elipse" in s.name)  # (130, 60) 50 × 30

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def mouse(self, kind, pos, button, buttons, mods=Qt.NoModifier):
        e = QMouseEvent(kind, QPointF(pos), QPointF(self.view.viewport().mapToGlobal(pos)), button, buttons, mods)
        app.sendEvent(self.view.viewport(), e)
        app.processEvents()

    def vp(self, x, y):
        return self.view.mapFromScene(QPointF(x, y))

    def arrastar(self, dy_mm, mods=Qt.NoModifier):
        a, b = self.vp(45, 40), self.vp(45, 40 + dy_mm)  # pela linha de cima
        self.mouse(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton, mods)
        self.mouse(QEvent.MouseMove, (a + b) / 2, Qt.NoButton, Qt.LeftButton, mods)
        self.mouse(QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton, mods)
        guia = not self.view._guias.path().isEmpty()
        self.mouse(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton, mods)
        return guia

    def cy(self, s):
        return ob.bounds([s]).center().y()

    def test_gruda_centro_com_centro_e_mostra_linha(self):
        self.assertTrue(self.arrastar(19.4))  # centro 55 -> ~74,4; o da elipse é 75
        self.assertAlmostEqual(self.cy(self.rect), self.cy(self.elipse), places=6)
        self.assertTrue(self.view._guias.path().isEmpty())  # some ao soltar
        self.win.undo_stack.undo()  # o desfazer recria os objetos: buscar de novo
        rect = next(s for s in self.view.shapes() if "Retângulo" in s.name)
        self.assertAlmostEqual(self.cy(rect), 55, places=6)  # um desfazer volta tudo

    def test_alt_nao_gruda(self):
        self.assertFalse(self.arrastar(19.4, Qt.AltModifier))
        self.assertNotAlmostEqual(self.cy(self.rect), self.cy(self.elipse), places=2)

    def test_menu_direito_tem_desagrupar(self):
        textos = [a.text().replace("&", "") for a in self.win._menu_contexto if a]
        self.assertIn("Desagrupar / separar", textos)
        self.assertIn("Agrupar", textos)
        vistos = []

        def fechar():
            m = app.activePopupWidget()
            if isinstance(m, QMenu):
                vistos.append(len(m.actions()))
                m.close()
        QTimer.singleShot(50, fechar)
        self.win._menu_desenho(self.vp(70, 40))  # botão direito sobre a linha do retângulo
        self.assertEqual(self.view.selected(), [self.rect])  # seleciona o que está sob o clique
        self.assertTrue(vistos and vistos[0] > 5)


if __name__ == "__main__":
    unittest.main()
