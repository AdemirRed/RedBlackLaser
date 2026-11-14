"""Redimensionar slots (ranhuras de encaixe): acha encaixes retos de uma largura e troca a largura.

Um slot = três segmentos retos seguidos A→B, B→C, C→D em que |BC| é a largura procurada e AB e CD são
paredes paralelas, em sentidos opostos e perpendiculares a BC. As duas paredes se afastam (ou aproximam) por
igual ao longo de BC, então o slot continua centrado; A e D deslizam sobre as bordas vizinhas.
shortcut: só segmentos retos e só slots que não passam pelo ponto inicial do contorno; para slots sobre o
ponto inicial ou com cantos arredondados, girar o início do contorno / reconhecer arcos.
"""
import math

from PySide6.QtGui import QPainterPath

ANG_TOL = math.radians(1.0)


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n, n) if n > 1e-9 else None


def _eh_slot(a, b, c, d, largura, tol):
    ab, bc, cd = _unit(a, b), _unit(b, c), _unit(c, d)
    if not (ab and bc and cd) or abs(bc[2] - largura) > tol:
        return None
    perp = abs(ab[0] * bc[0] + ab[1] * bc[1]) < math.sin(ANG_TOL) and abs(cd[0] * bc[0] + cd[1] * bc[1]) < math.sin(ANG_TOL)
    opostas = ab[0] * cd[0] + ab[1] * cd[1] < -math.cos(ANG_TOL)
    return (bc[0], bc[1]) if perp and opostas else None


def redimensionar(path: QPainterPath, largura, nova, tol=0.05):
    """(novo caminho, quantos slots mudaram). Caminho em mm de cena."""
    if nova <= 0 or largura <= 0:
        raise ValueError("larguras devem ser positivas")
    els = [(path.elementAt(i).type, path.elementAt(i).x, path.elementAt(i).y) for i in range(path.elementCount())]
    pts = [[e[1], e[2]] for e in els]
    reto = [e[0] in (QPainterPath.MoveToElement, QPainterPath.LineToElement) for e in els]
    inicio = [e[0] == QPainterPath.MoveToElement for e in els]
    n, mudou, i = len(els), 0, 0
    orig = [tuple(p) for p in pts]
    while i + 3 < n:
        janela = range(i, i + 4)
        if all(reto[k] for k in janela) and not any(inicio[k] for k in range(i + 1, i + 4)):
            u = _eh_slot(*(orig[k] for k in janela), largura, tol)
            if u:
                d = (nova - largura) / 2
                for k, s in ((i, -1), (i + 1, -1), (i + 2, 1), (i + 3, 1)):
                    pts[k][0] += s * d * u[0]
                    pts[k][1] += s * d * u[1]
                mudou += 1
                i += 3  # o próximo slot começa depois da borda que sai de D
                continue
        i += 1
    # contorno fechado: o último ponto acompanha o primeiro (e vice-versa) se ambos eram o mesmo ponto
    sub = [k for k in range(n) if inicio[k]] + [n]
    for a, b in zip(sub, sub[1:]):
        last = b - 1
        if last > a and orig[last] == orig[a]:
            if pts[a] != list(orig[a]):
                pts[last] = list(pts[a])
            elif pts[last] != list(orig[last]):
                pts[a] = list(pts[last])
    out = QPainterPath()
    out.setFillRule(path.fillRule())
    k = 0
    while k < n:
        t = els[k][0]
        if t == QPainterPath.MoveToElement:
            out.moveTo(*pts[k])
        elif t == QPainterPath.LineToElement:
            out.lineTo(*pts[k])
        elif t == QPainterPath.CurveToElement:
            out.cubicTo(*pts[k], *pts[k + 1], *pts[k + 2])
            k += 2
        k += 1
    return out, mudou
