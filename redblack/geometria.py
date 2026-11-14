"""Conversões de coordenadas e escalas — sem dependência de interface.

Unidade interna: mm.
- Documento (cena): origem no canto superior esquerdo da mesa, Y para baixo.
- Exibição (réguas/status): origem no canto inferior esquerdo, Y para cima.
"""
import math

# Área da mesa (mm) e canto da origem da máquina. Padrão DEMONSTRATIVO até ser confirmado na máquina
# (docs/MAQUINA.md); muda por Configurações do dispositivo -> definir_mesa(). Leia sempre como g.BED_W/g.BED_H.
BED_W, BED_H = 365.0, 370.0  # bancada da RedBlack: 365 de largura x 370 de altura
ORIGEM = "inf_esq"
CANTOS = {"inf_esq": "Inferior esquerdo", "sup_esq": "Superior esquerdo",
          "inf_dir": "Inferior direito", "sup_dir": "Superior direito"}
MESA_MIN, MESA_MAX = 10.0, 5000.0


def definir_mesa(largura: float, altura: float, origem: str = "inf_esq") -> None:
    global BED_W, BED_H, ORIGEM
    if not (MESA_MIN <= largura <= MESA_MAX and MESA_MIN <= altura <= MESA_MAX) or origem not in CANTOS:
        raise ValueError("mesa inválida")
    BED_W, BED_H, ORIGEM = float(largura), float(altura), origem


def canto_origem() -> tuple[float, float]:
    """Origem da máquina em coordenadas de documento (Y para baixo)."""
    return (BED_W if ORIGEM.endswith("dir") else 0.0, 0.0 if ORIGEM.startswith("sup") else BED_H)

# Limites de zoom em pixels por mm.
SCALE_MIN, SCALE_MAX = 0.2, 200.0

_STEPS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)


def to_display(x: float, y: float) -> tuple[float, float]:
    return x, BED_H - y


def from_display(x: float, y: float) -> tuple[float, float]:
    return x, BED_H - y


def clamp_scale(scale: float) -> float:
    return max(SCALE_MIN, min(SCALE_MAX, scale))


def grid_step(px_per_mm: float, min_px: float = 8.0, multiple_of: float | None = None) -> float:
    """Menor passo 'redondo' (1-2-5) com espaçamento na tela >= min_px.

    multiple_of garante que linhas principais coincidam com as secundárias.
    """
    for s in _STEPS:
        if s * px_per_mm < min_px:
            continue
        if multiple_of and abs(s / multiple_of - round(s / multiple_of)) > 1e-6:
            continue
        return s
    return _STEPS[-1]


def steps_for(px_per_mm: float) -> tuple[float, float]:
    """(passo secundário, passo principal/rótulo) para a escala atual."""
    minor = grid_step(px_per_mm, 8)
    return minor, grid_step(px_per_mm, 60, multiple_of=minor)


def ticks(start: float, end: float, step: float) -> list[float]:
    """Múltiplos de step dentro de [start, end], sem erro acumulado de ponto flutuante."""
    i0, i1 = math.ceil(start / step - 1e-9), math.floor(end / step + 1e-9)
    return [round(i * step, 6) for i in range(i0, i1 + 1)]


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def fmt_mm(v: float, step: float) -> str:
    """Rótulo de régua: casas decimais só quando o passo exige."""
    dec = 0 if step >= 1 else 1
    return f"{v:.{dec}f}".replace(".", ",")
