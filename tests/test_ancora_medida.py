"""Medida digitada no rótulo / ao digitar um número e âncoras (pai leva os presos)."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.canvas import centros_rotulos  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(m)
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def forma(self, x, y, w=40, h=20, kind="rect"):
        p = fm.rect_path(QRectF(x, y, w, h)) if kind == "rect" else fm.ellipse_path(QRectF(x, y, w, h))
        self.win.create_shape(p, kind)
        return self.win._sel()[0]

    def selecionar(self, *itens):
        self.view.scene().clearSelection()
        for it in itens:
            it.setSelected(True)
        app.processEvents()


class MedidaTest(Base):
    def test_clicar_no_rotulo_e_digitar(self):
        c = self.forma(100, 100, 50, 50, "ellipse")
        self.win.lock.setChecked(True)
        rr = QRectF(self.view.mapFromScene(ob.bounds([c])).boundingRect())
        pos = centros_rotulos(rr)["w"].toPoint()
        self.assertEqual(self.view.rotulo_em(QPointF(pos)), "w")
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
        ed = self.view.editor_medida
        self.assertTrue(ed.isVisible())
        self.assertEqual(ed.text(), "50,00")
        ed.selectAll()
        QTest.keyClicks(ed, "99,6")
        QTest.keyClick(ed, Qt.Key_Return)
        b = ob.bounds([c])
        self.assertAlmostEqual(b.width(), 99.6, 6)
        self.assertAlmostEqual(b.height(), 99.6, 6)                          # proporção mantida
        self.assertFalse(ed.isVisible())
        self.win.undo_stack.undo()
        self.assertAlmostEqual(ob.bounds(self.view.shapes()).width(), 50, 6)  # desfazer recria os objetos

    def test_digitar_numero_com_objeto_selecionado_e_tab_para_altura(self):
        r = self.forma(10, 10, 40, 20)
        self.win.lock.setChecked(False)
        self.view.setFocus()
        QTest.keyClick(self.view, Qt.Key_7)
        ed = self.view.editor_medida
        self.assertTrue(ed.isVisible())
        self.assertEqual(ed.text(), "7")
        QTest.keyClicks(ed, "5")
        QTest.keyClick(ed, Qt.Key_Tab)                                       # aplica largura, abre altura
        self.assertAlmostEqual(ob.bounds([r]).width(), 75, 6)
        self.assertTrue(ed.isVisible())
        ed.setText("30")
        QTest.keyClick(ed, Qt.Key_Return)
        self.assertAlmostEqual(ob.bounds([r]).height(), 30, 6)

    def test_valor_invalido_e_esc(self):
        r = self.forma(10, 10, 40, 20)
        self.view.editar_medida("w", "abc")
        QTest.keyClick(self.view.editor_medida, Qt.Key_Return)
        self.assertTrue(self.view.editor_medida.isVisible())                 # fica aberto, nada muda
        QTest.keyClick(self.view.editor_medida, Qt.Key_Escape)
        self.assertFalse(self.view.editor_medida.isVisible())
        self.assertAlmostEqual(ob.bounds([r]).width(), 40, 6)


class AncoraTest(Base):
    def prender(self):
        pai = self.forma(100, 100)
        filho = self.forma(200, 100, 10, 10)
        neto = self.forma(250, 100, 5, 5)
        self.selecionar(pai)
        filho.setSelected(True)
        app.processEvents()
        self.assertTrue(self.win.prender_ancora())
        self.selecionar(filho)
        neto.setSelected(True)
        app.processEvents()
        self.assertTrue(self.win.prender_ancora())
        return pai, filho, neto

    def test_arrastar_pai_leva_os_presos(self):
        pai, filho, neto = self.prender()
        self.selecionar(pai)
        vp = self.view.viewport()
        a = self.view.mapFromScene(QPointF(110, 100))  # na linha de cima, fora da alça do meio
        b = self.view.mapFromScene(QPointF(140, 130))
        QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a)
        QTest.mouseMove(vp, b)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b)
        d = ob.bounds([pai]).topLeft() - QPointF(100, 100)
        self.assertGreater(d.x(), 10)
        for it, x0 in ((filho, 200), (neto, 250)):                           # em cadeia
            self.assertAlmostEqual(ob.bounds([it]).left(), x0 + d.x(), 6)
            self.assertAlmostEqual(ob.bounds([it]).top(), 100 + d.y(), 6)
        self.win.undo_stack.undo()                                           # um passo desfaz tudo
        self.assertAlmostEqual(ob.bounds([self.win.canvas.view.shapes()[1]]).left(), 200, 6)

    def test_preso_se_move_sozinho_e_girar_pai(self):
        pai, filho, _ = self.prender()
        self.selecionar(filho)
        self.view.nudge(5, 0)                                                # filho sozinho: pai fica
        self.assertAlmostEqual(ob.bounds([pai]).left(), 100, 6)
        self.assertAlmostEqual(ob.bounds([filho]).left(), 205, 6)
        self.selecionar(pai)
        c = ob.bounds([pai]).center()
        self.win._edit("Girar", lambda: ob.rotate([pai], 180, c))              # filho gira em volta do pai
        self.assertAlmostEqual(ob.bounds([filho]).center().x(), 2 * c.x() - 210, 6)

    def test_ciclo_soltar_e_projeto(self):
        pai, filho, neto = self.prender()
        self.selecionar(neto)
        pai.setSelected(True)
        app.processEvents()
        self.assertFalse(self.win.prender_ancora())                          # pai preso ao neto = ciclo
        p = os.path.join(self.tmp.name, "a.rbl")
        self.win.save_to(p)
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["ancoras"], [[1, 0], [2, 1]])
        self.win.new_document()
        self.win.open_path(p)
        s = self.win.canvas.view.shapes()
        self.assertIs(s[1].ancora, s[0])
        self.assertIs(s[2].ancora, s[1])
        self.selecionar(s[1])
        self.win.soltar_ancora()
        self.assertIsNone(s[1].ancora)
        for ruim in ([[0, 0]], [[0, 1], [1, 0]], [[0, 9]], [[1, 0], [1, 2]]):
            with self.assertRaises(pj.ProjetoInvalido):
                pj.ancoras_from_dict({"ancoras": ruim}, 3)

    def test_apagar_pai_solta(self):
        pai, filho, _ = self.prender()
        self.selecionar(pai)
        self.win.delete()
        self.assertEqual(self.win.doc_state()[5], ((1, 0),))                  # só filho→neto continua


if __name__ == "__main__":
    unittest.main()
