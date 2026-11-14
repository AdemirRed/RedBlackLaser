"""Fumaça: dispara todos os comandos dos menus (diálogos simulados) e confere que nenhum quebra."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack.ui.dialogo_atalhos import chave  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
PULAR = {"Sair"}  # fecharia a janela do teste


class TodosComandosTest(unittest.TestCase):
    def test_nenhum_comando_quebra(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_error = lambda *a: None
        w.show_info = lambda *a: None
        for nome in [n for n in dir(w) if n.startswith("ask_")]:
            setattr(w, nome, lambda *a, **k: None)                            # todo diálogo "cancelado"
        w.ask_save = lambda: "discard"                                        # Novo projeto limpa de verdade
        w.pasta_auto = lambda: os.path.join(tmp.name, "auto")
        erros = []
        vazio = mock.patch.object(QFileDialog, "getOpenFileName", return_value=("", ""))
        with vazio, mock.patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
                mock.patch.object(QFileDialog, "getExistingDirectory", return_value=""), \
                mock.patch.object(QInputDialog, "getText", return_value=("", False)), \
                mock.patch.object(QInputDialog, "getDouble", return_value=(0.0, False)), \
                mock.patch.object(QMessageBox, "about"), mock.patch.object(QMessageBox, "information"), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Discard):
            for a in w.todas_acoes():
                if chave(a) in PULAR or not a.isEnabled():
                    continue
                w.new_document()
                w.create_shape(fm.rect_path(QRectF(10, 10, 40, 30)), "rect")
                w.create_shape(fm.polyline_path([QPointF(0, 60), QPointF(80, 60)]), "line")
                w.create_shape(fm.ellipse_path(QRectF(20, 15, 20, 20)), "ellipse")
                w.select_all()
                app.processEvents()
                import time
                t0 = time.perf_counter()
                try:
                    a.trigger()
                    app.processEvents()
                    w.tools["select"].setChecked(True)
                    if os.environ.get("RB_DEBUG") and time.perf_counter() - t0 > 0.3:
                        print(f"{chave(a)}: {time.perf_counter() - t0:.1f} s", flush=True)
                except Exception as e:  # noqa: BLE001 — queremos a lista de todos os que quebram
                    erros.append(f"{chave(a)}: {type(e).__name__}: {e}")
        w.close()
        tmp.cleanup()
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
