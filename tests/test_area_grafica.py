"""Etapa 2: coordenadas e escala consistentes em diferentes níveis de zoom."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import geometria as g  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AreaGraficaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"  # sem diálogo modal nos testes
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def wheel(self, pos, steps):
        e = QWheelEvent(QPointF(pos), QPointF(self.view.viewport().mapToGlobal(pos)), QPoint(),
                        QPoint(0, 120 * steps), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        app.sendEvent(self.view.viewport(), e)
        app.processEvents()

    def mouse(self, kind, pos, button, buttons):
        e = QMouseEvent(kind, QPointF(pos), QPointF(self.view.viewport().mapToGlobal(pos)), button, buttons, Qt.NoModifier)
        app.sendEvent(self.view.viewport(), e)

    def test_zoom_mantem_ponto_sob_cursor(self):
        pos = QPoint(300, 200)
        for steps in (3, 4, -2, 6, -9):
            before = self.view.mapToScene(pos)
            self.wheel(pos, steps)
            after = self.view.mapToScene(pos)
            tol = 1.5 / self.view.scale_px_mm  # barras de rolagem inteiras: até ~1 px
            self.assertAlmostEqual(before.x(), after.x(), delta=tol)
            self.assertAlmostEqual(before.y(), after.y(), delta=tol)

    def test_escala_limitada(self):
        self.wheel(QPoint(300, 200), 80)
        self.assertAlmostEqual(self.view.scale_px_mm, g.SCALE_MAX)
        self.wheel(QPoint(300, 200), -120)
        self.assertAlmostEqual(self.view.scale_px_mm, g.SCALE_MIN)

    def test_reguas_consistentes_em_varios_zooms(self):
        for steps in (0, 4, 8, 12, -3):
            if steps:
                self.wheel(QPoint(400, 300), steps)
            s = self.view.scale_px_mm
            for ruler in (self.win.canvas.top, self.win.canvas.left):
                ticks, _ = ruler.tick_positions()
                self.assertGreater(len(ticks), 2)
                (v0, p0, _), (v1, p1, _) = ticks[0], ticks[-1]
                # px por mm medido na régua == escala da vista (vertical cresce para cima)
                self.assertAlmostEqual(abs(p1 - p0) / abs(v1 - v0), s, delta=s * 0.01)
            # régua horizontal e posição da cena concordam no ponto 0 de exibição
            top = self.win.canvas.top
            off = self.view.viewport().pos().x()
            self.assertAlmostEqual(top._px(100), self.view.mapFromScene(QPointF(100, 0)).x() + off, delta=1)

    def test_deslocar_com_botao_do_meio(self):
        self.wheel(QPoint(400, 300), 5)  # aproxima para haver espaço de deslocamento
        before = self.view.mapToScene(QPoint(400, 300))
        self.mouse(QEvent.MouseButtonPress, QPoint(400, 300), Qt.MiddleButton, Qt.MiddleButton)
        self.mouse(QEvent.MouseMove, QPoint(500, 350), Qt.NoButton, Qt.MiddleButton)
        self.mouse(QEvent.MouseButtonRelease, QPoint(500, 350), Qt.MiddleButton, Qt.NoButton)
        after = self.view.mapToScene(QPoint(500, 350))
        tol = 1.5 / self.view.scale_px_mm
        self.assertAlmostEqual(before.x(), after.x(), delta=tol)  # conteúdo acompanhou o mouse
        self.assertAlmostEqual(before.y(), after.y(), delta=tol)

    def test_ajustar_a_mesa(self):
        self.wheel(QPoint(100, 100), 7)
        self.assertFalse(self.view.fit_mode)
        self.win.actions_by_key["zoom_fit"].trigger()
        vp = self.view.viewport().rect()
        a, b = self.view.mapFromScene(QPointF(0, 0)), self.view.mapFromScene(QPointF(g.BED_W, g.BED_H))
        self.assertTrue(vp.contains(a) and vp.contains(b))

    def test_coordenada_no_status(self):
        p = self.view.mapFromScene(QPointF(100, g.BED_H - 50))  # exibição (100, 50)
        self.mouse(QEvent.MouseMove, p, Qt.NoButton, Qt.NoButton)
        x, y = (float(t.replace(",", ".")) for t in self.win.coords.text().split()[1:4:2])
        tol = 1 / self.view.scale_px_mm
        self.assertAlmostEqual(x, 100, delta=tol)
        self.assertAlmostEqual(y, 50, delta=tol)

    def test_medir(self):
        msgs = []
        self.view.measured.connect(msgs.append)
        self.win.tools["measure"].setChecked(True)
        a = self.view.mapFromScene(QPointF(10, 10))
        b = self.view.mapFromScene(QPointF(40, 50))
        self.mouse(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)
        d = float(msgs[-1].split()[1].replace(",", "."))
        self.assertAlmostEqual(d, 50, delta=2 / self.view.scale_px_mm)
        self.view.toolExit.emit()
        self.assertFalse(self.win.tools["measure"].isChecked())
        self.assertFalse(self.view.measure_mode)


if __name__ == "__main__":
    unittest.main()
