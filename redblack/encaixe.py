"""Encaixe ("conexão") em cantos e pontos — para medir e desenhar com precisão.

Alvos, em coordenadas de documento (mm):
  - "canto": nós de caminhos (cantos de retângulo, vértices de polígono/linha, extremos de curva);
  - "centro": centro da caixa de cada objeto;
  - "mesa": cantos e centro da área de trabalho;
  - "início": primeiro ponto da linha em desenho (fechar o contorno);
  - "ponto": demais pontos já clicados na linha em desenho;
  - "linha": qualquer ponto do contorno de um objeto (o mais perto do cursor), quando não há nenhum dos acima.
Textos e imagens oferecem só os cantos e o centro da caixa (os nós dos glifos seriam ruído).
"""
import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform

from . import formas as fm
from .percurso import folhas

MAX_NOS_POR_OBJETO = 2000
PRIORIDADE = {"início": 0, "canto": 1, "ponto": 1, "mesa": 2, "centro": 3, "linha": 4}  # empate: canto antes de centro


@dataclass(frozen=True)
class Alvo:
    x: float
    y: float
    tipo: str


def _cantos_caixa(r):
    return [(r.left(), r.top()), (r.right(), r.top()), (r.right(), r.bottom()), (r.left(), r.bottom())]


def alvos_de_snapshot(snap) -> list:
    out = []
    for path, tf, _layer, extra in folhas(snap):
        caixa = tf.map(path).boundingRect()
        if extra is None:  # vetor comum: nós reais
            nos = fm.nodes(path)
            if len(nos) <= MAX_NOS_POR_OBJETO:
                for i in nos:
                    e = path.elementAt(i)
                    p = tf.map(QPointF(e.x, e.y))
                    out.append(Alvo(p.x(), p.y(), "canto"))
            else:
                out += [Alvo(x, y, "canto") for x, y in _cantos_caixa(caixa)]
        else:  # texto ou imagem: só a caixa
            out += [Alvo(x, y, "canto") for x, y in _cantos_caixa(caixa)]
        c = caixa.center()
        out.append(Alvo(c.x(), c.y(), "centro"))
    return out


_FINO = 20.0  # achatar curvas em 1/20 mm (o Qt achata em ~1 unidade)


def ponto_na_linha(snaps, x, y, raio):
    """Alvo "linha": o ponto mais próximo de (x, y) sobre o contorno de qualquer objeto, a até `raio` mm."""
    melhor, md = None, raio
    for snap in snaps:
        for path, tf, _layer, _extra in folhas(snap):
            caixa = tf.map(path).boundingRect().adjusted(-raio, -raio, raio, raio)
            if not caixa.contains(QPointF(x, y)):
                continue
            for poly in path.toSubpathPolygons(tf * QTransform.fromScale(_FINO, _FINO)):
                pts = [(q.x() / _FINO, q.y() / _FINO) for q in poly]
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    vx, vy = bx - ax, by - ay
                    L2 = vx * vx + vy * vy
                    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / L2))
                    px, py = ax + t * vx, ay + t * vy
                    d = math.hypot(px - x, py - y)
                    if d <= md:
                        melhor, md = Alvo(px, py, "linha"), d
    return melhor


LADOS = ("esq", "dir", "cima", "baixo")


