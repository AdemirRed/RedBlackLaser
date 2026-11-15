"""Gabarito 1:1 (folha A4) para colar os corações do porta-retrato Isabella e Nathan na posição da vista frontal.

Lê a vista frontal do PDF (p. 1, vetores em escala: base de 426 mm), separa os 2 cantos com corações (12 embaixo à
esquerda, 6 embaixo à direita) e grava só as linhas visíveis (coração de cima esconde o de baixo), as bordas da frente
e da janela. Cada canto tem uma moldura: recorte a folha nela e encoste no canto de baixo da frente (borda externa +
topo da base).

Executar:  python tools/projetos/porta_retrato_gabarito_coracoes.py <projeto.pdf> <saida.rbl>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402

CAMADA = "C01"
# canto: (nome, janela x0..x1 da frente em mm, onde fica a borda externa, posição na folha A4)
CANTOS = [("ESQUERDA", (0.0, 80.0), -98.0, 0.0, 15.0, 113.0, "borda esquerda"),
          ("DIREITA", (322.0, 414.0), -86.0, 414.0, 130.0, 101.0, "borda direita")]
JANELAS = {"ESQUERDA": (12.0, -15.0), "DIREITA": (399.0, -15.0)}  # borda lateral e de baixo da janela (vista)


def coracoes(pdf):
    """[(QPainterPath em mm, x, y)] na ordem de desenho; origem: canto de baixo à esquerda da frente (topo da base)."""
    pg = pymupdf.open(pdf)[0]
    ds = pg.get_drawings()
    base = next(d["rect"] for d in ds if d["items"][0][0] == "re" and 405 < d["rect"].width < 415
                and d["rect"].height < 12)
    k = base.width / 426.0                         # pt por mm
    x0 = base.x0 + 6 * k                           # a base passa 6 mm de cada lado da frente
    y0 = base.y0

    def mm(p):
        return QPointF((p.x - x0) / k, (p.y - y0) / k)

    out = []
    for d in ds:
        r = d["rect"]
        w, h = r.width / k, r.height / k
        cor = d.get("fill") or ()
        # corações: polígonos pequenos (10-45 mm), cor de madeira clara, encostados na parte de baixo da frente
        if not (8 < w < 46 and 8 < h < 46 and len(d["items"]) > 60 and cor and cor[0] > 0.85
                and (r.y1 - y0) / k > -100 and (r.y1 - y0) / k <= 0.5):
            continue
        p = QPainterPath()
        atual = None
        for it in d["items"]:
            a, b = mm(it[1]), mm(it[-1])
            if atual is None or (a - atual).manhattanLength() > 1e-3:
                if atual is not None:
                    p.closeSubpath()
                p.moveTo(a)
            p.lineTo(b)
            atual = b
        p.closeSubpath()
        out.append(p)
    return out


def _unir(ps):
    u = QPainterPath()
    for p in ps:
        u = u.united(p)
    return u


def escondida(linha, tampa, passo=0.2):
    """A linha aberta sem os trechos que ficam embaixo dos corações (amostra a cada `passo` mm)."""
    out = QPainterPath()
    n = max(1, int(linha.length() / passo))
    dentro = True
    for i in range(n + 1):
        p = linha.pointAtPercent(linha.percentAtLength(min(i * passo, linha.length())))
        coberto = tampa.contains(p)
        if not coberto:
            out.lineTo(p) if not dentro else out.moveTo(p)
        dentro = coberto
    return out


def gerar(pdf, saida):
    todos = coracoes(pdf)
    assert len(todos) == 18, f"esperava 18 corações na vista frontal, achei {len(todos)}"
    lid, cor = CAMADA, cm.cor(CAMADA)
    snaps = []
    for nome, (xa, xb), ytopo, _borda, ax, ay, borda in CANTOS:
        grupo = [p for p in todos if xa <= p.boundingRect().center().x() <= xb]
        tf = QTransform.fromTranslate(ax - xa, ay)  # mm da frente -> mm da folha A4
        vis = [p.subtracted(_unir(grupo[i + 1:])) for i, p in enumerate(grupo)]
        for i, p in enumerate(vis, 1):
            snaps.append(ob.Shape(tf.map(p), f"{nome}: coração {i}", lid, cor).snapshot())
        moldura = QPainterPath()
        moldura.addRect(QRectF(xa, ytopo, xb - xa, -ytopo))
        snaps.append(ob.Shape(tf.map(moldura), f"{nome}: moldura (recortar)", lid, cor).snapshot())
        jx, jy = JANELAS[nome]
        jan = QPainterPath()
        if nome == "ESQUERDA":
            jan.moveTo(jx, ytopo)
            jan.lineTo(jx, jy)
            jan.lineTo(xb, jy)
        else:
            jan.moveTo(xa, jy)
            jan.lineTo(jx, jy)
            jan.lineTo(jx, ytopo)
        snaps.append(ob.Shape(tf.map(escondida(jan, _unir(grupo))), f"{nome}: borda da janela", lid, cor).snapshot())
        for t, h, dy in ((f"{nome} ({len(grupo)} corações)", 4.0, 6.0),
                         (f"encoste: {borda} da frente + topo da base", 2.6, 11.0)):
            prm = tx.TextoParams(t, "Arial", h, negrito=True, alinhamento="esquerda")
            snaps.append((tx.build_path(prm), QTransform.fromTranslate(ax, ay + dy), f"Texto {nome}", lid, cor, prm))
    camada = cm.alterar(cm.Camada(CAMADA, "Gabarito (gravação superficial na folha)"), modo="linha",
                        velocidade_mm_min=3000.0, potencia_max=15.0, potencia_min=0.0, passadas=1)
    pj.save(saida, snaps, [camada],
            notas="Gabarito 1:1 dos corações (vista frontal do PDF). Folha A4 deitada no canto de origem da mesa.\n"
                  "Gravar a 15 %/3000 (teste antes: papel/cartão queima fácil). Recorte cada moldura, encoste no "
                  "canto de baixo da frente (borda externa + topo da base) e cole os corações sobre os desenhos.")
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
