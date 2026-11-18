"""Porta-retrato "Maria Olivia" (MDF 3 mm, foto 150 × 217) a partir do PDF "Maria_Olivia_Projeto_MDF3_Rebaixos" (Rev. 01).

- Base P01 (moldura + menina + suporte do nome): prancha 1:1 da página 14, alisada.
- Aplicações (N01 nome, C01 cabelo, K01 coroa, D01 vestido, H01–H05 corações, F01 flor, M01 miolo) e os detalhes
  gravados (mechas do cabelo, rosto, vestido): desenho montado da página 1, levado a 1:1 pela própria moldura e
  alisado (o PDF é traçado de imagem: degraus/tremido).
- REBAIXO = o mesmo contorno da peça + FOLGA mm por lado (o da Luana, sem folga, ficou justo), só onde há MDF; H01
  assenta na coroa K01 e M01 na flor F01. Espaçadores, fundo e apoios: medidas das páginas 8 e 9.
Rebaixos ocultos do verso (espaçadores/apoios) ficam de fora: exigem virar a peça; os espaçadores são colados.

Executar:  python tools/projetos/maria_olivia.py <entrada.pdf> <saida.rbl> [previa.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform  # noqa: E402

import luana as lu  # noqa: E402
import presepio as pr  # noqa: E402
from apollo_emily import PT, caminho  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

FOLGA = 0.10  # mm por lado no rebaixo (pedido do dono, 18/11/2026)
REBAIXO, DETALHE = "C10", "C03"
# cor do preenchimento no desenho montado (pág. 1) -> aplicações; identificadas pelo tamanho 1:1 (tabela da pág. 7)
TAMANHOS = {"N01": (206.54, 45.27), "C01": (115.46, 129.59), "K01": (84.12, 61.12), "D01": (117.07, 117.87),
            "H01": (17.68, 12.64), "F01": (47.95, 41.36), "M01": (12.05, 10.57), "H02": (39.92, 34.24),
            "H03": (39.38, 34.70), "H04": (39.92, 34.01), "H05": (39.38, 34.93)}
NOMES = {"P01": "Base (moldura + menina)", "P02": "Espaçador esquerdo", "P03": "Espaçador direito",
         "P04": "Espaçador inferior", "P05": "Fundo", "P06": "Apoio 1", "P07": "Apoio 2", "N01": "Nome Maria Olivia",
         "C01": "Cabelo", "K01": "Coroa", "D01": "Vestido", "H01": "Coração da coroa", "F01": "Flor",
         "M01": "Miolo da flor", "H02": "Coração lateral 1", "H03": "Coração lateral 2", "H04": "Coração lateral 3",
         "H05": "Coração lateral 4"}
SOBRE = {"H01": "K01", "M01": "F01"}
LATERAIS = ("H02", "H03", "H04", "H05")  # estas assentam em outra aplicação, não na base


def _maior(p):
    return max(p.toSubpathPolygons(), key=lambda q: abs(pr._area_pts(list(q))))


def _area_util(cont, furos):
    a = QPainterPath(cont)
    for f in furos:
        a = a.subtracted(f)
    return a


def _folga(area, mm):
    """`area` crescida `mm` para fora em todo o contorno (os vazados internos encolhem o mesmo)."""
    st = QPainterPathStroker()
    st.setWidth(2 * mm)
    st.setJoinStyle(Qt.RoundJoin)
    return area.united(st.createStroke(area))


def ler(pdf):
    doc = pymupdf.open(pdf)
    p1, p14 = doc[0].get_drawings(), doc[13].get_drawings()
    doc.close()
    # base 1:1 (pág. 14): o traço escuro tem o contorno de fora e a janela
    base = lu.suavizar(caminho({**next(d for d in p14 if d["type"] == "s" and len(d["items"]) > 100),
                                "closePath": True}), 0.25)
    fora, *resto = lu._subcaminhos(base)
    janela = max(resto, key=pr._area)
    # desenho montado (pág. 1) -> 1:1 pela moldura
    m1 = next(d for d in p1 if d["type"] == "s" and len(d["items"]) > 100)["rect"]
    m14 = fora.boundingRect()
    e = m14.width() / (m1.width * PT)
    tf = (QTransform.fromTranslate(-m1.x0 * PT, -m1.y0 * PT) * QTransform.fromScale(e, e)
          * QTransform.fromTranslate(m14.left(), m14.top()))
    apl, detalhes, laterais = {}, [], []
    for d in p1:
        if d["type"] == "fs" and len(d["items"]) > 20:
            p = lu.suavizar(tf.map(caminho({**d, "closePath": True})), 0.3)
            cont, furos = lu._partes(p)
            furos = [f for f in furos if min(f.boundingRect().width(), f.boundingRect().height()) >= 1.0]  # lascas
            r = cont.boundingRect()
            k = min(TAMANHOS, key=lambda c: abs(TAMANHOS[c][0] - r.width()) + abs(TAMANHOS[c][1] - r.height()))
            assert abs(TAMANHOS[k][0] - r.width()) < 1.5, (k, r)
            if k in LATERAIS:  # os 4 corações laterais têm quase o mesmo tamanho: ficam na ordem de cima p/ baixo
                laterais.append((r.top(), cont, furos))
            else:
                assert k not in apl, k
                apl[k] = (cont, furos)
        elif d["type"] == "f" and tuple(round(v, 2) for v in d["fill"]) == (0.27, 0.16, 0.06):
            g = tf.map(caminho({**d, "closePath": True}))
            if g.boundingRect().width() * g.boundingRect().height() > 0.05:
                detalhes.append(g)
    for k, (_y, cont, furos) in zip(LATERAIS, sorted(laterais, key=lambda t: t[0])):
        apl[k] = (cont, furos)
    assert set(apl) == set(TAMANHOS), set(TAMANHOS) - set(apl)
    pecas = {}
    solido = QPainterPath(fora).subtracted(janela)
    rebaixo_base = QPainterPath()
    for k, (cont, furos) in apl.items():
        partes = [(cont, "cont")] + [(f, "furo") for f in furos]
        util = _area_util(cont, furos)
        partes += [(g, "cheio") for g in detalhes if util.contains(g.boundingRect().center())]
        pecas[k] = {"cont": cont, "partes": partes}
        if k not in SOBRE:
            rebaixo_base = rebaixo_base.united(_folga(util, FOLGA))
    for k, alvo in SOBRE.items():  # coração na coroa, miolo na flor
        c, f = apl[k]
        cont_alvo, furos_alvo = apl[alvo]
        reb = _folga(_area_util(c, f), FOLGA).intersected(_area_util(cont_alvo, furos_alvo))
        pecas[alvo]["partes"].append((reb, "rebaixo"))
    det_base = [g for g in detalhes if solido.contains(g.boundingRect().center())
                and not any(_area_util(*apl[k]).contains(g.boundingRect().center()) for k in apl)]
    pecas["P01"] = {"cont": fora, "partes": [(fora, "cont"), (janela, "furo"),
                                             (rebaixo_base.intersected(solido), "rebaixo")]
                    + [(g, "cheio") for g in det_base]}
    for k, p in (("P05", lu._ret(0, 0, 212, 254, (7, 7, 7, 7))), ("P02", lu._ret(0, 0, 27.6, 254, (7, 0, 0, 7))),
                 ("P03", lu._ret(0, 0, 33.6, 254, (0, 7, 7, 0))), ("P04", lu._ret(0, 0, 150.8, 22.6))):
        pecas[k] = {"cont": p, "partes": [(p, "cont")]}
    for k in ("P06", "P07"):  # triângulo retângulo: 160 contra o fundo, 85 na mesa
        t = QPainterPath(QPointF(0, 0))
        t.lineTo(0, 160)
        t.lineTo(85, 160)
        t.closeSubpath()
        pecas[k] = {"cont": t, "partes": [(t, "cont")]}
    return pecas


def camadas():
    corte = dict(mt.corte_mdf(3), velocidade_mm_min=630.0)
    out = [cm.alterar(cm.Camada(REBAIXO, f"Rebaixo dos encaixes (gravado; peça + {FOLGA:g} mm por lado)"),
                      modo="preenchimento", velocidade_mm_min=1500.0, potencia_max=60.0, potencia_min=0.0,
                      passadas=1, intervalo_mm=0.1),
           cm.alterar(cm.Camada(DETALHE, "Detalhes gravados (cabelo, rosto, vestido)"), modo="preenchimento",
                      velocidade_mm_min=pr.GRAV_VEL, potencia_max=pr.GRAV_POT, potencia_min=0.0, passadas=1,
                      intervalo_mm=0.1)]
    for lid, nome, tipo in pr.CAMADAS:
        if lid in (pr.CORTE_DENTRO_FURO, pr.CONT_DENTRO, pr.FURO, pr.CONT):
            out.append(cm.alterar(cm.Camada(lid, nome), **corte))
    return out


def gerar(pdf, saida, png=None):
    pecas = ler(pdf)
    pr.NOMES.update(NOMES)
    pr.TIPO_CAMADA["rebaixo"], pr.DESC["rebaixo"] = REBAIXO, "rebaixo"
    pos = pr.encaixar(pecas, n_chapas=5)
    chapas = pr.folhas(pecas, pos)
    snaps = []
    for chapa in chapas:
        grupos = []
        for k, partes, _d in chapa:
            g = ob.group([ob.Shape(p, f"{k} — {pr.DESC[t]}", lid, cm.cor(lid)) for p, lid, t in partes])
            g.name = f"{k} {NOMES[k]}"
            grupos.append(g.snapshot())
        snaps.append(tuple(grupos))
    ap = [pr.aproveitamento(c) for c in chapas]
    notas = ("Porta-retrato Maria Olivia — MDF 3 mm, foto 150 × 217 (PDF Rev. 01). 18 peças em "
             f"{len(chapas)} chapa(s) de 365 × 370, 2 mm da borda e entre peças.\n"
             "Contornos alisados (o PDF é traçado de imagem).\n"
             f"REBAIXO (C10, gravado, 1º, 1500 mm/min 60 % 1 passada): contorno da peça + {FOLGA:g} mm por lado, só "
             "onde há MDF. Base P01: nome, cabelo, coroa, vestido, corações H02–H05 e flor. Coroa K01: coração H01. "
             "Flor F01: miolo M01.\nDetalhes (C03, 2000 mm/min 35 %): mechas do cabelo, vestido e rosto.\n"
             "Cores: cabelo marrom, coroa e flor amarelas, vestido verde (cintura branca pintada), corações e miolo "
             "vermelhos, nome verde; rosto e braços ficam no MDF da base.\n"
             "Montagem: espaçadores P02/P03/P04 colados no verso de P01 (topo aberto para a foto), fundo P05, apoios "
             "P06/P07 no verso em X85 e X207. Os rebaixos ocultos do verso do PDF não estão no arquivo.")
    pj.save(saida, snaps[0], camadas(), notas=notas, paginas=[None] + [(s, (), ()) for s in snaps[1:]],
            pagina_atual=0, nomes_paginas=[f"Chapa {i + 1}" for i in range(len(chapas))])
    if png:
        pr.previa(chapas, png)
    return saida, ap, [sorted(k for k, *_ in c) for c in chapas]


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(*sys.argv[1:4]))
