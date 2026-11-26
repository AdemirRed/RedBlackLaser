"""Testes do rotativo (desenhos que entram numa aba nova e são gravados pelo Iniciar normal).

Teste 1 — volta completa: linha A no começo e linha B exatamente uma volta da peça depois (π × diâmetro), com uma
escala de -5 a +5 mm ao lado de A. Se "mm por rotação" estiver certo, B cai em cima de A. Se cair no traço +e da
escala, a peça andou C + e; o valor certo é mm_por_rotacao × C / (C + e) (ver `corrigir`).
Teste 2 — medidas: quadrado 20 × 20, círculo Ø20, linhas de 40 mm nos dois sentidos e o texto "RB" (se sair
espelhado, ligue/desligue "Espelhar"), em 2 passadas: linha dobrada = a peça escorregou no rolo.
Medidas no desenho = medidas reais na superfície da peça (é o que o rotativo converte).
"""
import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QTransform

from . import formas as fm
from . import texto as tx

FONTE = "Arial"


def _linha(x0, y, x1):
    p = QPainterPath()
    p.moveTo(x0, y)
    p.lineTo(x1, y)
    return p


def _texto(t, x, y, altura=2.5, centro=False):
    p = tx.build_path(tx.TextoParams(t, FONTE, altura))
    b = p.boundingRect()
    dx = x - (b.center().x() if centro else b.left())
    return QTransform.fromTranslate(dx, y - b.center().y()).map(p)


def circunferencia(diametro_mm: float) -> float:
    return math.pi * diametro_mm


def volta_completa(diametro_mm: float, cx: float, y0: float):
    """[(path, nome)] do teste 1, com a linha A em y0 (mm do documento) e o meio em cx."""
    c = circunferencia(diametro_mm)
    out = [(_linha(cx - 30, y0, cx), "A (começo)"), (_linha(cx - 30, y0 + c, cx + 12, ), "B (uma volta depois)")]
    escala = QPainterPath()
    for k in range(-5, 6):
        escala.addPath(_linha(cx + 3, y0 + k, cx + (9 if k in (-5, 0, 5) else 6)))
    out.append((escala, "Escala -5…+5 mm"))
    rot = QPainterPath()
    for k, t in ((-5, "-5"), (0, "0"), (5, "+5")):
        rot.addPath(_texto(t, cx + 13, y0 + k))
    rot.addPath(_texto(f"Ø{diametro_mm:g}", cx - 30, y0 + 6))
    out.append((rot, "Números da escala"))
    return out


def medidas(cx: float, y0: float):
    """[(path, nome)] do teste 2 (40 × 45 mm de desenho), começando em y0."""
    out = [(fm.rect_path(QRectF(cx - 45, y0, 20, 20)), "Quadrado 20 × 20"),
           (fm.ellipse_path(QRectF(cx - 18, y0, 20, 20)), "Círculo Ø20"),
           (_linha(cx - 45, y0 + 27, cx + 5), "Linha de 50 mm (ao longo da peça)")]
    v = QPainterPath()
    v.moveTo(cx + 12, y0)
    v.lineTo(cx + 12, y0 + 40)
    out.append((v, "Linha de 40 mm (em volta da peça)"))
    out.append((_texto("RB", cx - 45, y0 + 37, altura=8), "Texto RB (confere espelhado)"))
    return out


def corrigir(mm_por_rotacao: float, diametro_mm: float, erro_mm: float) -> float:
    """Novo mm por rotação pelo teste 1: a linha B caiu no traço `erro_mm` da escala (+ = passou, - = faltou)."""
    c = circunferencia(diametro_mm)
    if not -c / 2 < erro_mm < c / 2:
        raise ValueError("erro maior que meia volta: faça antes o teste sem laser (girar uma volta)")
    return mm_por_rotacao * c / (c + erro_mm)

