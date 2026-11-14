"""Editor de teclas de atalho."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack.ui.dialogo_atalhos import AtalhosDialog, chave, conflitos  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AtalhosTest(unittest.TestCase):
    def test_trocar_lembrar_e_conflito(self):
        tmp = tempfile.TemporaryDirectory()
        st = QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat)
        w = MainWindow(st)
        w.ask_save = lambda: "discard"
        acoes = {chave(a): a for a in w.todas_acoes()}
        self.assertIn("Duplicar", acoes)
        self.assertEqual(acoes["Duplicar"].shortcut().toString(), "Ctrl+D")
        self.assertNotIn("Iniciar trabalho", acoes)                          # etapas futuras não entram
        mapa = AtalhosDialog(w, w.todas_acoes()).mapa()
        mapa["Duplicar"] = "Ctrl+J"
        self.assertTrue(w.editar_atalhos(mapa))
        self.assertEqual(acoes["Duplicar"].shortcut().toString(), "Ctrl+J")
        w.close()
        w2 = MainWindow(st)                                                   # lembrado
        self.assertEqual({chave(a): a for a in w2.todas_acoes()}["Duplicar"].shortcut().toString(), "Ctrl+J")
        dlg = AtalhosDialog(w2, w2.todas_acoes())
        i = [chave(a) for a in dlg.acoes].index("Agrupar")
        from PySide6.QtGui import QKeySequence
        dlg.editores[i].setKeySequence(QKeySequence("Ctrl+J"))                # repete a do Duplicar
        self.assertIn("Ctrl+J", dlg.aviso.text())
        self.assertFalse(dlg.botoes.button(dlg.botoes.StandardButton.Ok).isEnabled())
        self.assertEqual(conflitos({"a": "X", "b": "X", "c": ""}), {"X": ["a", "b"]})
        w2.ask_save = lambda: "discard"
        w2.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
