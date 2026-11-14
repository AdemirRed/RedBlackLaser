"""Barra de propriedades do texto."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class BarraTextoTest(unittest.TestCase):
    def test_editar_pela_barra(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        t = w.texto_campos
        self.assertFalse(t["altura_mm"].isEnabled())                          # nada selecionado
        w.create_text(tx.TextoParams("RedBlack", "Arial", 10), QPointF(50, 50))
        s = w._sel()[0]
        self.assertTrue(t["altura_mm"].isEnabled())
        self.assertEqual(t["altura_mm"].value(), 10)
        h0 = ob.geom_rect(s).height()
        t["altura_mm"].setValue(20)
        s = next(x for x in w.canvas.view.shapes() if isinstance(x, ob.TextShape))
        self.assertEqual(s.params.altura_mm, 20)
        self.assertGreater(ob.geom_rect(s).height(), h0 * 1.8)
        t["negrito"].setChecked(True)
        self.assertTrue(s.params.negrito)
        t["alinhamento"].setCurrentIndex(t["alinhamento"].findData("centro"))
        t["alinhamento"].activated.emit(t["alinhamento"].currentIndex())
        self.assertEqual(s.params.alinhamento, "centro")
        w.undo_stack.undo()
        w.undo_stack.undo()
        w.undo_stack.undo()
        s = next(x for x in w.canvas.view.shapes() if isinstance(x, ob.TextShape))
        self.assertEqual((s.params.altura_mm, s.params.negrito), (10, False))
        w.create_shape(fm.rect_path(QRectF(0, 0, 5, 5)), "rect")             # não é texto: barra desligada
        self.assertFalse(t["negrito"].isEnabled())
        w.close()
        tmp.cleanup()



class LayoutAntigoTest(unittest.TestCase):
    def test_layout_salvo_sem_quebra_ganha_quebra(self):
        tmp = tempfile.TemporaryDirectory()
        st = QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat)
        w = MainWindow(st)
        w.removeToolBarBreak(w.barra_texto)                                   # como num layout salvo antigo
        st.setValue("windowState", w.saveState())
        w.ask_save = lambda: "discard"
        w.close()
        w2 = MainWindow(st)
        self.assertTrue(w2.toolBarBreak(w2.barra_texto))
        self.assertEqual(w2.fields["wp"].value(), 100)
        w2.ask_save = lambda: "discard"
        w2.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
