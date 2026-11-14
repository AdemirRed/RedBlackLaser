"""Formas primárias e edição de nós (Etapa 8). Tudo em mm, coordenadas de cena.

Medidas previsíveis: retângulo/elipse ocupam exatamente a caixa arrastada; polígono regular
tem raio circunscrito exato com um vértice no topo.
"""
import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath

CLOSE_PX = 12  # clicar a esta distância (tela) do 1º ponto fecha a linha (8 px era pouco para a mão)


def drag_rect(a: QPointF, b: QPointF, square=False, center=False) -> QRectF:
    """Caixa de um arraste. square: lados iguais (maior dos dois); center: a = centro."""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    if square:
        s = max(abs(dx), abs(dy))
        dx, dy = math.copysign(s, dx or 1), math.copysign(s, dy or 1)
    if center:
        return QRectF(a.x() - abs(dx), a.y() - abs(dy), 2 * abs(dx), 2 * abs(dy))
    return QRectF(QPointF(a.x(), a.y()), QPointF(a.x() + dx, a.y() + dy)).normalized()


def rect_path(r: QRectF) -> QPainterPath:
    p = QPainterPath()
    p.addRect(r)
    return p


def ellipse_path(r: QRectF) -> QPainterPath:
    p = QPainterPath()
    p.addEllipse(r)
    return p


def polygon_path(center: QPointF, radius: float, sides: int) -> QPainterPath:
    """Polígono regular com raio circunscrito `radius` e um vértice no topo."""
    if sides < 3:
        raise ValueError("polígono precisa de 3+ lados")
    p = QPainterPath()
    for i in range(sides):
        a = -math.pi / 2 + 2 * math.pi * i / sides
        pt = QPointF(center.x() + radius * math.cos(a), center.y() + radius * math.sin(a))
        p.moveTo(pt) if i == 0 else p.lineTo(pt)
    p.closeSubpath()
    return p


def star_path(center: QPointF, radius: float, pontas: int, razao: float = 0.5) -> QPainterPath:
    """Estrela com `pontas` pontas, raio externo `radius`, raio interno = razao × radius; ponta no topo."""
    if pontas < 3 or not 0 < razao < 1:
        raise ValueError("estrela precisa de 3+ pontas e razão entre 0 e 1")
    p = QPainterPath()
    for i in range(2 * pontas):
        a = -math.pi / 2 + math.pi * i / pontas
        rr = radius if i % 2 == 0 else radius * razao
        pt = QPointF(center.x() + rr * math.cos(a), center.y() + rr * math.sin(a))
        p.moveTo(pt) if i == 0 else p.lineTo(pt)
    p.closeSubpath()
    return p


def polyline_path(points, closed=False) -> QPainterPath:
    p = QPainterPath()
    p.moveTo(points[0])
    for pt in points[1:]:
        p.lineTo(pt)
    if closed:
        p.closeSubpath()
    return p


def caminho_com_alcas(points, alcas, closed=False) -> QPainterPath:
    """Linha por pontos em que cada ponto pode ter alça (QPointF de deslocamento da alça de saída; a de
    entrada é o espelho): trecho entre pontos sem alça = reta; com alça em alguma ponta = curva de Bézier."""
    p = QPainterPath()
    p.moveTo(points[0])
    n = len(points)
    pares = [(i, i + 1) for i in range(n - 1)] + ([(n - 1, 0)] if closed and n > 2 else [])
    for a, b in pares:
        sa, eb = alcas.get(a), alcas.get(b)
        if sa is None and eb is None:
            p.lineTo(points[b])
        else:
            c1 = points[a] + sa if sa is not None else points[a]
            c2 = points[b] - eb if eb is not None else points[b]
            p.cubicTo(c1, c2, points[b])
    if closed:
        p.closeSubpath()
    return p


def controles(p: QPainterPath) -> list:
    """[(índice do controle, índice do nó a que ele pertence)] — c1 pertence ao nó anterior, c2 ao fim da curva."""
    out = []
    for i in range(p.elementCount()):
        if p.elementAt(i).type == QPainterPath.CurveToElement:
            out += [(i, i - 1), (i + 1, i + 2)]
    return out


def move_controle(p: QPainterPath, idx: int, dx: float, dy: float) -> QPainterPath:
    """Move só a alça idx (os nós e as outras alças ficam)."""
    q = QPainterPath(p)
    e = q.elementAt(idx)
    q.setElementPositionAt(idx, e.x + dx, e.y + dy)
    return q


