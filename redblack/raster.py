"""Gravação de imagens (raster): linhas de varredura com laser só onde a imagem pede.

Funciona no sistema da própria imagem (qualquer escala/giro/espelho vem da matriz do objeto): a imagem é
reamostrada para uma grade de pontos com lado = intervalo de linhas da camada, convertida para tons de cinza
(transparência = branco) e transformada em trechos:
  "limiar"     — escuro (abaixo do limiar) grava na potência máxima;
  "pontilhado" — difusão de erro Floyd–Steinberg, pontos na potência máxima (simula tons);
  "cinza"      — potência proporcional ao escuro, entre a mínima e a máxima da camada; branco não grava.
Branco nunca liga o laser.
"""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

MODOS = ("limiar", "pontilhado", "jarvis", "stucki", "atkinson", "cinza", "meio_tom")
# Difusão de erro: (dx, dy, peso) e divisor — "pontilhado" = Floyd–Steinberg.
_KERNELS = {
    "pontilhado": ([(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)], 16),
    "jarvis": ([(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5), (2, 1, 3),
                (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)], 48),
    "stucki": ([(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2),
                (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)], 42),
    "atkinson": ([(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)], 8),  # espalha só 6/8
}
MAX_PONTOS = 25_000_000  # proteção: grade grande demais para processar


class RasterGrandeDemais(ValueError):
    pass


