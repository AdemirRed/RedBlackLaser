"""Encaixe em cantos/pontos (pedido do usuário após a Etapa 13) e fechamento de linhas pelo ponto inicial."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import encaixe as enc  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AlvosTest(unittest.TestCase):
    def test_cantos_centro_e_prioridade(self):
        s = ob.Shape(fm.rect_path(QRectF(10, 20, 30, 40)), "r", "C01", cm.cor("C01"))
        alvos = enc.alvos_de_snapshot(s.snapshot())
        cantos = {(a.x, a.y) for a in alvos if a.tipo == "canto"}
        self.assertEqual(cantos, {(10, 20), (40, 20), (40, 60), (10, 60)})
        self.assertIn(enc.Alvo(25, 40, "centro"), alvos)
        self.assertEqual(enc.mais_proximo(41, 21, alvos, 3), enc.Alvo(40, 20, "canto"))
        self.assertIsNone(enc.mais_proximo(70, 70, alvos, 3))
        empate = [enc.Alvo(0, 0, "centro"), enc.Alvo(0, 0, "canto")]
        self.assertEqual(enc.mais_proximo(1, 0, empate, 2).tipo, "canto")

    def test_texto_e_grupo_girado(self):
        t = ob.TextShape(tx.TextoParams("Faca", "Arial", 10), "t")
        self.assertEqual(len(enc.alvos_de_snapshot(t.snapshot())), 5)        # 4 cantos da caixa + centro
        g = ob.group([ob.Shape(fm.rect_path(QRectF(0, 0, 20, 10)), "r", "C01", "#fff")])
        ob.rotate([g], 90, QPointF(0, 0))
        cantos = {(round(a.x, 9), round(a.y, 9)) for a in enc.alvos_de_snapshot(g.snapshot()) if a.tipo == "canto"}
        self.assertEqual(cantos, {(0, 0), (0, 20), (-10, 20), (-10, 0)})   # nós já transformados


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def send(self, kind, pos, buttons=Qt.LeftButton, button=Qt.LeftButton, mods=Qt.NoModifier):
        vp = self.view.viewport()
        app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), button, buttons, mods))
        app.processEvents()

    def click(self, pos, mods=Qt.NoModifier):
        self.send(QEvent.MouseMove, pos, Qt.NoButton, Qt.NoButton, mods)
        self.send(QEvent.MouseButtonPress, pos, mods=mods)
        self.send(QEvent.MouseButtonRelease, pos, Qt.NoButton, mods=mods)

    def P(self, x, y):
        return self.view.mapFromScene(QPointF(x, y))

    def test_linha_fecha_com_clique_um_pouco_fora_do_inicio(self):
        """Antes: tolerância de 8 px sem marca visível; um desvio de 6 px na diagonal deixava a linha aberta."""
        self.win.tools["pen"].setChecked(True)
        for x, y in ((100, 100), (200, 100), (200, 180)):
            self.click(self.P(x, y))
        self.send(QEvent.MouseMove, self.P(100, 100) + QPoint(7, 6), Qt.NoButton, Qt.NoButton)
        self.assertEqual(self.view.snap_ind.alvo.tipo, "início")           # o usuário vê "fechar"
        self.click(self.P(100, 100) + QPoint(7, 6))
        s = self.view.shapes()
        self.assertEqual(len(s), 1)
        path = s[0].path()
        self.assertEqual(len(fm.nodes(path)), 3)
        ini, fim = path.elementAt(0), path.elementAt(path.elementCount() - 1)
        self.assertEqual((fim.x, fim.y), (ini.x, ini.y))                   # fechada exatamente no início
        self.assertTrue(self.win.tools["select"].isChecked())

    def test_novo_projeto_descarta_linha_em_andamento(self):
        self.win.tools["pen"].setChecked(True)
        self.click(self.P(100, 100))
        self.click(self.P(150, 100))
        self.win.new_document()
        self.assertEqual(self.view._line_pts, [])
        self.assertIsNone(self.view.draw_tool)
        self.assertTrue(self.win.tools["select"].isChecked())

    def test_medir_de_canto_a_canto(self):
        self.win.create_shape(fm.rect_path(QRectF(50, 50, 120, 80)), "rect")
        self.view.scene().clearSelection()
        msgs = []
        self.view.measured.connect(msgs.append)
        self.win.tools["measure"].setChecked(True)
        a, b = self.P(50, 50) + QPoint(4, -3), self.P(170, 130) + QPoint(-5, 4)   # mão imprecisa
        self.send(QEvent.MouseMove, a, Qt.NoButton, Qt.NoButton)
        self.assertEqual(self.view.snap_ind.alvo.tipo, "canto")
        self.send(QEvent.MouseButtonPress, a)
        self.send(QEvent.MouseMove, b, Qt.NoButton)
        self.send(QEvent.MouseButtonRelease, b, Qt.NoButton)
        self.assertIn(f"{math.hypot(120, 80):.2f}".replace(".", ","), msgs[-1])   # 144,22 exatos
        self.assertIn("ΔX +120,00", msgs[-1])
        self.assertIn("ΔY -80,00", msgs[-1])

    def test_alt_desliga_e_botao_desliga(self):
        self.win.create_shape(fm.rect_path(QRectF(50, 50, 120, 80)), "rect")
        self.win.tools["measure"].setChecked(True)
        perto = self.P(50, 50) + QPoint(4, -3)
        self.send(QEvent.MouseMove, perto, Qt.NoButton, Qt.NoButton, Qt.AltModifier)
        self.assertIsNone(self.view.snap_ind.alvo)
        self.win.act_snap.setChecked(False)
        self.send(QEvent.MouseMove, perto, Qt.NoButton, Qt.NoButton)
        self.assertIsNone(self.view.snap_ind.alvo)
        self.win.act_snap.setChecked(True)
        self.send(QEvent.MouseMove, perto, Qt.NoButton, Qt.NoButton)
        self.assertIsNotNone(self.view.snap_ind.alvo)

    def test_retangulo_comeca_no_canto_de_outro(self):
        self.win.create_shape(fm.rect_path(QRectF(50, 50, 120, 80)), "rect")
        self.win.tools["rect"].setChecked(True)
        a, b = self.P(170, 130) + QPoint(3, 3), self.P(250, 200)
        self.send(QEvent.MouseMove, a, Qt.NoButton, Qt.NoButton)
        self.send(QEvent.MouseButtonPress, a)
        self.send(QEvent.MouseMove, b, Qt.NoButton)
        self.send(QEvent.MouseButtonRelease, b, Qt.NoButton)
        novo = self.view.selected()[0]
        r = ob.geom_rect(novo)
        self.assertEqual((r.left(), r.top()), (170.0, 130.0))            # começa exatamente no canto

    def test_no_encaixa_no_canto_de_outro_objeto(self):
        self.win.create_shape(fm.rect_path(QRectF(50, 50, 40, 40)), "rect")
        self.win.create_shape(fm.rect_path(QRectF(150, 50, 40, 40)), "rect")
        self.win.tools["node"].setChecked(True)                          # 2º retângulo selecionado
        de, para = self.P(150, 50), self.P(90, 90) + QPoint(4, 3)          # leva o canto até o canto do 1º
        self.send(QEvent.MouseButtonPress, de)
        self.send(QEvent.MouseMove, para, Qt.NoButton)
        self.send(QEvent.MouseButtonRelease, para, Qt.NoButton)
        e = self.view.selected()[0].path().elementAt(0)
        self.assertEqual((e.x, e.y), (90.0, 90.0))


if __name__ == "__main__":
    unittest.main()
