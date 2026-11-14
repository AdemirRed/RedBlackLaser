"""Rotativo (rolo ou mandril) no lugar do eixo Y: converte distância na superfície da peça em movimento do eixo.

O desenho continua em mm reais na superfície (a "altura" do desenho é o quanto se percorre em volta da peça).
No G-code, cada mm em Y vira `fator` mm de comando no eixo:
    mandril (a peça gira presa no eixo):   fator = mm_por_rotacao / (π × diâmetro da peça)
    rolo    (a peça gira apoiada em rolos): fator = mm_por_rotacao / (π × diâmetro do rolo)  — no rolo a superfície
            anda junto com a do rolo, então o diâmetro da peça não entra.
`mm_por_rotacao` = quanto o eixo precisa andar (em mm de comando) para o rotativo dar uma volta completa;
vem da calibração do rotativo na máquina (NÃO validado aqui).
A escala é feita a partir do ponto mais baixo do trabalho (o começo fica onde está).
"""
import math
from dataclasses import asdict, dataclass, fields

TIPOS = ("rolo", "mandril")


@dataclass(frozen=True)
class Rotativo:
    ativo: bool = False
    tipo: str = "rolo"
    mm_por_rotacao: float = 360.0
    diametro_objeto_mm: float = 50.0
    diametro_rolo_mm: float = 20.0
    espelhar: bool = False
    eixo: str = "Y"  # motor do rotativo ligado no Y (padrão) ou no X; o desenho não muda, só a saída

    @property
    def diametro_referencia(self) -> float:
        return self.diametro_rolo_mm if self.tipo == "rolo" else self.diametro_objeto_mm

    @property
    def fator(self) -> float:
        return self.mm_por_rotacao / (math.pi * self.diametro_referencia)

    @property
    def circunferencia_objeto(self) -> float:
        return math.pi * self.diametro_objeto_mm


def erros(r: Rotativo) -> list:
    out = []
    if r.tipo not in TIPOS:
        out.append("tipo de rotativo inválido")
    if r.eixo not in ("X", "Y"):
        out.append("eixo do rotativo inválido")
    for n, lo, hi in (("mm_por_rotacao", 0.1, 100000), ("diametro_objeto_mm", 0.1, 2000),
                      ("diametro_rolo_mm", 0.1, 500)):
        v = getattr(r, n)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            out.append(f"{n} fora de {lo}–{hi}")
    return out


def transformar_y(ys, r: Rotativo):
    """Função y_máquina → y_comando para um conjunto de Y de máquina do trabalho (escala a partir do menor)."""
    y0, y1 = min(ys), max(ys)
    f = r.fator

    def tf(y):
        return y0 + ((y1 - y) if r.espelhar else (y - y0)) * f
    return tf


def para_dict(r: Rotativo) -> dict:
    return asdict(r)


def de_dict(d) -> Rotativo:
    if not isinstance(d, dict):
        raise ValueError("rotativo inválido")
    nomes = {f.name for f in fields(Rotativo)}
    conv = {k: v for k, v in d.items() if k in nomes}
    r = Rotativo(**conv)
    e = erros(r)
    if e:
        raise ValueError("; ".join(e))
    return r
