"""Percurso do laser e estimativa de tempo (Etapa 10) — sem interface, sem G-code, sem máquina.

Gera, a partir do documento, a sequência de movimentos na ordem de saída:
  "corte": laser emitindo, na velocidade da camada;
  "vazio": deslocamento sem emissão, na velocidade de deslocamento (rápido);
  "sobra": sobrevarredura — laser apagado, na velocidade da camada, antes/depois de cada linha de preenchimento.
Ordem: camadas na ordem da lista (só as com Saída ligada; Exibir não importa), dentro da camada
os objetos na ordem do documento; passadas repetem a camada inteira. Parte da origem e volta a ela.

Modelo de tempo = comprimento / velocidade. NÃO considera aceleração, sobrevarredura nem
comportamento do firmware: é uma estimativa mínima; o tempo real tende a ser maior.
A velocidade de deslocamento padrão é uma suposição (máquina ainda não confirmada).
"""
import bisect
import math
from dataclasses import dataclass
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform

from . import camadas as cm
from . import geometria as g
from . import raster
from .importar_imagem import ImagemOriginal
from .objetos import GroupData

DEFAULT_RAPIDO_MM_MIN = 6000.0  # SUPOSIÇÃO: confirmar na máquina (docs/MAQUINA.md)
MAX_LINHAS = 400_000            # linhas de preenchimento somadas por objeto (~1 s a cada 160 mil); protege a interface
EPS = 1e-9
_ESC = 20.0                     # achatamento de curvas: tolerância do Qt (0,25) vira 0,0125 mm


class LimiteExcedido(Exception):
    """Trabalho grande demais para a prévia; a mensagem é exibida ao usuário."""


class Trecho(NamedTuple):
    tipo: str          # "corte" | "vazio" | "sobra"
    pontos: tuple      # ((x, y), …) em mm, coordenadas de documento
    camada: str
    velocidade: float  # mm/min
    comprimento: float
    tempo_s: float
    potencia: float = None  # % só para gravação de imagem em tons; None = potência máxima da camada


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _comprimento(pts):
    return sum(_dist(a, b) for a, b in zip(pts, pts[1:]))


# ---------- geometria ----------
def folhas(snap, parent=None):
    """(caminho, matriz total, camada, extra) de cada objeto folha; grupos são percorridos."""
    path, tf, _name, layer, _color, extra = snap
    total = tf if parent is None else tf * parent  # matriz do filho · matriz do grupo
    if isinstance(extra, GroupData):
        for c in extra.children:
            yield from folhas(c, total)
    else:
        yield path, total, layer, extra


def poligonos(path, tf):
    """Contornos achatados em mm de documento (curvas com erro < 0,0125 mm)."""
    m = tf * QTransform.fromScale(_ESC, _ESC)
    out = []
    for poly in path.toSubpathPolygons(m):
        pts = []
        for p in poly:
            q = (p.x() / _ESC, p.y() / _ESC)
            if not pts or _dist(pts[-1], q) > EPS:
                pts.append(q)
        if len(pts) >= 2:
            out.append(pts)
    return out


_KERF_ESC = 1000.0  # operações booleanas do Qt em µm: curvas achatadas com erro desprezível


def compensar_kerf(path: QPainterPath, kerf: float) -> QPainterPath:
    """Desloca os contornos fechados k/2 para FORA do material: a peça cresce k/2 e os furos encolhem k/2,
    então, depois que o feixe remove a largura k, a peça sai na medida desenhada.

    Material = área preenchida do caminho (regra do próprio caminho). Cantos ficam arredondados com raio k/2,
    como o próprio feixe faz. Trechos abertos (linhas soltas) não têm lado de dentro e ficam como estão.
    """
    if kerf <= 0 or path.isEmpty():
        return path
    fechados, abertos = QPainterPath(), QPainterPath()
    fechados.setFillRule(path.fillRule())
    for poly in path.toSubpathPolygons(QTransform.fromScale(_KERF_ESC, _KERF_ESC)):
        d = poly.first() - poly.last() if len(poly) > 2 else None
        alvo = fechados if d is not None and abs(d.x()) + abs(d.y()) < 1e-3 else abertos  # fechado (µm)
        alvo.addPolygon(poly)
    if fechados.isEmpty():
        return path
    st = QPainterPathStroker()
    st.setWidth(kerf * _KERF_ESC)
    st.setJoinStyle(Qt.RoundJoin)
    st.setCapStyle(Qt.RoundCap)
    out = QPainterPath()
    for poly in fechados.united(st.createStroke(fechados)).simplified().toSubpathPolygons():
        area = sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(poly, list(poly)[1:] + [poly.first()])) / 2
        if abs(area) > 1.0:  # descarta lascas da operação booleana (< 1e-6 mm²)
            out.addPolygon(poly)
    out.addPath(abertos)
    return QTransform.fromScale(1 / _KERF_ESC, 1 / _KERF_ESC).map(out)


