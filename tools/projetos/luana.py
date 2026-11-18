"""Porta-retrato "Luana" (MDF 3 mm, foto 100 × 80) a partir do PDF "Porta_Retrato_Luana_Projeto_Detalhado" (Rev. 03).

O PDF traz os contornos traçados de imagem (degraus de 0,1–0,2 mm: o "tremido"). Aqui:
  - nome, ramos, flores e a frente são SUAVIZADOS (reamostrados a 0,1 mm e alisados);
  - cada aplicação (N01, R01–R04, F01/F02) é cortada com o contorno suavizado E o rebaixo dela na frente é gravado
    com ESSE MESMO contorno, na posição do PDF: peça e rebaixo exatamente do mesmo tamanho, sem folga (pedido do
    dono). O rebaixo é só onde há MDF (sem a janela da foto) e não atravessa a frente;
  - fundo P05 e apoios P06/P07 vêm das pranchas 1:1; espaçadores P02–P04 das medidas (página 6);
  - tudo encaixado numa chapa (mesa 365 × 370, 2 mm da borda e entre peças).

Executar:  python tools/projetos/luana.py <entrada.pdf> <saida.rbl> [previa.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath, QPolygonF, QTransform  # noqa: E402

import presepio as pr  # noqa: E402
from apollo_emily import PT, caminho  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

APLICACOES = ["N01", "R01", "R02", "R03", "R04", "F01", "F02"]  # na ordem em que estão nas páginas 8 e 9
# posição (canto da caixa) em relação ao canto superior esquerdo do corpo 130 × 112 — tabela da página 5
POSICAO = {"N01": (30.35, -28.64), "R01": (11.04, -24.88), "R02": (-9.98, 22.85), "R03": (116.41, 32.82),
           "R04": (30.21, 93.29), "F01": (-6.57, -6.25), "F02": (99.37, 75.80)}
NOMES = {"P01": "Frente (com os rebaixos)", "P02": "Espaçador esquerdo", "P03": "Espaçador direito",
         "P04": "Espaçador inferior", "P05": "Fundo", "P06": "Apoio 1", "P07": "Apoio 2", "N01": "Nome Luana",
         "R01": "Ramo superior", "R02": "Ramo esquerdo", "R03": "Ramo direito", "R04": "Ramo inferior",
         "F01": "Flor de cima", "F02": "Flor de baixo"}
CORES = {"N01": "amarelo", "R01": "verde", "R02": "verde", "R03": "verde", "R04": "verde", "F01": "rosa",
         "F02": "rosa"}
SIGMA = 0.35   # mm: alisamento (some o degrau de 0,1–0,2 mm, as formas ficam iguais)
PASSO = 0.1    # mm entre pontos na reamostragem
REBAIXO = "C03"


def suavizar(p, sigma=SIGMA):
    """Cada contorno fechado reamostrado a PASSO mm e alisado (média gaussiana circular); sem degraus."""
    from scipy.ndimage import gaussian_filter1d
    from skimage.measure import approximate_polygon
    out = QPainterPath()
    out.setFillRule(Qt.OddEvenFill)
    for poly in p.toSubpathPolygons():
        pts = np.array([(q.x(), q.y()) for q in poly])
        if len(pts) < 4:
            continue
        if np.hypot(*(pts[0] - pts[-1])) > 1e-6:
            pts = np.vstack([pts, pts[:1]])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        s = np.concatenate([[0], np.cumsum(seg)])
        if s[-1] < 1.0:
            continue
        n = max(8, int(s[-1] / PASSO))
        t = np.linspace(0, s[-1], n, endpoint=False)
        x, y = np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])
        x = gaussian_filter1d(x, sigma / PASSO, mode="wrap")
        y = gaussian_filter1d(y, sigma / PASSO, mode="wrap")
        liso = approximate_polygon(np.column_stack([x, y, ]), 0.01)
        out.addPolygon(QPolygonF([QPointF(a, b) for a, b in liso]))
        out.closeSubpath()
    return out


def _subcaminhos(p):
    """Contornos separados (o maior é o de fora; os outros, furos)."""
    polys = sorted(p.toSubpathPolygons(), key=lambda q: -abs(pr._area_pts(list(q))) if len(q) > 2 else 0)
    out = []
    for q in polys:
        if len(q) > 2 and abs(pr._area_pts(list(q))) > 0.5:
            s = QPainterPath()
            s.addPolygon(q)
            s.closeSubpath()
            out.append(s)
    return out


def _partes(caminho_liso):
    subs = _subcaminhos(caminho_liso)
    return subs[0], subs[1:]


def _ret(x, y, w, h, raios=(0, 0, 0, 0)):
    """Retângulo com cantos (sup. esq., sup. dir., inf. dir., inf. esq.) de raio dado."""
    p = QPainterPath()
    a, b, c, d = raios
    p.moveTo(x + a, y)
    p.lineTo(x + w - b, y)
    if b:
        p.arcTo(x + w - 2 * b, y, 2 * b, 2 * b, 90, -90)
    p.lineTo(x + w, y + h - c)
    if c:
        p.arcTo(x + w - 2 * c, y + h - 2 * c, 2 * c, 2 * c, 0, -90)
    p.lineTo(x + d, y + h)
    if d:
        p.arcTo(x, y + h - 2 * d, 2 * d, 2 * d, 270, -90)
    p.lineTo(x, y + a)
    if a:
        p.arcTo(x, y, 2 * a, 2 * a, 180, -90)
    p.closeSubpath()
    return p


def ler(pdf):
    """{código: {"cont", "partes": [(path, tipo)]}} — tipos do presépio: cont, furo, cheio (= rebaixo)."""
    doc = pymupdf.open(pdf)
    desenhos = {n: [d for d in doc[n].get_drawings() if d["items"] and len(d["items"]) > 4] for n in (7, 8, 9)}
    doc.close()
    pecas = {}
    # aplicações: página 9 (peças) — suavizadas
    apl = [d for d in desenhos[8] if d["type"] == "fs"]
    assert len(apl) == 7, len(apl)
    liso = {}
    for k, d in zip(APLICACOES, apl):
        p = suavizar(caminho({**d, "closePath": True}))
        cont, furos = _partes(p)
        liso[k] = (cont, furos)
    # frente: página 8 — contorno de fora + janela (suavizados); corpo pelo nome (tabela da página 5)
    assentos = [d for d in desenhos[7] if d["type"] == "fs"]
    frente = next(d for d in desenhos[7] if d["type"] == "s")
    r_nome = assentos[0]["rect"]
    ox, oy = r_nome.x0 * PT - POSICAO["N01"][0], r_nome.y0 * PT - POSICAO["N01"][1]
    fr = suavizar(caminho({**frente, "closePath": True}), 0.25)
    fora, janelas = _partes(fr)
    janela = max(janelas, key=lambda q: pr._area(q))
    # cada aplicação no seu lugar (canto da caixa = corpo + tabela) e o rebaixo com o MESMO contorno
    solido = QPainterPath(fora).subtracted(janela)
    rebaixo = QPainterPath()
    for k in APLICACOES:
        cont, furos = liso[k]
        c = cont.boundingRect()
        tf = QTransform.fromTranslate(ox + POSICAO[k][0] - c.left(), oy + POSICAO[k][1] - c.top())
        area = QPainterPath(tf.map(cont))
        for f in furos:
            area = area.subtracted(tf.map(f))
        rebaixo = rebaixo.united(area)
        pecas[k] = {"cont": cont, "partes": [(cont, "cont")] + [(f, "furo") for f in furos]}
    rebaixo = rebaixo.intersected(solido)
    pecas["P01"] = {"cont": fora, "partes": [(fora, "cont"), (janela, "furo"), (rebaixo, "cheio")]}
    # fundo e apoios: página 10 (geométricos: sem alisar)
    doc = pymupdf.open(pdf)
    pag10 = [d for d in doc[9].get_drawings() if d["type"] == "fs"]
    doc.close()
    fundo = next(d for d in pag10 if abs(d["rect"].width * PT - 130) < 0.5)
    apoios = [d for d in pag10 if abs(d["rect"].width * PT - 55) < 0.5]
    for k, d in (("P05", fundo), ("P06", apoios[0]), ("P07", apoios[1])):
        p = caminho({**d, "closePath": True})
        pecas[k] = {"cont": p, "partes": [(p, "cont")]}
    # espaçadores (página 6): cantos externos R8 como o corpo
    for k, p in (("P02", _ret(0, 0, 14.6, 112, (8, 0, 0, 8))), ("P03", _ret(0, 0, 14.6, 112, (0, 8, 8, 0))),
                 ("P04", _ret(0, 0, 100.8, 18.6))):
        pecas[k] = {"cont": p, "partes": [(p, "cont")]}
    return pecas, (ox, oy)


def camadas():
    corte = dict(mt.corte_mdf(3), velocidade_mm_min=630.0)  # corte do dono (17/11/2026): 630 mm/min
    out = []
    for lid, nome, tipo in pr.CAMADAS:
        if lid not in (REBAIXO, pr.CORTE_DENTRO_FURO, pr.CONT_DENTRO, pr.FURO, pr.CONT):
            continue
        c = cm.Camada(lid, nome)
        if lid == REBAIXO:  # gravação funda (não atravessa): o assento de cada aplicação na frente
            c = cm.alterar(cm.Camada(lid, "Rebaixo dos encaixes (gravado, 1º) — teste a profundidade num retalho"),
                           modo="preenchimento", velocidade_mm_min=1500.0, potencia_max=60.0, potencia_min=0.0,
                           passadas=2, intervalo_mm=0.1)
        else:
            c = cm.alterar(c, **corte)
        out.append(c)
    return out


def gerar(pdf, saida, png=None):
    pecas, _orig = ler(pdf)
    pr.NOMES.update(NOMES)
    pos = pr.encaixar(pecas, n_chapas=3)
    chapas = pr.folhas(pecas, pos)
    snaps = []
    for chapa in chapas:
        grupos = []
        for k, partes, _d in chapa:
            g = ob.group([ob.Shape(p, f"{k} — {'rebaixo' if t == 'cheio' else pr.DESC[t]}",
                                   REBAIXO if t == "cheio" else lid, cm.cor(REBAIXO if t == "cheio" else lid))
                          for p, lid, t in partes])
            g.name = f"{k} {NOMES[k]}"
            grupos.append(g.snapshot())
        snaps.append(tuple(grupos))
    ap = [pr.aproveitamento(c) for c in chapas]
    notas = ("Porta-retrato Luana — MDF 3 mm, foto 100 × 80 (PDF Rev. 03). 14 peças em "
             f"{len(chapas)} chapa(s) de 365 × 370, 2 mm da borda e entre peças.\n"
             "Contornos do nome, ramos, flores e frente SUAVIZADOS (o PDF era traçado de imagem, com degraus).\n"
             "REBAIXO (C03, gravado, 1º): o assento de cada aplicação na frente, com o MESMO contorno da peça, na "
             "posição do PDF — sem folga. Só onde há MDF (não grava a janela) e não atravessa. Profundidade: teste "
             "C03 num retalho (1500 mm/min, 60 %, 2 passadas) e ajuste velocidade/passadas.\n"
             "Cores: Luana amarelo; ramos R01–R04 verde; flores F01/F02 rosa; frente branca.\n"
             "Ordem: C03 rebaixo → C05/C06 peças dentro de vazados → C02 janela e vazados → C01 contornos (630/85/2 "
             "conforme o material).\nMontagem: espaçadores P02–P04 atrás da frente (canal de cima livre para a foto), "
             "fundo P05, apoios P06/P07 em X35 e X95 do verso.")
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
