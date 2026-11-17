"""Porta-retrato "Princesas" (MDF 3 mm, 2 fotos 150 × 210) a partir do PDF "Princesas_Contorno_Integrado_Sem_Pingo".

O PDF traz 4 pranchas 1:1 de 370 × 365 mm, todas só de corte (traço preto). Aqui cada desenho vira peças: o
subcaminho de fora é o contorno e os que estão dentro dele são furos (janelas das fotos, coração, vazios do cabelo).
O encaixe nas chapas é o mesmo do presépio (mesa 365 × 370, 2 mm da borda e entre peças, peças pequenas dentro das
janelas das fotos, que virariam sobra; peça dentro de janela corta antes dela).

Executar:  python tools/projetos/princesas.py <entrada.pdf> <saida.rbl> [mapa.pdf] [previa.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf  # noqa: E402
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402

import presepio as pr  # noqa: E402
from apollo_emily import PT, caminho  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

# (página do PDF, x e y do canto da caixa em mm na página, código, nome) — tiradas do mapa das chapas (pág. 4)
PECAS = [(4, 6.0, 103.0, "F1A", "Moldura esquerda com contorno integrado"),
         (5, 6.0, 115.0, "F1B", "Moldura direita"), (5, 185.0, 115.0, "C1", "Cobertura central da emenda"),
         (5, 6.0, 19.0, "D3", "Palavra Princesas"), (5, 220.0, 339.0, "T1", "Teste da emenda 1"),
         (5, 270.0, 337.0, "T2", "Teste da emenda 2"),
         (6, 6.0, 115.0, "F2", "Fundo"), (6, 6.0, 35.5, "E1A", "Espaçador lateral esquerdo (parte a)"),
         (6, 176.0, 35.5, "E1B", "Espaçador lateral esquerdo (parte b)"),
         (6, 6.0, 66.0, "E2A", "Espaçador central (parte a)"), (6, 176.0, 66.0, "E2B", "Espaçador central (parte b)"),
         (6, 6.0, 95.5, "E3A", "Espaçador lateral direito (parte a)"),
         (6, 176.0, 95.5, "E3B", "Espaçador lateral direito (parte b)"),
         (7, 170.0, 113.0, "D1", "Silhueta da princesa (vai colada por cima)"),
         (7, 6.0, 169.0, "P1", "Pé 1"), (7, 90.0, 169.0, "P2", "Pé 2"),
         (7, 6.0, 89.0, "E4A", "Espaçador inferior (parte a)"), (7, 175.0, 89.0, "E4B", "Espaçador inferior (parte b)")]
NOMES = {c: n for *_x, c, n in PECAS}


def _area(poly):
    pts = list(poly)
    return abs(sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def _subcaminhos(p):
    """QPainterPath -> [subcaminho] (cada moveTo começa um), mantendo as curvas."""
    out, atual = [], None
    for i in range(p.elementCount()):
        e = p.elementAt(i)
        if e.isMoveTo():
            atual = QPainterPath()
            atual.moveTo(e.x, e.y)
            out.append(atual)
        elif e.isLineTo():
            atual.lineTo(e.x, e.y)
        elif e.isCurveTo():
            c2, fim = p.elementAt(i + 1), p.elementAt(i + 2)
            atual.cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
    return [s for s in out if s.elementCount() > 1]


def ler(pdf):
    """{código: {"cont", "partes": [(path, "cont"|"furo")]}} em mm da página do PDF."""
    doc = pymupdf.open(pdf)
    pecas = {}
    for n in sorted({p[0] for p in PECAS}):
        subs = [s for d in doc[n].get_drawings() for s in _subcaminhos(caminho({**d, "closePath": True}))]
        for s in subs:
            s.closeSubpath()
        fora = [s for s in subs if not any(o is not s and _area(o.toFillPolygon()) > _area(s.toFillPolygon())
                                           and o.boundingRect().contains(s.boundingRect())
                                           and o.contains(s.boundingRect().center()) for o in subs)]
        for s in fora:
            r = s.boundingRect()
            k = next((c for pg, x, y, c, _n in PECAS if pg == n and abs(r.x() - x) < 1.5 and abs(r.y() - y) < 1.5),
                     None)
            if k is None:
                raise ValueError(f"peça não identificada na página {n + 1}: {r}")
            furos = [h for h in subs if h is not s and r.contains(h.boundingRect()) and h not in fora]
            if k != "D3":  # lascas da junção silhueta + moldura (2 mm) só furariam a peça; nas letras são o miolo
                furos = [h for h in furos if _area(h.toFillPolygon()) >= 15.0]
            pecas[k] = {"cont": s, "partes": [(s, "cont")] + [(h, "furo") for h in furos]}
    faltam = set(NOMES) - set(pecas)
    if faltam:
        raise ValueError(f"peças do mapa não encontradas: {sorted(faltam)}")
    return pecas


def gerar(pdf, saida, mapa=None, png=None):
    pecas = ler(pdf)
    pr.NOMES.update(NOMES)  # o mapa e a prévia do presépio usam o nome pelo código
    pos = pr.encaixar(pecas, n_chapas=5)
    chapas = pr.folhas(pecas, pos)
    snaps = []
    for chapa in chapas:
        grupos = []
        for k, partes, _d in chapa:
            g = ob.group([ob.Shape(p, f"{k} — {pr.DESC[t]}", lid, cm.cor(lid)) for p, lid, t in partes])
            g.name = f"{k} {NOMES[k]}"
            grupos.append(g.snapshot())
            caixa = QRectF()
            for p, _l, _t in partes:
                caixa = caixa.united(p.boundingRect())
            assert QRectF(pr.MARGEM - 0.01, pr.MARGEM - 0.01, pr.MESA_W - 2 * pr.MARGEM + 0.02,
                          pr.MESA_H - 2 * pr.MARGEM + 0.02).contains(caixa), (k, caixa)
        snaps.append(tuple(grupos))
    ap = [pr.aproveitamento(c) for c in chapas]
    dentro = sorted(k for c in chapas for k, _p, d in c if d)
    camadas = [c for c in pr.camadas() if c.id in (pr.CORTE_DENTRO_FURO, pr.CONT_DENTRO, pr.FURO, pr.CONT)]
    notas = ("Porta-retrato Princesas — MDF 3 mm, 2 fotos 150 × 210 (PDF \"contorno integrado, sem pingo\"). "
             f"{len(pecas)} peças iguais ao PDF, reencaixadas em {len(chapas)} chapas de 365 × 370 mm, "
             f"{pr.MARGEM:g} mm da borda e {pr.VAO:g} mm entre peças.\n"
             + "".join(f"Chapa {i + 1} ({a:.0%}): " + ", ".join(f"{k} {NOMES[k]}" for k, *_ in sorted(c)) + ".\n"
                       for i, (c, a) in enumerate(zip(chapas, ap)))
             + f"Peças dentro das janelas das fotos (sobra que vira peça): {', '.join(dentro) or 'nenhuma'}; "
             "cortam ANTES da janela (C05/C06).\n"
             "Ordem: C05/C06 peças dentro de janelas → C02 janelas, coração e vazios → C01 contornos. "
             "Cortes 650 mm/min, 85 %, 2 passadas.\n"
             "Corte primeiro T1 e T2 (teste da emenda em V) e confira o encaixe. Montagem: guia do PDF (páginas 1–4).")
    nomes = [f"Chapa {i + 1}" for i in range(len(chapas))]
    pj.save(saida, snaps[0], camadas, notas=notas, paginas=[None] + [(s, (), ()) for s in snaps[1:]],
            pagina_atual=0, nomes_paginas=nomes)
    if mapa:
        pr.mapa_pdf(chapas, ap, mapa)
    if png:
        pr.previa(chapas, png)
    return saida, ap, [sorted(k for k, *_ in c) for c in chapas], dentro


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(*sys.argv[1:5]))
