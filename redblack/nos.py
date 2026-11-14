"""Operações de edição de nós sobre um caminho (coordenadas locais do objeto).

Estrutura intermediária: lista de contornos {"ini": (x, y), "segs": [("L", p) | ("C", c1, c2, p)], "fechado": bool};
num contorno fechado o último segmento termina no ponto inicial (o nó inicial aparece uma vez só).
Nós de um contorno: índice 0 = início, k = fim do segmento k-1 (k = 1..n; no fechado, n é o próprio início).
"""
import math

from PySide6.QtGui import QPainterPath


def estrutura(path: QPainterPath) -> list:
    out, i, n, cur = [], 0, path.elementCount(), None
    while i < n:
        e = path.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            cur = {"ini": (e.x, e.y), "segs": [], "fechado": False}
            out.append(cur)
        elif e.type == QPainterPath.LineToElement:
            cur["segs"].append(("L", (e.x, e.y)))
        elif e.type == QPainterPath.CurveToElement:
            c2, fim = path.elementAt(i + 1), path.elementAt(i + 2)
            cur["segs"].append(("C", (e.x, e.y), (c2.x, c2.y), (fim.x, fim.y)))
            i += 2
        i += 1
    for c in out:
        if c["segs"] and math.dist(c["segs"][-1][-1], c["ini"]) < 1e-9 and len(c["segs"]) > 1:
            c["fechado"] = True
    return [c for c in out if c["segs"]]


def montar(estr, regra) -> QPainterPath:
    p = QPainterPath()
    p.setFillRule(regra)
    for c in estr:
        p.moveTo(*c["ini"])
        for s in c["segs"]:
            if s[0] == "L":
                p.lineTo(*s[1])
            else:
                p.cubicTo(*s[1], *s[2], *s[3])
    return p


def _inicio(c, k):
    return c["ini"] if k == 0 else c["segs"][k - 1][-1]


def _ponto_seg(a, s, t):
    if s[0] == "L":
        b = s[1]
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    p0, p1, p2, p3 = a, s[1], s[2], s[3]
    u = 1 - t
    return tuple(u ** 3 * p0[i] + 3 * u * u * t * p1[i] + 3 * u * t * t * p2[i] + t ** 3 * p3[i] for i in (0, 1))


def localizar(path: QPainterPath, pt, tol):
    """("no", contorno, nó) se pt está a `tol` de um nó; senão ("seg", contorno, segmento, t); senão None."""
    estr = estrutura(path)
    melhor = None
    for ci, c in enumerate(estr):
        n = len(c["segs"])
        for k in range(n if c["fechado"] else n + 1):
            d = math.dist(pt, _inicio(c, k))
            if d <= tol and (melhor is None or d < melhor[0]):
                melhor = (d, ("no", ci, k))
    if melhor:
        return melhor[1]
    for ci, c in enumerate(estr):
        for k, s in enumerate(c["segs"]):
            a = _inicio(c, k)
            for j in range(1, 65):
                t = j / 64
                d = math.dist(pt, _ponto_seg(a, s, t))
                if d <= tol and (melhor is None or d < melhor[0]):
                    melhor = (d, ("seg", ci, k, t))
    return melhor[1] if melhor else None


def _dividir(a, s, t):
    """Dois segmentos que juntos são o segmento s (que começa em a), cortado em t."""
    if s[0] == "L":
        m = _ponto_seg(a, s, t)
        return ("L", m), ("L", s[1])
    p0, p1, p2, p3 = a, s[1], s[2], s[3]
    lerp = lambda u, v: (u[0] + (v[0] - u[0]) * t, u[1] + (v[1] - u[1]) * t)  # noqa: E731
    a1, b1, c1 = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    a2, b2 = lerp(a1, b1), lerp(b1, c1)
    m = lerp(a2, b2)
    return ("C", a1, a2, m), ("C", b2, c1, p3)


def inserir_no(path, ci, k, t):
    estr = estrutura(path)
    c = estr[ci]
    c["segs"][k:k + 1] = list(_dividir(_inicio(c, k), c["segs"][k], t))
    return montar(estr, path.fillRule())


