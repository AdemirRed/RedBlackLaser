"""Bloquear formas e interruptores Mover/Tamanho/Girar da barra de status."""
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
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.win.new_document()
        self.view = self.win.canvas.view
        self.win.create_shape(fm.rect_path(QRectF(100, 100, 40, 40)), "rect")
        self.s = self.win._sel()[0]

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def arrastar(self, a, b):
        vp = self.view.viewport()
        pa, pb = self.view.mapFromScene(a), self.view.mapFromScene(b)
        QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, pa)
        QTest.mouseMove(vp, pb)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, pb)


class BloqueioTest(Base):
    def test_bloqueado_nao_move_nem_muda_e_fica_salvo(self):
        self.win.bloquear(True)
        self.arrastar(QPointF(110, 100), QPointF(150, 140))
        self.assertEqual(ob.bounds([self.s]).left(), 100)
        self.view.nudge(5, 0)
        self.assertEqual(ob.bounds([self.s]).left(), 100)
        self.win.fields["w"].setValue(80)
        self.win.fields["w"].editingFinished.emit()
        self.assertEqual(ob.bounds([self.s]).width(), 40)
        self.assertIsNone(self.view.handle_at(self.view.mapFromScene(QPointF(140, 140))))
        p = os.path.join(self.tmp.name, "b.rbl")
        self.win.save_to(p)
        with open(p, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["bloqueados"], [0])
        self.win.new_document()
        self.win.open_path(p)
        self.assertTrue(self.win.canvas.view.shapes()[0].bloqueado)
        self.win.canvas.view.shapes()[0].setSelected(True)
        self.win.bloquear(False)
        self.win.undo_stack.undo()
        self.assertTrue(self.win.canvas.view.shapes()[0].bloqueado)
        with self.assertRaises(pj.ProjetoInvalido):
            pj.bloqueados_from_dict({"bloqueados": [5]}, 1)


class InterruptoresTest(Base):
    def test_mover_desligado(self):
        self.win.interruptores["mover"].setChecked(False)
        self.arrastar(QPointF(110, 100), QPointF(150, 140))
        self.assertEqual(ob.bounds([self.s]).left(), 100)
        self.assertTrue(self.s.isSelected())                                  # seleciona mesmo assim
        self.assertFalse(self.settings.value("permitir_mover", True, type=bool))
        self.win.interruptores["mover"].setChecked(True)
        self.arrastar(QPointF(110, 100), QPointF(150, 140))
        self.assertGreater(ob.bounds([self.s]).left(), 130)

    def test_tamanho_e_girar_desligados_escondem_alcas(self):
        canto = self.view.mapFromScene(QPointF(140, 140))
        self.assertEqual(self.view.handle_at(canto), "se")
        self.win.interruptores["tamanho"].setChecked(False)
        self.assertIsNone(self.view.handle_at(canto))
        rot = dict(self.view.overlay.handle_points())["rot"]
        self.assertEqual(self.view.handle_at(self.view.mapFromScene(rot)), "rot")
        self.win.interruptores["girar"].setChecked(False)
        self.assertIsNone(self.view.handle_at(self.view.mapFromScene(rot)))
        self.assertTrue(self.win.interruptores["girar"].text().startswith("○"))


if __name__ == "__main__":
    unittest.main()
