"""Corações do porta-retrato Isabella e Nathan já UNIDOS, para cortar em MDF 3 mm e colar de uma vez.

Lê a vista frontal do PDF (p. 1, vetores em escala: base de 426 mm) e junta os corações de cada canto (12 embaixo à
esquerda, 6 embaixo à direita) numa peça só, na posição do desenho. As divisas visíveis entre eles (o de cima esconde o
de baixo) são gravadas fracas (15 %, 3000 mm/min); a união é cortada (800 mm/min, 85 %).

Executar:  python tools/projetos/porta_retrato_coracoes_unidos.py <projeto.pdf> <saida.rbl>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

CANTOS = [("ESQUERDA", (0.0, 80.0)), ("DIREITA", (322.0, 414.0))]  # faixa x (mm da frente) de cada canto


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


def trechos(contorno, manter, passo=0.2):
    """Partes de cada subcaminho (fechado) de `contorno` cujos pontos satisfazem `manter` (amostra a cada `passo`)."""
    out = QPainterPath()
    for poli in contorno.toSubpathPolygons():
        linha = QPainterPath()
        linha.addPolygon(poli)
        n = max(1, int(linha.length() / passo))
        fora = True
        for k in range(n + 1):
            p = linha.pointAtPercent(linha.percentAtLength(min(k * passo, linha.length())))
            if manter(p):
                out.moveTo(p) if fora else out.lineTo(p)
                fora = False
            else:
                fora = True
    return out


def _engrossar(p, w):
    st = QPainterPathStroker()
    st.setWidth(w)
    st.setJoinStyle(Qt.RoundJoin)  # sem pontas de esquadria no contorno
    st.setCapStyle(Qt.RoundCap)
    return st.createStroke(p)


def _crescer(p, r, n=24):
    """p crescido r mm para todos os lados (soma com um círculo de n cópias deslocadas: sem pontas de stroker)."""
    return _unir([p] + [p.translated(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n))
                        for k in range(n)])


def _fechar(p, r):
    """Fechamento morfológico: cresce r e encolhe r (preenche frestas e pescoços menores que 2r, arredondado)."""
    g = _crescer(p, r)
    caixa = QPainterPath()
    caixa.addRect(g.boundingRect().adjusted(-3 * r, -3 * r, 3 * r, 3 * r))
    return g.subtracted(_crescer(caixa.subtracted(g), r))


def camadas():
    corte = {"modo": "linha", "velocidade_mm_min": 800.0, "potencia_max": 85.0, "potencia_min": 0.0, "passadas": 2}
    return [cm.alterar(cm.Camada("C03", "Linhas dos corações (gravação fraca, 1º)"), modo="linha",
                       velocidade_mm_min=3000.0, potencia_max=15.0, potencia_min=0.0, passadas=1),
            cm.alterar(cm.Camada("C02", "MDF 3: vãos entre corações (2º)"), **corte),
            cm.alterar(cm.Camada("C01", "MDF 3: contorno do conjunto (por último)"), **corte)]


def gerar(pdf, saida):
    """Cada canto vira UMA peça de MDF 3 mm (união dos corações), com as divisas gravadas fracas."""
    todos = coracoes(pdf)
    assert len(todos) == 18, f"esperava 18 corações na vista frontal, achei {len(todos)}"
    snaps, x_livre = [], 5.0
    for nome, (xa, xb) in CANTOS:
        grupo = [p for p in todos if xa <= p.boundingRect().center().x() <= xb]
        # "fechamento" de 1,5 mm (cresce e encolhe): onde dois corações se tocam numa pontinha ou deixam uma fresta,
        # a ligação fica cheia e arredondada (senão a peça quebra ali); o resto do contorno não muda
        base = _unir(grupo)
        uniao = base.united(_fechar(base, 1.5)).simplified()
        r = uniao.boundingRect()
        tf = QTransform.fromTranslate(x_livre - r.left(), 5.0 - r.top())
        x_livre += r.width() + 8
        polis = uniao.toSubpathPolygons()
        externos = [q for q in polis if not any(o is not q and o.containsPoint(q[0], Qt.OddEvenFill) for o in polis)]
        assert len(externos) == 1, f"{nome}: os corações não formam uma peça só ({len(externos)} partes)"
        miolo = uniao.subtracted(_engrossar(uniao, 1.0))  # 0,5 mm para dentro: não gravar em cima do corte
        for i, p in enumerate(grupo, 1):
            vis = p.subtracted(_unir(grupo[i:]))           # só a parte que aparece (os de cima escondem)
            linhas = trechos(vis, miolo.contains)
            if not linhas.isEmpty():
                snaps.append(ob.Shape(tf.map(linhas), f"{nome}: divisa coração {i}", "C03", cm.cor("C03")).snapshot())
        for q in polis:
            if not any(q is e for e in externos) and max(q.boundingRect().width(), q.boundingRect().height()) < 3:
                continue  # vãozinho menor que 3 mm: fica cheio (não vale o corte)
            p = QPainterPath()
            p.addPolygon(q)
            p.closeSubpath()
            ext = any(q is e for e in externos)
            lid = "C01" if ext else "C02"
            snaps.append(ob.Shape(tf.map(p), f"{nome}: {'contorno' if ext else 'vão'}", lid, cm.cor(lid)).snapshot())
    pj.save(saida, snaps, camadas(),
            notas="Corações do porta-retrato Isabella e Nathan já UNIDOS: 2 peças de MDF 3 mm (canto esquerdo com 12 e "
                  "canto direito com 6), na posição da vista frontal do PDF.\n"
                  "C03 grava fraco (3000 mm/min, 15 %) as divisas entre os corações; C02/C01 cortam (800 mm/min, 85 %, "
                  "2 passadas).\nCole a peça da esquerda no canto de baixo da frente esquerda (ponta dos corações no "
                  "topo da base, lado esquerdo rente à borda) e a da direita no canto de baixo da frente direita.")
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
