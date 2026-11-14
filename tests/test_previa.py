"""Etapa 10 na janela: prévia sobreposta, resumo, estimativa de tempo e simulação."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class PreviaJanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.show_error = lambda t, m: None
        self.win.show_info = lambda t, m: None
        self.win.resize(1500, 950)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.ov = self.view.percurso_overlay
        self.panel = self.win.preview_panel
        self.win.new_document()
        self.win.create_shape(fm.rect_path(QRectF(10, 20, 100, 50)), "rect")   # C01: contorno 300 mm
        self.win.set_layer_field("C01", "velocidade_mm_min", 600)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def abrir(self):
        self.win.act_preview.setChecked(True)
        app.processEvents()

    def test_fechada_por_padrao_e_nao_altera_objetos(self):
        self.assertFalse(self.win.preview_dock.isVisible())
        self.assertFalse(self.ov.isVisible())
        self.assertEqual({s.opacity() for s in self.view.shapes()}, {1.0})

    def test_abrir_mostra_percurso_resumo_e_esmaece_objetos(self):
        self.abrir()
        self.assertTrue(self.ov.isVisible())
        p = self.ov.percurso
        self.assertAlmostEqual(p.comprimento_corte, 300, delta=1e-9)
        self.assertIn("≈", self.panel.lbl_tempo.text())
        self.assertIn("mínimo", self.panel.lbl_tempo.text())
        self.assertIn("300,0 mm", self.panel.lbl_resumo.text())
        self.assertEqual(self.panel.tabela.rowCount(), 1)
        self.assertEqual(self.panel.tabela.item(0, 0).text(), "C01")
        self.assertEqual({s.opacity() for s in self.view.shapes()}, {0.3})
        self.win.act_preview.setChecked(False)
        app.processEvents()
        self.assertFalse(self.ov.isVisible())
        self.assertEqual({s.opacity() for s in self.view.shapes()}, {1.0})

    def test_tempo_acompanha_edicoes_e_desfazer(self):
        self.abrir()
        t0 = self.ov.percurso.tempo_s
        self.win.set_layer_field("C01", "velocidade_mm_min", 300)             # metade da velocidade
        t1 = self.ov.percurso.tempo_s
        self.assertAlmostEqual(self.ov.percurso.trechos[1].tempo_s, 60.0, delta=1e-9)   # 300 mm / 5 mm/s
        self.assertGreater(t1, t0)
        self.win.set_layer_field("C01", "passadas", 2)
        self.assertAlmostEqual(self.ov.percurso.comprimento_corte, 600, delta=1e-9)
        self.win.undo_stack.undo()
        self.win.undo_stack.undo()
        self.assertAlmostEqual(self.ov.percurso.tempo_s, t0, delta=1e-9)
        self.assertEqual({s.opacity() for s in self.view.shapes()}, {0.3})     # objetos recriados pelo desfazer

    def test_saida_desligada_zera_e_mostra_mensagem(self):
        self.abrir()
        self.win.set_layer_field("C01", "saida", False)
        self.assertFalse(self.ov.isVisible())
        self.assertIn("Nada para executar", self.panel.lbl_resumo.text())
        self.assertFalse(self.panel.slider.isEnabled())
        self.win.set_layer_field("C01", "saida", True)
        self.assertTrue(self.ov.isVisible())

    def test_velocidade_de_deslocamento_editavel(self):
        self.abrir()
        antes = self.ov.percurso.tempo_s
        self.panel.rapido.setValue(1000)
        self.panel.rapido.editingFinished.emit()
        self.assertEqual(self.ov.percurso.rapido, 1000)
        self.assertGreater(self.ov.percurso.tempo_s, antes)                  # deslocar mais devagar demora mais

    def test_simulacao_pelo_controle(self):
        self.abrir()
        p, total = self.ov.percurso, self.ov.percurso.tempo_s
        self.panel.slider.setValue(0)
        self.assertIn("deslocamento sem laser", self.panel.lbl_estado.text())
        self.assertFalse(self.ov._emitindo)
        meio_corte = p.trechos[0].tempo_s + p.trechos[1].tempo_s / 2
        self.panel.slider.setValue(round(1000 * meio_corte / total))
        self.assertIn("CORTANDO", self.panel.lbl_estado.text())
        self.assertTrue(self.ov._emitindo)
        self.assertTrue(self.ov._cortes_done)
        self.panel.slider.setValue(1000)
        self.assertIn("fim do percurso", self.panel.lbl_estado.text())
        self.assertAlmostEqual(self.ov._head[0], g.canto_origem()[0], delta=1e-9)
        self.assertAlmostEqual(self.ov._head[1], g.canto_origem()[1], delta=1e-9)

    def test_reproduzir_avanca_e_para_no_fim(self):
        self.abrir()
        self.panel.slider.setValue(0)
        self.panel.btn_play.setChecked(True)
        self.assertTrue(self.panel.timer.isActive())
        for _ in range(3):
            self.panel._tick()
        self.assertGreater(self.panel.slider.value(), 0)
        self.panel.slider.setValue(999)
        self.panel._tick()
        self.assertEqual(self.panel.slider.value(), 1000)
        self.assertFalse(self.panel.btn_play.isChecked())
        self.assertFalse(self.panel.timer.isActive())

    def test_aviso_fora_da_mesa_e_limite_de_linhas(self):
        self.win.create_shape(fm.rect_path(QRectF(380, 10, 60, 20)), "rect")
        self.abrir()
        self.assertFalse(self.panel.lbl_aviso.isHidden())
        self.assertIn("fora da área", self.panel.lbl_aviso.text())
        self.win.set_layer_field("C01", "modo", "preenchimento")
        self.win.set_layer_field("C01", "intervalo_mm", 0.01)
        for _ in range(11):                                                  # 11 × 40 000 linhas
            self.win.create_shape(fm.rect_path(QRectF(0, 0, 400, 400)), "rect")
        self.assertFalse(self.ov.isVisible())
        self.assertIn("grande demais", self.panel.lbl_resumo.text())

    def test_projeto_novo_atualiza_e_previa_nao_envia_nada(self):
        self.abrir()
        self.win.new_document()
        self.assertIn("Nada para executar", self.panel.lbl_resumo.text())
        self.assertNotIn("PySide6.QtSerialPort", sys.modules)


if __name__ == "__main__":
    unittest.main()
