"""Aparar formas (tesoura): remove o trecho de um contorno entre os dois cruzamentos mais próximos do clique.

Tudo em mm de cena. O contorno aparado vira polilinha (curvas achatadas com erro < 0,0125 mm); os demais
contornos do mesmo objeto ficam como estão (curvas preservadas).
"""
import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath, QTransform

from . import formas as fm

_ESC = 20.0  # mesmo achatamento do percurso: erro de curva < 0,0125 mm
EPS = 1e-9
TOQUE_MM = 0.2  # ponta/nó de outra linha a até 0,2 mm do contorno = encosta (junta em "T"): também corta ali


def _polilinha(sub: QPainterPath):
    """(pontos, fechado) de um contorno."""
    polys = sub.toSubpathPolygons(QTransform.fromScale(_ESC, _ESC))
    if not polys:
        return [], False
    pts = [(p.x() / _ESC, p.y() / _ESC) for p in polys[0]]
    limpos = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, limpos[-1]) > EPS:
            limpos.append(p)
    fechado = len(limpos) > 2 and math.dist(limpos[0], limpos[-1]) < 1e-6
    if fechado:
        limpos[-1] = limpos[0]
    return limpos, fechado


def _cum(pts):
    c = [0.0]
    for a, b in zip(pts, pts[1:]):
        c.append(c[-1] + math.dist(a, b))
    return c


def _cruza(p1, p2, q1, q2):
    """Parâmetro t em [0, 1] sobre p1→p2 onde cruza q1→q2, ou None."""
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    qx, qy = q1[0] - p1[0], q1[1] - p1[1]
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    return t if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9 else None


def _caixa(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _trecho(pts, cum, s0, s1):
    """Pontos da polilinha entre as distâncias s0 < s1 (pontas interpoladas)."""
    def ponto(s):
        for i in range(len(cum) - 1):
            if cum[i] - EPS <= s <= cum[i + 1] + EPS:
                L = cum[i + 1] - cum[i]
                t = 0.0 if L < EPS else (s - cum[i]) / L
                a, b = pts[i], pts[i + 1]
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        return pts[-1]
    out = [ponto(s0)] + [pts[i] for i in range(len(pts)) if s0 + EPS < cum[i] < s1 - EPS] + [ponto(s1)]
    return out


def _distancia(pt, a, b):
    """(distância, posição ao longo do segmento)."""
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 < EPS else max(0.0, min(1.0, ((pt[0] - a[0]) * vx + (pt[1] - a[1]) * vy) / L2))
    q = (a[0] + vx * t, a[1] + vy * t)
    return math.dist(pt, q), t * math.sqrt(L2)


def aparar(alvo: QPainterPath, outros, ponto: QPointF, tol: float):
    """(novo caminho, trecho removido) ou None se o clique não estiver a `tol` mm do alvo.

    `outros`: caminhos (mm de cena) que cortam o alvo. Outros contornos do próprio alvo também cortam.
    Sem cruzamentos no contorno clicado, o contorno inteiro é removido.
    """
    subs = fm.subcaminhos(alvo)
    linhas = [_polilinha(s) for s in subs]
    pt = (ponto.x(), ponto.y())
    melhor = None
    for k, (pts, _) in enumerate(linhas):
        cum = _cum(pts)
        for i in range(len(pts) - 1):
            d, pos = _distancia(pt, pts[i], pts[i + 1])
            if melhor is None or d < melhor[0]:
                melhor = (d, k, cum[i] + pos)
    if melhor is None or melhor[0] > tol:
        return None
    _, k, s_clique = melhor
    pts, fechado = linhas[k]
    cum = _cum(pts)
    L = cum[-1]
    cx0, cy0, cx1, cy1 = _caixa(pts)
    cortes = []
    for o in [p for j, (p, _) in enumerate(linhas) if j != k] + \
             [_polilinha(s)[0] for p in outros for s in fm.subcaminhos(p)]:
        if len(o) < 2:
            continue
        ox0, oy0, ox1, oy1 = _caixa(o)
        if ox1 < cx0 or ox0 > cx1 or oy1 < cy0 or oy0 > cy1:
            continue
        for i in range(len(pts) - 1):
            for j in range(len(o) - 1):
                t = _cruza(pts[i], pts[i + 1], o[j], o[j + 1])
                if t is not None:
                    cortes.append(cum[i] + t * (cum[i + 1] - cum[i]))
        # linha que só ENCOSTA (termina em cima do contorno ou passa raspando num nó) também divide o contorno
        for q in (o[0], o[-1]) if math.dist(o[0], o[-1]) > EPS else ():
            perto = min(((_distancia(q, pts[i], pts[i + 1]), i) for i in range(len(pts) - 1)), default=None)
            if perto is not None and perto[0][0] <= TOQUE_MM:
                cortes.append(cum[perto[1]] + perto[0][1])
    if not fechado and len(pts) > 2:  # a própria linha que termina em cima de si mesma (ex.: contorno que encosta)
        for q, s_q in ((pts[0], 0.0), (pts[-1], L)):
            for i in range(len(pts) - 1):
                d, pos = _distancia(q, pts[i], pts[i + 1])
                s_i = cum[i] + pos
                if d <= TOQUE_MM and abs(s_i - s_q) > 5 * TOQUE_MM:
                    cortes.append(s_i)
    cortes = sorted(set(round(c, 9) for c in cortes if (0 < c < L) or fechado))
    if fechado:
        cortes = sorted(set(c % L for c in cortes))
    manter, removido = [], []
    if fechado:
        if len(cortes) < 2:
            removido = [pts]
        else:
            antes = [c for c in cortes if c < s_clique]
            depois = [c for c in cortes if c > s_clique]
            a = antes[-1] if antes else cortes[-1] - L      # cruzamento anterior (pode dar a volta)
            b = depois[0] if depois else cortes[0] + L      # próximo
            dobro, cum2 = pts + pts[1:], cum + [L + c for c in cum[1:]]
            base = a if a >= 0 else a + L
            fim_rem = b if a >= 0 else b + L
            removido = [_trecho(dobro, cum2, base, fim_rem)]
            manter = [_trecho(dobro, cum2, fim_rem, base + L)]
    else:
        antes = [c for c in cortes if c < s_clique]
        depois = [c for c in cortes if c > s_clique]
        a, b = (antes[-1] if antes else 0.0), (depois[0] if depois else L)
        removido = [_trecho(pts, cum, a, b)]
        if a > EPS:
            manter.append(_trecho(pts, cum, 0.0, a))
        if b < L - EPS:
            manter.append(_trecho(pts, cum, b, L))
    novo = QPainterPath()
    novo.setFillRule(alvo.fillRule())
    for j, s in enumerate(subs):
        if j != k:
            novo.addPath(s)
    for m in manter:
        if len(m) >= 2:
            novo.addPath(fm.polyline_path([QPointF(*p) for p in m]))
    rem = QPainterPath()
    for m in removido:
        if len(m) >= 2:
            rem.addPath(fm.polyline_path([QPointF(*p) for p in m]))
    return novo, rem
