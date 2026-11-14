"""Salvamento automático no próprio arquivo (sem perder o Desfazer), recuperação e reabrir o último projeto."""
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
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class SalvamentoAutomaticoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ini = os.path.join(self.tmp.name, "t.ini")
        self.janelas = []

    def tearDown(self):
        for w in self.janelas:
            w.ask_save = lambda: "discard"
            w.close()
        self.tmp.cleanup()

    def janela(self):
        w = MainWindow(QSettings(self.ini, QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_error = w.show_info = lambda *a: None
        w.pasta_auto = lambda: os.path.join(self.tmp.name, "auto")
        self.janelas.append(w)
        return w

    def ret(self, w, x):
        w.create_shape(fm.rect_path(QRectF(x, 10, 10, 10)), "rect")

    def test_salva_no_arquivo_e_o_desfazer_continua(self):
        w = self.janela()
        w.new_document()
        arq = os.path.join(self.tmp.name, "p.rbl")
        self.ret(w, 10)
        self.assertTrue(w.save_to(arq))
        self.ret(w, 40)
        self.assertEqual(w.auto_salvar(), arq)
        self.assertTrue(w.undo_stack.isClean())
        self.assertEqual(len(pj.load(arq)), 2)  # o arquivo já tem a 2ª peça
        self.assertTrue(w.undo_stack.canUndo())
        w.undo_stack.undo()  # desfaz a peça salva automaticamente
        self.assertEqual(len(w.canvas.view.shapes()), 1)
        self.assertFalse(w.undo_stack.isClean())

    def test_grupo_aberto_vai_para_a_copia_e_nao_mexe_no_arquivo(self):
        w = self.janela()
        w.new_document()
        arq = os.path.join(self.tmp.name, "g.rbl")
        self.ret(w, 10)
        self.ret(w, 40)
        w.select_all()
        w.group_selected()
        self.assertTrue(w.save_to(arq))
        w.abrir_grupo(next(s for s in w.canvas.view.shapes() if isinstance(s, ob.GroupShape)))
        self.ret(w, 80)
        destino = w.auto_salvar()
        self.assertNotEqual(destino, arq)
        self.assertTrue(destino.endswith(".autosave.rbl"))
        self.assertTrue(any(s.grupo_aberto for s in w.canvas.view.shapes()))  # o grupo continua aberto
        self.assertEqual(len(pj.load(arq)), 1)  # arquivo intacto (só o grupo)

    def test_recupera_projeto_sem_titulo_depois_de_fechar_sem_salvar(self):
        w = self.janela()
        w.new_document()
        self.ret(w, 10)
        self.ret(w, 40)
        rec = w.auto_salvar()
        self.assertTrue(os.path.isfile(rec))
        w.settings.sync()
        self.janelas.remove(w)  # simula o programa fechando à força (sem closeEvent)
        w.deleteLater()
        w2 = self.janela()
        self.assertTrue(w2.restaurar_sessao())
        self.assertEqual(len(w2.canvas.view.shapes()), 2)
        self.assertIsNone(w2.file_path)
        self.assertFalse(w2.undo_stack.isClean())  # continua pedindo para salvar
        self.assertNotIn(rec, w2.recentes())

    def test_reabre_o_ultimo_projeto(self):
        w = self.janela()
        w.new_document()
        arq = os.path.join(self.tmp.name, "ultimo.rbl")
        self.ret(w, 10)
        w.save_to(arq)
        w.close()
        self.janelas.remove(w)
        w2 = self.janela()
        self.assertTrue(w2.restaurar_sessao())
        self.assertEqual(os.path.normcase(w2.file_path), os.path.normcase(arq))
        self.assertTrue(w2.undo_stack.isClean())
        # projeto novo descartado ao fechar: próximo início começa limpo
        w2.new_document()
        self.ret(w2, 10)
        w2.close()
        self.janelas.remove(w2)
        w3 = self.janela()
        self.assertFalse(w3.restaurar_sessao())

    def test_opcoes_desligadas(self):
        w = self.janela()
        w.settings.setValue("abrir_ultimo", False)
        w.settings.setValue("auto_salvar_arquivo", False)
        w.new_document()
        arq = os.path.join(self.tmp.name, "x.rbl")
        self.ret(w, 10)
        w.save_to(arq)
        self.ret(w, 40)
        self.assertNotEqual(w.auto_salvar(), arq)  # só cópia de recuperação
        self.assertEqual(len(pj.load(arq)), 1)
        self.assertFalse(self.janela().restaurar_sessao())


if __name__ == "__main__":
    unittest.main()