def grade(qimage: QImage, largura_mm, altura_mm, passo_mm, negativo=False):
    """Matriz de cinzas 0 (preto) … 255 (branco), uma linha por linha de varredura (de cima para baixo)."""
    nx, ny = max(1, round(largura_mm / passo_mm)), max(1, round(altura_mm / passo_mm))
    if nx * ny > MAX_PONTOS:
        raise RasterGrandeDemais(f"Imagem grande demais para o intervalo escolhido ({nx} × {ny} pontos). "
                                 "Aumente o intervalo de linhas.")
    base = QImage(qimage.size(), QImage.Format_ARGB32)
    base.fill(QColor("white"))  # transparente vira branco (não grava)
    p = QPainter(base)
    p.drawImage(0, 0, qimage)
    p.end()
    g = base.scaled(nx, ny, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
    linhas = []
    for y in range(ny):
        bits = g.constScanLine(y)
        lin = list(bytes(bits)[:nx])
        linhas.append([255 - v for v in lin] if negativo else lin)
    return linhas, nx, ny


def ajustar(linhas, brilho_pct=0.0, contraste_pct=0.0, gama=1.0):
    """Brilho (+ clareia), contraste (+ aumenta) e gama (> 1 clareia os meios-tons), nessa ordem: gama, contraste,
    brilho. Valores 0..255."""
    if not brilho_pct and not contraste_pct and gama == 1.0:
        return linhas
    tab = []
    for v in range(256):
        x = (v / 255) ** (1 / gama)
        x = (x - 0.5) * (1 + contraste_pct / 100) + 0.5
        x += brilho_pct / 100
        tab.append(max(0, min(255, round(x * 255))))
    return [[tab[v] for v in lin] for lin in linhas]


def _area_disco(r2: float) -> float:
    """Fração da célula unitária coberta por um disco centrado de raio² = r2."""
    if r2 <= 0.25:
        return math.pi * r2
    if r2 >= 0.5:
        return 1.0
    r = math.sqrt(r2)
    return math.pi * r2 - 4 * (r2 * math.acos(0.5 / r) - 0.5 * math.sqrt(r2 - 0.25))


def meio_tom(linhas, pmax, cpi, angulo_graus, passo_mm):
    """Pontos redondos numa grade girada; a área do ponto em cada célula = escuridão do tom ali.
    Cada pixel acende se a escuridão passa a área do disco que chega até ele (limiar por posição)."""
    cel = max(2.0, 25.4 / cpi / passo_mm)  # pixels por célula (mínimo 2, senão não forma ponto)
    a = math.radians(angulo_graus)
    ca, sa = math.cos(a) / cel, math.sin(a) / cel
    out = []
    for y, lin in enumerate(linhas):
        yc = y + 0.5
        row = []
        for x, v in enumerate(lin):
            xc = x + 0.5
            u, w = xc * ca + yc * sa, -xc * sa + yc * ca
            fu, fw = u - math.floor(u) - 0.5, w - math.floor(w) - 0.5
            row.append(pmax if 1 - v / 255 > _area_disco(fu * fu + fw * fw) else 0)
        out.append(row)
    return out


def _difusao(linhas, kernel, div, pmax):
    """Difusão de erro (Floyd/Jarvis/Stucki/Atkinson). Mesmo resultado da versão simples, ~3x mais rápida: linhas com
    2 colunas de folga de cada lado (sem testar bordas; o erro que cai na folga é descartado, como antes) e os
    vizinhos de cada linha pré-calculados."""
    ny, nx = len(linhas), len(linhas[0]) if linhas else 0
    pad = 2
    por_linha = {}
    for dx, dy, w in kernel:
        por_linha.setdefault(dy, []).append((dx + pad, w))
    t0 = tuple(por_linha.get(0, ()))
    t1 = tuple(por_linha.get(1, ()))
    t2 = tuple(por_linha.get(2, ()))
    zeros = [0.0] * pad
    err = [zeros + [float(v) for v in lin] + zeros for lin in linhas]
    vazio = [0.0] * (nx + 2 * pad)
    out = []
    for y in range(ny):
        e0 = err[y]
        e1 = err[y + 1] if y + 1 < ny else vazio[:]
        e2 = err[y + 2] if y + 2 < ny else vazio[:]
        lin = [0] * nx
        for x in range(nx):
            velho = e0[x + pad]
            if velho < 128:
                lin[x] = pmax
                e = velho / div
            else:
                e = (velho - 255.0) / div
            if e:
                for dx, w in t0:
                    e0[x + dx] += e * w
                for dx, w in t1:
                    e1[x + dx] += e * w
                for dx, w in t2:
                    e2[x + dx] += e * w
        out.append(lin)
    return out


def potencias(linhas, modo, limiar_pct, pmin, pmax, meio_tom_param=(50.0, 45.0, 0.1)):
    """Mesma forma da grade, com a potência (%) de cada ponto, ou 0 = apagado.
    meio_tom_param = (células por polegada, ângulo, passo em mm) — só no modo meio_tom."""
    if modo == "limiar":
        lim = limiar_pct / 100 * 255
        return [[pmax if v < lim else 0 for v in lin] for lin in linhas]
    if modo in _KERNELS:
        return _difusao(linhas, *_KERNELS[modo], pmax)
    if modo == "meio_tom":
        return meio_tom(linhas, pmax, *meio_tom_param)
    if modo == "cinza":
        return [[0 if v >= 250 else round(pmin + (pmax - pmin) * (1 - v / 255), 1) for v in lin] for lin in linhas]
    raise ValueError(f"modo de imagem desconhecido: {modo}")


def trechos(qimage, largura_mm, altura_mm, tf, passo_mm, modo, limiar_pct, pmin, pmax, bidirecional=True,
            negativo=False, ajuste=(0.0, 0.0, 1.0), meio_tom_param=(50.0, 45.0)):
    """Linhas de varredura: [[(pontos em mm de cena, potência %), …], …] — em cada linha, um trecho por sequência
    de pontos vizinhos com a mesma potência (linhas vazias não aparecem)."""
    linhas, nx, ny = grade(qimage, largura_mm, altura_mm, passo_mm, negativo)
    pot = potencias(ajustar(linhas, *ajuste), modo, limiar_pct, pmin, pmax, (*meio_tom_param, passo_mm))
    dx, dy = largura_mm / nx, altura_mm / ny
    out, emitidas = [], 0
    for y in range(ny):
        corridas, x = [], 0
        lin = pot[y]
        while x < nx:
            if lin[x] > 0:
                x0, v = x, lin[x]
                while x < nx and lin[x] == v:
                    x += 1
                corridas.append((x0, x, v))
            else:
                x += 1
        if not corridas:
            continue
        yy = (y + 0.5) * dy
        if bidirecional and emitidas % 2 == 1:
            corridas = [(b, a, v) for a, b, v in reversed(corridas)]
        linha = []
        for a, b, v in corridas:
            p0, p1 = tf.map(QPointF(a * dx, yy)), tf.map(QPointF(b * dx, yy))
            linha.append((((p0.x(), p0.y()), (p1.x(), p1.y())), v))
        out.append(linha)
        emitidas += 1
    return out


def imagem_processada(qimage, largura_mm, altura_mm, c, max_pontos=None) -> QImage:
    """Como o laser vai gravar a imagem com a camada `c` (mesmo cálculo de `trechos`): preto = potência máxima,
    branco = apagado, cinzas proporcionais. Um pixel por ponto do intervalo de linhas. `max_pontos` reduz o passo
    (só para prévia rápida)."""
    passo = c.intervalo_mm
    if max_pontos:
        while (largura_mm / passo) * (altura_mm / passo) > max_pontos:
            passo *= 1.5
    linhas, nx, ny = grade(qimage, largura_mm, altura_mm, passo, c.negativo)
    pot = potencias(ajustar(linhas, c.brilho_pct, c.contraste_pct, c.gama), c.modo_imagem, c.limiar_pct,
                    c.potencia_min, c.potencia_max, (c.meio_tom_cpi, c.meio_tom_angulo, passo))
    pmax = max(c.potencia_max, 1e-9)
    out = QImage(nx, ny, QImage.Format_Grayscale8)
    for y in range(ny):
        out.scanLine(y)[:nx] = bytes(255 - min(255, round(v / pmax * 255)) for v in pot[y])
    dpm = round(1000 / passo)  # pontos por metro: o PNG sai na escala certa
    out.setDotsPerMeterX(dpm)
    out.setDotsPerMeterY(dpm)
    return out
