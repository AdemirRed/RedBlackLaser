"""Transporte (Etapa 12): interface única para falar com o controlador.

A implementação simulada é usada em testes e no modo demonstrativo; a serial real (Etapa 13)
seguirá a mesma interface, para que o restante do programa não precise saber qual está em uso.
"""


import threading
from collections import deque


class TransporteErro(Exception):
    """Falha de comunicação (porta fechada, cabo removido…)."""


def listar_portas() -> list:
    """[(nome, descrição)] das portas seriais do sistema. Não abre nenhuma."""
    from PySide6.QtSerialPort import QSerialPortInfo  # importado só quando o usuário pede
    out = []
    for p in QSerialPortInfo.availablePorts():
        desc = p.description() or "porta serial"
        if p.hasVendorIdentifier():
            desc += f" (USB {p.vendorIdentifier():04X}:{p.productIdentifier():04X})"
        out.append((p.portName(), desc))
    return out


class TransporteSerial:
    """Porta serial real (pyserial, 8N1, sem controle de fluxo) com uma THREAD SÓ PARA LER, como o LaserGRBL.

    Antes a leitura dependia da interface (QSerialPort na thread da tela): enquanto a mesa era redesenhada (a mira
    andando, projeto pesado) o "ok" do GRBL esperava, o buffer de 127 bytes esvaziava e a máquina PARAVA no meio da
    linha — marca/furinho na peça. Agora cada linha que chega vai na hora para `ao_linha` (chamado NA THREAD de
    leitura; quem usa trata com trava), que já manda a próxima linha do trabalho. Sem `ao_linha`, as linhas ficam
    na fila de `ler_linhas()`. `porta_serial` permite injetar um objeto equivalente a serial.Serial nos testes.
    """

    def __init__(self, porta: str, baud: int = 115200, porta_serial=None):
        self.porta, self.baud = porta, baud
        self.nome = f"{porta} @ {baud}"
        self._s = porta_serial
        self._buf = b""
        self._fila = deque()
        self._perdida = None
        self.ao_linha = None
        self._escrita = threading.Lock()
        self._parar = threading.Event()
        self._thread = None

    @property
    def aberto(self) -> bool:
        return self._s is not None and self._s.is_open and self._perdida is None

    def abrir(self):
        if self._s is None:
            import serial  # pyserial: importado só ao conectar
            self._s = serial.Serial()
            self._s.port, self._s.baudrate = self.porta, self.baud
            self._s.timeout, self._s.write_timeout = 0.02, 2.0
        if not self._s.is_open:
            try:
                self._s.open()
            except Exception as e:  # SerialException: porta inexistente, em uso, sem permissão
                raise TransporteErro(str(e)) from e
        self._buf, self._perdida = b"", None
        self._fila.clear()
        self._parar.clear()
        self._thread = threading.Thread(target=self._ler, name=f"serial {self.porta}", daemon=True)
        self._thread.start()

    def _ler(self):
        while not self._parar.is_set():
            try:
                dados = self._s.read(self._s.in_waiting or 1)  # espera até 20 ms por 1 byte
            except Exception as e:  # cabo removido, placa desligada
                if not self._parar.is_set():
                    self._perdida = str(e) or "Conexão perdida."
                return
            if dados:
                self.entrada(dados)

    def entrada(self, dados: bytes):
        """Bytes recebidos -> linhas completas (para `ao_linha` ou para a fila)."""
        self._buf += dados
        if len(self._buf) > 65536:  # lixo sem quebra de linha (velocidade errada?): descarta
            self._buf = self._buf[-4096:]
        *linhas, self._buf = self._buf.split(b"\n")
        for ln in linhas:
            texto = ln.decode("ascii", "replace").rstrip("\r")
            if self.ao_linha is not None:
                try:
                    self.ao_linha(texto)
                except TransporteErro as e:
                    self._perdida = str(e)
            else:
                self._fila.append(texto)

    def fechar(self):
        self._parar.set()
        if self._s is not None and self._s.is_open:
            self._s.close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.3)  # pode estar esperando a trava de quem fecha: sai sozinha depois

    def escrever(self, data: bytes):
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")
        try:
            with self._escrita:
                self._s.write(data)
        except Exception as e:
            self._perdida = str(e) or "Falha ao escrever na porta."
            raise TransporteErro(self._perdida) from e

    def ler_linhas(self) -> list:
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")
        out = []
        while self._fila:
            out.append(self._fila.popleft())
        return out

    def esperar(self, segundos: float):
        """Na serial o tempo é real e a leitura é na thread própria: só confere se a porta continua viva."""
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")


class TransporteSimulado:
    """Liga o programa a um SimuladorGrbl em memória."""

    nome = "Simulador GRBL (nenhuma máquina conectada)"

    def __init__(self, simulador):
        self.sim = simulador
        self._aberto = False

    @property
    def aberto(self) -> bool:
        return self._aberto and self.sim.conectado

    def abrir(self):
        if not self.sim.conectado:
            self.sim.reconectar()  # abrir de novo = controlador reiniciado, nada é retomado
        self._aberto = True

    def fechar(self):
        self._aberto = False

    def escrever(self, data: bytes):
        if not self.aberto:
            raise TransporteErro("Porta fechada ou controlador desconectado.")
        self.sim.receber(data)

    def ler_linhas(self) -> list:
        if not self.aberto:
            raise TransporteErro("Porta fechada ou controlador desconectado.")
        return self.sim.ler()

    def esperar(self, segundos: float):
        """Deixa o tempo (virtual) passar; na serial real será o tempo do relógio."""
        if not self.aberto:
            raise TransporteErro("Porta fechada ou controlador desconectado.")
        self.sim.avancar(segundos)
