"""Leitura das mensagens de um controlador GRBL (Etapa 13). Somente interpretação, sem E/S.

Tudo que vem da serial é dado não confiável: linhas longas são truncadas e campos inválidos ignorados.
"""
import re
from dataclasses import dataclass, field

MAX_LINHA = 512
_WELCOME = re.compile(r"^Grbl\s+(\S+)(.*)$")
_SETTING = re.compile(r"^\$(\d+)=([-+]?\d*\.?\d+)")


@dataclass(frozen=True)
class Status:
    estado: str                  # Idle, Run, Hold:0, Alarm, Door:1, Check, Home, Jog, Sleep…
    mpos: tuple = None           # posição de máquina (x, y, z) quando informada
    wpos: tuple = None           # posição de trabalho quando informada ($10=0)
    feed: float = None
    spindle: float = None
    campos: dict = field(default_factory=dict, compare=False)

    @property
    def em_alarme(self):
        return self.estado.startswith("Alarm")


def limpar(linha: str) -> str:
    return linha.strip()[:MAX_LINHA]


def boas_vindas(linha: str):
    """'Grbl 1.1h [...]' -> ('1.1h', resto); FluidNC também começa com 'Grbl'. None se não for."""
    m = _WELCOME.match(limpar(linha))
    return (m.group(1), m.group(2).strip()) if m else None


def _nums(s):
    try:
        return tuple(float(v) for v in s.split(","))
    except ValueError:
        return None


def status(linha: str):
    """'<Idle|MPos:0.000,0.000,0.000|FS:0,0>' -> Status; None se a linha não for um relatório."""
    s = limpar(linha)
    if not (s.startswith("<") and s.endswith(">")):
        return None
    partes = s[1:-1].split("|")
    if not partes or not partes[0]:
        return None
    campos = {}
    for p in partes[1:]:
        if ":" in p:
            k, v = p.split(":", 1)
            campos[k] = v
    fs = _nums(campos.get("FS", "")) or _nums(campos.get("F", "")) or ()
    return Status(partes[0], _nums(campos["MPos"]) if "MPos" in campos else None,
                  _nums(campos["WPos"]) if "WPos" in campos else None,
                  fs[0] if len(fs) > 0 else None, fs[1] if len(fs) > 1 else None, campos)


def configuracao(linha: str):
    """'$130=400.000' -> (130, 400.0); None se não for."""
    m = _SETTING.match(limpar(linha))
    return (int(m.group(1)), float(m.group(2))) if m else None


@dataclass
class MaquinaInfo:
    firmware: str = ""                 # ex.: "1.1h"
    detalhe: str = ""                  # resto da linha de boas-vindas
    versao: str = ""                   # [VER:…]
    opcoes: str = ""                   # [OPT:…]
    config: dict = field(default_factory=dict)

    def valor(self, n, padrao=None):
        return self.config.get(n, padrao)

    @property
    def area(self):
        if 130 in self.config and 131 in self.config:
            return self.config[130], self.config[131]
        return None

    def avisos(self) -> list:
        """Itens que impedem ou exigem cuidado antes de usar o G-code gerado (Etapa 11)."""
        out = []
        if not self.config:
            return ["Configurações ($$) não lidas."]
        if self.valor(32) != 1:
            out.append("Modo laser DESLIGADO ($32 ≠ 1): G0 não apaga o feixe. NÃO execute trabalhos assim.")
        if self.valor(30) not in (None, 1000):
            out.append(f"Potência máxima $30 = {self.valor(30):g} (o G-code atual assume 1000).")
        a = self.area
        if a and a != (400.0, 400.0):
            out.append(f"Área da máquina {a[0]:g} × {a[1]:g} mm difere da área demonstrativa 400 × 400 mm.")
        if self.valor(20) == 0:
            out.append("Limites por software desligados ($20 = 0): o controlador não barra movimentos fora da área.")
        return out

    def resumo(self) -> dict:
        nomes = {10: "relatorio_status", 20: "limites_software", 21: "limites_hardware", 22: "homing",
                 30: "potencia_max_S", 31: "potencia_min_S", 32: "modo_laser", 110: "vel_max_x_mm_min",
                 111: "vel_max_y_mm_min", 120: "acel_x_mm_s2", 121: "acel_y_mm_s2", 130: "curso_x_mm", 131: "curso_y_mm"}
        return {"firmware": self.firmware, "detalhe": self.detalhe, "versao": self.versao, "opcoes": self.opcoes,
                **{nome: self.config[n] for n, nome in nomes.items() if n in self.config},
                "configuracoes": {f"${k}": v for k, v in sorted(self.config.items())}}
