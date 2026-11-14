"""Formas prontas (menu suspenso das ferramentas de forma): cada uma preenche a caixa arrastada na mesa."""
import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTransform


def _poligono(pts):
    p = QPainterPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.closeSubpath()
    return p


def _regular(n, girar=-90.0):
    return [(math.cos(math.radians(girar + 360 * k / n)), math.sin(math.radians(girar + 360 * k / n))) for k in range(n)]


def _estrela(pontas, razao):
    pts = []
    for k in range(2 * pontas):
        r = 1.0 if k % 2 == 0 else razao
        a = math.radians(-90 + 180 * k / pontas)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def _coracao():
    p = QPainterPath()
    p.moveTo(0.5, 1.0)
    p.cubicTo(0.15, 0.75, 0.0, 0.55, 0.0, 0.32)
    p.cubicTo(0.0, 0.12, 0.15, 0.0, 0.29, 0.0)
    p.cubicTo(0.40, 0.0, 0.47, 0.06, 0.5, 0.15)
    p.cubicTo(0.53, 0.06, 0.60, 0.0, 0.71, 0.0)
    p.cubicTo(0.85, 0.0, 1.0, 0.12, 1.0, 0.32)
    p.cubicTo(1.0, 0.55, 0.85, 0.75, 0.5, 1.0)
    p.closeSubpath()
    return p


def _balao():
    p = QPainterPath()
    p.addRoundedRect(QRectF(0, 0, 1, 0.75), 0.12, 0.12)
    ponta = _poligono([(0.22, 0.70), (0.18, 1.0), (0.42, 0.70)])
    return p.united(ponta)


# nome -> (grupo, função que devolve o caminho num espaço qualquer; é encaixado na caixa arrastada)
CATALOGO = {
    "Triângulo": ("Polígonos", lambda: _poligono(_regular(3))),
    "Triângulo retângulo": ("Polígonos", lambda: _poligono([(0, 0), (0, 1), (1, 1)])),
    "Losango": ("Polígonos", lambda: _poligono([(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)])),
    "Pentágono": ("Polígonos", lambda: _poligono(_regular(5))),
    "Hexágono": ("Polígonos", lambda: _poligono(_regular(6, 0))),
    "Octógono": ("Polígonos", lambda: _poligono(_regular(8, 22.5))),
    "Estrela de 4 pontas": ("Estrelas", lambda: _poligono(_estrela(4, 0.4))),
    "Estrela de 5 pontas": ("Estrelas", lambda: _poligono(_estrela(5, 0.382))),
    "Estrela de 6 pontas": ("Estrelas", lambda: _poligono(_estrela(6, 0.55))),
    "Estrela de 8 pontas": ("Estrelas", lambda: _poligono(_estrela(8, 0.6))),
    "Coração": ("Símbolos", _coracao),
    "Seta": ("Símbolos", lambda: _poligono([(0, 0.3), (0.6, 0.3), (0.6, 0), (1, 0.5), (0.6, 1), (0.6, 0.7), (0, 0.7)])),
    "Cruz": ("Símbolos", lambda: _poligono([(0.33, 0), (0.67, 0), (0.67, 0.33), (1, 0.33), (1, 0.67), (0.67, 0.67),
                                            (0.67, 1), (0.33, 1), (0.33, 0.67), (0, 0.67), (0, 0.33), (0.33, 0.33)])),
    "Balão de fala": ("Símbolos", _balao),
    "Oblongo (pega)": ("Símbolos", None),  # depende da caixa: pontas com raio = metade do lado menor
}


def forma_pronta(nome: str, caixa: QRectF) -> QPainterPath:
    """Caminho da forma `nome` ocupando exatamente a caixa (mm)."""
    if caixa.width() <= 0 or caixa.height() <= 0:
        return QPainterPath()
    if nome == "Oblongo (pega)":
        p = QPainterPath()
        r = min(caixa.width(), caixa.height()) / 2
        p.addRoundedRect(caixa, r, r)
        return p
    base = CATALOGO[nome][1]()
    b = base.boundingRect()
    tf = QTransform.fromTranslate(caixa.left(), caixa.top())
    tf.scale(caixa.width() / b.width(), caixa.height() / b.height())
    tf.translate(-b.left(), -b.top())
    return tf.map(base)


def grupos():
    """{grupo: [nomes]} na ordem do catálogo (para montar o menu)."""
    out = {}
    for nome, (grupo, _) in CATALOGO.items():
        out.setdefault(grupo, []).append(nome)
    return out
