"""Importação de SVG — subconjunto explícito (Etapa 5).

Suportado: <svg> (width/height/viewBox), <g>, <path> (M L H V C S Q T A Z, absolutos e relativos),
<rect> (rx/ry), <circle>, <ellipse>, <line>, <polyline>, <polygon>; atributo transform completo
(matrix, translate, scale, rotate, skewX, skewY) aninhado; display="none" é pulado.
Todo o resto é contado em `ignorados` e informado ao usuário.

Saída em mm, coordenadas de documento (origem no canto superior esquerdo, Y para baixo — mesma
orientação do SVG).
"""
import math
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath, QTransform

PX_MM = 25.4 / 96  # CSS: 96 px por polegada
UNITS = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": PX_MM, "": PX_MM}
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
# Elementos sem geometria a importar; não geram aviso.
SILENT = {"title", "desc", "metadata", "defs", "style", "namedview", "sodipodi:namedview"}
MAX_BYTES = 50 * 1024 * 1024
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


class SvgInvalido(Exception):
    """Arquivo não pode ser importado; mensagem exibida ao usuário."""


@dataclass
class Resultado:
    objetos: list = field(default_factory=list)       # [(nome, QPainterPath em mm)]
    ignorados: Counter = field(default_factory=Counter)  # tag -> quantidade
    avisos: list = field(default_factory=list)


# ---------- valores ----------
def numbers(s: str) -> list:
    return [float(x) for x in _NUM.findall(s or "")]


def parse_length(s, default=None):
    """'10mm' -> 10.0 (mm). Sem unidade = px. '%' devolve None (não suportado)."""
    if s is None:
        return default
    m = re.fullmatch(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-z%]*)\s*", s)
    if not m or m.group(2) == "%" or m.group(2) not in UNITS:
        return None
    return float(m.group(1)) * UNITS[m.group(2)]


def parse_transform(s: str) -> QTransform:
    """Lista de transformações SVG -> QTransform (convenção Qt: primeiro a da direita no SVG)."""
    total = QTransform()
    for name, args in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", s or ""):
        a = numbers(args)
        if name == "matrix" and len(a) == 6:
            t = QTransform(a[0], a[1], a[2], a[3], a[4], a[5])
        elif name == "translate" and a:
            t = QTransform.fromTranslate(a[0], a[1] if len(a) > 1 else 0)
        elif name == "scale" and a:
            t = QTransform.fromScale(a[0], a[1] if len(a) > 1 else a[0])
        elif name == "rotate" and a:
            cx, cy = (a[1], a[2]) if len(a) == 3 else (0.0, 0.0)
            t = QTransform.fromTranslate(-cx, -cy) * QTransform().rotate(a[0]) * QTransform.fromTranslate(cx, cy)
        elif name == "skewX" and a:
            t = QTransform(1, 0, math.tan(math.radians(a[0])), 1, 0, 0)
        elif name == "skewY" and a:
            t = QTransform(1, math.tan(math.radians(a[0])), 0, 1, 0, 0)
        else:
            continue
        total = t * total  # SVG aplica da direita para a esquerda
    return total


# ---------- arcos ----------
def arc_to_curves(p: QPainterPath, x1, y1, rx, ry, phi, large, sweep, x2, y2):
    """Arco elíptico SVG (parametrização por extremos, spec SVG F.6) em cúbicas de até 90°."""
    if (x1, y1) == (x2, y2):
        return
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        p.lineTo(x2, y2)
        return
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = c * dx + s * dy, -s * dx + c * dy
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:  # raios pequenos demais: ampliar (F.6.6)
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    k = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cxp, cyp = k * rx * y1p / ry, -k * ry * x1p / rx
    cx, cy = c * cxp - s * cyp + (x1 + x2) / 2, s * cxp + c * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(1, math.ceil(abs(dt) / (math.pi / 2) - 1e-9))
    d = dt / n
    alpha = 4 / 3 * math.tan(d / 4)

    def point(t):
        return (cx + rx * math.cos(t) * c - ry * math.sin(t) * s, cy + rx * math.cos(t) * s + ry * math.sin(t) * c)

    def deriv(t):
        return (-rx * math.sin(t) * c - ry * math.cos(t) * s, -rx * math.sin(t) * s + ry * math.cos(t) * c)

    for i in range(n):
        a, b = t1 + i * d, t1 + (i + 1) * d
        (ax, ay), (bx, by) = point(a), point(b)
        (dax, day), (dbx, dby) = deriv(a), deriv(b)
        p.cubicTo(ax + alpha * dax, ay + alpha * day, bx - alpha * dbx, by - alpha * dby, bx, by)
    p.setElementPositionAt(p.elementCount() - 1, x2, y2)  # extremo exato


