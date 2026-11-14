"""Configurações (preferências): valores aplicados ao editor e cópia automática."""
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
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.dialogo_preferencias import PADROES, PreferenciasDialog  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class PreferenciasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.win.ask_save = lambda: "discard"
        self.win.new_document()
        self.win.pasta_auto = lambda: os.path.join(self.tmp.name, "auto")

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def aplicar(self, **kw):
        base = {k: v for k, (v, _) in PADROES.items()}
        base.update(kw)
        self.win.ask_preferencias = lambda: base
        self.win._preferencias_dialogo()

    def test_aplica_no_editor(self):
        self.aplicar(passo_seta_mm=0.5, passo_seta_shift_mm=5.0, encaixe_px=20, zoom_invertido=True,
                     auto_salvar_min=0)
        v = self.win.canvas.view
        self.assertEqual((v.passo_seta, v.passo_seta_shift, v.snap_px, v.zoom_invertido), (0.5, 5.0, 20, True))
        self.assertFalse(self.win._auto_timer.isActive())
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 5, 5)), "rect")
        v.setFocus()
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        QTest.keyClick(v, Qt.Key_Right)
        self.assertAlmostEqual(ob.bounds(self.win._sel()).left(), 10.5, 6)
        w2 = MainWindow(self.settings)                                      # lembrado
        self.assertEqual(w2.canvas.view.passo_seta, 0.5)
        w2.ask_save = lambda: "discard"
        w2.close()

    def test_texto_padrao_e_voltar_selecionar(self):
        self.aplicar(texto_altura_mm=7.5, voltar_selecionar=False)
        pedidos = []
        self.win.ask_text = lambda p: pedidos.append(p) or None
        self.win._on_text_click(QPointF(10, 10))
        self.assertEqual(pedidos[0].altura_mm, 7.5)
        self.win.tools["rect"].setChecked(True)
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 5, 5)), "rect")
        self.assertTrue(self.win.tools["rect"].isChecked())                  # continua na ferramenta

    def test_copia_automatica(self):
        self.assertIsNone(self.win.auto_salvar())                            # nada alterado: nada salvo
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 5, 5)), "rect")
        destino = self.win.auto_salvar()
        self.assertTrue(destino.endswith("sem_titulo.autosave.rbl"))
        self.assertEqual(len(pj.load(destino)), 1)
        self.assertFalse(self.win.undo_stack.isClean())                     # continua "não salvo"
        self.assertIsNone(self.win.file_path)

    def test_encaixe_na_grade(self):
        v = self.win.canvas.view
        v.fit()
        p = QPointF(101.3, 400 - 52.6)
        self.assertEqual(v.snap(p), p)                                        # sem alvo perto e sem grade: igual
        self.aplicar(encaixe_grade=True)
        q = v.snap(p)
        from redblack import geometria as g
        passo = g.steps_for(v.scale_px_mm)[0]
        self.assertAlmostEqual(q.x() / passo, round(q.x() / passo), 6)
        self.assertAlmostEqual((400 - q.y()) / passo, round((400 - q.y()) / passo), 6)
        self.assertEqual(v.snap_ind.alvo.tipo, "grade")

    def test_dialogo_ida_e_volta(self):
        dlg = PreferenciasDialog(self.win, self.settings)
        v = dlg.valores()
        self.assertEqual(v["passo_seta_mm"], 1.0)
        dlg.w["encaixe_px"].setValue(30)
        dlg.carregar(padrao=True)
        self.assertEqual(dlg.valores()["encaixe_px"], 12)


if __name__ == "__main__":
    unittest.main()
