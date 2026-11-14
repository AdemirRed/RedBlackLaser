"""Etapa 3: dimensões numéricas correspondem à geometria; proporção opcional funciona."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402

from redblack import geometria as g  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
TOL = 1e-6


def rect_shape(x, y, w, h, name="r"):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return ob.Shape(p, name, "C01", "#fff")


def ellipse_shape(x, y, w, h):
    p = QPainterPath()
    p.addEllipse(QRectF(x, y, w, h))
    return ob.Shape(p, "e", "C01", "#fff")


class TransformacoesTest(unittest.TestCase):
    def setUp(self):
        self.scene = QGraphicsScene()

    def add(self, *items):
        for it in items:
            self.scene.addItem(it)
        return list(items)

    def assertRect(self, r, x, y, w, h, tol=TOL):
        for a, b in ((r.left(), x), (r.top(), y), (r.width(), w), (r.height(), h)):
            self.assertAlmostEqual(a, b, delta=tol)

    def test_medidas_da_elipse_sao_exatas(self):
        # sem traço nem pontos de controle: 50 × 30 mesmo após girar 0°
        e, = self.add(ellipse_shape(130, 60, 50, 30))
        self.assertRect(ob.geom_rect(e), 130, 60, 50, 30, 1e-3)

    def test_tamanho_numerico_com_cada_ancora(self):
        for idx in range(9):
            r, = self.add(rect_shape(40, 40, 60, 30))
            before = ob.anchor_point(ob.bounds([r]), idx)
            ob.set_size([r], 80, 45, idx)
            b = ob.bounds([r])
            self.assertAlmostEqual(b.width(), 80, delta=TOL)
            self.assertAlmostEqual(b.height(), 45, delta=TOL)
            after = ob.anchor_point(b, idx)
            self.assertAlmostEqual(before.x(), after.x(), delta=TOL, msg=idx)  # âncora fixa
            self.assertAlmostEqual(before.y(), after.y(), delta=TOL, msg=idx)

    def test_posicao_numerica(self):
        r, = self.add(rect_shape(40, 40, 60, 30))
        ob.set_anchor_pos([r], 200, 100, 0)  # canto superior esquerdo
        self.assertRect(ob.bounds([r]), 200, 100, 60, 30)
        ob.set_anchor_pos([r], 10, 10, 4)  # centro
        self.assertEqual(ob.bounds([r]).center().toTuple(), (10.0, 10.0))

    def test_girar(self):
        r, = self.add(rect_shape(40, 40, 60, 30))
        c = ob.bounds([r]).center()
        ob.rotate([r], 90, c)
        b = ob.bounds([r])
        self.assertAlmostEqual(b.width(), 30, delta=TOL)
        self.assertAlmostEqual(b.height(), 60, delta=TOL)
        self.assertAlmostEqual(b.center().x(), c.x(), delta=TOL)
        ob.rotate([r], -45, c)
        b = ob.bounds([r])
        self.assertAlmostEqual(b.width(), 90 / math.sqrt(2), delta=1e-6)
        ob.rotate([r], -45, c)
        self.assertRect(ob.bounds([r]), 40, 40, 60, 30)
        # positivo = horário na tela: o canto superior direito vai para baixo
        r2, = self.add(rect_shape(0, 0, 10, 0.0001))
        ob.rotate([r2], 90, QPointF(0, 0))
        self.assertGreater(ob.bounds([r2]).center().y(), 0)

    def test_espelhar_mantem_caixa(self):
        r, t = self.add(rect_shape(40, 40, 60, 30), rect_shape(150, 100, 10, 10))
        ob.mirror([r, t], True)
        self.assertRect(ob.bounds([r, t]), 40, 40, 120, 70)
        self.assertRect(ob.geom_rect(t), 40, 100, 10, 10)  # foi para o outro lado

    def test_alinhar(self):
        a, b, c = self.add(rect_shape(10, 10, 20, 20), rect_shape(50, 40, 10, 30), rect_shape(90, 5, 5, 5))
        ob.align([a, b, c], "left")
        self.assertTrue(all(abs(ob.geom_rect(i).left() - 10) < TOL for i in (a, b, c)))
        ob.align([a, b, c], "bottom")
        self.assertTrue(all(abs(ob.geom_rect(i).bottom() - 70) < TOL for i in (a, b, c)))
        ob.align([a, b, c], "hcenter")
        cx = {round(ob.geom_rect(i).center().x(), 6) for i in (a, b, c)}
        self.assertEqual(len(cx), 1)

    def test_distribuir(self):
        items = self.add(rect_shape(0, 0, 10, 10), rect_shape(13, 0, 4, 4), rect_shape(70, 0, 6, 6),
                         rect_shape(100, 0, 20, 20))
        ob.distribute(items, True)
        cs = sorted(ob.geom_rect(i).center().x() for i in items)
        gaps = [round(b - a, 6) for a, b in zip(cs, cs[1:])]
        self.assertEqual(len(set(gaps)), 1, gaps)
        self.assertAlmostEqual(cs[0], 5)
        self.assertAlmostEqual(cs[-1], 110)

    def test_eixo_zero_nao_quebra(self):
        p = QPainterPath()
        p.moveTo(0, 0)
        p.lineTo(50, 0)
        line, = self.add(ob.Shape(p, "l", "C01", "#fff"))
        ob.set_size([line], 100, 10, 4)
        b = ob.bounds([line])
        self.assertAlmostEqual(b.width(), 100)
        self.assertAlmostEqual(b.height(), 0)


class InteracaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"  # sem diálogo modal nos testes
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.rect = next(s for s in self.view.shapes() if "Retângulo" in s.name)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def mouse(self, kind, pos, button, buttons, mods=Qt.NoModifier):
        e = QMouseEvent(kind, QPointF(pos), QPointF(self.view.viewport().mapToGlobal(pos)), button, buttons, mods)
        app.sendEvent(self.view.viewport(), e)
        app.processEvents()

    def drag(self, a, b, mods=Qt.NoModifier):
        self.mouse(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton, mods)
        mid = (a + b) / 2
        self.mouse(QEvent.MouseMove, mid, Qt.NoButton, Qt.LeftButton, mods)
        self.mouse(QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton, mods)
        self.mouse(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton, mods)

    def vp(self, x, y):
        return self.view.mapFromScene(QPointF(x, y))

    def set_field(self, key, value):
        sb = self.win.fields[key]
        sb.setValue(value)
        sb.editingFinished.emit()
        app.processEvents()

    def test_clique_seleciona_e_campos_mostram_medidas(self):
        self.mouse(QEvent.MouseButtonPress, self.vp(70, 40), Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, self.vp(70, 40), Qt.LeftButton, Qt.NoButton)
        self.assertEqual(self.view.selected(), [self.rect])
        f = self.win.fields
        self.assertAlmostEqual(f["w"].value(), 60)
        self.assertAlmostEqual(f["h"].value(), 30)
        self.assertAlmostEqual(f["x"].value(), 70)                  # centro X
        self.assertAlmostEqual(f["y"].value(), g.BED_H - 55)        # centro Y em exibição
        node = self.win._tree_map[id(self.rect)][1]
        self.assertTrue(node.isSelected())                          # painel Objetos sincronizado

    def test_campos_alteram_geometria_com_e_sem_proporcao(self):
        self.rect.setSelected(True)
        app.processEvents()
        self.set_field("w", 90)  # proporção travada (padrão)
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.width(), 90, delta=1e-6)
        self.assertAlmostEqual(b.height(), 45, delta=1e-6)
        self.win.lock.setChecked(False)
        self.set_field("h", 20)
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.width(), 90, delta=1e-6)
        self.assertAlmostEqual(b.height(), 20, delta=1e-6)
        self.assertAlmostEqual(self.win.fields["h"].value(), 20)
        # posição com âncora no canto inferior esquerdo (ponto 6)
        self.win.anchor_group.button(6).setChecked(True)
        self.set_field("x", 10)
        self.set_field("y", 10)
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.left(), 10, delta=1e-6)
        self.assertAlmostEqual(g.BED_H - b.bottom(), 10, delta=1e-6)
        self.set_field("rot", 90)
        self.assertAlmostEqual(ob.geom_rect(self.rect).width(), 20, delta=1e-6)
        self.assertAlmostEqual(self.win.fields["rot"].value(), 90)  # campo mostra o giro atual (pedido do usuário)
        self.set_field("rot", 0)                                   # valor absoluto: volta ao original
        self.assertAlmostEqual(ob.geom_rect(self.rect).width(), 90, delta=1e-6)

    def test_arrastar_objeto_move(self):
        start = ob.geom_rect(self.rect)
        self.drag(self.vp(70, 40), self.vp(90, 60))
        b = ob.geom_rect(self.rect)
        tol = 1.5 / self.view.scale_px_mm
        self.assertAlmostEqual(b.left() - start.left(), 20, delta=tol)
        self.assertAlmostEqual(b.top() - start.top(), 20, delta=tol)
        self.assertAlmostEqual(b.width(), 60, delta=1e-6)

    def test_alca_de_canto_mantem_proporcao_e_shift_libera(self):
        self.rect.setSelected(True)
        app.processEvents()
        self.drag(self.vp(100, 70), self.vp(160, 80))  # canto inferior direito
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.width() / b.height(), 2, delta=1e-6)
        self.assertAlmostEqual(b.left(), 40, delta=1e-6)               # canto oposto fixo
        corner = QPointF(b.right(), b.bottom())
        self.drag(self.vp(corner.x(), corner.y()), self.vp(corner.x() + 10, corner.y() + 30), Qt.ShiftModifier)
        b2 = ob.geom_rect(self.rect)
        self.assertNotAlmostEqual(b2.width() / b2.height(), 2, delta=0.05)

    def test_alca_de_lado_altera_um_eixo(self):
        self.rect.setSelected(True)
        app.processEvents()
        self.drag(self.vp(100, 55), self.vp(130, 90))  # lado direito
        b = ob.geom_rect(self.rect)
        tol = 1.5 / self.view.scale_px_mm
        self.assertAlmostEqual(b.width(), 90, delta=tol)
        self.assertAlmostEqual(b.height(), 30, delta=1e-6)

    def test_alca_de_rotacao_com_shift_passos_de_15(self):
        self.rect.setSelected(True)
        app.processEvents()
        handle = dict(self.view.overlay.handle_points())["rot"]
        c = ob.geom_rect(self.rect).center()
        # arrastar até a direita do centro = 90° horário
        self.drag(self.view.mapFromScene(handle), self.vp(c.x() + 50, c.y() + 3), Qt.ShiftModifier)
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.width(), 30, delta=1e-6)
        self.assertAlmostEqual(b.height(), 60, delta=1e-6)

    def test_setas_movem_1mm_e_shift_10mm(self):
        self.rect.setSelected(True)
        self.view.setFocus()
        start = ob.geom_rect(self.rect)
        for key, mods in ((Qt.Key_Right, Qt.NoModifier), (Qt.Key_Up, Qt.ShiftModifier)):
            app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, key, mods))
        b = ob.geom_rect(self.rect)
        self.assertAlmostEqual(b.left() - start.left(), 1)
        self.assertAlmostEqual(b.top() - start.top(), -10)   # para cima na tela

    def test_shift_clique_adiciona_a_selecao(self):
        ell = next(s for s in self.view.shapes() if "Elipse" in s.name)
        self.mouse(QEvent.MouseButtonPress, self.vp(70, 40), Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, self.vp(70, 40), Qt.LeftButton, Qt.NoButton)
        self.mouse(QEvent.MouseButtonPress, self.vp(155, 60), Qt.LeftButton, Qt.LeftButton, Qt.ShiftModifier)
        self.mouse(QEvent.MouseButtonRelease, self.vp(155, 60), Qt.LeftButton, Qt.NoButton, Qt.ShiftModifier)
        self.assertEqual(set(self.view.selected()), {self.rect, ell})
        self.assertAlmostEqual(self.win.fields["w"].value(), 140)

    def test_copiar_colar_excluir_selecionar_tudo(self):
        n = len(self.view.shapes())
        self.rect.setSelected(True)
        self.win.copy()
        self.win.paste()
        app.processEvents()
        self.assertEqual(len(self.view.shapes()), n + 1)
        pasted = self.view.selected()[0]
        self.assertAlmostEqual(ob.geom_rect(pasted).left(), 45)
        self.assertEqual(self.win.obj_tree.topLevelItemCount(), n + 1)
        self.win.delete()
        app.processEvents()
        self.assertEqual(len(self.view.shapes()), n)
        self.win.select_all()
        app.processEvents()
        self.assertEqual(len(self.view.selected()), n)

    def test_acoes_dependem_da_quantidade(self):
        acts = {a.text(): a for a in self.win._sel_actions}
        self.assertFalse(acts["Alinhar à esquerda"].isEnabled())
        self.win.select_all()
        app.processEvents()
        self.assertTrue(acts["Alinhar à esquerda"].isEnabled())
        self.assertTrue(acts["Distribuir na horizontal"].isEnabled())


if __name__ == "__main__":
    unittest.main()
