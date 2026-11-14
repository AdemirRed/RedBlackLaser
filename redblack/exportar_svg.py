"""Exportar vetores para SVG em mm (1 unidade = 1 mm), legível pelo próprio importador e por outros programas.

Cada objeto folha vira um <path> na cor da sua camada (sem preenchimento). Imagens não são exportadas
(são raster); a função devolve quantas ficaram de fora.
"""
from xml.sax.saxutils import quoteattr

from PySide6.QtGui import QPainterPath

from .camadas import cor
from .importar_imagem import ImagemOriginal
from .percurso import folhas


def _n(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def caminho_d(p: QPainterPath) -> str:
    out, i, n = [], 0, p.elementCount()
    while i < n:
        e = p.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            out.append(f"M{_n(e.x)} {_n(e.y)}")
        elif e.type == QPainterPath.LineToElement:
            out.append(f"L{_n(e.x)} {_n(e.y)}")
        elif e.type == QPainterPath.CurveToElement:
            c2, fim = p.elementAt(i + 1), p.elementAt(i + 2)
            out.append(f"C{_n(e.x)} {_n(e.y)} {_n(c2.x)} {_n(c2.y)} {_n(fim.x)} {_n(fim.y)}")
            i += 2
        i += 1
    return " ".join(out)


def gerar(snapshots, largura_mm, altura_mm) -> tuple:
    """(texto SVG, imagens ignoradas)."""
    linhas = [f'<?xml version="1.0" encoding="UTF-8"?>',
              f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(largura_mm)}mm" height="{_n(altura_mm)}mm" '
              f'viewBox="0 0 {_n(largura_mm)} {_n(altura_mm)}">',
              "<!-- RedBlack Laser: unidades em mm; origem no canto superior esquerdo da mesa -->"]
    ignoradas = 0
    for snap in snapshots:
        for path, tf, layer, extra in folhas(snap):
            if isinstance(extra, ImagemOriginal):
                ignoradas += 1
                continue
            d = caminho_d(tf.map(path))
            if d:
                linhas.append(f'<path d={quoteattr(d)} fill="none" stroke="{cor(layer)}" stroke-width="0.1" '
                              f'data-camada={quoteattr(layer)}/>')
    linhas.append("</svg>")
    return "\n".join(linhas) + "\n", ignoradas


def salvar(caminho, texto):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    import os
    os.replace(tmp, caminho)
