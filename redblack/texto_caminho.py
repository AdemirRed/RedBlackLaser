"""Texto ao longo de um caminho: cada letra é posicionada pela distância percorrida e girada pela tangente.

Usa a mesma fonte e escala do texto comum (altura = X maiúsculo, texto.build_path). A linha de base segue o
caminho; "fora" põe as letras do lado de fora da curva no sentido do caminho (para um círculo desenhado no
sentido horário da tela, as letras ficam por fora, em pé).
"""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFontMetricsF, QPainterPath, QTransform

from . import texto as tx


def _polilinha(path: QPainterPath):
    polys = path.toSubpathPolygons(QTransform.fromScale(20, 20))
    if not polys:
        return []
    return [(p.x() / 20, p.y() / 20) for p in polys[0]]


def _no_caminho(pts, cum, d):
    """(ponto, ângulo em graus) a `d` mm do início (fora do intervalo: segue a reta da ponta)."""
    if d <= 0:
        i = 0
    elif d >= cum[-1]:
        i = len(pts) - 2
    else:
        i = next(k for k in range(len(cum) - 1) if cum[k] <= d <= cum[k + 1])
    a, b = pts[i], pts[i + 1]
    seg = cum[i + 1] - cum[i]
    t = (d - cum[i]) / seg if seg > 1e-12 else 0.0
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def aplicar(params: tx.TextoParams, caminho: QPainterPath, inicio_pct=0.0, deslocamento_mm=0.0, inverter=False):
    """QPainterPath (mm de cena) com o texto (1ª linha) ao longo do 1º contorno de `caminho` (mm de cena).

    inicio_pct: onde começa (0–100 % do comprimento; com alinhamento centro, é onde fica o meio do texto).
    deslocamento_mm: afasta a linha de base do caminho (positivo = para o lado das letras).
    inverter: percorre o caminho no sentido contrário (letras do outro lado).
    """
    pts = _polilinha(caminho)
    if len(pts) < 2:
        raise ValueError("caminho vazio")
    if inverter:
        pts = pts[::-1]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    L = cum[-1]
    linha = tx.texto_efetivo(params).split("\n")[0]
    font = tx.make_font(params)
    fm = QFontMetricsF(font)
    ref = QPainterPath()
    ref.addText(0, 0, font, "X")
    escala = params.altura_mm / (ref.boundingRect().height() or fm.capHeight() or fm.ascent())
    largura = fm.horizontalAdvance(linha) * escala
    base = L * inicio_pct / 100
    if params.alinhamento == "centro":
        base -= largura / 2
    elif params.alinhamento == "direita":
        base -= largura
    out = QPainterPath()
    out.setFillRule(Qt.WindingFill)
    x = 0.0
    for i, ch in enumerate(linha):
        adv = fm.horizontalAdvance(linha[:i + 1]) * escala - x  # inclui o kerning com a letra anterior
        if not ch.isspace():
            g = QPainterPath()
            g.addText(0, 0, font, ch)
            glifo = QTransform.fromScale(escala, escala).map(g)
            if params.distorcer:
                out.addPath(_curvar(glifo, pts, cum, base + x, deslocamento_mm))
            else:
                meio = base + x + adv / 2  # a letra gira em torno do seu meio, sobre o caminho
                (px, py), ang = _no_caminho(pts, cum, meio)
                t = QTransform()
                t.translate(px, py)
                t.rotate(ang)
                t.translate(-adv / 2, -deslocamento_mm)
                out.addPath(t.map(glifo))
        x += adv
    if params.soldado:
        out = out.simplified()
        out.setFillRule(Qt.WindingFill)
    return out


def _curvar(glifo: QPainterPath, pts, cum, x0, deslocamento_mm) -> QPainterPath:
    """Cada ponto do glifo vai para o caminho: x = distância percorrida, y = afastamento pela normal."""
    out = QPainterPath()
    for poly in glifo.toSubpathPolygons():
        novos = []
        for p in poly:
            (px, py), ang = _no_caminho(pts, cum, x0 + p.x())
            a = math.radians(ang)
            dy = p.y() - deslocamento_mm
            novos.append(QPointF(px - dy * math.sin(a), py + dy * math.cos(a)))
        if novos:
            out.moveTo(novos[0])
            for q in novos[1:]:
                out.lineTo(q)
            out.closeSubpath()
    return out
