"""DXF: importar (subconjunto) e exportar (R12 ASCII). Código próprio, sem bibliotecas externas.

Importa LINE, LWPOLYLINE (com arcos por "bulge"), POLYLINE/VERTEX, CIRCLE, ARC e ELLIPSE; o resto entra num
relatório. Unidades pelo $INSUNITS (sem ele: mm, com aviso). O eixo Y do DXF aponta para cima: o (0, 0) do DXF
fica no canto inferior esquerdo da mesa (y_documento = altura_mesa − y_dxf), como a origem da máquina.
Exporta cada contorno como POLYLINE (curvas achatadas com erro < 0,0125 mm), em mm.
"""
import math
import os
from collections import Counter

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTransform

from .importar_svg import Resultado

MAX_BYTES = 50 * 1024 * 1024
_UNIDADES = {0: (1.0, True), 1: (25.4, False), 2: (304.8, False), 4: (1.0, False), 5: (10.0, False),
             6: (1000.0, False), 8: (2.54e-5, False), 9: (0.0254, False), 10: (914.4, False), 13: (0.001, False),
             14: (100.0, False)}


class DxfInvalido(Exception):
    """Arquivo não pôde ser lido; a mensagem é exibida ao usuário."""


def _pares(texto):
    linhas = texto.splitlines()
    if len(linhas) % 2:
        linhas = linhas[:-1]
    for i in range(0, len(linhas), 2):
        try:
            yield int(linhas[i].strip()), linhas[i + 1].strip()
        except ValueError as e:
            raise DxfInvalido(f"Código de grupo inválido na linha {i + 1}.") from e


def _entidades(pares):
    """[(tipo, [(código, valor)])] das seções HEADER e ENTITIES."""
    secao, atual, out, header = None, None, [], []
    for cod, val in pares:
        if cod == 0:
            if atual is not None:
                (header if secao == "HEADER" else out).append(atual)
                atual = None
            if val == "SECTION":
                secao = "?"
                continue
            if val == "ENDSEC":
                secao = None
                continue
            if secao in ("ENTITIES", "HEADER") or (secao == "BLOCKS" and False):
                atual = (val, [])
            continue
        if cod == 2 and secao == "?":
            secao = val
            if secao == "HEADER":
                atual = ("HEADER", [])
            continue
        if atual is not None:
            atual[1].append((cod, val))
    if atual is not None:
        (header if secao == "HEADER" else out).append(atual)
    return out, header


def _num(grupos, cod, padrao=0.0):
    for c, v in grupos:
        if c == cod:
            try:
                return float(v)
            except ValueError:
                return padrao
    return padrao


def _arco(p: QPainterPath, cx, cy, r, a0, a1):
    """Arco anti-horário (graus) do DXF, em coordenadas DXF (Y para cima), anexado a p."""
    while a1 <= a0:
        a1 += 360
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    # arcTo do Qt usa Y para baixo; com Y para cima o sentido anti-horário corresponde a ângulos negativos
    p.arcTo(rect, -a0, -(a1 - a0))


def _bulge(p: QPainterPath, a, b, bulge):
    if abs(bulge) < 1e-12:
        p.lineTo(*b)
        return
    theta = 4 * math.atan(bulge)
    dx, dy = b[0] - a[0], b[1] - a[1]
    corda = math.hypot(dx, dy)
    if corda < 1e-12:
        return
    r = corda / (2 * math.sin(abs(theta) / 2))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    h = math.sqrt(max(r * r - (corda / 2) ** 2, 0.0))
    s = 1 if (bulge > 0) == (abs(theta) < math.pi) else -1  # centro à esquerda para bulge positivo e arco < 180°
    cx, cy = mx - s * h * dy / corda, my + s * h * dx / corda
    a0 = math.degrees(math.atan2(a[1] - cy, a[0] - cx))
    a1 = math.degrees(math.atan2(b[1] - cy, b[0] - cx))
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    varr = math.degrees(theta)  # positivo = anti-horário (Y para cima)
    p.arcTo(rect, -a0, -varr)
    p.lineTo(*b)  # garante o ponto exato


