"""Ferramenta Linha: clicar, apontar com o mouse e digitar a medida = segmento exato naquela direção."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class LinhaMedidaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.v = self.w.canvas.view
        self.v.encaixe_ativo = False

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_digita_comprimento_na_direcao_do_mouse(self):
        v = self.v
        v.draw_tool = "line"
        v._line_pts = [QPointF(50, 50)]
        v._mouse_linha = QPointF(80, 90)  # direção 3-4-5
        for ch in "25,5":
            QTest.keyClick(v, ch)
        QTest.keyClick(v, Qt.Key_Return, Qt.ShiftModifier)  # Shift+Enter: ângulo livre do mouse
        p = v._line_pts[-1]
        self.assertAlmostEqual(math.hypot(p.x() - 50, p.y() - 50), 25.5, places=6)
        self.assertAlmostEqual(p.x(), 50 + 25.5 * 0.6, places=6)
        self.assertAlmostEqual(p.y(), 50 + 25.5 * 0.8, places=6)
        v._mouse_linha = QPointF(200, p.y() + 30)  # mais para a direita do que para baixo: Enter = reto em X
        QTest.keyClick(v, "1")
        QTest.keyClick(v, "0")
        QTest.keyClick(v, Qt.Key_Backspace)  # corrige para 1
        QTest.keyClick(v, "2")
        QTest.keyClick(v, Qt.Key_Enter)
        q = v._line_pts[-1]
        self.assertAlmostEqual(q.x() - p.x(), 12, places=6)
        self.assertAlmostEqual(q.y(), p.y(), places=6)
        v._mouse_linha = QPointF(q.x() - 5, q.y() - 80)  # para cima
        QTest.keyClick(v, "7")
        QTest.keyClick(v, Qt.Key_Return)
        r = v._line_pts[-1]
        self.assertAlmostEqual(r.x(), q.x(), places=6)
        self.assertAlmostEqual(r.y(), q.y() - 7, places=6)
        n = len(v.shapes())
        QTest.keyClick(v, Qt.Key_Return)  # Enter sem número termina a linha
        self.assertEqual(len(v.shapes()), n + 1)

    def test_guias_de_alinhamento_fecham_a_caixa(self):
        self.w.new_document()  # sem os objetos de exemplo (também dão guias)
        v = self.v
        v.encaixe_ativo, v.encaixe_grade = True, False
        v.draw_tool = "line"
        v._line_pts = [QPointF(10, 10), QPointF(10, 50), QPointF(60, 50)]  # um L
        tol = v.snap_px / v.scale_px_mm
        p = v._line_point(QPointF(60 + tol / 3, 10 + tol / 2), Qt.NoModifier)  # longe do início, quase alinhado
        self.assertEqual((p.x(), p.y()), (60.0, 10.0))  # X do canto do L e Y do ponto inicial
        self.assertFalse(v._guias.path().isEmpty())  # guias tracejadas aparecem
        p = v._line_point(QPointF(35, 30), Qt.NoModifier)  # longe de tudo: sem guia, ponto livre
        self.assertEqual((p.x(), p.y()), (35.0, 30.0))
        self.assertTrue(v._guias.path().isEmpty())


if __name__ == "__main__":
    unittest.main()
