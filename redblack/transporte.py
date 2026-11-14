"""Transporte (Etapa 12): interface única para falar com o controlador.

A implementação simulada é usada em testes e no modo demonstrativo; a serial real (Etapa 13)
seguirá a mesma interface, para que o restante do programa não precise saber qual está em uso.
"""


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
    """Porta serial real via QtSerialPort (8N1, sem controle de fluxo), não bloqueante.

    `porta_qt` permite injetar um objeto equivalente nos testes.
    """

    def __init__(self, porta: str, baud: int = 115200, porta_qt=None):
        self.porta, self.baud = porta, baud
        self.nome = f"{porta} @ {baud}"
        self._p = porta_qt
        self._buf = b""
        self._perdida = None

    @property
    def aberto(self) -> bool:
        return self._p is not None and self._p.isOpen() and self._perdida is None

    def abrir(self):
        from PySide6.QtCore import QIODevice
        if self._p is None:
            from PySide6.QtSerialPort import QSerialPort  # importado só ao conectar
            p = QSerialPort()
            p.setPortName(self.porta)
            p.setBaudRate(self.baud)
            p.setDataBits(QSerialPort.Data8)
            p.setParity(QSerialPort.NoParity)
            p.setStopBits(QSerialPort.OneStop)
            p.setFlowControl(QSerialPort.NoFlowControl)
            p.errorOccurred.connect(self._erro)
            self._p = p
        if not self._p.isOpen() and not self._p.open(QIODevice.ReadWrite):
            raise TransporteErro(self._p.errorString())
        self._buf, self._perdida = b"", None

    # Erros do QSerialPort que tornam a porta inutilizável (comparados pelo NOME: a numeração mudou do Qt 5 para o
    # Qt 6 — no Qt 6 TimeoutError = 9, que no Qt 5 era o ResourceError). TimeoutError NÃO é perda: é só "nada
    # chegou ainda" (acontece em toda espera curta, ex.: placa ainda iniciando) — antes isso derrubava a conexão.
    FATAIS = ("DeviceNotFoundError", "PermissionError", "OpenError", "WriteError", "ReadError", "ResourceError",
              "NotOpenError")

    @staticmethod
    def _nome_erro(code):
        nome = getattr(code, "name", None)
        if nome:
            return nome
        try:
            from PySide6.QtSerialPort import QSerialPort
            return QSerialPort.SerialPortError(int(code)).name
        except Exception:  # sem QtSerialPort (testes): número desconhecido = trata como perda
            return "UnknownError" if int(code) else "NoError"

    def _erro(self, code):
        nome = self._nome_erro(code)
        if nome in self.FATAIS:
            self._perdida = self._p.errorString() if self._p else nome
        elif nome != "NoError" and self._p is not None and hasattr(self._p, "clearError"):
            self._p.clearError()  # aviso sem importância (ex.: tempo esgotado numa espera de 0 s)

    def fechar(self):
        if self._p is not None and self._p.isOpen():
            self._p.close()

    def escrever(self, data: bytes):
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")
        if self._p.write(data) != len(data):
            raise TransporteErro("Falha ao escrever na porta.")
        self._p.flush()

    def ler_linhas(self) -> list:
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")
        self._buf += bytes(self._p.readAll())
        if len(self._buf) > 65536:  # lixo sem quebra de linha (velocidade errada?): descarta
            self._buf = self._buf[-4096:]
        *linhas, self._buf = self._buf.split(b"\n")
        return [ln.decode("ascii", "replace").rstrip("\r") for ln in linhas]

    def esperar(self, segundos: float):
        """Na serial o tempo é real; só verifica se chegou algo, sem bloquear a interface."""
        if not self.aberto:
            raise TransporteErro(self._perdida or "Porta fechada.")
        self._p.waitForReadyRead(0)


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
