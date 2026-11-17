"""Etapa 13: conexão e identificação sem executar trabalho nem emitir laser (validado no simulador)."""
import os
import sys
import time
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
        antes = c.n_log
        for i in range(2000):
            c._evento(f"e{i}")
        self.assertLessEqual(len(c.log), 600)  # corta para 500 quando passa de 600
        self.assertEqual(c.n_log - antes, 2000)  # a interface conta pelo total (mostra as novas mesmo depois do corte)
        self.assertEqual(c.log[-1][1], "e1999")


class PortaFalsa:
    """Imita serial.Serial (pyserial) para testar o transporte sem tocar em portas reais."""

    def __init__(self):
        self.is_open, self.entrada, self.saida, self.quebrar = False, b"", b"", False

    def open(self): self.is_open = True
    def close(self): self.is_open = False
    def write(self, data): self.saida += bytes(data); return len(data)

    @property
    def in_waiting(self): return len(self.entrada)

    def read(self, n):
        if self.quebrar:
            raise OSError("O dispositivo não reconhece o comando")  # cabo removido
        if not self.entrada:
            time.sleep(0.005)
            return b""
        d, self.entrada = self.entrada[:n], self.entrada[n:]
        return d


def esperar(cond, s=2.0):
    fim = time.monotonic() + s
    while time.monotonic() < fim and not cond():
        time.sleep(0.005)
    return cond()


class TransporteSerialTest(unittest.TestCase):
    def test_linhas_partidas_crlf_e_lixo(self):
        p = PortaFalsa()
        tr = TransporteSerial("COM9", porta_serial=p)
        tr.abrir()
        try:
            tr.entrada(b"Grbl 1.1h ['$' for ")
            self.assertEqual(tr.ler_linhas(), [])
            tr.entrada(b"help]\r\nok\r\n<Idle|MPos:0,0,0")
            self.assertEqual(tr.ler_linhas(), ["Grbl 1.1h ['$' for help]", "ok"])
            tr.entrada(b"|FS:0,0>\r\n")
            self.assertEqual(tr.ler_linhas(), ["<Idle|MPos:0,0,0|FS:0,0>"])
            tr.entrada(b"\xff" * 70000)                     # velocidade errada: lixo sem quebra de linha
            self.assertEqual(tr.ler_linhas(), [])
            self.assertLessEqual(len(tr._buf), 4096)
            tr.escrever(b"$I\n")
            self.assertEqual(p.saida, b"$I\n")
        finally:
            tr.fechar()

    def test_thread_entrega_cada_linha_na_hora(self):
        """O "ok" chega pela thread da serial e vai direto para quem trata (como o LaserGRBL), sem esperar a tela."""
        p = PortaFalsa()
        tr = TransporteSerial("COM4", porta_serial=p)
        recebidas = []
        tr.ao_linha = recebidas.append
        tr.abrir()
        try:
            p.entrada = b"ok\r\nok\r\nerror:20\r\n"
            self.assertTrue(esperar(lambda: len(recebidas) == 3))
            self.assertEqual(recebidas, ["ok", "ok", "error:20"])
            self.assertEqual(tr.ler_linhas(), [])  # já foram entregues
        finally:
            tr.fechar()

    def test_cabo_removido(self):
        p = PortaFalsa()
        tr = TransporteSerial("COM9", porta_serial=p)
        tr.abrir()
        p.quebrar = True
        self.assertTrue(esperar(lambda: not tr.aberto))
        with self.assertRaises(TransporteErro):
            tr.escrever(b"?")
        with self.assertRaises(TransporteErro):
            tr.ler_linhas()
        tr.fechar()

    def test_porta_que_nao_abre(self):
        class NaoAbre(PortaFalsa):
            def open(self):
                raise OSError("could not open port 'COM99': Acesso negado")
        with self.assertRaises(TransporteErro):
            TransporteSerial("COM99", porta_serial=NaoAbre()).abrir()


class GrblFalso(PortaFalsa):
    """Responde "ok" a cada linha recebida (como o GRBL quando o planejador aceita a linha)."""

    def write(self, data):
        super().write(data)
        self.entrada += b"ok\r\n" * bytes(data).count(b"\n")
        return len(data)


class TelaOcupadaTest(unittest.TestCase):
    def test_trabalho_continua_com_a_tela_parada(self):
        """O bug das travadas: com a interface ocupada (mesa redesenhando), o "ok" esperava e a máquina parava. Com a
        thread da serial, o trabalho inteiro vai sem a interface chamar tick() nenhuma vez."""
        p = GrblFalso()
        tr = TransporteSerial("COM4", porta_serial=p)
        c = cx.Conexao(tr)
        tr.ao_linha = c.chegou
        tr.abrir()
        try:
            c.estado, c.controle = cx.CONECTADO, True
            linhas = [f"G1 X{k % 50}.25 Y{k % 7}.5 S100 F3000" for k in range(400)]
            c.iniciar_trabalho("\n".join(linhas) + "\n")
            c._alimentar_trabalho()  # o 1º lote sai pela interface; o resto, só pela thread
            time.sleep(0.5)  # "tela ocupada": ninguém chama tick()
            self.assertTrue(esperar(lambda: c.trabalho_ok == 400, 3.0), c.trabalho_ok)
            self.assertEqual(p.saida.count(b"\n"), 400)
        finally:
            tr.fechar()


class ChegouTest(unittest.TestCase):
    def test_ok_da_thread_manda_a_proxima_linha_e_nao_enche_o_registro(self):
        _sim, tr, c = conectar()
        c.habilitar_controle(True)
        linhas = [f"G1 X{k % 50} Y{k % 7} S100 F3000" for k in range(200)]
        c.iniciar_trabalho("\n".join(linhas) + "\n")
        c._alimentar_trabalho()
        enviadas = len(tr.escrito)
        no_registro = c.n_log
        for _ in range(3):
            c.chegou("ok")  # como a thread da serial faria
        self.assertGreater(len(tr.escrito), enviadas)  # mandou mais linhas na hora
        self.assertEqual(c.n_log, no_registro)  # "ok" do trabalho não vai para o registro


if __name__ == "__main__":
    unittest.main()