def snap_angle(a: QPointF, b: QPointF, step_deg=45.0) -> QPointF:
    """b restrito a múltiplos de step_deg a partir de a, mantendo a distância."""
    d = math.hypot(b.x() - a.x(), b.y() - a.y())
    ang = round(math.atan2(b.y() - a.y(), b.x() - a.x()) / math.radians(step_deg)) * math.radians(step_deg)
    return QPointF(a.x() + d * math.cos(ang), a.y() + d * math.sin(ang))


# ---------- cantos arredondados ----------
def _filete(v, p, n, r):
    """Arco de raio r no canto v (entre os segmentos v→p e v→n): (t1, c1, c2, t2) ou None.

    O recuo em cada lado é limitado à metade do segmento menor, para filetes vizinhos não se
    cruzarem; nesse caso o raio efetivo fica menor que o pedido.
    """
    ax, ay, bx, by = p.x() - v.x(), p.y() - v.y(), n.x() - v.x(), n.y() - v.y()
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la < 1e-9 or lb < 1e-9:
        return None
    ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
    theta = math.acos(max(-1.0, min(1.0, ax * bx + ay * by)))  # ângulo interno
    if theta < 1e-6 or math.pi - theta < 1e-6:  # segmentos colineares: nada a arredondar
        return None
    t = min(r / math.tan(theta / 2), la / 2, lb / 2)
    r_ef = t * math.tan(theta / 2)
    h = 4 / 3 * math.tan((math.pi - theta) / 4) * r_ef  # alça da cúbica que aproxima o arco
    t1 = QPointF(v.x() + ax * t, v.y() + ay * t)
    t2 = QPointF(v.x() + bx * t, v.y() + by * t)
    c1 = QPointF(t1.x() - ax * h, t1.y() - ay * h)
    c2 = QPointF(t2.x() - bx * h, t2.y() - by * h)
    return t1, c1, c2, t2


def arredondar(p: QPainterPath, r: float):
    """Arredonda os cantos de subcaminhos feitos só de retas. Devolve (novo caminho, cantos arredondados).

    Subcaminhos com curvas ficam como estão. Em linhas abertas os extremos não são arredondados.
    """
    if r <= 0:
        return QPainterPath(p), 0
    out = QPainterPath()
    out.setFillRule(p.fillRule())
    total = 0
    for start, end in _subpaths(p):
        tipos = {p.elementAt(i).type for i in range(start + 1, end + 1)}
        pts = [QPointF(p.elementAt(i).x, p.elementAt(i).y) for i in range(start, end + 1)]
        if not tipos <= {QPainterPath.LineToElement} or len(pts) < 3:
            for i in range(start, end + 1):  # copia como está (curvas ou segmento único)
                e = p.elementAt(i)
                if e.type == QPainterPath.MoveToElement:
                    out.moveTo(e.x, e.y)
                elif e.type == QPainterPath.LineToElement:
                    out.lineTo(e.x, e.y)
                elif e.type == QPainterPath.CurveToElement:
                    c2, fim = p.elementAt(i + 1), p.elementAt(i + 2)
                    out.cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
            continue
        fechado = pts[0] == pts[-1]
        if fechado:
            pts = pts[:-1]
        n = len(pts)
        if fechado:
            fil = [_filete(pts[i], pts[i - 1], pts[(i + 1) % n], r) for i in range(n)]
        else:
            fil = [None] + [_filete(pts[i], pts[i - 1], pts[i + 1], r) for i in range(1, n - 1)] + [None]
        total += sum(f is not None for f in fil)

        def entrada(i):
            return fil[i][0] if fil[i] else pts[i]

        def saida(i):
            return fil[i][3] if fil[i] else pts[i]

        out.moveTo(saida(0))
        for i in list(range(1, n)) + ([0] if fechado else []):
            out.lineTo(entrada(i))
            if fil[i]:
                out.cubicTo(fil[i][1], fil[i][2], fil[i][3])
        if fechado:
            out.closeSubpath()
    return out, total


# ---------- nós ----------
def _subpaths(p: QPainterPath):
    """[(início, fim)] índices de elementos de cada subcaminho."""
    starts = [i for i in range(p.elementCount()) if p.elementAt(i).type == QPainterPath.MoveToElement]
    return [(s, (starts[k + 1] if k + 1 < len(starts) else p.elementCount()) - 1) for k, s in enumerate(starts)]


def _closing_twin(p, start, end):
    """Índice do último ponto se ele coincide com o início (subcaminho fechado), senão None."""
    if end > start:
        a, b = p.elementAt(start), p.elementAt(end)
        if (a.x, a.y) == (b.x, b.y):
            return end
    return None


