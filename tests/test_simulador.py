"""Etapa 12: respostas, erros, desconexão e estados reproduzíveis (simulador GRBL, sem máquina)."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 e compensação X desligada)

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.simulador import BOAS_VINDAS, SimuladorGrbl  # noqa: E402
from redblack.transporte import TransporteErro, TransporteSimulado  # noqa: E402
from tools.simular import linhas_de_codigo, transmitir  # noqa: E402

app = QApplication.instance() or QApplication([])


def novo(config=None):
    sim = SimuladorGrbl(config)
    tr = TransporteSimulado(sim)
    tr.abrir()
    return sim, tr


def env(sim, *linhas):
    for ln in linhas:
        sim.receber((ln + "\n").encode())
    return sim.ler()


def trabalho(lay=None):
    lay = lay or [cm.alterar(cm.nova("C01"), velocidade_mm_min=600, potencia_max=50)]
    snap = ob.Shape(fm.rect_path(QRectF(10, 20, 100, 50)), "r", "C01", cm.cor("C01")).snapshot()
    perc = pc.gerar([snap], lay)
    return perc, gc.gerar(perc, lay)


class RespostasTest(unittest.TestCase):
    def test_boot_status_e_informacoes(self):
        sim, _ = novo()
        self.assertEqual(sim.ler(), [BOAS_VINDAS])
        sim.receber(b"?")
        self.assertEqual(sim.ler(), ["<Idle|MPos:0.000,0.000,0.000|FS:0,0|Bf:15,128>"])
        out = env(sim, "$I")
        self.assertEqual(out[-1], "ok")
        self.assertIn("[OPT:V,15,128]", out)
        out = env(sim, "$$")
        self.assertIn("$30=1000", out)
        self.assertIn("$32=1", out)
        self.assertIn("$130=400", out)
        self.assertEqual(out[-1], "ok")
        self.assertEqual(env(sim, "$G")[-1], "ok")

    def test_erros_com_codigos_do_grbl(self):
        sim, _ = novo()
        sim.ler()
        casos = {"G1 X10": "error:22",       # sem F
                 "G5": "error:20",           # não suportado
                 "G1 Xab": "error:2",        # número inválido
                 "10 X10": "error:1",        # número sem letra (GRBL ignora espaços: "X10 10" seria X1010)
                 "$99=1": "error:3",         # configuração inexistente
                 "$H": "error:5",            # homing desabilitado
                 "G1 X1 " + "0" * 80: "error:11",  # linha longa demais
                 "G2 X1 Y1 I1 J0": "error:20"}     # arco: não simulado
        for linha, esperado in casos.items():
            self.assertEqual(env(sim, linha), [esperado], linha)
        self.assertEqual(env(sim, "; só comentário", ""), ["ok", "ok"])
        self.assertEqual(sim.estado, "Idle")  # erro não muda o estado

    def test_trabalho_gerado_executa_igual_a_previa(self):
        perc, texto = trabalho()
        sim, tr = novo()
        tr.ler_linhas()
        rel = transmitir(tr, linhas_de_codigo(texto))
        self.assertEqual((rel["erros"], rel["alarmes"]), ([], []))
        self.assertEqual(rel["oks"], len(linhas_de_codigo(texto)))
        self.assertAlmostEqual(sim.comprimento_com_laser(), perc.comprimento_corte, delta=0.01)
        rapidos = [s for s in sim.trilha if s.rapido]
        self.assertTrue(rapidos and all(s.potencia == 0 for s in rapidos))   # G0 sempre apagado
        self.assertEqual({s.potencia for s in sim.trilha if not s.rapido}, {500})  # 50 % de 1000
        self.assertEqual(sim.pos, (0.0, 0.0))
        self.assertEqual(sim.estado, "Idle")
        self.assertFalse(sim.emitindo)
        self.assertEqual(sim.estouros, 0)
        self.assertAlmostEqual(sim.emissao_parada_s, 0.0, delta=1e-9)       # nunca parado com laser ligado
        self.assertAlmostEqual(sim.tempo - 0.0, perc.tempo_s, delta=0.05)    # mesmo modelo de tempo


class FluxoTest(unittest.TestCase):
    def test_planejador_cheio_segura_o_ok(self):
        sim, _ = novo()
        sim.ler()
        env(sim, "G1 F600")
        lote = b"".join(b"G1X%d\n" % (i + 1) for i in range(17))  # 17 linhas, < 128 bytes
        self.assertLess(len(lote), 128)
        sim.receber(lote)
        self.assertEqual(sim.ler().count("ok"), 15)   # só cabe 15 no planejador
        self.assertIn("Bf:0,", sim.status())
        sim.avancar(0.1)                               # 1 mm a 10 mm/s conclui o 1º bloco
        self.assertEqual(sim.ler().count("ok"), 1)
        sim.avancar(10)
        self.assertEqual(sim.ler().count("ok"), 1)
        self.assertEqual(sim.pos, (17.0, 0.0))

    def test_estouro_do_buffer_perde_dados(self):
        sim, _ = novo()
        sim.ler()
        env(sim, *["G1X%dF600" % (i + 1) for i in range(15)])     # planejador cheio (15 blocos)
        self.assertEqual(sim.estouros, 0)
        sim.receber(b"G1X99F600\n" * 15)                          # 150 bytes sem esperar "ok": não cabem
        self.assertEqual(sim.estouros, 150 - 128)                 # o excedente é perdido
        self.assertEqual(sim.status().split("Bf:")[1], "0,0>")

    def test_transmissor_correto_nao_estoura(self):
        sim, tr = novo()
        tr.ler_linhas()
        linhas = [f"G1 X{i % 50 + 1} Y{i % 7 + 1} F3000" for i in range(300)]
        rel = transmitir(tr, linhas)
        self.assertEqual((sim.estouros, rel["oks"], rel["erros"]), (0, 300, []))


class EstadosTest(unittest.TestCase):
    def test_pausa_e_retomada(self):
        sim, _ = novo()
        sim.ler()
        env(sim, "M3 S500", "G1 X100 F600")
        sim.avancar(1)
        self.assertEqual(sim.estado, "Run")
        self.assertTrue(sim.emitindo)
        sim.receber(b"!")
        self.assertEqual(sim.estado, "Hold:0")
        self.assertFalse(sim.emitindo)                 # pausa apaga o laser
        parado = sim.pos
        sim.avancar(5)
        self.assertEqual(sim.pos, parado)
        self.assertEqual(sim.emissao_parada_s, 0.0)
        sim.receber(b"~")
        sim.avancar(100)
        self.assertEqual((sim.estado, sim.pos), ("Idle", (100.0, 0.0)))

    def test_reset_em_movimento_gera_alarme_3_e_nao_retoma(self):
        sim, _ = novo()
        sim.ler()
        env(sim, "M3 S500", "G1 X100 F600", "G1 X0 F600")
        sim.avancar(2)
        sim.receber(b"\x18")
        out = sim.ler()
        self.assertEqual(out[:2], ["ALARM:3", BOAS_VINDAS])
        self.assertEqual(sim.estado, "Alarm")
        self.assertFalse(sim.planner)
        self.assertFalse(sim.emitindo)
        self.assertEqual(env(sim, "G1 X5 F600"), ["error:9"])    # travado
        self.assertEqual(env(sim, "$X"), ["[MSG:Caution: Unlocked]", "ok"])
        self.assertEqual(sim.estado, "Idle")

    def test_reset_parado_nao_gera_alarme(self):
        sim, _ = novo()
        sim.ler()
        sim.receber(b"\x18")
        self.assertEqual(sim.ler(), [BOAS_VINDAS])
        self.assertEqual(sim.estado, "Idle")

    def test_limite_por_software(self):
        sim, _ = novo({20: 1})
        sim.ler()
        env(sim, "M3 S800", "G1 X10 Y10 F600")
        self.assertEqual(env(sim, "G1 X500 F600"), ["ALARM:2"])
        self.assertEqual(sim.estado, "Alarm")
        self.assertFalse(sim.emitindo)
        self.assertEqual(sim.spindle, "M5")

    def test_transmissor_para_no_alarme_e_aponta_a_linha(self):
        sim, tr = novo({20: 1})
        tr.ler_linhas()
        linhas = ["G21", "G90", "M3 S500", "G1 X10 Y10 F600", "G1 X450 Y10", "G1 X10 Y10", "M5"]
        rel = transmitir(tr, linhas)
        self.assertEqual(rel["alarmes"], ["ALARM:2 (linha 5: G1 X450 Y10)"])
        self.assertEqual(rel["erros"], [])
        self.assertEqual(sim.estado, "Alarm")
        self.assertFalse(sim.emitindo)

    def test_homing_e_inicio_travado(self):
        sim, _ = novo({22: 1})
        self.assertEqual(sim.ler(), [BOAS_VINDAS, "[MSG:'$H'|'$X' to unlock]"])
        self.assertEqual(sim.estado, "Alarm")
        env(sim, "$X")
        env(sim, "G0 X30 Y40")
        sim.avancar(10)
        sim.ler()
        self.assertEqual(env(sim, "$H"), [])          # o "ok" só vem ao terminar
        self.assertEqual(sim.estado, "Home")
        sim.avancar(50 / (3000 / 60))                 # 50 mm a $25=3000 mm/min
        self.assertEqual(sim.ler(), ["ok"])
        self.assertEqual((sim.estado, sim.pos), ("Idle", (0.0, 0.0)))

    def test_jog_cancelamento_e_limite(self):
        sim, _ = novo({20: 1})
        sim.ler()
        self.assertEqual(env(sim, "$J=G91 X10 F600"), ["ok"])
        self.assertEqual(sim.estado, "Jog")
        self.assertFalse(sim.emitindo)
        sim.avancar(0.5)
        sim.receber(b"\x85")
        self.assertEqual(sim.estado, "Idle")
        self.assertAlmostEqual(sim.pos[0], 5.0, delta=1e-9)
        self.assertTrue(sim.absoluto)                 # G91 do jog não vaza para o programa
        self.assertEqual(env(sim, "$J=G90 X900 F600"), ["error:15"])
        self.assertEqual(sim.estado, "Idle")          # jog fora do limite não dispara alarme
        self.assertEqual(env(sim, "$J=X10"), ["error:16"])

    def test_modo_verificacao(self):
        _, texto = trabalho()
        sim, _ = novo()
        sim.ler()
        self.assertEqual(env(sim, "$C"), ["[MSG:Enabled]", "ok"])
        self.assertEqual(sim.estado, "Check")
        out = env(sim, *linhas_de_codigo(texto), "G1 X1")
        self.assertEqual(out[-1], "ok")
        self.assertNotIn("error:22", out[:-1])
        sim.avancar(100)
        self.assertEqual((sim.pos, sim.trilha), ((0.0, 0.0), []))   # nada se moveu
        self.assertEqual(sim.emissao_parada_s, 0.0)

    def test_m3_parado_e_detectado_m4_nao(self):
        sim, _ = novo()
        sim.ler()
        env(sim, "M3 S300")
        sim.avancar(2)
        self.assertAlmostEqual(sim.emissao_parada_s, 2.0)
        self.assertTrue(sim.emitindo)
        env(sim, "M4 S300")
        sim.avancar(2)
        self.assertAlmostEqual(sim.emissao_parada_s, 2.0)            # M4: potência ~0 parado
        env(sim, "M5")
        self.assertFalse(sim.emitindo)


class ConexaoTest(unittest.TestCase):
    def test_desconexao_no_meio_e_reconexao_sem_retomar(self):
        _, texto = trabalho()
        sim, tr = novo()
        tr.ler_linhas()
        linhas = linhas_de_codigo(texto)
        for ln in linhas[:6]:
            tr.escrever((ln + "\n").encode())
        tr.esperar(3)
        sim.desconectar()
        self.assertFalse(tr.aberto)
        with self.assertRaises(TransporteErro):
            tr.escrever(b"G1 X1\n")
        with self.assertRaises(TransporteErro):
            tr.ler_linhas()
        tr.abrir()                                        # nova conexão = controlador reiniciado
        self.assertEqual(tr.ler_linhas(), [BOAS_VINDAS])
        self.assertEqual(sim.estado, "Idle")
        self.assertFalse(sim.planner)
        tr.esperar(10)
        self.assertEqual(sim.pos, (0.0, 0.0))             # nada foi retomado sozinho
        self.assertEqual(sim.spindle, "M5")

    def test_porta_fechada(self):
        sim, tr = novo()
        tr.fechar()
        with self.assertRaises(TransporteErro):
            tr.escrever(b"?")


class ReprodutibilidadeTest(unittest.TestCase):
    def execucao(self):
        _, texto = trabalho([cm.alterar(cm.nova("C01"), modo="preenchimento", intervalo_mm=1.0)])
        sim, tr = novo()
        tr.ler_linhas()
        rel = transmitir(tr, linhas_de_codigo(texto))
        sim.receber(b"?")
        return rel, sim.trilha, sim.ler(), sim.tempo

    def test_mesma_entrada_mesmo_resultado(self):
        self.assertEqual(self.execucao(), self.execucao())


if __name__ == "__main__":
    unittest.main()
