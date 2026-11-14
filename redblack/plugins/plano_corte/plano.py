"""Plano de corte: encaixe de peças retangulares em chapas (MaxRects, lado mais curto que sobra — BSSF).

Por material: as peças (com quantidade) entram da maior para a menor, cada uma no lugar livre onde sobra menos,
na primeira chapa onde couber; se não couber em nenhuma, abre outra chapa. "Gira" por peça permite 90°.
Medidas em mm; (x, y) = canto superior esquerdo da peça na chapa.
"""
from dataclasses import dataclass, field

EPS = 1e-9


@dataclass
class Peca:
    qtd: int
    larg: float
    alt: float
    material: int
    desc: str = ""
    girar: bool = True


@dataclass
class Material:
    cod: int
    nome: str
    esp: float
    larg: float
    alt: float


@dataclass
class Colocada:
    x: float
    y: float
    larg: float
    alt: float
    girada: bool
    desc: str
    n: int


@dataclass
class Chapa:
    pecas: list = field(default_factory=list)
    livres: list = field(default_factory=list)

    def usado(self, L, A):
        return sum(p.larg * p.alt for p in self.pecas) / (L * A)


def _cortar(livres, x, y, w, h):
    novos = []
    for fx, fy, fw, fh in livres:
        if x >= fx + fw - EPS or x + w <= fx + EPS or y >= fy + fh - EPS or y + h <= fy + EPS:
            novos.append((fx, fy, fw, fh))
            continue
        if x > fx + EPS:
            novos.append((fx, fy, x - fx, fh))
        if x + w < fx + fw - EPS:
            novos.append((x + w, fy, fx + fw - x - w, fh))
        if y > fy + EPS:
            novos.append((fx, fy, fw, y - fy))
        if y + h < fy + fh - EPS:
            novos.append((fx, y + h, fw, fy + fh - y - h))
    out = []
    for i, a in enumerate(novos):  # tira os contidos em outro
        if not any(j != i and a[0] >= b[0] - EPS and a[1] >= b[1] - EPS and a[0] + a[2] <= b[0] + b[2] + EPS
                   and a[1] + a[3] <= b[1] + b[3] + EPS and (a != b or j < i) for j, b in enumerate(novos)):
            out.append(a)
    return out


def _lugar(livres, w0, h0, girar):
    melhor = None
    for w, h, gir in ((w0, h0, False), (h0, w0, True)) if girar else ((w0, h0, False),):
        for fx, fy, fw, fh in livres:
            if w <= fw + EPS and h <= fh + EPS:
                k = (min(fw - w, fh - h), max(fw - w, fh - h), fy, fx)
                if melhor is None or k < melhor[0]:
                    melhor = (k, fx, fy, w, h, gir)
    return melhor


def planejar(pecas, L, A, espaco=3.0, margem=5.0):
    """(chapas, nao_cabem) para peças de UM material numa chapa L × A."""
    if espaco < 0 or margem < 0 or L <= 0 or A <= 0:
        raise ValueError("chapa, espaço e margem devem ser válidos")
    lista, n = [], 0
    for p in pecas:
        for _ in range(max(0, int(p.qtd))):
            n += 1
            lista.append((p, n))
    lista.sort(key=lambda t: (-max(t[0].larg, t[0].alt), -t[0].larg * t[0].alt))
    chapas, nao_cabem = [], []
    for p, k in lista:
        if p.larg <= 0 or p.alt <= 0:
            continue
        w0, h0 = p.larg + espaco, p.alt + espaco
        alvo = lugar = None
        for ch in chapas:
            lugar = _lugar(ch.livres, w0, h0, p.girar)
            if lugar:
                alvo = ch
                break
        if lugar is None:
            ch = Chapa(livres=[(margem, margem, L - 2 * margem + espaco, A - 2 * margem + espaco)])
            lugar = _lugar(ch.livres, w0, h0, p.girar)
            if lugar is None:
                nao_cabem.append(p)
                continue
            chapas.append(ch)
            alvo = ch
        _, x, y, w, h, gir = lugar
        alvo.pecas.append(Colocada(x, y, p.alt if gir else p.larg, p.larg if gir else p.alt, gir, p.desc, k))
        alvo.livres = _cortar(alvo.livres, x, y, w, h)
    return chapas, nao_cabem


def planejar_tudo(pecas, materiais, espaco=3.0, margem=5.0):
    """[(material, chapas, nao_cabem)] agrupando as peças pelo material."""
    por_cod = {m.cod: m for m in materiais}
    grupos = {}
    for p in pecas:
        grupos.setdefault(p.material, []).append(p)
    out = []
    for cod, ps in grupos.items():
        m = por_cod.get(cod)
        if m is None:
            out.append((None, [], ps))
            continue
        chapas, fora = planejar(ps, m.larg, m.alt, espaco, margem)
        out.append((m, chapas, fora))
    return out
