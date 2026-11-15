"""Biblioteca de materiais: parâmetros iniciais por material para aplicar numa camada.

Os valores de referência abaixo NÃO são validados: vêm de uma tabela de teste publicada por revendedor
para a SCULPFUN S30 Pro Max 20 W (máquina ainda não disponível para teste) e o próprio texto da tabela diz
que são "para referência" e precisam de ajuste. Servem de ponto de partida para a matriz de testes.
Presets do usuário ("meus") são guardados nas configurações e marcados como tal.
"""
import json
from dataclasses import asdict, dataclass, fields, replace

from . import camadas as cm

MAQUINA = "SCULPFUN S30 Pro Max 20 W"
FONTE = "tabela de teste do revendedor GeekBuying (2026-11-08), \"para referência\" — ver docs/MAQUINA.md."
# URL: https://www.geekbuying.com/item/SCULPFUN-S30-Pro-Max-20W-Laser-Engraver-Cutter-517193.html
INTERVALO_SUGERIDO = 0.1  # mm entre linhas de gravação: NÃO consta na tabela, é suposição


@dataclass(frozen=True)
class Material:
    nome: str
    espessura_mm: float          # 0 = gravação de superfície
    operacao: str                # "corte" | "gravação"
    velocidade_mm_min: float
    potencia_max: float          # %
    passadas: int = 1
    air: bool = False
    intervalo_mm: float = INTERVALO_SUGERIDO
    nota: str = ""
    origem: str = "referência"   # "referência" (não validado) | "meu" (cadastrado pelo usuário)

    @property
    def modo(self) -> str:
        return "linha" if self.operacao == "corte" else "preenchimento"

    def rotulo(self) -> str:
        esp = f" {self.espessura_mm:g} mm".replace(".", ",") if self.espessura_mm else ""
        marca = "" if self.origem == "meu" else " — não validado"
        return f"{'[Meu] ' if self.origem == 'meu' else ''}{self.nome}{esp} · {self.operacao}{marca}"

    def campos_camada(self, modo_atual: str) -> dict:
        """Campos para cm.alterar. Camada de imagem continua imagem (só gravação se aplica a ela)."""
        modo = modo_atual if modo_atual == "imagem" else self.modo
        return {"modo": modo, "velocidade_mm_min": self.velocidade_mm_min, "potencia_max": self.potencia_max,
                "potencia_min": 0.0, "passadas": self.passadas, "air": self.air, "intervalo_mm": self.intervalo_mm}


_ACR = "Só acrílico escuro/opaco: o acrílico transparente quase não absorve a luz azul do diodo."
_GRAV = "Intervalo 0,1 mm é sugestão do RedBlack (a tabela não informa)."

REFERENCIA_S30_PRO_MAX_20W = (
    Material("Compensado", 3, "corte", 780, 100, 1, True),
    Material("Compensado", 6, "corte", 360, 100, 1, True),
    Material("Compensado", 10, "corte", 300, 100, 2, True),
    Material("Compensado", 0, "gravação", 3000, 20, nota=_GRAV),
    Material("Basswood (tília)", 3, "corte", 600, 100, 1, True),
    Material("Basswood (tília)", 6, "corte", 300, 100, 2, True),
    Material("Paulownia (tung) / cortiça", 10, "corte", 300, 100, 2, True),
    Material("Paulownia (tung) / cortiça", 15, "corte", 180, 100, 1, True,
             nota="Tabela indica 1 passada (10 mm pede 2): conferir com teste."),
    Material("Paulownia (tung) / cortiça", 20, "corte", 180, 100, 3, True),
    Material("Acrílico preto", 6, "corte", 300, 100, 3, True, nota=_ACR),
    Material("Acrílico preto", 11, "corte", 180, 100, 6, True, nota=_ACR),
    Material("MDF", 3.6, "corte", 300, 100, 1, True),
    Material("MDF", 0, "gravação", 3000, 18, nota=_GRAV),
    Material("Aço inox", 0, "gravação", 900, 100,
             nota="Marcação de superfície; o diodo não corta metal. " + _GRAV),
    Material("Papel kraft", 0, "gravação", 1800, 15, nota=_GRAV),
    Material("Couro", 0, "gravação", 1800, 15, nota=_GRAV),
)


# Predefinições da RedBlack (aparecem no topo, valem em qualquer PC; um material seu com o mesmo nome,
# espessura e operação substitui a predefinição).
PREDEFINIDOS_REDBLACK = (
    Material("MDF", 3, "corte", 650, 85, 2, True, nota="Predefinição RedBlack: 650 mm/min, 85 %, 2 passadas.",
             origem="meu"),
    Material("MDF", 6, "corte", 600, 85, 5, True, nota="Predefinição RedBlack: 600 mm/min, 85 %, 5 passadas.",
             origem="meu"),
)


def corte_mdf(espessura_mm: float) -> dict:
    """Campos de camada (cm.alterar) do corte de MDF da RedBlack nessa espessura; geradores de projeto usam isto."""
    m = next(m for m in PREDEFINIDOS_REDBLACK
             if (m.nome, m.espessura_mm, m.operacao) == ("MDF", espessura_mm, "corte"))
    return m.campos_camada("linha")


def erros(m: Material) -> list:
    out = []
    if not isinstance(m.nome, str) or not m.nome.strip() or len(m.nome) > 80:
        out.append("nome inválido")
    if m.operacao not in ("corte", "gravação"):
        out.append("operação inválida")
    if m.origem not in ("referência", "meu"):
        out.append("origem inválida")
    if isinstance(m.espessura_mm, bool) or not isinstance(m.espessura_mm, (int, float)) or not 0 <= m.espessura_mm <= 100:
        out.append("espessura inválida")
    if not out:  # faixas iguais às da camada
        out += cm.validar(cm.Camada("C01", "x", m.modo, m.velocidade_mm_min, m.potencia_max, 0.0, m.passadas,
                                    m.intervalo_mm, air=m.air))
    return out


def do_camada(c: cm.Camada, nome: str, espessura_mm: float, nota="") -> Material:
    """Preset do usuário a partir dos parâmetros atuais de uma camada."""
    m = Material(nome.strip()[:80], espessura_mm, "corte" if c.modo == "linha" else "gravação",
                 c.velocidade_mm_min, c.potencia_max, c.passadas, c.air, c.intervalo_mm, nota, "meu")
    e = erros(m)
    if e:
        raise ValueError("; ".join(e))
    return m


CHAVE = "materiais_meus"  # QSettings


def meus(settings) -> list:
    """Presets do usuário; entradas corrompidas são ignoradas."""
    try:
        bruto = json.loads(settings.value(CHAVE, "[]") or "[]")
    except (TypeError, ValueError):
        return []
    nomes = {f.name for f in fields(Material)}
    out = []
    for d in bruto if isinstance(bruto, list) else ():
        if isinstance(d, dict) and set(d) == nomes:
            try:
                m = replace(Material(**d), origem="meu")
            except TypeError:
                continue
            if not erros(m):
                out.append(m)
    return out


def gravar_meus(settings, lista):
    settings.setValue(CHAVE, json.dumps([asdict(m) for m in lista], ensure_ascii=False))