def _linhas_estimadas(polys, intervalo):
    ys = [y for poly in polys for _, y in poly]
    return max(1, math.ceil((max(ys) - min(ys)) / intervalo)) if ys else 0


def _girar(pts, graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def hachura(polys, intervalo, winding=True, angulo=0.0, bidirecional=True):
    """Linhas de preenchimento no ângulo dado (0 = horizontal, 90 = vertical; positivo = horário na tela).

    O ângulo é feito girando os contornos, varrendo na horizontal e desfazendo o giro nas linhas.
    """
    if abs(angulo % 360) > 1e-12:
        linhas = _hachura_h([_girar(p, -angulo) for p in polys], intervalo, winding, bidirecional)
        return [tuple(_girar(list(ln), angulo)) for ln in linhas]
    return _hachura_h(polys, intervalo, winding, bidirecional)


def _hachura_h(polys, intervalo, winding=True, bidirecional=True):
    """Linhas horizontais de preenchimento, alternando o sentido (bidirecional).

    Linhas em y = topo + (k + 0,5)·intervalo; contornos abertos contam como fechados.
    Regra de preenchimento: winding (não-zero) ou par-ímpar. Forma menor que o intervalo recebe
    uma linha no meio (para não sumir).
    """
    ys = [y for poly in polys for _, y in poly]
    if not ys:
        return []
    top, bottom = min(ys), max(ys)
    n = math.ceil((bottom - top) / intervalo - 0.5)
    ymid = None
    if (bottom - top) > EPS and n < 1:
        n, ymid = 1, top + (bottom - top) / 2  # forma menor que o intervalo: uma linha no centro
    if n < 1:
        return []
    cruz = [[] for _ in range(n)]

    def y_of(k):
        return ymid if ymid is not None else top + (k + 0.5) * intervalo

    for poly in polys:
        pts = poly if poly[0] == poly[-1] else poly + [poly[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y0 == y1:
                continue
            lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
            d = 1 if y1 > y0 else -1
            if ymid is not None:
                ks = [0] if lo <= ymid < hi else []
            else:
                k_lo = max(0, math.ceil((lo - top) / intervalo - 0.5))
                k_hi = min(n - 1, math.ceil((hi - top) / intervalo - 0.5) - 1)  # [lo, hi): vértice conta uma vez
                ks = range(k_lo, k_hi + 1)
            for k in ks:
                y = y_of(k)
                cruz[k].append((x0 + (y - y0) * (x1 - x0) / (y1 - y0), d))
    linhas, emitidas = [], 0
    for k in range(n):
        spans, count, start = [], 0, None
        for x, d in sorted(cruz[k]):
            was = (count != 0) if winding else (count % 2 == 1)
            count += d if winding else 1
            now = (count != 0) if winding else (count % 2 == 1)
            if not was and now:
                start = x
            elif was and not now and x - start > EPS:
                spans.append((start, x))
        if not spans:
            continue
        y = y_of(k)
        if emitidas % 2 == 0 or not bidirecional:
            linhas += [((a, y), (b, y)) for a, b in spans]
        else:
            linhas += [((b, y), (a, y)) for a, b in reversed(spans)]
        emitidas += 1
    return linhas


# ---------- percurso ----------
@dataclass(frozen=True)
class Percurso:
    trechos: tuple
    rapido: float
    inicio: tuple

    @property
    def tempo_s(self):
        return sum(t.tempo_s for t in self.trechos)

    @property
    def comprimento_corte(self):
        return sum(t.comprimento for t in self.trechos if t.tipo == "corte")

    @property
    def comprimento_vazio(self):
        return sum(t.comprimento for t in self.trechos if t.tipo == "vazio")

    def por_camada(self) -> dict:
        """{camada: (comprimento de corte, tempo de corte)} na ordem de saída."""
        out = {}
        for t in self.trechos:
            if t.tipo == "corte":
                c, s = out.get(t.camada, (0.0, 0.0))
                out[t.camada] = (c + t.comprimento, s + t.tempo_s)
        return out

    def limites(self):
        """(xmin, ymin, xmax, ymax) de tudo que o laser percorre, ou None."""
        pts = [p for t in self.trechos for p in t.pontos]
        if not pts:
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def fora_da_mesa(self) -> bool:
        b = self.limites()
        return bool(b) and (b[0] < -EPS or b[1] < -EPS or b[2] > g.BED_W + EPS or b[3] > g.BED_H + EPS)

    def cronograma(self):
        """Tempos acumulados no fim de cada trecho (para a simulação)."""
        acc, out = 0.0, []
        for t in self.trechos:
            acc += t.tempo_s
            out.append(acc)
        return out

    def estado_em(self, t: float, cron=None):
        """Estado da simulação no instante t (s): (trechos concluídos, pontos do trecho em curso até
        agora, ponto atual, emitindo?). Antes do início e depois do fim ficam no ponto inicial/final."""
        cron = cron or self.cronograma()
        if not self.trechos:
            return 0, (), self.inicio, False
        t = min(max(t, 0.0), cron[-1])
        i = min(bisect.bisect_right(cron, t), len(self.trechos) - 1)
        tr = self.trechos[i]
        t0 = cron[i - 1] if i else 0.0
        if t >= cron[i] - 1e-9:  # trecho concluído: devolve o ponto final exato (sem erro de arredondamento)
            return i + 1, tr.pontos, tr.pontos[-1], tr.tipo == "corte"
        frac = 0.0 if tr.tempo_s <= 0 else (t - t0) / tr.tempo_s
        alvo, pts, acc = frac * tr.comprimento, [tr.pontos[0]], 0.0
        for a, b in zip(tr.pontos, tr.pontos[1:]):
            seg = _dist(a, b)
            if acc + seg >= alvo - EPS:
                f = 0.0 if seg == 0 else (alvo - acc) / seg
                pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                break
            pts.append(b)
            acc += seg
        return i, tuple(pts), pts[-1], tr.tipo == "corte"


def _dentro(pt, poly) -> bool:
    """Ponto dentro de um polígono fechado (regra par-ímpar)."""
    x, y = pt
    dentro = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            dentro = not dentro
    return dentro


def _fechada(pts) -> bool:
    return len(pts) > 3 and _dist(pts[0], pts[-1]) < 1e-6


class _LinhaRaster:
    """Uma linha de varredura de imagem: [(pontos, potência), …] na mesma reta."""
    __slots__ = ("segs",)

    def __init__(self, segs):
        self.segs = segs


def com_sobrecorte(pts, mm):
    """Contorno fechado que continua `mm` além do ponto inicial (dá a volta de novo pelo começo)."""
    if mm <= 0 or not _fechada(pts):
        return pts
    extra, acc = [], 0.0
    for a, b in zip(pts, pts[1:]):
        d = _dist(a, b)
        if acc + d >= mm:
            t = (mm - acc) / d if d > EPS else 0.0
            extra.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
        extra.append(b)
        acc += d
    return list(pts) + extra


def _ponta_na_sobra(p, d, contornos, mm):
    """Ponto a `mm` de p, perpendicular à direção d, do lado da sobra (fora do material = dentro de um número
    par de contornos: vale para o contorno externo e para furos). None se nenhum lado serve."""
    n = math.hypot(*d)
    if n < EPS:
        return None
    nx, ny = -d[1] / n, d[0] / n
    for dist in (mm, mm / 2):
        for s in (1, -1):
            q = (p[0] + s * nx * dist, p[1] + s * ny * dist)
            dentro_mesa = -EPS <= q[0] <= g.BED_W + EPS and -EPS <= q[1] <= g.BED_H + EPS
            if dentro_mesa and sum(_dentro(q, c) for c in contornos if _fechada(c)) % 2 == 0:
                return q
    return None


def com_entrada_saida(pts, contornos, entrada, saida):
    """Contorno fechado com reta de entrada antes do início e de saída depois do fim (lado da sobra)."""
    if (entrada <= 0 and saida <= 0) or not _fechada(pts):
        return pts
    pts = list(pts)
    if entrada > 0 and (q := _ponta_na_sobra(pts[0], (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]),
                                             contornos, entrada)):
        pts = [q] + pts
    if saida > 0 and (q := _ponta_na_sobra(pts[-1], (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]),
                                           contornos, saida)):
        pts = pts + [q]
    return pts


def com_guias(pts, qtd, largura):
    """Contorno fechado dividido em `qtd` trechos de corte, deixando `qtd` pontes de `largura` mm sem corte,
    igualmente espaçadas (a 1ª ponte no meio do 1º intervalo). Abertos ou curtos demais: inalterados."""
    if qtd <= 0 or largura <= 0 or not _fechada(pts):
        return [pts]
    dobro = list(pts) + list(pts[1:])  # dar a volta = seguir pelo contorno repetido
    cum = [0.0]
    for a, b in zip(dobro, dobro[1:]):
        cum.append(cum[-1] + _dist(a, b))
    L = cum[len(pts) - 1]
    if qtd * largura >= L * 0.9:
        return [pts]

    def ponto(s):
        for i in range(len(cum) - 1):
            if cum[i] - EPS <= s <= cum[i + 1] + EPS:
                seg = cum[i + 1] - cum[i]
                t = 0.0 if seg < EPS else (s - cum[i]) / seg
                a, b = dobro[i], dobro[i + 1]
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        return dobro[-1]

    passo, out = L / qtd, []
    for k in range(qtd):  # do fim da ponte k ao começo da ponte k+1
        s0 = k * passo + passo / 2 + largura / 2
        s1 = (k + 1) * passo + passo / 2 - largura / 2
        out.append([ponto(s0)] + [dobro[i] for i in range(len(dobro)) if s0 + EPS < cum[i] < s1 - EPS] + [ponto(s1)])
    return out


def sem_sobrepostas(linhas):
    """Tira trechos repetidos (mesmas pontas, em qualquer sentido, tolerância 0,001 mm) entre todas as linhas
    da camada; cada linha é quebrada onde um trecho saiu. Sobreposição parcial (pontas diferentes) fica."""
    vistos, out = set(), []
    for ln in linhas:
        atual = [ln[0]]
        for a, b in zip(ln, ln[1:]):
            ka, kb = (round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))
            chave = (ka, kb) if ka <= kb else (kb, ka)
            if chave in vistos or ka == kb:
                if len(atual) >= 2:
                    out.append(atual)
                atual = [b]
            else:
                vistos.add(chave)
                atual.append(b)
        if len(atual) >= 2:
            out.append(atual)
    return out