def distancias_lados(caixa, snaps, largura, altura) -> dict:
    """Distância de cada lado da caixa (esq, topo, dir, base em mm, Y para baixo) até o primeiro contorno de outro
    objeto (ou a borda da mesa), em linha reta a partir do MEIO do lado.

    {"esq"|"dir"|"cima"|"baixo": (distância, (x, y) no lado, (x, y) onde a linha toca)} — só lados com algo.
    Serve para "furo a 3 mm da borda": a linha da esquerda de um furo toca o contorno da peça em volta dele.
    """
    l, t, r, b = caixa
    cx, cy = (l + r) / 2, (t + b) / 2
    melhor = {}
    if l >= -1e-9:
        melhor["esq"] = (l, (l, cy), (0.0, cy))
    if r <= largura + 1e-9:
        melhor["dir"] = (largura - r, (r, cy), (largura, cy))
    if t >= -1e-9:
        melhor["cima"] = (t, (cx, t), (cx, 0.0))
    if b <= altura + 1e-9:
        melhor["baixo"] = (altura - b, (cx, b), (cx, altura))
    for snap in snaps:
        for path, tf, _layer, _extra in folhas(snap):
            bb = tf.map(path).boundingRect()
            horiz = bb.top() <= cy <= bb.bottom()
            vert = bb.left() <= cx <= bb.right()
            if not (horiz or vert):
                continue
            for poly in path.toSubpathPolygons(tf * QTransform.fromScale(_FINO, _FINO)):
                pts = [(q.x() / _FINO, q.y() / _FINO) for q in poly]
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if horiz and (ay - cy) * (by - cy) <= 0 and ay != by:
                        x = ax + (cy - ay) * (bx - ax) / (by - ay)
                        for lado, d, ini in (("esq", l - x, (l, cy)), ("dir", x - r, (r, cy))):
                            if d >= -1e-9 and (lado not in melhor or d < melhor[lado][0]):
                                melhor[lado] = (max(d, 0.0), ini, (x, cy))
                    if vert and (ax - cx) * (bx - cx) <= 0 and ax != bx:
                        y = ay + (cx - ax) * (by - ay) / (bx - ax)
                        for lado, d, ini in (("cima", t - y, (cx, t)), ("baixo", y - b, (cx, b))):
                            if d >= -1e-9 and (lado not in melhor or d < melhor[lado][0]):
                                melhor[lado] = (max(d, 0.0), ini, (cx, y))
    return melhor


def deslocamento_para(lado, atual, novo) -> tuple:
    """(dx, dy) que deixa a distância daquele lado igual a `novo` (mm)."""
    d = novo - atual
    return {"esq": (d, 0.0), "dir": (-d, 0.0), "cima": (0.0, d), "baixo": (0.0, -d)}[lado]


def alvos_mesa(largura, altura) -> list:
    return [Alvo(x, y, "mesa") for x, y in ((0, 0), (largura, 0), (largura, altura), (0, altura),
                                             (largura / 2, altura / 2))]


def mais_proximo(x, y, alvos, raio):
    """Alvo mais próximo dentro do raio (mm); em empate de distância vence a prioridade do tipo."""
    melhor, chave = None, None
    for a in alvos:
        d = math.hypot(a.x - x, a.y - y)
        if d <= raio:
            k = (round(d, 9), PRIORIDADE.get(a.tipo, 9))
            if chave is None or k < chave:
                melhor, chave = a, k
    return melhor


def _eixo(meus, alvos, tol):
    """Melhor deslocamento (ou None) para um dos meus valores coincidir com um valor dos alvos."""
    melhor = None
    for v in alvos:
        for o in meus:
            d = v - o
            if abs(d) <= tol and (melhor is None or abs(d) < abs(melhor)):
                melhor = d
    return melhor


def guias_alinhamento(caixa, outras, tol, eps=1e-6):
    """Guias inteligentes ao arrastar: (dx, dy, segmentos).

    caixa/outras = (esquerda, topo, direita, base) em mm. Bordas e centro da caixa encaixam nas bordas e
    centros das outras (dentro de `tol`); dx/dy é o ajuste (0 se nada perto). Segmentos = linhas a mostrar,
    ((x1, y1), (x2, y2)), ligando a caixa já ajustada a cada outra alinhada com ela.
    """
    def xs(r):
        return (r[0], (r[0] + r[2]) / 2, r[2])

    def ys(r):
        return (r[1], (r[1] + r[3]) / 2, r[3])

    dx = _eixo(xs(caixa), [v for r in outras for v in xs(r)], tol) or 0.0
    dy = _eixo(ys(caixa), [v for r in outras for v in ys(r)], tol) or 0.0
    c = (caixa[0] + dx, caixa[1] + dy, caixa[2] + dx, caixa[3] + dy)
    segs = []
    for r in outras:
        for x in xs(c):
            if any(abs(x - v) <= eps for v in xs(r)):
                segs.append(((x, min(c[1], r[1])), (x, max(c[3], r[3]))))
        for y in ys(c):
            if any(abs(y - v) <= eps for v in ys(r)):
                segs.append(((min(c[0], r[0]), y), (max(c[2], r[2]), y)))
    return dx, dy, segs
