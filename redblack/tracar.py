"""Traçar imagem (vetorizar): contornos das áreas escuras de uma imagem, em mm.

1. cinza (transparente = branco) e limiar → grade de pixels "cheios";
2. bordas entre cheio e vazio viram arestas orientadas (cheio sempre à esquerda) e são encadeadas em laços;
3. cada laço é simplificado (Douglas–Peucker, tolerância em pixels) — some a escada dos pixels;
4. laços pequenos (ruído) são descartados.
Furos ficam como contornos de sentido contrário: com a regra par-ímpar o desenho sai certo.
"""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath

MAX_PIXELS = 4_000_000


PADRAO = dict(corte=0, limiar=128, ignorar=2.0, suavidade=1.0, otimizar=0.2, transparencia=False, esboco=False,
              linha_central=False, negativo=False, area=None)


def _reduzir(img, max_lado):
    esc = 1.0
    if max(img.width(), img.height()) > max_lado:
        esc = max_lado / max(img.width(), img.height())
        img = img.scaled(max(1, round(img.width() * esc)), max(1, round(img.height() * esc)), Qt.IgnoreAspectRatio,
                         Qt.SmoothTransformation)
    return img, esc


def mascara(qimage: QImage, op=None, max_lado=1500):
    """(linhas de bool, largura, altura, escala). Pixel "cheio" = brilho entre Corte e Limiar (0–255), ou opaco no
    modo Traçar transparência. Esboço: compara com a média da vizinhança (luz irregular, desenho a lápis).
    `area` (x, y, w, h em frações 0–1 da imagem) limita o traçado a um retângulo."""
    op = {**PADRAO, **(op or {})}
    base, esc = _reduzir(qimage.convertToFormat(QImage.Format_ARGB32), max_lado)
    w, h = base.width(), base.height()
    if op["transparencia"]:
        linhas = []
        for y in range(h):
            b = bytes(base.constScanLine(y))[:4 * w]
            linhas.append([b[4 * x + 3] >= 128 for x in range(w)])  # ARGB32 na memória: B G R A
    else:
        img = QImage(base.size(), QImage.Format_ARGB32)
        img.fill(QColor("white"))  # transparente = branco
        pt = QPainter(img)
        pt.drawImage(0, 0, base)
        pt.end()
        g = img.convertToFormat(QImage.Format_Grayscale8)
        lo, hi = min(op["corte"], op["limiar"]), max(op["corte"], op["limiar"])
        if op["esboco"]:  # média local: reduz muito e amplia de volta (borrão barato)
            k = max(1, round(max(w, h) / 24))
            media = g.scaled(max(1, w // k), max(1, h // k), Qt.IgnoreAspectRatio, Qt.SmoothTransformation).scaled(
                w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
            folga = (255 - hi) * 0.12 + 6  # Limiar mais alto = pega traços mais fracos
        linhas = []
        for y in range(h):
            b = bytes(g.constScanLine(y))[:w]
            if op["esboco"]:
                m = bytes(media.constScanLine(y))[:w]
                linhas.append([v >= lo and v < mv - folga for v, mv in zip(b, m)])
            else:
                linhas.append([lo <= v <= hi for v in b])
    if op["negativo"]:
        linhas = [[not v for v in ln] for ln in linhas]
    if op["area"]:
        ax, ay, aw, ah = op["area"]
        x0, x1 = max(0, int(ax * w)), min(w, int(math.ceil((ax + aw) * w)))
        y0, y1 = max(0, int(ay * h)), min(h, int(math.ceil((ay + ah) * h)))
        linhas = [[v and x0 <= x < x1 for x, v in enumerate(ln)] if y0 <= y < y1 else [False] * w
                  for y, ln in enumerate(linhas)]
    return linhas, w, h, esc


def grade_binaria(qimage: QImage, limiar_pct=50.0, negativo=False, max_lado=1500):
    """Compatível com a versão antiga: escuro (abaixo do limiar em %) = cheio."""
    lim = limiar_pct / 100 * 255
    return mascara(qimage, dict(corte=0, limiar=math.ceil(lim) - 1, negativo=negativo), max_lado)


def _lacos(cheio, w, h):
    """Laços de arestas entre pixels (cantos inteiros), com o cheio à esquerda."""
    def c(x, y):
        return 0 <= x < w and 0 <= y < h and cheio[y][x]

    saida = {}
    for y in range(h + 1):
        for x in range(w + 1):
            # aresta horizontal em y, de x a x+1: cheio embaixo (y) e vazio em cima (y-1) → sentido para a esquerda
            if x < w:
                em_baixo, em_cima = c(x, y), c(x, y - 1)
                if em_baixo and not em_cima:
                    saida.setdefault((x + 1, y), []).append((x, y))
                elif em_cima and not em_baixo:
                    saida.setdefault((x, y), []).append((x + 1, y))
            if y < h:
                dir_, esq = c(x, y), c(x - 1, y)
                if dir_ and not esq:
                    saida.setdefault((x, y), []).append((x, y + 1))
                elif esq and not dir_:
                    saida.setdefault((x, y + 1), []).append((x, y))
    lacos = []
    while saida:
        ini = next(iter(saida))
        laco, atual = [ini], ini
        while True:
            prox = saida[atual].pop()
            if not saida[atual]:
                del saida[atual]
            if prox == ini:
                break
            laco.append(prox)
            atual = prox
            if atual not in saida:  # não deveria acontecer em bordas bem formadas
                break
        lacos.append(laco)
    return lacos


def _dp(pts, tol):
    """Douglas–Peucker (não recursivo) numa polilinha aberta."""
    if len(pts) < 3:
        return pts
    manter = [False] * len(pts)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pts) - 1)]
    while pilha:
        a, b = pilha.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        melhor, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dx * (ay - py) - (ax - px) * dy) / L if L > 1e-12 else math.hypot(px - ax, py - ay)
            if d > melhor:
                melhor, idx = d, i
        if melhor > tol:
            manter[idx] = True
            pilha += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, manter) if k]