def excluir_no(path, ci, k):
    """Remove o nó: os dois segmentos vizinhos viram uma reta. Contorno que ficaria com menos de 2 pontos some."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    if c["fechado"]:
        if n <= 2:
            del estr[ci]
        elif k == 0:  # o início passa a ser o próximo nó
            c["ini"] = c["segs"][0][-1]
            c["segs"] = c["segs"][1:-1] + [("L", c["ini"])]
        else:
            c["segs"][k - 1:k + 1] = [("L", c["segs"][k][-1])]
    else:
        if n <= 1:
            del estr[ci]
        elif k == 0:
            c["ini"] = c["segs"][0][-1]
            c["segs"] = c["segs"][1:]
        elif k == n:
            c["segs"] = c["segs"][:-1]
        else:
            c["segs"][k - 1:k + 1] = [("L", c["segs"][k][-1])]
    return montar(estr, path.fillRule())


def alternar_reta_curva(path, ci, k):
    """L: reta vira curva (alças a 1/3 e 2/3, mesma forma até mexer nelas); curva vira reta."""
    estr = estrutura(path)
    c = estr[ci]
    s = c["segs"][k]
    if s[0] == "C":
        c["segs"][k] = ("L", s[-1])
    else:
        a, b = _inicio(c, k), s[1]
        c["segs"][k] = ("C", (a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3),
                        (a[0] + (b[0] - a[0]) * 2 / 3, a[1] + (b[1] - a[1]) * 2 / 3), b)
    return montar(estr, path.fillRule())


def cantos_boleaveis(path) -> list:
    """[(contorno, nó, (x, y))] dos cantos entre duas RETAS (os que dá para bolear), mesmo em formas com curvas."""
    out = []
    for ci, c in enumerate(estrutura(path)):
        n = len(c["segs"])
        nos_ = range(n) if c["fechado"] else range(1, n)
        for k in nos_:
            entra, sai = c["segs"][(k - 1) % n], c["segs"][k % n]
            if entra[0] == "L" and sai[0] == "L":
                out.append((ci, k, _inicio(c, k)))
    return out


def bolear(path, r, alvos=None):
    """Arredonda (boleia) com raio r os cantos entre duas retas: todos, ou só os de `alvos` [(contorno, nó)].
    Devolve (novo caminho, quantos cantos). O recuo em cada reta é no máximo metade dela (com r grande, um retângulo
    vira pontas totalmente redondas, como uma pega). Trechos curvos ficam como estão."""
    from PySide6.QtCore import QPointF
    from .formas import _filete
    if r <= 0:
        return QPainterPath(path), 0
    estr, total = estrutura(path), 0
    escolhidos = None if alvos is None else set(alvos)
    for ci, c in enumerate(estr):
        n = len(c["segs"])
        P = [_inicio(c, k) for k in range(n + 1)]
        fil = {}
        for k in (range(n) if c["fechado"] else range(1, n)):
            if c["segs"][(k - 1) % n][0] != "L" or c["segs"][k % n][0] != "L":
                continue  # só cantos entre duas retas
            if escolhidos is not None and (ci, k) not in escolhidos:
                continue
            ant = P[k - 1] if k > 0 else P[n - 1]  # no fechado, o nó 0 vem depois do último trecho
            f = _filete(QPointF(*P[k]), QPointF(*ant), QPointF(*P[k + 1]), r)
            if f:
                fil[k] = tuple((q.x(), q.y()) for q in f)
        if not fil:
            continue
        total += len(fil)
        novos = []
        for k, s in enumerate(c["segs"]):
            fim = (k + 1) % n if c["fechado"] else k + 1
            if s[0] == "L":
                f = fil.get(fim)
                novos.append(("L", f[0] if f else s[1]))
                if f:
                    novos.append(("C", f[1], f[2], f[3]))
            else:
                novos.append(s)
        if c["fechado"] and 0 in fil:
            c["ini"] = fil[0][3]  # o contorno passa a começar no fim do arco do nó inicial
        c["segs"] = novos
    return montar(estr, path.fillRule()), total


def cantos_redondos(path) -> list:
    """[(contorno, trecho, (x, y) no meio)] dos arcos de bolear (curva entre duas retas)."""
    out = []
    for ci, c in enumerate(estrutura(path)):
        n = len(c["segs"])
        for k, s in enumerate(c["segs"]):
            if s[0] != "C" or (not c["fechado"] and (k == 0 or k == n - 1)):
                continue
            if c["segs"][(k - 1) % n][0] == "L" and c["segs"][(k + 1) % n][0] == "L":
                out.append((ci, k, _ponto_seg(_inicio(c, k), s, 0.5)))
    return out


def _intersecao(a, b, c, d):
    """Ponto onde a reta a-b encontra a reta c-d (None se paralelas)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    return (a[0] + t * r[0], a[1] + t * r[1])


def chanfros(path) -> list:
    """[(contorno, trecho, (x, y) no meio)] dos cantos em 45° (reta curta entre duas retas, simétrica, que dá para
    voltar a canto vivo)."""
    out = []
    for ci, c in enumerate(estrutura(path)):
        n = len(c["segs"])
        if n < 3:
            continue
        for k, s in enumerate(c["segs"]):
            if s[0] != "L" or (not c["fechado"] and (k == 0 or k == n - 1)):
                continue
            ant, prox = c["segs"][(k - 1) % n], c["segs"][(k + 1) % n]
            if ant[0] != "L" or prox[0] != "L":
                continue
            p0, p1 = _inicio(c, (k - 1) % n), _inicio(c, k)
            p2, p3 = s[1], prox[1]
            L = math.dist(p1, p2)
            if L < 1e-9 or L > 0.5 * min(math.dist(p0, p1), math.dist(p2, p3)):
                continue  # só reta curta (chanfro), não um lado da peça
            x = _intersecao(p0, p1, p2, p3)
            if x is None:
                continue
            if abs(math.dist(x, p1) - math.dist(x, p2)) > 1e-3 * max(1.0, L):
                continue  # chanfro simétrico (o que o bolear faz)
            out.append((ci, k, ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)))
    return out


