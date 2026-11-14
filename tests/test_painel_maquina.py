"""Etapa 13 na janela: conectar ao simulador, ler identificação, nada de movimento/laser."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import conexao as cx  # noqa: E402
from redblack import transporte as tp  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class PainelMaquinaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.show_error = lambda t, m: None
        self.win.show()
        app.processEvents()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def conectar_simulador(self, segundos=1.5):
        self.win.port_combo.setCurrentIndex(0)
        self.win._toggle_conexao()
        for _ in range(int(segundos / 0.05)):
            self.win._tick_conexao()

    def test_conecta_ao_simulador_e_mostra_identificacao(self):
        self.conectar_simulador()
        w = self.win
        self.assertEqual(w.conexao.estado, cx.CONECTADO)
        self.assertIn("Conectado", w.machine_state.text())
        self.assertIn("Idle", w.machine_state.text())
        self.assertIn("Grbl 1.1h", w.machine_info.text())
        self.assertIn("400 × 400", w.machine_info.text())
        self.assertIn("$32 modo laser: 1", w.machine_info.text())
        self.assertEqual(w.btn_connect.text(), "Desconectar")
        self.assertEqual(w.machine_status_label.text(), "Máquina: conectado (simulador, somente leitura)")
        self.assertFalse(w.port_combo.isEnabled())
        self.assertTrue(w.btn_report.isEnabled())
        log = w.machine_log.toPlainText()
        self.assertIn("→ $I", log)
        self.assertIn("→ $$", log)
        self.assertNotIn("<Idle", log)                       # status periódico fora do registro
        sim = w.conexao.tr.sim
        self.assertEqual((sim.trilha, sim.spindle), ([], "M5"))  # nada se moveu, laser nunca armado
        self.assertTrue(w.machine_warn.isVisible())           # simulador: $20=0 gera aviso

    def test_desconectar_e_relatorio(self):
        self.conectar_simulador()
        p = os.path.join(self.tmp.name, "maquina.json")
        self.assertTrue(self.win.salvar_relatorio_maquina(p))
        with open(p, encoding="utf-8") as f:
            rel = json.load(f)
        self.assertEqual((rel["firmware"], rel["modo_laser"], rel["curso_x_mm"]), ("1.1h", 1, 400))
        self.assertIn("$130", rel["configuracoes"])
        self.win._toggle_conexao()
        self.assertEqual(self.win.conexao.estado, cx.DESCONECTADO)
        self.assertEqual(self.win.btn_connect.text(), "Conectar")
        self.assertEqual(self.win.machine_status_label.text(), "Máquina: desconectada")
        self.assertTrue(self.win.port_combo.isEnabled())
        self.assertFalse(self.win._conexao_timer.isActive())

    def test_procurar_portas_nao_abre_nada(self):
        orig = tp.listar_portas
        tp.listar_portas = lambda: [("COM7", "USB-SERIAL CH340 (USB 1A86:7523)")]
        try:
            self.win._procurar_portas()
        finally:
            tp.listar_portas = orig
        self.assertEqual(self.win.port_combo.count(), 2)
        self.assertEqual(self.win.port_combo.itemData(1), "COM7")
        self.assertIsNone(self.win.conexao)

    def test_porta_que_nao_abre_vira_falha(self):
        class NaoAbre(tp.TransporteSerial):
            def abrir(self):
                raise tp.TransporteErro("Acesso negado")
        orig = tp.TransporteSerial
        tp.TransporteSerial = NaoAbre
        try:
            self.win.port_combo.addItem("COM99 — teste", "COM99")
            self.win.port_combo.setCurrentIndex(1)
            self.win._toggle_conexao()
        finally:
            tp.TransporteSerial = orig
        self.assertEqual(self.win.conexao.estado, cx.FALHA)
        self.assertIn("Acesso negado", self.win.machine_state.text())
        self.assertEqual(self.win.btn_connect.text(), "Conectar")


if __name__ == "__main__":
    unittest.main()