def _esqueleto(cheio, w, h):
    """Afinamento Zhang–Suen: linhas de 1 pixel no meio das áreas cheias (para Linha central)."""
    g = [[1 if v else 0 for v in ln] for ln in cheio]
    mudou = True
    while mudou:
        mudou = False
        for passo in (0, 1):
            apagar = []
            for y in range(1, h - 1):
                acima, linha, abaixo = g[y - 1], g[y], g[y + 1]
                for x in range(1, w - 1):
                    if not linha[x]:
                        continue
                    p2, p3, p4, p5 = acima[x], acima[x + 1], linha[x + 1], abaixo[x + 1]
                    p6, p7, p8, p9 = abaixo[x], abaixo[x - 1], linha[x - 1], acima[x - 1]
                    viz = (p2, p3, p4, p5, p6, p7, p8, p9)
                    if not 2 <= sum(viz) <= 6:
                        continue
                    if sum(viz[i] == 0 and viz[(i + 1) % 8] == 1 for i in range(8)) != 1:
                        continue
                    if passo == 0 and (p2 * p4 * p6 or p4 * p6 * p8):
                        continue
                    if passo == 1 and (p2 * p4 * p8 or p2 * p6 * p8):
                        continue
                    apagar.append((x, y))
            for x, y in apagar:
                g[y][x] = 0
            mudou = mudou or bool(apagar)
    return g


_VIZ8 = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


def _linhas_centrais(g, w, h):
    """Polilinhas seguindo o esqueleto, em coordenadas de centro de pixel."""
    pts = {(x, y) for y in range(h) for x in range(w) if g[y][x]}
    viz = {p: [(p[0] + dx, p[1] + dy) for dx, dy in _VIZ8 if (p[0] + dx, p[1] + dy) in pts] for p in pts}
    usadas, out = set(), []

    def seguir(a, b):
        cam = [a, b]
        usadas.add(frozenset((a, b)))
        while len(viz[b]) == 2:
            c = next((q for q in viz[b] if frozenset((b, q)) not in usadas), None)
            if c is None:
                break
            usadas.add(frozenset((b, c)))
            cam.append(c)
            b = c
        return cam
    nos = sorted(p for p in pts if len(viz[p]) != 2)  # pontas e cruzamentos primeiro
    for p in nos + sorted(pts):
        for q in viz[p]:
            if frozenset((p, q)) not in usadas:
                out.append(seguir(p, q))
    return [[(x + 0.5, y + 0.5) for x, y in c] for c in out]