def chanfrar(path, ci, k):
    """Arco do canto vira reta (canto em 45°)."""
    estr = estrutura(path)
    s = estr[ci]["segs"][k]
    estr[ci]["segs"][k] = ("L", s[-1])
    return montar(estr, path.fillRule())


def canto_vivo(path, ci, k):
    """Tira o trecho k (chanfro) estendendo as retas vizinhas até se encontrarem."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    p0, p1 = _inicio(c, (k - 1) % n), _inicio(c, k)
    p2, p3 = c["segs"][k][1], c["segs"][(k + 1) % n][1]
    x = _intersecao(p0, p1, p2, p3)
    if x is None:
        return None  # retas paralelas: não há canto para refazer
    c["segs"][(k - 1) % n] = ("L", x)
    del c["segs"][k]
    if c["fechado"] and k in (0, n - 1):
        c["ini"] = x  # o trecho tirado tocava o início do contorno: o canto refeito vira o início
    return montar(estr, path.fillRule())


def em_reta(path, ci, k):
    estr = estrutura(path)
    s = estr[ci]["segs"][k]
    estr[ci]["segs"][k] = ("L", s[-1])
    return montar(estr, path.fillRule())


def em_canto(path, ci, k):
    """Nó vira canto vivo: as alças das curvas vizinhas vão para o próprio nó."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    no = _inicio(c, k)
    entra = (k - 1) % n if c["fechado"] or k > 0 else None
    sai = k % n if c["fechado"] or k < n else None
    if entra is not None and c["segs"][entra][0] == "C":
        s = c["segs"][entra]
        c["segs"][entra] = ("C", s[1], no, s[3])
    if sai is not None and c["segs"][sai][0] == "C":
        s = c["segs"][sai]
        c["segs"][sai] = ("C", no, s[2], s[3])
    return montar(estr, path.fillRule())


def suavizar(path, ci, k):
    """Nó suave: os trechos vizinhos viram curvas com alças alinhadas (tangente = direção do nó anterior ao
    seguinte), cada alça com 1/3 do comprimento do seu trecho. Ponta de linha aberta não muda."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    k = k % n if c["fechado"] else k
    entra = (k - 1) % n if c["fechado"] or k > 0 else None
    sai = k if c["fechado"] or k < n else None
    if entra is None or sai is None:
        return path
    no = _inicio(c, k)
    ant, prox = _inicio(c, entra), c["segs"][sai][-1]
    tx, ty = prox[0] - ant[0], prox[1] - ant[1]
    L = math.hypot(tx, ty)
    if L < 1e-12:
        return path
    tx, ty = tx / L, ty / L
    d_in, d_out = math.dist(ant, no) / 3, math.dist(no, prox) / 3
    s = c["segs"][entra]
    c1 = s[1] if s[0] == "C" else (ant[0] + (no[0] - ant[0]) / 3, ant[1] + (no[1] - ant[1]) / 3)
    c["segs"][entra] = ("C", c1, (no[0] - tx * d_in, no[1] - ty * d_in), no)
    s = c["segs"][sai]
    c2 = s[2] if s[0] == "C" else (prox[0] + (no[0] - prox[0]) / 3, prox[1] + (no[1] - prox[1]) / 3)
    c["segs"][sai] = ("C", (no[0] + tx * d_out, no[1] + ty * d_out), c2, prox)
    return montar(estr, path.fillRule())


def quebrar(path, ci, k):
    """Abre o contorno no nó: fechado vira aberto começando e terminando ali; aberto vira dois."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    if c["fechado"]:
        k %= n
        c["ini"] = _inicio(c, k)
        c["segs"] = c["segs"][k:] + c["segs"][:k]
        c["fechado"] = False
    elif 0 < k < n:
        novo = {"ini": c["segs"][k - 1][-1], "segs": c["segs"][k:], "fechado": False}
        c["segs"] = c["segs"][:k]
        estr.insert(ci + 1, novo)
    p = montar(estr, path.fillRule())
    return p


def excluir_seg(path, ci, k):
    """Apaga o trecho k: contorno fechado vira aberto (começa no fim do trecho); aberto vira até dois."""
    estr = estrutura(path)
    c = estr[ci]
    n = len(c["segs"])
    if c["fechado"]:
        segs = c["segs"][k + 1:] + c["segs"][:k]
        novos = [{"ini": c["segs"][k][-1], "segs": segs, "fechado": False}] if segs else []
    else:
        antes = {"ini": c["ini"], "segs": c["segs"][:k], "fechado": False}
        depois = {"ini": c["segs"][k][-1], "segs": c["segs"][k + 1:], "fechado": False}
        novos = [x for x in (antes, depois) if x["segs"]]
    estr[ci:ci + 1] = novos
    return montar(estr, path.fillRule())
