"""Controle da máquina (Etapa 14/15) no simulador GRBL: liberar, mover, enquadrar, enviar trabalho, pausar, parar."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack import conexao as cx  # noqa: E402
from tests.test_conexao import conectar, rodar  # noqa: E402


class ControleTest(unittest.TestCase):
    def setUp(self):
        self.sim, self.tr, self.c = conectar()
        self.assertEqual(self.c.estado, cx.CONECTADO)

    def test_sem_liberar_nada_move(self):
        for fn in (lambda: self.c.jog(10, 0), lambda: self.c.ir_para(5, 5), lambda: self.c.desbloquear(),
                   lambda: self.c.iniciar_trabalho("G1 X1 F100\n")):
            with self.assertRaises(cx.ComandoProibido):
                fn()
        self.assertNotIn(b"$J=", self.tr.escrito)
        self.c.parar()  # parar é sempre permitido
        self.assertIn(bytes([0x18]), self.tr.escrito)

    def test_jog_e_enquadrar_sem_laser(self):
        self.c.habilitar_controle(True)
        self.c.jog(10, 5, 6000)
        rodar(self.c, 1.0)
        self.assertEqual(tuple(round(v, 3) for v in self.sim.pos), (10.0, 5.0))
        self.c.enquadrar(10, 5, 40, 25, 6000)
        rodar(self.c, 3.0)
        self.assertEqual(tuple(round(v, 3) for v in self.sim.pos), (10.0, 5.0))  # voltou ao começo
        self.assertEqual(self.sim.comprimento_com_laser(), 0.0)  # enquadrar nunca liga o laser
        self.assertTrue(all(s.potencia == 0 for s in self.sim.trilha))

    def test_comandos_fora_da_lista_recusados(self):
        self.c.habilitar_controle(True)
        with self.assertRaises(cx.ComandoProibido):
            self.c._linha_controle("$32=0")
        with self.assertRaises(cx.ComandoProibido):
            self.c.iniciar_trabalho("G1 X1 F100\n$32=0\n")  # comando de sistema dentro do trabalho

    def test_trabalho_completo_com_buffer(self):
        self.c.habilitar_controle(True)
        linhas = ["G21", "G90", "M4 S0"] + [f"G1 X{10 + (k % 2) * 20} Y{5 + k * 0.5} S500 F3000" for k in range(60)]
        linhas += ["M5 S0", "G0 X0 Y0"]
        self.c.iniciar_trabalho("; teste\n" + "\n".join(linhas) + "\n")
        self.assertEqual(self.c.trabalho, cx.TRABALHO_RODANDO)
        maximo = 0
        for _ in range(4000):
            self.c.tick(0.05)
            maximo = max(maximo, sum(self.c._job_pend))
            if self.c.trabalho != cx.TRABALHO_RODANDO:
                break
        self.assertEqual(self.c.trabalho, cx.TRABALHO_FIM)
        self.assertLessEqual(maximo, cx.RX_BUFFER)  # nunca estoura o buffer do GRBL
        self.assertGreater(self.sim.comprimento_com_laser(), 500)  # gravou de verdade (no simulador)
        self.assertFalse(self.sim.emitindo)  # terminou com o laser apagado
        self.assertEqual(self.c.progresso, 0.0)

    def test_erro_no_meio_pausa_e_parar_apaga(self):
        self.c.habilitar_controle(True)
        self.c.iniciar_trabalho("G21\nG90\nM4 S300\nG1 X20 Y0 F600\nG2 X30 Y10 I5 J5\nG1 X40 Y0\nM5\n")
        rodar(self.c, 3.0)
        self.assertEqual(self.c.trabalho, cx.TRABALHO_ERRO)  # G2 dá error:20 no simulador
        depois_do_erro = self.tr.escrito.split(b"G2 X30")[1]
        self.assertIn(b"!", depois_do_erro)  # pausou na hora (linhas já no buffer do GRBL ficam paradas)
        self.assertEqual(self.c._job_i, len(self.c._job))  # e não vai mandar mais nada
        self.c.parar()
        rodar(self.c, 2.0)
        self.assertFalse(self.sim.emitindo)

    def test_pausar_retomar_e_parar_durante_trabalho(self):
        self.c.habilitar_controle(True)
        self.c.iniciar_trabalho("G21\nG90\nM4 S500\nG1 X100 Y0 F600\nG1 X100 Y50\nM5\n")
        rodar(self.c, 1.0)
        self.c.pausar()
        self.assertEqual(self.c.trabalho, cx.TRABALHO_PAUSADO)
        x = self.sim.pos[0]
        rodar(self.c, 2.0)
        self.assertAlmostEqual(self.sim.pos[0], x, places=6)  # parado na pausa
        self.c.retomar()
        rodar(self.c, 1.0)
        self.assertGreater(self.sim.pos[0], x)
        self.c.parar()
        self.assertEqual(self.c.trabalho, cx.TRABALHO_ERRO)
        rodar(self.c, 2.0)
        self.assertFalse(self.sim.emitindo)
        self.assertEqual(self.c.estado, cx.CONECTADO)  # reiniciou e reidentificou, nada retomado

    def test_ar_e_enquadrar_com_laser_fraco(self):
        self.c.habilitar_controle(True)
        self.c.ar(True)
        rodar(self.c, 0.5)
        self.assertIn(b"M8\n", self.tr.escrito)
        self.c.enquadrar_com_laser(10, 10, 30, 20, potencia_pct=50, feed=6000, s_max=1000)  # pediu 50 %: limita a 5 %
        self.assertIn("M4 S50", self.c._job)
        for _ in range(400):
            self.c.tick(0.05)
            if self.c.trabalho != cx.TRABALHO_RODANDO:
                break
        self.assertEqual(self.c.trabalho, cx.TRABALHO_FIM)
        self.assertAlmostEqual(self.sim.comprimento_com_laser(), 60, delta=1)  # perímetro 2×(20+10) com laser
        self.assertTrue(all(sg.potencia <= 50 for sg in self.sim.trilha))
        self.assertFalse(self.sim.emitindo)

    def test_parar_destrava_e_alarme_de_verdade_nao(self):
        self.c.habilitar_controle(True)
        self.c.iniciar_trabalho("G21\nG90\nM4 S300\nG1 X100 Y0 F600\nM5\n")
        rodar(self.c, 1.0)
        self.c.parar()  # reset no meio do movimento: o GRBL volta em ALARM:3
        rodar(self.c, 3.0)
        self.assertEqual(self.c.status.estado, "Idle")  # desbloqueou sozinho
        self.c.jog(10, 0, 6000)
        rodar(self.c, 1.0)
        self.assertEqual(self.c.status.estado, "Idle")
        self.assertAlmostEqual(self.c.posicao[0] - 0, self.sim.pos[0], places=3)
        # alarme que NÃO veio do Parar (ex.: limite): continua travado e avisa
        self.sim._alarme(2)
        rodar(self.c, 1.0)
        self.c.jog(5, 0, 6000)
        rodar(self.c, 1.0)
        self.assertEqual(self.c.ultimo_erro_comando, "error:9")
        self.assertIn("Desbloquear", self.c.log[-1][1] + " ".join(t for _, t in self.c.log[-6:]))
        self.c.desbloquear()
        rodar(self.c, 1.0)
        self.c.jog(5, 0, 6000)
        rodar(self.c, 1.0)
        self.assertEqual(self.c.ultimo_erro_comando, "")

    def test_posicao_do_cabecote(self):
        self.c.habilitar_controle(True)
        self.c.jog(12, 7, 6000)
        rodar(self.c, 1.0)
        self.assertEqual(tuple(round(v, 3) for v in self.c.posicao), (12.0, 7.0))
        self.c._receber("<Idle|MPos:20.000,10.000,0.000|FS:0,0|WCO:5.000,2.000,0.000>")
        self.assertEqual(self.c.posicao, (15.0, 8.0))  # posição do trabalho = máquina − origem


if __name__ == "__main__":
    unittest.main()