def _suave(caminho, pts, fechado, sx, sy, suavidade):
    """Polilinha -> caminho; com suavidade > 0, vértices pouco angulosos viram curvas (Catmull-Rom)."""
    P = [QPointF(x * sx, y * sy) for x, y in pts]
    if fechado and len(P) > 2 and P[0] == P[-1]:
        P = P[:-1]
    n = len(P)
    caminho.moveTo(P[0])
    if suavidade <= 0 or n < 3:
        for q in P[1:]:
            caminho.lineTo(q)
        if fechado:
            caminho.closeSubpath()
        return
    s = min(suavidade, 1.33)
    limite = math.radians(30 + 50 * s)  # vira curva onde a direção muda menos que isto; acima, fica canto

    def liso(i):
        if not fechado and (i == 0 or i == n - 1):
            return False
        a, b, c = P[(i - 1) % n], P[i], P[(i + 1) % n]
        u, v = b - a, c - b
        return abs(math.atan2(u.x() * v.y() - u.y() * v.x(), u.x() * v.x() + u.y() * v.y())) < limite
    k = s / 6
    lisos = [liso(i) for i in range(n)]
    for i in range(n if fechado else n - 1):
        a, b = P[i], P[(i + 1) % n]
        c1 = a + (b - P[(i - 1) % n]) * k if lisos[i] else a
        c2 = b - (P[(i + 2) % n] - a) * k if lisos[(i + 1) % n] else b
        if c1 == a and c2 == b:
            caminho.lineTo(b)
        else:
            caminho.cubicTo(c1, c2, b)
    if fechado:
        caminho.closeSubpath()


def tracar_opcoes(qimage: QImage, largura_mm, altura_mm, op=None, max_lado=1500) -> QPainterPath:
    """Traçado com as opções da janela Traçar imagem (ver PADRAO). Contornos em mm, 0,0 no canto da imagem."""
    op = {**PADRAO, **(op or {})}
    if op["linha_central"]:
        max_lado = min(max_lado, 900)  # o afinamento é pixel a pixel
    cheio, w, h, _ = mascara(qimage, op, max_lado)
    if w * h > MAX_PIXELS:
        raise ValueError("Imagem grande demais para traçar.")
    sx, sy = largura_mm / w, altura_mm / h
    tol = max(op["otimizar"], 0.01) + 0.5  # meio pixel tira a escada do contorno
    out = QPainterPath()
    out.setFillRule(Qt.OddEvenFill)
    if op["linha_central"]:
        for c in _linhas_centrais(_esqueleto(cheio, w, h), w, h):
            if sum(math.dist(a, b) for a, b in zip(c, c[1:])) < max(op["ignorar"], 1):
                continue
            fechado = len(c) > 3 and math.dist(c[0], c[-1]) < 1.5
            _suave(out, _dp(c, tol), fechado, sx, sy, op["suavidade"])
        return out
    for laco in _lacos(cheio, w, h):
        area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(laco, laco[1:] + laco[:1]))) / 2
        if area < op["ignorar"]:
            continue
        if op["suavidade"] > 0:  # meio das arestas de pixel: a escadinha das diagonais vira reta
            laco = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(laco, laco[1:] + laco[:1])]
        pts = _dp(laco + [laco[0]], tol)
        if len(pts) < 4:
            continue
        _suave(out, pts, True, sx, sy, op["suavidade"])
    return out


def tracar(qimage: QImage, largura_mm, altura_mm, limiar_pct=50.0, suavizar_px=1.0, minimo_px=4.0,
           negativo=False) -> QPainterPath:
    """Versão simples (compatível): escuro abaixo do limiar em %, simplificação em px, só retas."""
    lim = limiar_pct / 100 * 255
    return tracar_opcoes(qimage, largura_mm, altura_mm,
                         dict(corte=0, limiar=math.ceil(lim) - 1, negativo=negativo, ignorar=minimo_px,
                              otimizar=max(suavizar_px - 0.5, 0.0), suavidade=0))