def load(caminho, altura_mesa) -> Resultado:
    if os.path.getsize(caminho) > MAX_BYTES:
        raise DxfInvalido("Arquivo DXF grande demais.")
    try:
        texto = open(caminho, "rb").read().decode("utf-8")
    except UnicodeDecodeError:
        texto = open(caminho, "rb").read().decode("cp1252", "replace")
    if "SECTION" not in texto:
        raise DxfInvalido("Não parece um DXF em texto (DXF binário não é suportado).")
    ents, header = _entidades(_pares(texto))
    res = Resultado()
    unid = 0
    for _, grupos in header:
        for i, (c, v) in enumerate(grupos):
            if c == 9 and v == "$INSUNITS" and i + 1 < len(grupos):
                try:
                    unid = int(grupos[i + 1][1])
                except ValueError:
                    pass
    fator, sem_unid = _UNIDADES.get(unid, (1.0, True))
    if sem_unid:
        res.avisos.append("DXF sem unidade definida ($INSUNITS): considerado em milímetros.")
    paths = []
    i = 0
    while i < len(ents):
        tipo, g = ents[i]
        p = QPainterPath()
        if tipo == "LINE":
            p.moveTo(_num(g, 10), _num(g, 20))
            p.lineTo(_num(g, 11), _num(g, 21))
        elif tipo == "CIRCLE":
            cx, cy, r = _num(g, 10), _num(g, 20), _num(g, 40)
            if r > 0:
                p.addEllipse(QPointF(cx, cy), r, r)
        elif tipo == "ARC":
            cx, cy, r = _num(g, 10), _num(g, 20), _num(g, 40)
            a0, a1 = _num(g, 50), _num(g, 51)
            if r > 0:
                p.moveTo(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
                _arco(p, cx, cy, r, a0, a1)
        elif tipo == "ELLIPSE":
            cx, cy = _num(g, 10), _num(g, 20)
            mx, my, razao = _num(g, 11), _num(g, 21), _num(g, 40, 1.0)
            t0, t1 = _num(g, 41, 0.0), _num(g, 42, 2 * math.pi)
            maior = math.hypot(mx, my)
            if maior > 0:
                ang = math.atan2(my, mx)
                if t1 <= t0:
                    t1 += 2 * math.pi
                n = max(16, int(64 * (t1 - t0) / (2 * math.pi)))
                for k in range(n + 1):
                    t = t0 + (t1 - t0) * k / n
                    x, y = maior * math.cos(t), maior * razao * math.sin(t)
                    q = (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))
                    p.moveTo(*q) if k == 0 else p.lineTo(*q)
        elif tipo in ("LWPOLYLINE", "POLYLINE"):
            fechado = int(_num(g, 70)) & 1
            vert = []  # [(x, y, bulge)]
            if tipo == "LWPOLYLINE":
                for c, v in g:
                    if c == 10:
                        vert.append([float(v), 0.0, 0.0])
                    elif c == 20 and vert:
                        vert[-1][1] = float(v)
                    elif c == 42 and vert:
                        vert[-1][2] = float(v)
            else:
                i += 1
                while i < len(ents) and ents[i][0] == "VERTEX":
                    vg = ents[i][1]
                    vert.append([_num(vg, 10), _num(vg, 20), _num(vg, 42)])
                    i += 1
                if i < len(ents) and ents[i][0] != "SEQEND":
                    i -= 1
            if len(vert) >= 2:
                p.moveTo(vert[0][0], vert[0][1])
                pares = list(zip(vert, vert[1:])) + ([(vert[-1], vert[0])] if fechado else [])
                for a, b in pares:
                    _bulge(p, (a[0], a[1]), (b[0], b[1]), a[2])
        elif tipo not in ("SEQEND", "VERTEX"):
            res.ignorados[tipo] += 1
        if not p.isEmpty():
            paths.append((tipo, p))
        i += 1
    tf = QTransform(fator, 0, 0, -fator, 0, altura_mesa)  # (x·f, H − y·f)
    for k, (tipo, p) in enumerate(paths, 1):
        res.objetos.append((f"{tipo.capitalize()} {k}", tf.map(p)))
    return res


def gerar(paths, altura_mesa) -> str:
    """paths: caminhos em mm de documento. Texto DXF R12 (POLYLINE por contorno)."""
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4",
           "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    esc = 20.0
    for p in paths:
        for poly in p.toSubpathPolygons(QTransform.fromScale(esc, esc)):
            pts = [(q.x() / esc, altura_mesa - q.y() / esc) for q in poly]
            if len(pts) < 2:
                continue
            fechado = len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6
            if fechado:
                pts = pts[:-1]
            out += ["0", "POLYLINE", "8", "0", "66", "1", "70", "1" if fechado else "0"]
            for x, y in pts:
                out += ["0", "VERTEX", "8", "0", "10", f"{x:.4f}", "20", f"{y:.4f}"]
            out += ["0", "SEQEND"]
    out += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(out) + "\n"


def contar(res: Resultado) -> Counter:
    return Counter(n.split()[0] for n, _ in res.objetos)
