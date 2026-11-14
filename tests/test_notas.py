"""Notas do projeto."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class NotasTest(unittest.TestCase):
    def test_notas_salvas_e_desfazer(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        self.assertTrue(w.undo_stack.isClean())
        w.notas_edit.setPlainText("MDF 3 mm: 300 mm/min, 100 %, foco 2 mm abaixo")
        w._notas_timer.timeout.emit()                                         # pausa na digitação
        self.assertFalse(w.undo_stack.isClean())                             # marca como alterado
        p = os.path.join(tmp.name, "n.rbl")
        w.save_to(p)
        with open(p, encoding="utf-8") as f:
            self.assertIn("foco 2 mm", json.load(f)["notas"])
        w.new_document()
        self.assertEqual(w.notas_edit.toPlainText(), "")
        w.open_path(p)
        self.assertIn("300 mm/min", w.notas_edit.toPlainText())
        w.notas_edit.setPlainText("outra")
        w._notas_timer.timeout.emit()
        w.undo_stack.undo()
        self.assertIn("300 mm/min", w.notas_edit.toPlainText())
        self.assertEqual(w.act_notas.shortcut().toString(), "Ctrl+Alt+N")
        with self.assertRaises(pj.ProjetoInvalido):
            pj.notas_from_dict({"notas": 5})
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
