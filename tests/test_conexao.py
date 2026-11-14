"""Etapa 13: conexão e identificação sem executar trabalho nem emitir laser (validado no simulador)."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack import conexao as cx  # noqa: E402
from redblack import grbl  # noqa: E402
from redblack.simulador import SimuladorGrbl  # noqa: E402
from redblack.transporte import TransporteErro, TransporteSerial, TransporteSimulado  # noqa: E402


class Espiao(TransporteSimulado):
    """Transporte simulado que registra tudo que o programa escreve."""

    def __init__(self, sim):
        super().__init__(sim)
        self.escrito = b""

    def escrever(self, data):
        self.escrito += data
        super().escrever(data)


class Mudo:
    """Porta que abre mas nunca responde (velocidade errada / não é GRBL)."""
    nome, aberto = "mudo", True

    def abrir(self): pass
    def fechar(self): self.aberto = False
    def escrever(self, data): pass
    def ler_linhas(self): return []
    def esperar(self, s): pass


def rodar(c, segundos, dt=0.05):
    for _ in range(int(round(segundos / dt))):
        c.tick(dt)


def conectar(config=None):
    sim = SimuladorGrbl(config)
    sim.ler()  # a placa já estava ligada; o boot abaixo é o da abertura da porta
    sim.conectado = False
    tr = Espiao(sim)
    c = cx.Conexao(tr)
    c.conectar()
    rodar(c, 1.0)
    return sim, tr, c


class ParserTest(unittest.TestCase):
    def test_status_variantes(self):
        s = grbl.status("<Idle|MPos:1.000,2.500,0.000|FS:0,0|Bf:15,128>")
        self.assertEqual((s.estado, s.mpos, s.feed, s.spindle), ("Idle", (1.0, 2.5, 0.0), 0.0, 0.0))
        s = grbl.status("<Alarm|WPos:0,0,0|F:500|WCO:0,0,0>")
        self.assertTrue(s.em_alarme)
        self.assertEqual((s.wpos, s.mpos, s.feed), ((0.0, 0.0, 0.0), None, 500.0))
        self.assertEqual(grbl.status("<Hold:0|MPos:x,y,z>").mpos, None)  # número inválido ignorado
        for lixo in ("ok", "<>", "Idle|MPos:0,0,0", "<" + "A" * 2000):
            self.assertIsNone(grbl.status(lixo), lixo[:20])

    def test_boas_vindas_e_config(self):
        self.assertEqual(grbl.boas_vindas("Grbl 1.1h ['$' for help]"), ("1.1h", "['$' for help]"))
        self.assertEqual(grbl.boas_vindas("Grbl 3.7 [FluidNC v3.7.18 (wifi) '$' for help]")[0], "3.7")
        self.assertIsNone(grbl.boas_vindas("ok"))
        self.assertEqual(grbl.configuracao("$130=410.500"), (130, 410.5))
        self.assertIsNone(grbl.configuracao("$N0="))

    def test_avisos_da_maquina(self):
        info = grbl.MaquinaInfo(config={30: 1000, 32: 0, 130: 410, 131: 400, 20: 0})
        av = " ".join(info.avisos())
        self.assertIn("Modo laser DESLIGADO", av)
        self.assertIn("410 × 400", av)
        self.assertIn("$20 = 0", av)
        ok = grbl.MaquinaInfo(config={30: 1000, 32: 1, 130: 400, 131: 400, 20: 1})
        self.assertEqual(ok.avisos(), [])
        self.assertEqual(ok.resumo()["modo_laser"], 1)


class ConexaoTest(unittest.TestCase):
    def test_conecta_identifica_e_fica_lendo_status(self):
        sim, tr, c = conectar()
        self.assertEqual(c.estado, cx.CONECTADO)
        self.assertEqual(c.info.firmware, "1.1h")
        self.assertIn("1.1h", c.info.versao)
        self.assertEqual(c.info.opcoes, "V,15,128")
        self.assertEqual((c.info.valor(30), c.info.valor(32), c.info.area), (1000, 1, (400.0, 400.0)))
        self.assertEqual(c.status.estado, "Idle")
        antes = tr.escrito.count(b"?")
        rodar(c, 3.0)
        self.assertGreaterEqual(tr.escrito.count(b"?") - antes, 2)   # status periódico

    def test_nada_alem_de_consultas_foi_enviado(self):
        sim, tr, c = conectar()
        rodar(c, 5.0)
        texto = tr.escrito.decode()
        self.assertEqual(set(texto.replace("?", "").split()), {"$I", "$$"})
        self.assertEqual(sim.trilha, [])                 # nada se moveu
        self.assertEqual(sim.spindle, "M5")              # laser nunca foi armado
        self.assertEqual(sim.emissao_parada_s, 0.0)

    def test_comandos_proibidos(self):
        _, tr, c = conectar()
        for cmd in ("G0 X10", "$X", "$H", "M3 S100", "$J=X1F100", "$32=0", "\x18", "~", "!"):
            with self.assertRaises(cx.ComandoProibido, msg=cmd):
                c.consultar(cmd)
        c.consultar("$G")
        rodar(c, 0.5)
        self.assertIn(b"$G\n", tr.escrito)

    def test_placa_que_nao_reinicia_ao_abrir(self):
        sim = SimuladorGrbl()
        sim.ler()                                        # boas-vindas já foram consumidas antes
        tr = Espiao(sim)
        c = cx.Conexao(tr)
        c.conectar()
        rodar(c, 1.0)
        self.assertEqual(c.estado, cx.CONECTANDO)        # esperando boas-vindas que não virão
        rodar(c, 2.0)                                    # após 2,5 s pergunta "?"
        self.assertEqual(c.estado, cx.CONECTADO)
        self.assertEqual(c.info.firmware, "")            # sem boas-vindas, mas identificado por $I/$$
        self.assertIn("1.1h", c.info.versao)

    def test_sem_resposta_vira_falha_e_fecha(self):
        tr = Mudo()
        c = cx.Conexao(tr)
        c.conectar()
        rodar(c, 7.0)
        self.assertEqual(c.estado, cx.FALHA)
        self.assertIn("Sem resposta", c.erro)
        self.assertFalse(tr.aberto)

    def test_maquina_em_alarme_nao_e_desbloqueada(self):
        sim, tr, c = conectar({22: 1})                   # homing ligado: inicia em Alarm
        self.assertEqual(c.estado, cx.CONECTADO)
        self.assertTrue(c.status.em_alarme)
        rodar(c, 3.0)
        self.assertNotIn(b"$X", tr.escrito)
        self.assertNotIn(b"$H", tr.escrito)
        self.assertEqual(sim.estado, "Alarm")

    def test_cabo_removido_e_reinicio_da_placa(self):
        sim, tr, c = conectar()
        sim.receber(b"\x18")                             # alguém apertou reset na placa
        rodar(c, 1.0)
        self.assertEqual(c.reinicios, 1)
        self.assertEqual(c.estado, cx.CONECTADO)         # reidentificou, só leitura
        sim.desconectar()                                # cabo puxado
        rodar(c, 0.2)
        self.assertEqual(c.estado, cx.FALHA)
        self.assertIn("Conexão perdida", c.erro)
        self.assertIn("Nada será retomado", c.erro)
        rodar(c, 5.0)                                    # não tenta reconectar sozinho
        self.assertEqual(c.estado, cx.FALHA)

    def test_porta_inexistente(self):
        class NaoAbre(Mudo):
            def abrir(self):
                raise TransporteErro("Acesso negado")
        c = cx.Conexao(NaoAbre())
        c.conectar()
        self.assertEqual(c.estado, cx.FALHA)
        self.assertIn("Acesso negado", c.erro)

    def test_registro_limitado(self):
        _, _, c = conectar()
        for i in range(2000):
            c._evento(f"e{i}")
        self.assertLessEqual(len(c.log), 500)


class _Codigo:
    """Erro do QSerialPort pelo nome (sem importar QtSerialPort: os outros testes conferem que ela só carrega ao conectar)."""

    def __init__(self, name):
        self.name = name


class PortaFalsa:
    """Imita QSerialPort para testar o transporte serial sem tocar em portas reais."""

    def __init__(self):
        self.aberta, self.entrada, self.saida = False, b"", b""

    def isOpen(self): return self.aberta
    def open(self, mode): self.aberta = True; return True
    def close(self): self.aberta = False
    def write(self, data): self.saida += bytes(data); return len(data)
    def flush(self): return True
    def readAll(self): d, self.entrada = self.entrada, b""; return d
    def waitForReadyRead(self, ms): return bool(self.entrada)
    def errorString(self): return "Recurso indisponível"


class TransporteSerialTest(unittest.TestCase):
    def test_linhas_partidas_crlf_e_lixo(self):
        p = PortaFalsa()
        tr = TransporteSerial("COM9", porta_qt=p)
        tr.abrir()
        p.entrada = b"Grbl 1.1h ['$' for "
        self.assertEqual(tr.ler_linhas(), [])
        p.entrada = b"help]\r\nok\r\n<Idle|MPos:0,0,0"
        self.assertEqual(tr.ler_linhas(), ["Grbl 1.1h ['$' for help]", "ok"])
        p.entrada = b"|FS:0,0>\r\n"
        self.assertEqual(tr.ler_linhas(), ["<Idle|MPos:0,0,0|FS:0,0>"])
        p.entrada = b"\xff" * 70000                     # velocidade errada: lixo sem quebra de linha
        self.assertEqual(tr.ler_linhas(), [])
        self.assertLessEqual(len(tr._buf), 4096)
        tr.escrever(b"$I\n")
        self.assertEqual(p.saida, b"$I\n")

    def test_tempo_esgotado_nao_derruba_a_conexao(self):
        """Espera de 0 s sem dados gera TimeoutError (12) no QSerialPort: não é perda de conexão."""
        p = PortaFalsa()
        p.clearError = lambda: None
        tr = TransporteSerial("COM4", porta_qt=p)
        tr.abrir()
        tr._erro(_Codigo("TimeoutError"))
        self.assertTrue(tr.aberto)
        tr.esperar(0.1)
        p.entrada = b"Grbl 1.1h ['$' for help]\r\n"
        self.assertEqual(tr.ler_linhas(), ["Grbl 1.1h ['$' for help]"])

    def test_cabo_removido(self):
        p = PortaFalsa()
        tr = TransporteSerial("COM9", porta_qt=p)
        tr.abrir()
        tr._erro(_Codigo("ResourceError"))
        self.assertFalse(tr.aberto)
        with self.assertRaises(TransporteErro):
            tr.escrever(b"?")
        with self.assertRaises(TransporteErro):
            tr.ler_linhas()


if __name__ == "__main__":
    unittest.main()