def nodes(p: QPainterPath) -> list:
    """Índices dos pontos sobre a curva (sem pontos de controle e sem o ponto duplicado de fechamento)."""
    out = []
    for start, end in _subpaths(p):
        twin = _closing_twin(p, start, end)
        i = start
        while i <= end:
            t = p.elementAt(i).type
            if t == QPainterPath.CurveToElement:
                i += 2  # c1, c2 -> o ponto final é i+2
            if i != twin:
                out.append(i)
            i += 1
    return out


def move_node(p: QPainterPath, idx: int, dx: float, dy: float) -> QPainterPath:
    """Move o nó idx; controles adjacentes acompanham (a curva mantém a tangente local)."""
    q = QPainterPath(p)

    def shift(i):
        e = q.elementAt(i)
        q.setElementPositionAt(i, e.x + dx, e.y + dy)

    moved = {idx}
    for start, end in _subpaths(p):
        if start <= idx <= end:
            twin = _closing_twin(p, start, end)
            if twin is not None and idx == start:
                moved.add(twin)  # mover o início fechado move também o ponto de fechamento
    for i in moved:
        shift(i)
        if i >= 1 and p.elementAt(i).type == QPainterPath.CurveToDataElement:
            shift(i - 1)  # controle de entrada (c2)
        if i + 1 < p.elementCount() and p.elementAt(i + 1).type == QPainterPath.CurveToElement:
            shift(i + 1)  # controle de saída (c1 do próximo segmento)
    return q


def subcaminhos(path: QPainterPath) -> list:
    """Cada contorno (começa num MoveTo) como caminho próprio, mantendo as curvas."""
    out, cur, i, n = [], None, 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            cur = QPainterPath()
            cur.setFillRule(path.fillRule())
            out.append(cur)
            cur.moveTo(e.x, e.y)
        elif e.type == QPainterPath.LineToElement:
            cur.lineTo(e.x, e.y)
        elif e.type == QPainterPath.CurveToElement:
            c2, fim = path.elementAt(i + 1), path.elementAt(i + 2)
            cur.cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
            i += 2
        i += 1
    return [c for c in out if c.elementCount() > 1]


def n_contornos(path: QPainterPath) -> int:
    return sum(path.elementAt(i).type == QPainterPath.MoveToElement for i in range(path.elementCount()))


def _iguais(a: QPainterPath, b: QPainterPath, tol=1e-6) -> bool:
    if a.elementCount() != b.elementCount():
        return False
    for i in range(a.elementCount()):
        x, y = a.elementAt(i), b.elementAt(i)
        if x.type != y.type or abs(x.x - y.x) > tol or abs(x.y - y.y) > tol:
            return False
    return True


def raio_retangulo(path: QPainterPath):
    """Raio dos cantos se o caminho é um retângulo (cantos vivos = 0) ou um retângulo arredondado por
    `arredondar`; None para outras formas. Assim o raio "fica salvo" na própria geometria da peça."""
    b = path.boundingRect()
    if b.width() <= 0 or b.height() <= 0 or path.elementCount() == 0:
        return None
    base = rect_path(b)
    if _iguais(path, base):
        return 0.0
    r = path.elementAt(0).x - b.left()  # arredondar começa no fim do filete do canto superior esquerdo
    if r <= 0:
        return None
    return r if _iguais(path, arredondar(base, r)[0], 1e-6 * max(1.0, b.width(), b.height())) else None


def aberto(sub: QPainterPath) -> bool:
    """Contorno sem fechamento (fim diferente do início)."""
    n = sub.elementCount()
    if n < 2:
        return True
    a, b = sub.elementAt(0), sub.elementAt(n - 1)
    return abs(a.x - b.x) + abs(a.y - b.y) > 1e-9


def tem_aberto(path: QPainterPath) -> bool:
    return any(aberto(c) for c in subcaminhos(path))


def fechar_contornos(path: QPainterPath, tol=None):
    """(novo caminho, quantos fechados). tol=None fecha todos com uma reta; senão só os de vão ≤ tol (o fim
    passa a ser exatamente o início)."""
    out = QPainterPath()
    out.setFillRule(path.fillRule())
    n = 0
    for c in subcaminhos(path):
        if aberto(c):
            a, b = c.elementAt(0), c.elementAt(c.elementCount() - 1)
            vao = math.hypot(a.x - b.x, a.y - b.y)
            if tol is None or vao <= tol:
                if tol is not None and c.elementAt(c.elementCount() - 1).type == QPainterPath.LineToElement:
                    c.setElementPositionAt(c.elementCount() - 1, a.x, a.y)  # emenda no próprio início
                else:
                    c.lineTo(a.x, a.y)
                n += 1
        out.addPath(c)
    return out, n