# ---------- path d ----------
def parse_path(d: str) -> QPainterPath:
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + _NUM.pattern, d or "")
    p = QPainterPath()
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    last_c = last_q = None  # pontos de controle para S/T

    def take(n):
        nonlocal i
        vals = tokens[i:i + n]
        if len(vals) < n or any(v.isalpha() for v in vals):
            raise SvgInvalido(f"Dados de caminho incompletos perto de '{' '.join(tokens[max(0, i - 3):i + 3])}'.")
        i += n
        return [float(v) for v in vals]

    def flag():
        # Flags de arco podem vir coladas: "a1 1 0 01 2 2" -> a parte inteira é um só dígito.
        nonlocal i
        t = tokens[i]
        i += 1
        if t in ("0", "1"):
            return int(t)
        if t[0] in "01" and len(t) > 1:
            tokens.insert(i, t[1:])
            return int(t[0])
        raise SvgInvalido("Flag de arco inválida.")

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
        elif cmd is None:
            raise SvgInvalido("Caminho começa sem comando.")
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if C == "Z":
            p.closeSubpath()
            x, y = sx, sy
            last_c = last_q = None
            continue
        if C == "M":
            x, y = (v + o for v, o in zip(take(2), (ox, oy)))
            p.moveTo(x, y)
            sx, sy = x, y
            cmd = "l" if rel else "L"  # pares seguintes são lineto
            last_c = last_q = None
            continue
        if C == "L":
            x, y = (v + o for v, o in zip(take(2), (ox, oy)))
            p.lineTo(x, y)
            last_c = last_q = None
        elif C == "H":
            x = take(1)[0] + ox
            p.lineTo(x, y)
            last_c = last_q = None
        elif C == "V":
            y = take(1)[0] + oy
            p.lineTo(x, y)
            last_c = last_q = None
        elif C in "CS":
            if C == "C":
                x1, y1, x2, y2, ex, ey = take(6)
                x1, y1 = x1 + ox, y1 + oy
            else:
                x2, y2, ex, ey = take(4)
                x1, y1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            x2, y2, ex, ey = x2 + ox, y2 + oy, ex + ox, ey + oy
            p.cubicTo(x1, y1, x2, y2, ex, ey)
            last_c, last_q = (x2, y2), None
            x, y = ex, ey
        elif C in "QT":
            if C == "Q":
                qx, qy, ex, ey = take(4)
                qx, qy = qx + ox, qy + oy
            else:
                ex, ey = take(2)
                qx, qy = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            ex, ey = ex + ox, ey + oy
            p.quadTo(qx, qy, ex, ey)
            last_q, last_c = (qx, qy), None
            x, y = ex, ey
        elif C == "A":
            rx, ry, phi = take(3)
            large, sweep = flag(), flag()
            ex, ey = (v + o for v, o in zip(take(2), (ox, oy)))
            arc_to_curves(p, x, y, rx, ry, phi, large, sweep, ex, ey)
            x, y = ex, ey
            last_c = last_q = None
    return p


# ---------- elementos ----------
def _f(el, name, default=0.0):
    v = parse_length(el.get(name))
    return default if v is None else v / PX_MM  # coordenadas internas ficam em unidades do usuário


def shape_path(tag, el) -> QPainterPath:
    p = QPainterPath()
    if tag == "path":
        return parse_path(el.get("d", ""))
    if tag == "rect":
        x, y, w, h = _f(el, "x"), _f(el, "y"), _f(el, "width"), _f(el, "height")
        rx, ry = el.get("rx"), el.get("ry")
        rx = _f(el, "rx") if rx is not None else None
        ry = _f(el, "ry") if ry is not None else None
        rx, ry = (rx if rx is not None else ry or 0.0), (ry if ry is not None else rx or 0.0)
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if rx > 0 and ry > 0:
            p.addRoundedRect(x, y, w, h, rx, ry)
        else:
            p.addRect(x, y, w, h)
    elif tag == "circle":
        r = _f(el, "r")
        p.addEllipse(_f(el, "cx") - r, _f(el, "cy") - r, 2 * r, 2 * r)
    elif tag == "ellipse":
        rx, ry = _f(el, "rx"), _f(el, "ry")
        p.addEllipse(_f(el, "cx") - rx, _f(el, "cy") - ry, 2 * rx, 2 * ry)
    elif tag == "line":
        p.moveTo(_f(el, "x1"), _f(el, "y1"))
        p.lineTo(_f(el, "x2"), _f(el, "y2"))
    elif tag in ("polyline", "polygon"):
        pts = numbers(el.get("points", ""))
        if len(pts) >= 4:
            p.moveTo(pts[0], pts[1])
            for k in range(2, len(pts) - 1, 2):
                p.lineTo(pts[k], pts[k + 1])
            if tag == "polygon":
                p.closeSubpath()
    return p


