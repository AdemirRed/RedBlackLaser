"""Camada em modo Preenchimento aparece preenchida (translúcida) na tela; Linha só o contorno."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class TelaPreenchimentoTest(unittest.TestCase):
    def test_preenchimento_pinta_por_dentro(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.resize(1200, 800)
            w.show()
            app.processEvents()
            w.new_document()
            v = w.canvas.view
            s = ob.Shape(fm.rect_path(QRectF(100, 100, 80, 60)), "Placa", "C01", "#2f6bff")
            w._edit("t", lambda: v.scene().addItem(s))
            v.ajustar_a(QRectF(80, 80, 120, 100))
            app.processEvents()

            def centro():
                app.processEvents()
                pt = v.mapFromScene(140, 130)
                return v.viewport().grab().toImage().pixelColor(pt)
            antes = centro()
            self.assertTrue(w.set_layer_fields("C01", {"modo": "preenchimento"}, "modo"))
            self.assertIn("C01", ob.PREENCHIDAS)
            depois = centro()
            self.assertNotEqual(antes.name(), depois.name())  # o miolo ganhou cor
            self.assertGreater(depois.blue(), depois.red())
            w.undo_stack.undo()
            self.assertNotIn("C01", ob.PREENCHIDAS)
            self.assertEqual(centro().name(), antes.name())
            w.close()


if __name__ == "__main__":
    unittest.main()
