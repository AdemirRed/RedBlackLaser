"""Gera o projeto "Suporte hexagonal de cuia — Francieli" (.rbl) a partir de Projeto_Cuia_Francieli.pdf.

Página 4 do PDF = chapa 1:1 (370 × 365 mm). O arquivo veio com contornos ABERTOS (falta uma borda em cada peça:
lado esquerdo das laterais, um lado de cada hexágono e uma borda de vários rasgos). Cada uma dessas peças é um
traço só: fechar o traço do fim ao começo recoloca exatamente a borda que falta (conferido pelo comprimento).

20 peças: 6 laterais (L1–L6, com janela e o nome gravado), tampo T01 (furo Ø80) e base fechada B01 (12 rasgos
10,10 × 2,95 cada), 6 laços (A1–A6) e 6 miolos Ø7 (M1–M6) que saem das sobras das janelas.
Camadas (regras do dono, docs/COMO_CRIAR_PROJETOS.md): C03 nome (preenchimento 2000/35 %), C06 laço e miolo
(dentro da janela, cortam ANTES dela), C02 janelas/rasgos/furo, C01 contornos (por último). Corte 630/85 %/2.

Executar:  python tools/projetos/cuia_francieli.py [pdf] [saida.rbl]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtGui import QPainterPath  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import importar_pdf as pdfimp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

PDF = r"F:\Downloads\Projeto_Cuia_Francieli.pdf"
PAGINA = 3  # 4ª página: vetores 1:1
LADO_HEX = 127.02 / 2


def _perto(a, b, tol=0.2):
    return abs(a - b) <= tol


def fechar(path: QPainterPath):
    """Fecha o traço aberto; devolve (path fechado, comprimento da borda recolocada ou 0 se já era fechado)."""
    polys = path.toSubpathPolygons()
    assert len(polys) == 1, "esperava um traço por peça aberta"
    q = polys[0]
    gap = math.hypot(q.last().x() - q.first().x(), q.last().y() - q.first().y())
    if gap < 0.01:
        return path, 0.0
    p = QPainterPath(path)
    p.closeSubpath()
    return p, gap


def classificar(objetos):
    """Separa as peças do PDF pelo tamanho (não pela ordem). Devolve dict com listas de (path, gap)."""
    out = {k: [] for k in ("lateral", "janela", "laco", "miolo", "hex", "furo", "rasgo", "letra")}
    for _n, path in objetos:
        b = path.boundingRect()
        w, h = b.width(), b.height()
        if _perto(w, 54) and _perto(h, 90):
            k = "lateral"
        elif _perto(w, 38) and _perto(h, 46):
            k = "janela"
        elif _perto(w, 34) and _perto(h, 22):
            k = "laco"
        elif _perto(w, 7) and _perto(h, 7):
            k = "miolo"
        elif _perto(w, 127.02) and _perto(h, 110):
            k = "hex"
        elif _perto(w, 80) and _perto(h, 80):
            k = "furo"
        elif (_perto(w, 10.1) and _perto(h, 2.95)) or (_perto(w, 7.6) and _perto(h, 10.22)):
            k = "rasgo"
        else:
            k = "letra"
        p, gap = fechar(path) if k != "letra" else (path, 0.0)
        out[k].append((p, gap))
    return out


def conferir(c):
    """Quantidades e bordas recolocadas com o tamanho certo (assert: projeto errado não sai)."""
    n = {k: len(v) for k, v in c.items()}
    assert (n["lateral"], n["janela"], n["laco"], n["miolo"], n["hex"], n["furo"], n["rasgo"]) == \
        (6, 6, 6, 6, 2, 1, 24), n
    for _p, gap in c["lateral"]:
        assert _perto(gap, 84, 0.3) or _perto(gap, 90, 0.3), f"lateral: borda recolocada de {gap:.2f} mm"
    for _p, gap in c["hex"]:
        assert _perto(gap, LADO_HEX, 0.3), f"hexágono: borda recolocada de {gap:.2f} mm"
    for _p, gap in c["rasgo"]:
        assert gap == 0 or _perto(gap, 2.95, 0.1) or _perto(gap, 10.1, 0.1), f"rasgo: borda de {gap:.2f} mm"
    for p, _g in sum((c[k] for k in ("lateral", "janela", "laco", "miolo", "hex", "furo", "rasgo")), []):
        q = p.toSubpathPolygons()[0]
        assert math.hypot(q.last().x() - q.first().x(), q.last().y() - q.first().y()) < 0.01, "contorno aberto"
    for p, _g in c["rasgo"]:  # rasgo fechado = área de 10,10 × 2,95
        q = p.toSubpathPolygons()[0]
        area = abs(sum(q[i].x() * q[i + 1].y() - q[i + 1].x() * q[i].y() for i in range(q.size() - 1))) / 2
        assert _perto(area, 10.1 * 2.95, 0.5), f"rasgo com área {area:.2f}"


def _dentro(p, caixa):
    return caixa.adjusted(-0.5, -0.5, 0.5, 0.5).contains(p.boundingRect())


def _grupo(itens, nome):
    g = ob.group([ob.Shape(p, f"{nome} — {desc}", lid, cm.cor(lid)) for p, lid, desc in itens])
    g.name = nome
    return g.snapshot()


def pecas(c):
    """Snapshots agrupados: L1–L6, A1–A6, M1–M6, T01, B01 (ordem da esquerda para a direita)."""
    snaps = []
    lat = sorted((p for p, _ in c["lateral"]), key=lambda p: p.boundingRect().left())
    for i, contorno in enumerate(lat, 1):
        cx = contorno.boundingRect()
        jan = [p for p, _ in c["janela"] if _dentro(p, cx)]
        letras = [p for p, _ in c["letra"] if _dentro(p, cx)]
        assert len(jan) == 1 and len(letras) >= 5, (i, len(jan), len(letras))
        nome = QPainterPath()
        for p in letras:
            nome.addPath(p)
        snaps.append(_grupo([(nome, "C03", "nome gravado"), (jan[0], "C02", "janela"),
                             (contorno, "C01", "contorno")], f"L{i} Lateral {i} (Francieli)"))
        jb = jan[0].boundingRect()
        laco = [p for p, _ in c["laco"] if _dentro(p, jb)]
        miolo = [p for p, _ in c["miolo"] if _dentro(p, jb)]
        assert len(laco) == 1 and len(miolo) == 1, (i, len(laco), len(miolo))
        snaps.append(_grupo([(laco[0], "C06", "laço")], f"A{i} Laço {i}"))
        snaps.append(_grupo([(miolo[0], "C06", "miolo Ø7")], f"M{i} Miolo {i}"))
    hexes = sorted((p for p, _ in c["hex"]), key=lambda p: p.boundingRect().left())
    for k, h in enumerate(hexes):
        hb = h.boundingRect()
        ras = [p for p, _ in c["rasgo"] if _dentro(p, hb)]
        furo = [p for p, _ in c["furo"] if _dentro(p, hb)]
        assert len(ras) == 12, len(ras)
        tampo = k == 0
        assert len(furo) == (1 if tampo else 0), ("tampo tem o furo de 80 mm, a base é fechada", k, len(furo))
        rasgos = QPainterPath()
        for p in ras:
            rasgos.addPath(p)
        itens = ([(furo[0], "C02", "furo Ø80")] if tampo else []) + [(rasgos, "C02", "12 rasgos"),
                                                                       (h, "C01", "contorno")]
        snaps.append(_grupo(itens, "T01 Tampo (furo Ø80)" if tampo else "B01 Base fechada"))
    return snaps


def camadas():
    corte = dict(modo="linha", velocidade_mm_min=630.0, potencia_max=85.0, potencia_min=0.0, passadas=2, air=True)
    return [cm.alterar(cm.Camada("C03", "Nome Francieli (gravação)"), modo="preenchimento",
                       velocidade_mm_min=2000.0, potencia_max=35.0, passadas=1, intervalo_mm=0.1, air=True),
            cm.alterar(cm.Camada("C06", "Laços e miolos (dentro das janelas: cortam antes)"), **corte),
            cm.alterar(cm.Camada("C02", "Janelas, rasgos e furo"), **corte),
            cm.alterar(cm.Camada("C01", "Contornos (por último)"), **corte)]


NOTAS = """Suporte hexagonal de cuia — Francieli (PDF Projeto_Cuia_Francieli, base fechada, encaixes 2,95 mm).
Contornos abertos do PDF foram fechados (lado esquerdo das laterais, um lado de cada hexágono, bordas de rasgos).
MDF 3 mm, chapa única. Grave antes de cortar; laços/miolos antes das janelas; contornos por último.
Montagem: B01 embaixo, 6 laterais com o nome para fora, T01 em cima (12 dentes nos 12 rasgos); laço 2 mm abaixo
do topo do corpo da lateral e miolo no centro do laço."""


def gerar(pdf=PDF, destino="Cuia_Francieli_MDF_3mm_RedBlack.rbl"):
    res = pdfimp.load(pdf, PAGINA)
    c = classificar(res.objetos)
    conferir(c)
    snaps = pecas(c)
    assert len(snaps) == 20, len(snaps)
    pj.save(destino, tuple(snaps), camadas(), notas=NOTAS, nomes_paginas=["Chapa única — MDF 3 mm"])
    return destino, c


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    a = sys.argv[1:]
    d, c = gerar(a[0] if a else PDF, a[1] if len(a) > 1 else "Cuia_Francieli_MDF_3mm_RedBlack.rbl")
    print(d)
    for k in ("lateral", "hex", "rasgo"):
        print(k, "bordas recolocadas:", sorted({round(g, 2) for _p, g in c[k]}))
