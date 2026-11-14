"""Frisos para dobra (kerf bending): painel retangular com rebaixos paralelos que deixam o material curvar.

Geometria pura em mm de documento. Os frisos são retângulos finos (largura do friso) distribuídos com passo
igual: passo = largura do painel / (quantidade + 1), o 1º e o último a um passo das bordas.
A profundidade NÃO é definida pelo desenho: depende de potência/velocidade calibradas (matriz de testes).
"""
import math
from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

MAX_FRISOS = 2000


def desenvolvimento(diametro_interno, espessura, pele):
    """Comprimento planificado aproximado pelo eixo neutro no meio da pele residual: π·(Di + 2t − e)."""
    return math.pi * (diametro_interno + 2 * espessura - pele)


@dataclass(frozen=True)
class Frisos:
    largura_mm: float = 330.4955   # comprimento planificado do painel
    altura_mm: float = 150.0
    quantidade: int = 109
    largura_friso_mm: float = 0.30
    margem_mm: float = 0.0         # frisos param a esta distância das bordas de cima e de baixo (0 = altura toda)
    x_mm: float = 10.0             # canto superior esquerdo (documento)
    y_mm: float = 10.0

    @property
    def passo(self) -> float:
        return self.largura_mm / (self.quantidade + 1)

    def centros(self):
        return [self.x_mm + k * self.passo for k in range(1, self.quantidade + 1)]

    def contorno(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(QRectF(self.x_mm, self.y_mm, self.largura_mm, self.altura_mm))
        return p

    def frisos(self) -> QPainterPath:
        p = QPainterPath()
        w = self.largura_friso_mm
        for cx in self.centros():
            p.addRect(QRectF(cx - w / 2, self.y_mm + self.margem_mm, w, self.altura_mm - 2 * self.margem_mm))
        return p


def erros(f: Frisos, mesa_w, mesa_h) -> list:
    out = []
    if isinstance(f.quantidade, bool) or not isinstance(f.quantidade, int) or not 1 <= f.quantidade <= MAX_FRISOS:
        return [f"quantidade de frisos de 1 a {MAX_FRISOS}"]
    if f.largura_mm <= 0 or f.altura_mm <= 0:
        out.append("painel precisa de largura e altura")
    elif f.largura_friso_mm <= 0 or f.largura_friso_mm >= f.passo:
        out.append(f"largura do friso deve ser maior que 0 e menor que o passo ({f.passo:.3f} mm)".replace(".", ","))
    if f.margem_mm < 0 or 2 * f.margem_mm >= f.altura_mm:
        out.append("margem deve ser menor que metade da altura")
    if f.x_mm < 0 or f.y_mm < 0 or f.x_mm + f.largura_mm > mesa_w + 1e-6 or f.y_mm + f.altura_mm > mesa_h + 1e-6:
        out.append(f"o painel sai da mesa de {mesa_w:g} × {mesa_h:g} mm")
    return out