class _Grade:
    """Índice espacial simples: caixas em células de uma grade regular (busca sem comparar todos com todos)."""

    def __init__(self, caixas, n_cel=64):
        xs0 = min(c[0] for c in caixas)
        ys0 = min(c[1] for c in caixas)
        xs1 = max(c[2] for c in caixas)
        ys1 = max(c[3] for c in caixas)
        self.x0, self.y0 = xs0, ys0
        self.cel = max((xs1 - xs0), (ys1 - ys0), 1e-9) / n_cel
        self.celulas = {}

    def chave(self, x, y):
        return int((x - self.x0) // self.cel), int((y - self.y0) // self.cel)

    def inserir_caixa(self, i, c):
        (a, b), (e, f) = self.chave(c[0], c[1]), self.chave(c[2], c[3])
        for gx in range(a, e + 1):
            for gy in range(b, f + 1):
                self.celulas.setdefault((gx, gy), []).append(i)

    def no_ponto(self, x, y):
        return self.celulas.get(self.chave(x, y), ())


def ordenar_contornos(linhas, pos, internas_primeiro=True, vizinho=False):
    """Ordem de corte dos contornos de uma camada (modo Linha).

    internas_primeiro: o que está dentro de outro contorno fechado sai antes dele (furos antes do contorno
    externo — a peça não se solta antes de terminar). A ordem original é mantida no resto (ordenação estável).
    vizinho: dentro de cada nível, o próximo é o mais perto da posição atual; contornos fechados começam no
    vértice mais próximo e linhas abertas podem ser feitas ao contrário.
    Usa um índice espacial em grade: milhares de contornos sem comparar todos com todos.
    """
    linhas = [list(x) for x in linhas]
    if internas_primeiro and len(linhas) > 1:
        caixas = [(min(p[0] for p in ln), min(p[1] for p in ln), max(p[0] for p in ln), max(p[1] for p in ln))
                  for ln in linhas]
        grade = _Grade(caixas)
        for j, ln in enumerate(linhas):
            if _fechada(ln):
                grade.inserir_caixa(j, caixas[j])

        def prof(i):
            a = caixas[i]
            x, y = linhas[i][0]
            return sum(1 for j in grade.no_ponto(x, y) if j != i
                       and caixas[j][0] <= a[0] and caixas[j][1] <= a[1] and caixas[j][2] >= a[2] and caixas[j][3] >= a[3]
                       and (caixas[j] != a or j < i) and _dentro(linhas[i][0], linhas[j]))

        niveis = [prof(i) for i in range(len(linhas))]
        ordem = sorted(range(len(linhas)), key=lambda i: -niveis[i])
        grupos = []
        for i in ordem:
            if grupos and niveis[grupos[-1][0]] == niveis[i]:
                grupos[-1].append(i)
            else:
                grupos.append([i])
    else:
        grupos = [list(range(len(linhas)))]
    if not vizinho:
        return [linhas[i] for g in grupos for i in g]
    out = []
    for g in grupos:
        out += _vizinho(linhas, g, pos)
        if out:
            pos = out[-1][-1]
    return out


def _melhor_inicio(ln, pos):
    """(distância, contorno pronto para cortar) começando o mais perto de pos."""
    if _fechada(ln):
        j = min(range(len(ln) - 1), key=lambda k: _dist(pos, ln[k]))
        return _dist(pos, ln[j]), ln[j:-1] + ln[:j] + [ln[j]]
    d0, d1 = _dist(pos, ln[0]), _dist(pos, ln[-1])
    return (d0, ln) if d0 <= d1 else (d1, ln[::-1])


def _vizinho(linhas, indices, pos):
    """Vizinho mais próximo com busca em anéis numa grade de caixas (resultado igual ao de comparar todos)."""
    if not indices:
        return []
    caixas = {i: (min(p[0] for p in linhas[i]), min(p[1] for p in linhas[i]),
                  max(p[0] for p in linhas[i]), max(p[1] for p in linhas[i])) for i in indices}
    grade = _Grade(list(caixas.values()), n_cel=max(4, int(len(indices) ** 0.5)))
    for i in indices:
        grade.inserir_caixa(i, caixas[i])
    restam, out = set(indices), []

    def dist_caixa(c, p):  # distância de p à caixa (limite inferior da distância a qualquer vértice)
        dx = max(c[0] - p[0], 0.0, p[0] - c[2])
        dy = max(c[1] - p[1], 0.0, p[1] - c[3])
        return math.hypot(dx, dy)

    nmax = max(max(k[0] for k in grade.celulas), max(k[1] for k in grade.celulas)) + 2
    while restam:
        cx, cy = grade.chave(*pos)
        melhor, anel = None, 0
        while True:
            vistos = set()
            for gx in range(cx - anel, cx + anel + 1):
                for gy in (cy - anel, cy + anel) if abs(gx - cx) != anel else range(cy - anel, cy + anel + 1):
                    for i in grade.celulas.get((gx, gy), ()):
                        if i in restam and i not in vistos:
                            vistos.add(i)
                            if melhor is not None and dist_caixa(caixas[i], pos) >= melhor[0]:
                                continue
                            d, feita = _melhor_inicio(linhas[i], pos)
                            if melhor is None or d < melhor[0] or (d == melhor[0] and i < melhor[1]):
                                melhor = (d, i, feita)
            # células além do anel ficam a pelo menos `anel` células de distância
            if melhor is not None and melhor[0] <= anel * grade.cel:
                break
            anel += 1
            if anel > nmax + abs(cx) + abs(cy):
                break
        _, i, feita = melhor
        restam.discard(i)
        out.append(feita)
        pos = feita[-1]
    return out


def gerar(snapshots, camadas, rapido=DEFAULT_RAPIDO_MM_MIN, inicio=None, internas_primeiro=True,
          vizinho=False, remover_sobrepostas=False) -> Percurso:
    if rapido <= 0:
        raise ValueError("velocidade de deslocamento deve ser positiva")
    if inicio is None:
        inicio = g.canto_origem()  # o laser parte da origem da máquina e volta para ela
    por_camada = {}
    for snap in snapshots:
        for path, tf, layer, extra in folhas(snap):
            por_camada.setdefault(layer, []).append((path, tf, extra))
    camadas = cm.expandir(camadas)  # subcamadas viram camadas virtuais sobre os mesmos objetos
    for c in camadas:
        if c.id not in por_camada and cm.base_id(c.id) in por_camada:
            por_camada[c.id] = por_camada[cm.base_id(c.id)]
    ativas = [c for c in camadas if c.saida and por_camada.get(c.id)]
    # Proteção: conta as linhas de preenchimento antes de gerá-las.
    linhas = 0
    for c in ativas:
        if c.modo != "linha":
            for path, tf, _ in por_camada[c.id]:
                linhas += _linhas_estimadas(poligonos(path, tf), c.intervalo_mm)
            if linhas > MAX_LINHAS:
                raise LimiteExcedido(f"Preenchimento grande demais para a prévia (camada {c.id}: "
                                     f"mais de {MAX_LINHAS} linhas). Aumente o intervalo de linhas.")
    trechos, pos = [], tuple(inicio)

    from . import gcode as _gc  # compensação do eixo X (só cortes): o tempo estimado acompanha o G-code
    _comp = (_gc.PERFIL.comp_x_desconto, _gc.PERFIL.comp_x_minimo)
    _linha = {c.id for c in camadas if c.modo == "linha"}

    def _tempo(pts, vel, camada):
        if _comp[0] <= 0 or camada not in _linha:
            return _comprimento(pts) / (vel / 60.0)
        t = 0.0
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            seg = math.hypot(dx, dy)
            if seg > 0:
                t += seg / (_gc.velocidade_compensada(vel, _gc.peso_x(dx, dy), *_comp) / 60.0)
        return t

    def add(tipo, pts, camada, vel, pot=None):
        comp = _comprimento(pts)
        if comp > EPS:
            tempo = _tempo(pts, vel, camada) if tipo == "corte" else comp / (vel / 60.0)
            trechos.append(Trecho(tipo, tuple(pts), camada, vel, comp, tempo, pot))

    for c in ativas:
        imagens = [(path, tf, ex) for path, tf, ex in por_camada[c.id] if isinstance(ex, ImagemOriginal)]
        objs = [(poligonos(path, tf), path, tf) for path, tf, ex in por_camada[c.id]
                if not isinstance(ex, ImagemOriginal)]

        def linhas_da_passada(k):
            if c.modo == "linha":
                out = []
                for polys, path, tf in objs:
                    if c.kerf_mm > 0:
                        polys = poligonos(compensar_kerf(tf.map(path), c.kerf_mm), QTransform())
                    out += [tuple(p) for p in polys]
                ordem = ordenar_contornos(out, pos, internas_primeiro, vizinho)
                if remover_sobrepostas:
                    ordem = sem_sobrepostas(ordem)
                if c.guias_qtd > 0 and c.guias_mm > 0:  # guias primeiro: seguram a peça (sobrecorte não se aplica)
                    ordem = [t for ln in ordem for t in com_guias(ln, c.guias_qtd, c.guias_mm)]
                else:
                    if c.sobrecorte_mm > 0:
                        ordem = [com_sobrecorte(ln, c.sobrecorte_mm) for ln in ordem]
                    if c.entrada_mm > 0 or c.saida_corte_mm > 0:  # guias abrem o contorno: aí não se aplica
                        ordem = [com_entrada_saida(ln, out, c.entrada_mm, c.saida_corte_mm) for ln in ordem]
                return [(tuple(map(tuple, ln)), None) for ln in ordem]
            ang = c.angulo_graus + k * c.angulo_inc_graus
            ras = []
            for path, tf, ex in imagens:  # imagem: só onde há tom (branco nunca liga o laser)
                r_ = path.boundingRect()
                # Tamanho REAL na mesa (a imagem pode ter sido reduzida/ampliada pela transformação): a grade de
                # pontos usa esse tamanho, senão o intervalo de linhas sairia dividido pela escala (ex.: imagem
                # colada a 335 mm e reduzida para 50 mm → linhas a 0,015 mm em vez de 0,1 mm).
                sx, sy = math.hypot(tf.m11(), tf.m12()) or 1.0, math.hypot(tf.m21(), tf.m22()) or 1.0
                local = (QTransform.fromScale(1 / sx, 1 / sy) * QTransform.fromTranslate(r_.left(), r_.top()) * tf)
                img, larg, alt = ex.qimage, r_.width() * sx, r_.height() * sy
                if abs(ang % 180 - 90) < 0.5:  # varredura vertical: varre a imagem girada 90° e devolve ao lugar
                    # shortcut: imagem só varre a 0° ou 90° (outros ângulos ficam em 0°); girar livre se pedirem
                    img = img.transformed(QTransform().rotate(90))  # pixel (x, y) -> (alt - y, x)
                    local = QTransform(0, -1, 1, 0, 0, alt) * local  # (u, v) girado -> (v, alt - u) original
                    larg, alt = alt, larg
                try:
                    ras += raster.trechos(img, larg, alt, local, c.intervalo_mm,
                                          c.modo_imagem,
                                          c.limiar_pct, c.potencia_min, c.potencia_max, c.bidirecional, c.negativo,
                                          (c.brilho_pct, c.contraste_pct, c.gama),
                                          (c.meio_tom_cpi, c.meio_tom_angulo))
                except raster.RasterGrandeDemais as e:
                    raise LimiteExcedido(f"Camada {c.id}: {e}") from e
            angs = [ang] + ([ang + 90] if c.hachura_cruzada else [])
            if c.preencher_juntas and objs:  # uma varredura para todos (regra winding só se todos forem winding)
                todos = [q for polys, _, _ in objs for q in polys]
                wind = all(path.fillRule() == Qt.WindingFill for _, path, _ in objs)
                return [_LinhaRaster(r) for r in ras] + [(ln, None) for a in angs for ln in hachura(
                    todos, c.intervalo_mm, wind, a, c.bidirecional)]
            return [_LinhaRaster(r) for r in ras] + [(ln, None) for a in angs for polys, path, _ in objs
                          for ln in hachura(polys, c.intervalo_mm, path.fillRule() == Qt.WindingFill, a,
                                            c.bidirecional)]

        fixas = linhas_da_passada(0) if c.modo == "linha" or not c.angulo_inc_graus else None
        sobra = c.sobrevarredura_mm if c.modo != "linha" else 0.0
        for k in range(c.passadas):
            for item in (fixas if fixas is not None else linhas_da_passada(k)):
                if isinstance(item, _LinhaRaster):  # imagem: a linha inteira na velocidade da camada
                    segs = item.segs
                    ini, fim = segs[0][0][0], segs[-1][0][-1]
                    L = _dist(ini, fim)
                    ux, uy = ((fim[0] - ini[0]) / L, (fim[1] - ini[1]) / L) if L > EPS else (0.0, 0.0)
                    antes = (ini[0] - ux * sobra, ini[1] - uy * sobra)
                    if _dist(pos, antes) > EPS:
                        add("vazio", (pos, antes), c.id, rapido)
                    cur = antes
                    for pts, pot in segs:
                        if _dist(cur, pts[0]) > EPS:  # vão (ou sobrevarredura): G1 com laser em zero, sem frear
                            add("sobra", (cur, pts[0]), c.id, c.velocidade_mm_min)
                        add("corte", pts, c.id, c.velocidade_mm_min, pot)
                        cur = pts[-1]
                    depois = (fim[0] + ux * sobra, fim[1] + uy * sobra)
                    if sobra > 0:
                        add("sobra", (fim, depois), c.id, c.velocidade_mm_min)
                    pos = depois if sobra > 0 else fim
                    continue
                pts, pot = item
                ini, fim = pts[0], pts[-1]
                if sobra > 0:
                    L = _dist(ini, fim)
                    ux, uy = ((fim[0] - ini[0]) / L, (fim[1] - ini[1]) / L) if L > EPS else (0.0, 0.0)
                    antes = (ini[0] - ux * sobra, ini[1] - uy * sobra)
                    depois = (fim[0] + ux * sobra, fim[1] + uy * sobra)
                    if _dist(pos, antes) > EPS:
                        add("vazio", (pos, antes), c.id, rapido)
                    add("sobra", (antes, ini), c.id, c.velocidade_mm_min)
                    add("corte", pts, c.id, c.velocidade_mm_min, pot)
                    add("sobra", (fim, depois), c.id, c.velocidade_mm_min)
                    pos = depois
                    continue
                if _dist(pos, ini) > EPS:
                    add("vazio", (pos, ini), c.id, rapido)
                add("corte", pts, c.id, c.velocidade_mm_min, pot)
                pos = fim
    if trechos and _dist(pos, inicio) > EPS:
        add("vazio", (pos, tuple(inicio)), "—", rapido)
    return Percurso(tuple(trechos), rapido, tuple(inicio))


def fmt_tempo(s: float) -> str:
    s = int(round(s))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {sec:02d} s"
    return f"{sec} s"
