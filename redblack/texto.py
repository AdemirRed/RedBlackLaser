"""Texto (Etapa 7): parâmetros imutáveis -> contorno em mm.

Altura = altura do "X" maiúsculo da fonte, em mm, exata (a referência documenta como aproximada).
Origem local: linha de base da primeira linha, no ponto de alinhamento horizontal
(esquerda/centro/direita). Linhas seguintes descem `espacamento` × entrelinha da fonte.
"""
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QPainterPath, QTransform

ALINHAMENTOS = ("esquerda", "centro", "direita")
_REF_PT = 100.0  # tamanho de construção; o resultado é escalado para a altura pedida


@dataclass(frozen=True)
class TextoParams:
    texto: str
    fonte: str
    altura_mm: float = 10.0
    negrito: bool = False
    italico: bool = False
    alinhamento: str = "esquerda"
    espacamento: float = 1.0  # multiplicador da entrelinha da fonte
    variavel: bool = False    # True: `texto` é um modelo com marcadores ({n}, {nome}…); ver variaveis.py
    peca: int = 0             # posição no gabarito: usa a linha atual + peca da planilha
    maiusculas: bool = False  # força maiúsculas (o texto digitado é mantido)
    soldado: bool = False     # letras fundidas num contorno só (sobreposições somem: corta tudo de uma vez)
    distorcer: bool = False   # no texto ao longo do caminho, as letras curvam junto (não só giram)


def texto_efetivo(p: "TextoParams") -> str:
    return p.texto.upper() if p.maiusculas else p.texto


def font_available(family: str) -> bool:
    fam = family.casefold()
    return any(f.casefold() == fam for f in QFontDatabase.families())


def make_font(p: TextoParams) -> QFont:
    f = QFont(p.fonte)
    f.setPointSizeF(_REF_PT)
    f.setBold(p.negrito)
    f.setItalic(p.italico)
    f.setKerning(True)
    return f


def build_path(p: TextoParams) -> QPainterPath:
    if p.alinhamento not in ALINHAMENTOS:
        raise ValueError(f"alinhamento inválido: {p.alinhamento}")
    font = make_font(p)
    fm = QFontMetricsF(font)
    x_ref = QPainterPath()
    x_ref.addText(0, 0, font, "X")
    cap = x_ref.boundingRect().height() or fm.capHeight() or fm.ascent()
    out = QPainterPath()
    out.setFillRule(Qt.WindingFill)  # contornos de glifos se sobrepõem
    for i, line in enumerate(texto_efetivo(p).split("\n")):
        width = fm.horizontalAdvance(line)
        x = {"esquerda": 0.0, "centro": -width / 2, "direita": -width}[p.alinhamento]
        out.addText(QPointF(x, i * fm.lineSpacing() * p.espacamento), font, line)
    s = p.altura_mm / cap
    path = QTransform.fromScale(s, s).map(out)
    if p.soldado:
        path = path.simplified()  # união dos glifos; furos (O, A…) continuam furos
    path.setFillRule(Qt.WindingFill)
    return path
