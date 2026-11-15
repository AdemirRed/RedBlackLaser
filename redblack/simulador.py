"""Simulador de controlador GRBL 1.1 (Etapa 12) — para testar comunicação SEM máquina.

Determinístico: não usa relógio real nem threads. O tempo só anda por `avancar(segundos)`.
Modelo baseado na documentação pública do GRBL 1.1 (interface, comandos, códigos de erro/alarme):
  - protocolo por linha: cada linha recebe "ok" ou "error:N";
  - comandos de tempo real de 1 byte, fora do buffer: "?" status, "!" pausa, "~" retoma,
    0x18 reset, 0x85 cancela jog;
  - buffer de recepção de 128 bytes e planejador de 15 blocos: o "ok" de um movimento só sai quando
    há espaço no planejador; bytes além de 128 são PERDIDOS (como numa serial real sem controle);
  - alarmes travam o G-code (error:9) até $X ou $H; reset durante movimento gera ALARM:3;
  - modo laser ($32=1): G0 apaga o feixe; com M3 e S>0 o laser fica LIGADO parado (risco de
    queimar se o envio parar) — o simulador mede esse tempo em `emissao_parada_s`; com M4 a potência
    cai a zero parado.
Limitações (diferenças do firmware real): sem aceleração (movimento a velocidade constante), pausa
instantânea, sem arcos G2/G3 (respondem error:20), sem portas/interruptores físicos. Uma linha que
dispara ALARM:2 (limite por software) recebe "ALARM:2" no lugar do "ok" — a sequência exata de
mensagens do firmware real nesse caso ainda precisa ser confirmada na máquina.
"""
import math
import re
from collections import deque
from dataclasses import dataclass

VERSAO = "1.1h"
BOAS_VINDAS = f"Grbl {VERSAO} ['$' for help]"
RX_BYTES = 128
PLANNER_BLOCOS = 15
MAX_LINHA = 80
TEMPO_REAL = {ord("?"), ord("!"), ord("~"), 0x18, 0x85}

CONFIG_PADRAO = {  # valores típicos de GRBL; NÃO são os da SCULPFUN (serão lidos na Etapa 13)
    0: 10, 1: 25, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 10: 1, 11: 0.010, 12: 0.002, 13: 0, 20: 0, 21: 0,
    22: 0, 23: 0, 24: 25.0, 25: 3000.0, 26: 250, 27: 1.0, 30: 1000, 31: 0, 32: 1,
    100: 80.0, 101: 80.0, 102: 80.0, 110: 6000.0, 111: 6000.0, 112: 500.0,
    120: 1000.0, 121: 1000.0, 122: 10.0, 130: 400.0, 131: 400.0, 132: 1.0,
}


@dataclass(frozen=True)
class Segmento:
    """Movimento executado (completo ou interrompido), em mm de máquina."""
    origem: tuple
    destino: tuple
    rapido: bool
    potencia: float   # S efetivo durante o movimento (0 = apagado)

    @property
    def comprimento(self):
        return math.hypot(self.destino[0] - self.origem[0], self.destino[1] - self.origem[1])


@dataclass
class _Bloco:
    destino: tuple
    feed: float          # mm/min
    rapido: bool
    potencia: float
    jog: bool = False
    feito: float = 0.0   # mm já percorridos

    def comprimento(self, de):
        return math.hypot(self.destino[0] - de[0], self.destino[1] - de[1])


