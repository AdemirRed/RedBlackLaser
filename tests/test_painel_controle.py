"""Painel Máquina com controle, no simulador: liberar, mover, enquadrar, iniciar trabalho do projeto, parar."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import conexao as cx  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class PainelControleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_error = self.w.show_info = lambda *a: None
        self.w.new_document()

    def tearDown(self):
        if self.w.conexao:
            self.w.conexao.desconectar()
        self.w.close()
        self.tmp.cleanup()

    def ticks(self, n):
        for _ in range(n):
            self.w._tick_conexao()

    def conectar(self):
        self.w.port_combo.setCurrentIndex(0)  # simulador
        self.w._toggle_conexao()
        self.w._conexao_timer.stop()  # os testes avançam o tempo na mão
        self.ticks(40)
        self.assertEqual(self.w.conexao.estado, cx.CONECTADO)

    def test_setas_movem_o_cabecote(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.conectar()
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        sim = self.w.conexao.tr.sim
        b = self.w.jog_btns["right"]
        for tecla, mod in ((Qt.Key_Right, Qt.NoModifier), (Qt.Key_Up, Qt.ShiftModifier),
                           (Qt.Key_Right, Qt.ControlModifier), (Qt.Key_Up, Qt.AltModifier)):
            QTest.keyClick(b, tecla, mod)  # toque: um passo
            self.ticks(80)
        self.assertEqual(tuple(round(v, 3) for v in sim.pos), (11.0, 50.1))
        # segurar: jog longo; soltar cancela (0x85) e o cabeçote fica no meio do caminho
        QTest.keyPress(b, Qt.Key_Right)
        self.w._jog_segurar.stop()
        self.w._jog_continuo()
        self.ticks(5)
        QTest.keyRelease(b, Qt.Key_Right)
        self.ticks(40)
        self.assertIn("[cancelar jog]", [t for _, t in self.w.conexao.log])
        self.assertGreater(sim.pos[0], 11.0)
        self.assertLess(sim.pos[0], gc.area(gc.PERFIL)[0])
        self.assertIsNone(self.w._jog_seta)

    def test_fluxo_completo_no_simulador(self):
        self.conectar()
        self.assertFalse(self.w.jog_btns["up"].isEnabled())  # conectado, mas controle ainda travado
        self.w.ask_liberar_controle = lambda: False
        self.w.btn_controle.setChecked(True)
        self.assertFalse(self.w.conexao.controle)  # recusou: continua travado
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.assertTrue(self.w.conexao.controle)
        self.assertTrue(self.w.jog_btns["up"].isEnabled())
        sim = self.w.conexao.tr.sim
        self.w.jog_passo.setCurrentIndex(2)  # 10 mm
        self.w.jog_btns["right"].click()
        self.w.jog_btns["up"].click()
        self.ticks(80)
        self.assertEqual(tuple(round(v, 3) for v in sim.pos), (10.0, 10.0))
        from redblack import gcode as gc
        W, H = gc.area(gc.PERFIL)
        esperado = gc.doc_para_maquina(10.0, 10.0, W, H)  # cabeçote mostrado na mesa, no lugar certo
        mira = self.w.canvas.view.cabecote_alvo  # a mira desliza até aqui
        self.assertIsNotNone(mira)
        self.assertAlmostEqual(mira.x(), esperado[0], places=2)
        self.assertAlmostEqual(mira.y(), esperado[1], places=2)
        self.assertIn("cabeçote X 10,0 Y 10,0", self.w.machine_state.text())
        # uma peça no projeto: enquadrar (sem laser) e gravar
        self.w.create_shape(fm.rect_path(QRectF(20, 300, 30, 20)), "rect")
        rapida = self.w.caixa_do_trabalho()  # só geometria (instantâneo)
        _, completa, _ = self.w.gcode_do_trabalho()  # pelo percurso inteiro
        for a, b in zip(rapida, completa):
            self.assertAlmostEqual(a, b, delta=0.05)
        self.assertTrue(self.w.enquadrar_trabalho())
        self.ticks(200)
        self.assertEqual(sim.comprimento_com_laser(), 0.0)
        self.w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertTrue(self.w.iniciar_trabalho())
        self.assertFalse(self.w.btn_iniciar.isEnabled())
        self.assertTrue(self.w.btn_pausar.isEnabled())
        for _ in range(4000):
            self.w._tick_conexao()
            if self.w.conexao.trabalho == cx.TRABALHO_FIM:
                break
        self.assertEqual(self.w.conexao.trabalho, cx.TRABALHO_FIM)
        self.assertGreater(sim.comprimento_com_laser(), 90)  # perímetro do retângulo com laser (camada C01)
        self.assertFalse(sim.emitindo)
        self.assertTrue(self.w.btn_iniciar.isEnabled())

    def test_parar_sempre_disponivel(self):
        self.conectar()
        self.assertTrue(self.w.btn_parar.isEnabled())  # mesmo sem liberar o controle
        self.w.btn_parar.click()
        self.assertIn("PARAR", self.w.conexao.log[-1][1] + str(self.w.conexao.log[-2:]))

    def test_posicao_atual_sem_gravar_origem_e_limite_do_curso(self):
        from redblack import gcode as gc
        self.conectar()
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.w.jog_passo.setCurrentIndex(2)
        self.w.jog_btns["right"].click()
        self.w.jog_btns["up"].click()
        self.ticks(80)  # cabeçote em (10, 10)
        self.w.create_shape(fm.rect_path(QRectF(200, 100, 30, 20)), "rect")
        self.w.inicio_trabalho.setCurrentIndex(1)  # posição atual
        self.w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertTrue(self.w.iniciar_trabalho())
        self.assertFalse(any("G10" in t for _, t in self.w.conexao.log))  # nada gravado no controlador
        job = self.w.conexao._job
        xs = [float(t[1:]) for ln in job if ln.startswith("G1") for t in ln.split() if t.startswith("X")]
        self.assertAlmostEqual(min(xs), 10, delta=0.5)  # o canto do trabalho ficou onde estava o cabeçote
        for _ in range(4000):
            self.w._tick_conexao()
            if self.w.conexao.trabalho == cx.TRABALHO_FIM:
                break
        # trabalho que passa do curso: pergunta e, sem confirmar, não começa
        self.w.inicio_trabalho.setCurrentIndex(0)
        self.w.conexao.wco = (300.0, 0.0, 0.0)  # origem deslocada 300 mm: o desenho em X 200 cai em X 500
        perguntou = []
        self.w.ask_fora_do_curso = lambda av: perguntou.append(av) or False
        self.assertFalse(self.w.iniciar_trabalho())
        self.assertTrue(perguntou and "passa do curso" in perguntou[0][0])
        self.assertEqual(self.w.conexao.trabalho, cx.TRABALHO_FIM)  # não iniciou outro
        entrada = chr(10).join(["G0 X1 Y2", "G1 X3.5 Y-1 S10 F100", "M5"]) + chr(10)
        esperado = chr(10).join(["G0 X11.000 Y22.000", "G1 X13.500 Y19.000 S10 F100", "M5"]) + chr(10)
        self.assertEqual(gc.deslocar(entrada, 10, 20), esperado)

    def test_referenciar_pelos_fins_de_curso(self):
        self.conectar()
        sim = self.w.conexao.tr.sim
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.w.jog_btns["right"].click()
        self.w.jog_btns["up"].click()
        self.ticks(80)
        self.assertEqual(sim.config[22], 0)  # sem homing ainda
        self.w.ask_ativar_homing = lambda: False
        self.assertFalse(self.w.referenciar_maquina())  # recusou: não grava nada
        self.assertEqual(sim.config[22], 0)
        self.w.ask_ativar_homing = lambda: True
        self.assertTrue(self.w.referenciar_maquina())
        self.ticks(200)
        self.assertEqual(sim.config[22], 1)  # $22=1 gravado no controlador
        self.assertEqual(self.w.conexao.info.valor(22), 1)
        self.assertEqual(tuple(round(v, 3) for v in sim.pos), (0.0, 0.0))  # foi até os fins de curso
        self.assertEqual(self.w.conexao.status.estado, "Idle")
        self.assertTrue(any("G10 L20 P1 X0" in t for _, t in self.w.conexao.log))
        self.assertEqual(tuple(round(v, 3) for v in self.w.conexao.posicao), (0.0, 0.0))
        # automático ao liberar o controle
        self.w.jog_btns["right"].click()
        self.ticks(60)
        self.w.btn_controle.setChecked(False)
        self.w.chk_home_auto.setChecked(True)
        self.w.btn_controle.setChecked(True)
        self.ticks(200)
        self.assertEqual(tuple(round(v, 3) for v in sim.pos), (0.0, 0.0))

    def test_duplo_clique_leva_o_laser(self):
        from PySide6.QtCore import QPointF
        self.conectar()
        self.assertFalse(self.w.laser_ate_ponto(QPointF(50, 50)))  # sem controle liberado: não mexe
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        W, H = gc.area(gc.PERFIL)
        alvo = gc.doc_para_maquina(120, 80, W, H)
        self.assertTrue(self.w.laser_ate_ponto(QPointF(120, 80)))
        self.ticks(300)
        sim = self.w.conexao.tr.sim
        self.assertAlmostEqual(sim.pos[0], alvo[0], delta=0.01)
        self.assertAlmostEqual(sim.pos[1], alvo[1], delta=0.01)
        self.assertFalse(self.w.laser_ate_ponto(QPointF(-50, 80)))  # fora da mesa

    def test_mira_desliza_e_fica_em_cima_do_desenho(self):
        import time
        from PySide6.QtCore import QPointF
        from redblack import rotativo as rt
        v = self.w.canvas.view
        v.definir_cabecote(QPointF(0, 0))
        time.sleep(0.1)
        v.definir_cabecote(QPointF(100, 0))  # nova leitura: a mira não pula, desliza
        v._passo_cabecote()
        self.assertLess(v.cabecote.x(), 100)
        time.sleep(0.15)
        v._passo_cabecote()
        self.assertAlmostEqual(v.cabecote.x(), 100, places=6)
        # posição atual (+30, +5) com rotativo ×2: a máquina em (40, 25) é o desenho em (10, 20 + (20 - 20) / 2) …
        self.w.definir_rotativo(rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360,
                                            diametro_objeto_mm=360 / (2 * 3.141592653589793)))
        mapa = self.w._mapa_saida_para_desenho((10, 20, 50, 40), 30, 5)
        x, y = mapa((40, 25 + 40))  # 40 mm de G-code na volta = 20 mm no desenho
        self.assertAlmostEqual(x, 10, places=6)
        self.assertAlmostEqual(y, 40, places=6)
        self.assertEqual(self.w._caixa_na_saida((10, 20, 50, 40)), (10, 20, 50, 60))
        self.w.definir_rotativo(rt.Rotativo())

    def _rodar(self, limite=6000):
        for _ in range(limite):
            self.w._tick_conexao()
            if self.w.conexao.trabalho in (cx.TRABALHO_FIM, cx.TRABALHO_ERRO):
                return

    def test_retomar_depois_de_parar_e_comecar_no_meio(self):
        self.conectar()
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        for k in range(6):
            self.w.create_shape(fm.rect_path(QRectF(20 + 25 * k, 20, 15, 15)), "rect")
        self.w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertIsNone(self.w.trabalho_salvo())
        self.assertTrue(self.w.iniciar_trabalho())
        total = len(self.w.conexao._job)
        for _ in range(60):  # anda um pouco e "cai a luz" (Parar = reset no meio)
            self.w._tick_conexao()
        self.w.conexao.parar()
        self.ticks(20)
        salvo = self.w.trabalho_salvo()
        self.assertIsNotNone(salvo)
        linhas, prog = salvo
        self.assertEqual(len(linhas), total)
        self.assertTrue(0 < prog["ok"] < total)
        self.ticks(40)  # alarme do reset é desbloqueado sozinho
        self.w.ask_retomar = lambda prog, total: 5  # volta 5 linhas
        self.assertTrue(self.w.retomar_interrompido())
        self.assertEqual(self.w.conexao._job[:3], ["G21", "G90", "M5"])  # começa com o estado restaurado
        self._rodar()
        self.assertEqual(self.w.conexao.trabalho, cx.TRABALHO_FIM)
        self.ticks(5)
        self.assertIsNone(self.w.trabalho_salvo())  # terminou: nada mais para retomar
        # começar no meio: só um trecho
        self.w.ask_faixa = lambda linhas: (len(linhas) // 2, len(linhas) // 2 + 6)
        self.assertTrue(self.w.iniciar_trabalho(escolher_faixa=True))
        self.assertLess(len(self.w.conexao._job), total)
        self._rodar()
        self.assertEqual(self.w.conexao.trabalho, cx.TRABALHO_FIM)

    def test_mira_continua_e_soltar_motores(self):
        self.conectar()
        sim = self.w.conexao.tr.sim
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.ticks(5)
        self.w.btn_mira.setChecked(True)
        self.ticks(20)
        enviados = [t for d, t in self.w.conexao.log if d == "→"]
        self.assertTrue(any(t.startswith("M3 S") for t in enviados) and "G1 F1000" in enviados)
        s_mira = int(next(t for t in enviados if t.startswith("M3 S"))[4:])
        self.assertLessEqual(s_mira, 20)  # nunca passa de 2 % de 1000
        self.w.btn_mira.setChecked(False)
        self.ticks(10)
        self.assertEqual(sim.spindle, "M5")
        self.w.btn_motores.setChecked(True)
        self.ticks(10)
        self.assertEqual(sim.config[1], 25)
        self.w.btn_motores.setChecked(False)
        self.ticks(10)
        self.assertEqual(sim.config[1], 255)

    def test_enviar_teste_de_precisao_para_a_maquina(self):
        self.conectar()
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.w.ask_precisao = lambda: {"lado": 40.0, "potencia": 10.0, "velocidade": 3000.0, "acao": "maquina"}
        self.w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertTrue(self.w.teste_precisao())
        for _ in range(8000):
            self.w._tick_conexao()
            if self.w.conexao.trabalho in (cx.TRABALHO_FIM, cx.TRABALHO_ERRO):
                break
        self.assertEqual(self.w.conexao.trabalho, cx.TRABALHO_FIM)

    def test_aviso_do_rotativo_e_desligar(self):
        import dataclasses
        self.w.definir_rotativo(dataclasses.replace(self.w.rotativo, ativo=True))
        self.assertFalse(self.w.aviso_rotativo.isHidden())
        self.assertIn("ROTATIVO LIGADO", self.w.aviso_rotativo.text())
        self.w.btn_desligar_rot.click()
        self.assertFalse(self.w.rotativo.ativo)
        self.assertTrue(self.w.aviso_rotativo.isHidden())

    def test_sons_iniciar_terminar_e_parar(self):
        from redblack.ui import sons
        tocados = []
        original = sons.tocar
        sons.tocar = lambda ev: tocados.append(ev) or True
        try:
            self.conectar()
            self.w.ask_liberar_controle = lambda: True
            self.w.btn_controle.setChecked(True)
            self.w.create_shape(fm.rect_path(QRectF(20, 300, 30, 20)), "rect")
            self.w.ask_confirmar_trabalho = lambda info, caixa: True
            self.w.iniciar_trabalho()
            for _ in range(4000):
                self.w._tick_conexao()
                if self.w.conexao.trabalho == cx.TRABALHO_FIM:
                    break
            self.w._tick_conexao()
            self.assertEqual(tocados[:2], ["inicio", "fim"])
            self.w.iniciar_trabalho()
            self.ticks(3)
            self.w.btn_parar.click()
            self.ticks(3)
            self.assertEqual(tocados[-1], "parado")
        finally:
            sons.tocar = original

    def test_arquivos_de_som(self):
        import wave
        from redblack.ui import sons
        for ev in sons.TONS:
            with wave.open(sons.arquivo(ev)) as w:
                self.assertGreater(w.getnframes(), 1000)


if __name__ == "__main__":
    unittest.main()