def _hidden(el) -> bool:
    style = el.get("style", "").replace(" ", "")
    return el.get("display") == "none" or "display:none" in style


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def root_transform(root, res: Resultado) -> QTransform:
    """Unidades do usuário -> mm, a partir de width/height/viewBox (preserveAspectRatio padrão)."""
    vb = numbers(root.get("viewBox", ""))
    w, h = parse_length(root.get("width")), parse_length(root.get("height"))
    for attr, v in (("width", w), ("height", h)):
        if root.get(attr) is not None and v is None:
            res.avisos.append(f"{attr}='{root.get(attr)}' sem suporte; usando o viewBox em px (96 por polegada).")
    if len(vb) != 4 or vb[2] <= 0 or vb[3] <= 0:
        return QTransform.fromScale(PX_MM, PX_MM)
    vx, vy, vw, vh = vb
    if w is None and h is None:
        w, h = vw * PX_MM, vh * PX_MM
    elif w is None:
        w = h * vw / vh
    elif h is None:
        h = w * vh / vw
    sx, sy = w / vw, h / vh
    if root.get("preserveAspectRatio", "").split()[:1] == ["none"]:
        return QTransform.fromTranslate(-vx, -vy) * QTransform.fromScale(sx, sy)
    if root.get("preserveAspectRatio") not in (None, "", "xMidYMid", "xMidYMid meet"):
        res.avisos.append("preserveAspectRatio diferente do padrão; usando xMidYMid meet.")
    s = min(sx, sy)  # xMidYMid meet: escala uniforme, centralizada
    tx, ty = (w - vw * s) / 2, (h - vh * s) / 2
    return QTransform.fromTranslate(-vx, -vy) * QTransform.fromScale(s, s) * QTransform.fromTranslate(tx, ty)


def _walk(el, tf: QTransform, res: Resultado, counter: Counter):
    for child in el:
        if not isinstance(child.tag, str):
            continue  # comentários / instruções de processamento
        tag = _local(child.tag)
        if _hidden(child):
            res.ignorados[f"{tag} (oculto)"] += 1
            continue
        local = parse_transform(child.get("transform", "")) * tf
        if tag in ("g", "a"):
            _walk(child, local, res, counter)
        elif tag in SHAPES:
            path = shape_path(tag, child)
            if path.isEmpty():
                res.ignorados[f"{tag} (vazio)"] += 1
                continue
            counter[tag] += 1
            name = child.get("id") or f"{tag} {counter[tag]}"
            mapped = local.map(path)
            # Padrão SVG é nonzero; evenodd só no próprio elemento (herança de <g> não tratada).
            style = child.get("style", "").replace(" ", "")
            evenodd = child.get("fill-rule") == "evenodd" or "fill-rule:evenodd" in style
            mapped.setFillRule(Qt.OddEvenFill if evenodd else Qt.WindingFill)
            res.objetos.append((name, mapped))
        elif tag not in SILENT:
            res.ignorados[tag] += 1


def parse_svg(data) -> Resultado:
    """data: bytes do arquivo (a codificação declarada no XML é respeitada) ou str."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    # Entidades XML permitem ataques de expansão ("billion laughs"); SVG comum não precisa delas.
    if re.search(rb"<!ENTITY", raw, re.I):
        raise SvgInvalido("SVG com declarações de entidade XML não é aceito por segurança.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise SvgInvalido(f"XML inválido: {e}") from e
    if _local(root.tag) != "svg":
        raise SvgInvalido("O arquivo não é um SVG (elemento raiz não é <svg>).")
    res = Resultado()
    _walk(root, parse_transform(root.get("transform", "")) * root_transform(root, res), res, Counter())
    return res


def load(path: str) -> Resultado:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            raise SvgInvalido("Arquivo SVG grande demais (limite 50 MB).")
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise SvgInvalido(f"Não foi possível ler o arquivo: {e}") from e
    return parse_svg(data)
