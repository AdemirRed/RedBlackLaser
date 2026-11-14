"""Operações booleanas e deslocamento (offset) de formas, em mm de documento.

Tudo é feito com as operações de caminho do Qt em µm (escala 1000) para que o achatamento de curvas fique com erro
desprezível, e "lascas" microscópicas que essas operações às vezes deixam são descartadas.
Caminhos de entrada já devem estar em coordenadas de cena (matriz aplicada).
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform

ESC = 1000.0
_JUNTAS = {"redondo": Qt.RoundJoin, "canto": Qt.MiterJoin, "bisel": Qt.BevelJoin}


def _sobe(p: QPainterPath) -> QPainterPath:
    return QTransform.fromScale(ESC, ESC).map(p)


def _desce(p: QPainterPath) -> QPainterPath:
    return QTransform.fromScale(1 / ESC, 1 / ESC).map(p)


def _area(poly) -> float:
    pts = list(poly)
    return sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def _limpo(p: QPainterPath) -> QPainterPath:
    """Sem lascas (< 1e-6 mm² na escala de trabalho)."""
    out = QPainterPath()
    out.setFillRule(Qt.WindingFill)
    for poly in p.simplified().toSubpathPolygons():
        if abs(_area(poly)) > 1.0:
            out.addPolygon(poly)
            out.closeSubpath()
    return out


def fechado(p: QPainterPath) -> bool:
    """Todos os contornos fechados (booleanas só fazem sentido em áreas)."""
    polys = p.toSubpathPolygons()
    return bool(polys) and all(len(q) > 2 and (q.first() - q.last()).manhattanLength() < 1e-6 for q in polys)


def _traco(p: QPainterPath, largura: float, canto: str) -> QPainterPath:
    st = QPainterPathStroker()
    st.setWidth(largura)
    st.setJoinStyle(_JUNTAS[canto])
    st.setMiterLimit(8)
    st.setCapStyle(Qt.RoundCap)
    return st.createStroke(p)


def deslocar(path: QPainterPath, dist: float, direcao="fora", canto="redondo") -> QPainterPath:
    """Contorno paralelo a `dist` mm: "fora", "dentro" ou "ambos" (os dois contornos)."""
    if dist <= 0:
        raise ValueError("distância deve ser maior que zero")
    if direcao not in ("fora", "dentro", "ambos") or canto not in _JUNTAS:
        raise ValueError("direção ou canto inválido")
    a = _sobe(path)
    tr = _traco(a, 2 * dist * ESC, canto)
    out = QPainterPath()
    if direcao in ("fora", "ambos"):
        out.addPath(_limpo(a.united(tr)))
    if direcao in ("dentro", "ambos"):
        out.addPath(_limpo(a.subtracted(tr)))
    return _desce(out)


def uniao(paths) -> QPainterPath:
    acc = QPainterPath()
    acc.setFillRule(Qt.WindingFill)
    for p in paths:
        acc = acc.united(_sobe(p))
    return _desce(_limpo(acc))


def subtrair(base: QPainterPath, outros) -> QPainterPath:
    acc = _sobe(base)
    for p in outros:
        acc = acc.subtracted(_sobe(p))
    return _desce(_limpo(acc))


def intersecao(paths) -> QPainterPath:
    paths = list(paths)
    acc = _sobe(paths[0])
    for p in paths[1:]:
        acc = acc.intersected(_sobe(p))
    return _desce(_limpo(acc))


def cortar(alvo: QPainterPath, cortador: QPainterPath):
    """Cortador de biscoito: (parte dentro, parte fora) do alvo em relação ao cortador; vazios omitidos."""
    a, c = _sobe(alvo), _sobe(cortador)
    return [_desce(x) for x in (_limpo(a.intersected(c)), _limpo(a.subtracted(c))) if not x.isEmpty()]