class SimuladorGrbl:
    def __init__(self, config=None):
        self.config = dict(CONFIG_PADRAO)
        self.config.update(config or {})
        self.conectado = True
        self.saida = []                 # linhas enviadas ao "computador"
        self.trilha = []                # Segmentos executados
        self.estouros = 0               # bytes perdidos por estouro do buffer de recepção
        self.emissao_parada_s = 0.0     # tempo com laser ligado sem movimento (risco)
        self.tempo = 0.0                # relógio virtual (s)
        self.linhas_recebidas = 0
        self._boot()

    # ---------- inicialização ----------
    def _boot(self, alarme=None):
        self.rx = bytearray()
        self.planner = deque()
        self.pos = (0.0, 0.0)
        self.absoluto, self.mm = True, True
        self.motion_modal = 0  # G0 no início, como o GRBL
        self.feed = None
        self.s = 0.0
        self.spindle = "M5"
        self.ar, self._ar_mudou = False, False  # M8 (air assist); o reset desliga
        self.hold = False
        self.check = False
        self.homing_restante = None
        if alarme:
            self.saida.append(f"ALARM:{alarme}")
        self.saida.append(BOAS_VINDAS)
        if alarme or self.config[22]:  # homing habilitado: GRBL inicia travado até $H/$X
            self.estado_base = "Alarm"
            self.saida.append("[MSG:'$H'|'$X' to unlock]")
        else:
            self.estado_base = "Idle"

    # ---------- entrada ----------
    def receber(self, data: bytes):
        if not self.conectado:
            raise ConnectionError("simulador desconectado")
        for b in data:
            if b in TEMPO_REAL:
                self._tempo_real(b)
            elif len(self.rx) >= RX_BYTES:
                self.estouros += 1      # perdido, como numa serial real
            else:
                self.rx.append(b)
                if b == ord("\n"):
                    self._processar_rx()  # o GRBL consome cada linha assim que ela chega

    def _tempo_real(self, b):
        if b == ord("?"):
            self.saida.append(self.status())
        elif b == ord("!"):
            if self.planner and self.estado_base != "Alarm":
                self.hold = True
        elif b == ord("~"):
            self.hold = False
        elif b == 0x18:
            em_movimento = bool(self.planner) or self.homing_restante is not None
            self._boot(alarme=3 if em_movimento else None)
        elif b == 0x85:
            if self.planner and self.planner[0].jog:
                self.planner.clear()
                self.hold = False

    def _processar_rx(self):
        while b"\n" in self.rx:
            if self.homing_restante is not None:
                return  # durante o homing nada é processado
            idx = self.rx.index(b"\n")
            raw = self.rx[:idx].decode("ascii", "replace").strip()
            up = raw.split(";", 1)[0].upper().replace(" ", "")
            # Qualquer linha com X/Y pode virar bloco (movimento modal sem G0/G1 explícito).
            movimento = up.startswith("$J=") or (not up.startswith("$") and re.search(r"[XY]", up) is not None)
            if movimento and len(self.planner) >= PLANNER_BLOCOS:
                return  # planejador cheio: a linha espera; o "ok" sai quando houver espaço
            del self.rx[:idx + 1]
            self.linhas_recebidas += 1
            self.saida.append(self._linha(raw))

    # ---------- interpretação ----------
    def _linha(self, raw: str) -> str:
        line = raw.split(";", 1)[0]
        line = re.sub(r"\(.*?\)", "", line).replace(" ", "").upper()
        if len(raw) > MAX_LINHA:
            return "error:11"
        if not line:
            return "ok"
        if line.startswith("$"):
            return self._sistema(line)
        if self.estado_base == "Alarm":
            return "error:9"
        return self._gcode(line)

    def _sistema(self, line):
        if line == "$$":
            self.saida += [f"${k}={v:g}" if isinstance(v, float) else f"${k}={v}" for k, v in sorted(self.config.items())]
            return "ok"
        if line == "$I":
            self.saida += [f"[VER:{VERSAO}.20190825:]", f"[OPT:V,{PLANNER_BLOCOS},{RX_BYTES}]"]
            return "ok"
        if line == "$G":
            self.saida.append(f"[GC:{'G0'} G54 G17 {'G21' if self.mm else 'G20'} {'G90' if self.absoluto else 'G91'} "
                              f"G94 {self.spindle} M9 T0 F{self.feed or 0:g} S{self.s:g}]")
            return "ok"
        if line == "$X":
            if self.estado_base == "Alarm":
                self.estado_base = "Idle"
                self.saida.append("[MSG:Caution: Unlocked]")
            return "ok"
        if line == "$C":
            self.check = not self.check
            self.saida.append("[MSG:Enabled]" if self.check else "[MSG:Disabled]")
            return "ok"
        if line == "$H":
            if not self.config[22]:
                return "error:5"
            dist = math.hypot(*self.pos)
            self.homing_restante = dist / (self.config[25] / 60) if dist else 0.0
            self._concluir_homing_se_pronto()  # o "ok" sai quando o homing termina
            return ""
        if line.startswith("$J="):
            if self.estado_base == "Alarm":
                return "error:9"  # como o GRBL: em alarme o jog também é recusado ($X ou $H libera)
            return self._gcode(line[3:], jog=True)
        m = re.fullmatch(r"\$(\d+)=([-+]?\d*\.?\d+)", line)
        if m:
            k = int(m.group(1))
            if k not in self.config:
                return "error:3"
            v = float(m.group(2))
            self.config[k] = int(v) if float(v).is_integer() and isinstance(self.config[k], int) else v
            return "ok"
        return "error:3"

    def _gcode(self, line, jog=False):
        g10 = re.fullmatch(r"G10L(2|20)P1X(-?[\d.]+)Y(-?[\d.]+)", line)
        if g10 and not jog:  # origem do trabalho (G54): L2 = valor do deslocamento, L20 = "aqui vale X,Y"
            x, y = float(g10.group(2)), float(g10.group(3))
            self.wco = (x, y) if g10.group(1) == "2" else (self.pos[0] - x, self.pos[1] - y)
            self._wco_mudou = True  # como o GRBL: o próximo status traz o WCO novo
            return "ok"
        words = re.findall(r"([A-Z])([^A-Z]*)", line)
        if not words or "".join(a + b for a, b in words) != line:
            return "error:1"
        vals = {}
        motion = None
        absoluto, mm = self.absoluto, self.mm
        for letra, num in words:
            try:
                v = float(num)
            except ValueError:
                return "error:2"
            if letra == "G":
                g = int(v) if v.is_integer() else v
                if g in (0, 1):
                    motion = g
                elif g in (90, 91):
                    absoluto = g == 90
                elif g in (20, 21):
                    mm = g == 21
                elif g in (17, 54, 94):
                    pass
                else:
                    return "error:20"  # inclui G2/G3: não simulados
            elif letra == "M":
                m = int(v)
                if m in (3, 4, 5) and not jog:
                    vals["spindle"] = f"M{m}"
                elif m in (2, 30) and not jog:
                    vals["fim"] = True
                elif m in (8, 9) and not jog:
                    vals["ar"] = m == 8
                else:
                    return "error:20"
            elif letra in "XYZFS":
                vals[letra] = v
            else:
                return "error:20"
        escala = 1.0 if mm else 25.4
        if jog:
            # $J=: exige F; não aceita G0/G1; G90/G91/G20/G21 valem só para este jog.
            if motion is not None or "F" not in vals or "S" in vals or "spindle" in vals:
                return "error:16"
            return self._mover(1, vals, escala, absoluto, jog=True)
        # Linha com erro é descartada inteira: valida ANTES de mudar qualquer estado modal.
        movimento = motion if motion is not None else self.motion_modal
        feed = vals["F"] * escala if "F" in vals else self.feed
        if ("X" in vals or "Y" in vals) and movimento == 1 and feed is None:
            return "error:22"
        self.absoluto, self.mm = absoluto, mm
        if "F" in vals:
            self.feed = vals["F"] * escala
        if "S" in vals:
            self.s = max(0.0, min(vals["S"], float(self.config[30])))
        if "spindle" in vals:
            self.spindle = vals["spindle"]
        if "ar" in vals:
            self._ar_mudou = self._ar_mudou or self.ar != vals["ar"]
            self.ar = vals["ar"]
        if vals.get("fim"):
            self.ar = False
            self.spindle, self.absoluto, self.mm = "M5", True, True
        if motion is not None:
            self.motion_modal = motion
        if "X" not in vals and "Y" not in vals:
            return "ok"  # só estado modal
        return self._mover(self.motion_modal, vals, escala, self.absoluto)

    def _mover(self, motion, vals, escala, absoluto, jog=False):
        base = self.planner[-1].destino if self.planner else self.pos
        if absoluto:  # coordenadas do trabalho (G54) -> máquina
            wx, wy = getattr(self, "wco", (0.0, 0.0))
            destino = (vals["X"] * escala + wx if "X" in vals else base[0],
                       vals["Y"] * escala + wy if "Y" in vals else base[1])
        else:
            destino = (base[0] + vals.get("X", 0.0) * escala, base[1] + vals.get("Y", 0.0) * escala)
        rapido = motion == 0
        feed = self.config[110] if rapido else (vals["F"] * escala if jog else self.feed)
        if feed is None:
            return "error:22"
        if self.config[20] and not self._dentro(destino):
            if jog:
                return "error:15"
            self._alarme(2)
            return "ALARM:2"
        if self.check:
            return "ok"  # modo de verificação: interpreta, não move
        if self.spindle == "M5" or (rapido and self.config[32]):
            pot = 0.0
        else:
            pot = self.s
        self.planner.append(_Bloco(destino, min(feed, self.config[110]), rapido, pot, jog))
        return "ok"

    def _dentro(self, p):
        return -1e-9 <= p[0] <= self.config[130] + 1e-9 and -1e-9 <= p[1] <= self.config[131] + 1e-9

    def _alarme(self, code):
        self.planner.clear()
        self.rx.clear()
        self.hold = False
        self.estado_base = "Alarm"
        self.spindle = "M5"

    # ---------- tempo ----------
    def avancar(self, segundos: float):
        """Executa movimento por `segundos` de tempo virtual."""
        if not self.conectado:
            return
        restante = segundos
        while restante > 1e-12:
            if self.homing_restante is not None:
                passo = min(restante, self.homing_restante)
                self.homing_restante -= passo
                restante -= passo
                self.tempo += passo
                self._concluir_homing_se_pronto()
                continue
            if not self.planner or self.hold:
                if not self.hold and not self.check and self.spindle == "M3" and self.s > 0 \
                        and self.config[32] and self.estado_base != "Alarm":
                    self.emissao_parada_s += restante  # M3: laser ligado parado
                self.tempo += restante
                break
            b = self.planner[0]
            total = b.comprimento(self.pos) + b.feito
            falta = total - b.feito
            v = b.feed / 60.0
            dt = falta / v if v > 0 else 0.0
            if dt <= restante + 1e-12:
                self.trilha.append(Segmento(self.pos, b.destino, b.rapido, b.potencia))
                self.pos = b.destino
                self.planner.popleft()
                restante -= dt
                self.tempo += dt
                self._processar_rx()
            else:
                frac = restante * v / b.comprimento(self.pos)
                novo = (self.pos[0] + (b.destino[0] - self.pos[0]) * frac,
                        self.pos[1] + (b.destino[1] - self.pos[1]) * frac)
                self.trilha.append(Segmento(self.pos, novo, b.rapido, b.potencia))
                self.pos = novo
                self.tempo += restante
                restante = 0

    def _concluir_homing_se_pronto(self):
        if self.homing_restante is not None and self.homing_restante <= 1e-12:
            self.homing_restante = None
            self.pos = (0.0, 0.0)
            self.estado_base = "Idle"
            self.saida.append("ok")
            self._processar_rx()

    # ---------- consulta ----------
    @property
    def estado(self) -> str:
        if self.homing_restante is not None:
            return "Home"
        if self.estado_base == "Alarm":
            return "Alarm"
        if self.check:
            return "Check"
        if self.hold:
            return "Hold:0"
        if self.planner:
            return "Jog" if self.planner[0].jog else "Run"
        return "Idle"

    @property
    def emitindo(self) -> bool:
        """Laser emitindo agora (movimento com potência, ou M3 com S>0 parado)."""
        if self.estado in ("Alarm", "Hold:0", "Home", "Check"):
            return False
        if self.planner:
            return self.planner[0].potencia > 0
        return self.spindle == "M3" and self.s > 0 and bool(self.config[32])

    def status(self) -> str:
        feed = 0 if not self.planner or self.hold else self.planner[0].feed
        wx, wy = getattr(self, "wco", (0.0, 0.0))
        return (f"<{self.estado}|MPos:{self.pos[0]:.3f},{self.pos[1]:.3f},0.000|"
                f"FS:{feed:g},{self.s if self.spindle != 'M5' else 0:g}|"
                f"Bf:{PLANNER_BLOCOS - len(self.planner)},{RX_BYTES - len(self.rx)}"
                + ("|Ov:100,100,100|A:F" if self.ar else "|Ov:100,100,100" if self._ar_avisar() else "")
                + (f"|WCO:{wx:.3f},{wy:.3f},0.000" if (wx, wy) != (0.0, 0.0) or self._wco_avisar() else "") + ">")

    def _ar_avisar(self):  # como o GRBL: "Ov:" sem "A:" no relatório seguinte = acessórios desligados
        mudou, self._ar_mudou = getattr(self, "_ar_mudou", False), False
        return mudou

    def _wco_avisar(self):
        mudou, self._wco_mudou = getattr(self, "_wco_mudou", False), False
        return mudou

    def ler(self) -> list:
        out, self.saida = self.saida, []
        return [ln for ln in out if ln != ""]

    def comprimento_com_laser(self) -> float:
        return sum(s.comprimento for s in self.trilha if s.potencia > 0)

    # ---------- conexão ----------
    def desconectar(self):
        """Cabo removido: tudo que estava no buffer é perdido; nada é retomado depois."""
        self.conectado = False
        self.planner.clear()
        self.rx.clear()
        self.saida.clear()  # respostas ainda não lidas se perdem com o cabo

    def reconectar(self):
        """Nova conexão = controlador reiniciado (como uma placa GRBL ao abrir a porta)."""
        self.conectado = True
        self._boot()