def e_circulo(path: QPainterPath, tol=0.01) -> bool:
    """Um único contorno fechado cujos pontos ficam todos à mesma distância do centro (±1 %)."""
    subs = subcaminhos(path)
    if len(subs) != 1 or aberto(subs[0]):
        return False
    b = path.boundingRect()
    if b.width() <= 0 or abs(b.width() - b.height()) > tol * b.width():
        return False
    c, r = b.center(), b.width() / 2
    pts = path.toSubpathPolygons()[0]
    return len(pts) >= 8 and all(abs(math.hypot(q.x() - c.x(), q.y() - c.y()) - r) <= tol * r for q in pts)


def juntar_abertos(paths, tol=0.05):
    """Une contornos abertos cujas pontas coincidem (até `tol` mm), mantendo curvas.

    Devolve (lista de caminhos resultantes, quantas uniões). Contorno que volta ao próprio início fecha.
    Contornos já fechados passam direto.
    """
    pecas, prontos = [], []
    for p in paths:
        for c in subcaminhos(p):
            (prontos if not aberto(c) else pecas).append(c)

    def pontas(c):
        a, b = c.elementAt(0), c.elementAt(c.elementCount() - 1)
        return (a.x, a.y), (b.x, b.y)

    unioes = 0
    while pecas:
        atual = pecas.pop(0)
        mudou = True
        while mudou:
            mudou = False
            ini, fim = pontas(atual)
            if math.dist(ini, fim) <= tol and atual.elementCount() > 2:
                break  # já fechou um laço
            for i, outra in enumerate(pecas):
                oi, of = pontas(outra)
                for inverter, encaixe in ((False, math.dist(fim, oi)), (True, math.dist(fim, of))):
                    if encaixe <= tol:
                        seg = outra.toReversed() if inverter else outra
                        atual = _anexar(atual, seg)
                        pecas.pop(i)
                        unioes += 1
                        mudou = True
                        break
                if mudou:
                    break
                for inverter, encaixe in ((False, math.dist(ini, of)), (True, math.dist(ini, oi))):
                    if encaixe <= tol:
                        seg = outra.toReversed() if inverter else outra
                        atual = _anexar(seg, atual)
                        pecas.pop(i)
                        unioes += 1
                        mudou = True
                        break
                if mudou:
                    break
        ini, fim = pontas(atual)
        if math.dist(ini, fim) <= tol and atual.elementCount() > 2:
            atual.setElementPositionAt(atual.elementCount() - 1, *ini)  # fecha exatamente
        prontos.append(atual)
    return prontos, unioes


def _anexar(a: QPainterPath, b: QPainterPath) -> QPainterPath:
    """a seguido de b (o início de b é descartado: coincide com o fim de a)."""
    out = QPainterPath(a)
    i, n = 1, b.elementCount()
    while i < n:
        e = b.elementAt(i)
        if e.type == QPainterPath.LineToElement:
            out.lineTo(e.x, e.y)
        elif e.type == QPainterPath.CurveToElement:
            c2, fim = b.elementAt(i + 1), b.elementAt(i + 2)
            out.cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
            i += 2
        i += 1
    return out


def simplificar(path: QPainterPath, tol: float):
    """(novo caminho, nós antes, nós depois): contornos só de retas reduzidos por Douglas–Peucker (tol em mm).
    Contornos com curvas ficam como estão. Contorno fechado continua fechado."""
    from .tracar import _dp
    out = QPainterPath()
    out.setFillRule(path.fillRule())
    antes = depois = 0
    for c in subcaminhos(path):
        tipos = {c.elementAt(i).type for i in range(1, c.elementCount())}
        pts = [(c.elementAt(i).x, c.elementAt(i).y) for i in range(c.elementCount())]
        antes += len(pts)
        if tipos <= {QPainterPath.LineToElement} and len(pts) > 2:
            novo = _dp(pts, tol)
            if len(novo) >= (4 if not aberto(c) else 2):
                pts = novo
        depois += len(pts)
        q = polyline_path([QPointF(*p) for p in pts]) if tipos <= {QPainterPath.LineToElement} else c
        out.addPath(q)
    return out, antes, depois
