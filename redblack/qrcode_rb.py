"""Código QR próprio (ISO/IEC 18004): modo byte (UTF-8), correção de erros nível M, versões 1 a 10.

Sem bibliotecas externas. `matriz(texto)` devolve a grade de módulos (True = escuro); `caminho(texto, lado_mm)`
devolve um QPainterPath em mm (retângulos por trecho de linha, origem no canto do símbolo, sem zona de silêncio).
"""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

# versão: (codewords totais, EC por bloco, blocos) — nível M
_TAB_M = {1: (26, 10, 1), 2: (44, 16, 1), 3: (70, 26, 1), 4: (100, 18, 2), 5: (134, 24, 2), 6: (172, 16, 4),
          7: (196, 18, 4), 8: (242, 22, 4), 9: (292, 22, 5), 10: (346, 26, 5)}
_ALINH = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
          9: [6, 26, 46], 10: [6, 28, 50]}
_FORMATO_M = 0  # bits do nível M no campo de formato


class TextoLongoDemais(ValueError):
    pass


# ---------- Reed-Solomon em GF(256), polinômio 0x11D ----------
def _mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _divisor(grau):
    r = [0] * (grau - 1) + [1]
    raiz = 1
    for _ in range(grau):
        for j in range(grau):
            r[j] = _mul(r[j], raiz)
            if j + 1 < grau:
                r[j] ^= r[j + 1]
        raiz = _mul(raiz, 0x02)
    return r


def _resto(dados, divisor):
    r = [0] * len(divisor)
    for b in dados:
        f = b ^ r.pop(0)
        r.append(0)
        for i, coef in enumerate(divisor):
            r[i] ^= _mul(coef, f)
    return r


# ---------- dados ----------
def _versao(n_bytes):
    for v, (total, ec, blocos) in _TAB_M.items():
        cap_bits = (total - ec * blocos) * 8
        if 4 + (8 if v < 10 else 16) + 8 * n_bytes <= cap_bits:
            return v
    raise TextoLongoDemais("Texto longo demais para o código QR (máximo ~213 bytes nesta versão).")


def _codewords(dados: bytes, v):
    total, ec, blocos = _TAB_M[v]
    cap = total - ec * blocos
    bits = [0, 1, 0, 0]
    n_cont = 8 if v < 10 else 16
    bits += [(len(dados) >> i) & 1 for i in range(n_cont - 1, -1, -1)]
    for b in dados:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(cw) < cap:
        cw.append(pad)
        pad ^= 0xEC ^ 0x11
    # blocos: os curtos primeiro
    curtos = blocos - total % blocos
    tam_curto = total // blocos
    div = _divisor(ec)
    dblocos, eblocos, k = [], [], 0
    for i in range(blocos):
        n = tam_curto - ec + (0 if i < curtos else 1)
        d = cw[k:k + n]
        k += n
        dblocos.append(d)
        eblocos.append(_resto(d, div))
    out = []
    for i in range(max(len(d) for d in dblocos)):
        out += [d[i] for d in dblocos if i < len(d)]
    for i in range(ec):
        out += [e[i] for e in eblocos]
    return out


# ---------- matriz ----------
def _base(v):
    n = 17 + 4 * v
    m = [[False] * n for _ in range(n)]
    f = [[False] * n for _ in range(n)]

    def p(x, y, escuro):
        m[y][x] = escuro
        f[y][x] = True

    for i in range(n):
        p(6, i, i % 2 == 0)
        p(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < n and 0 <= y < n:
                    p(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    pos = _ALINH[v]
    for i, ay in enumerate(pos):
        for j, ax in enumerate(pos):
            if (i, j) in ((0, 0), (0, len(pos) - 1), (len(pos) - 1, 0)):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    p(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
    _formato(m, f, 0, n)
    if v >= 7:
        r = v
        for _ in range(12):
            r = (r << 1) ^ ((r >> 11) * 0x1F25)
        bits = v << 12 | r
        for i in range(18):
            b = (bits >> i) & 1 == 1
            a, c = n - 11 + i % 3, i // 3
            p(a, c, b)
            p(c, a, b)
    return m, f


def _formato(m, f, mascara, n):
    dados = _FORMATO_M << 3 | mascara
    r = dados
    for _ in range(10):
        r = (r << 1) ^ ((r >> 9) * 0x537)
    bits = (dados << 10 | r) ^ 0x5412

    def p(x, y, i):
        m[y][x] = (bits >> i) & 1 == 1
        f[y][x] = True

    for i in range(6):
        p(8, i, i)
    p(8, 7, 6)
    p(8, 8, 7)
    p(7, 8, 8)
    for i in range(9, 15):
        p(14 - i, 8, i)
    for i in range(8):
        p(n - 1 - i, 8, i)
    for i in range(8, 15):
        p(8, n - 15 + i, i)
    m[n - 8][8] = True  # módulo escuro fixo
    f[n - 8][8] = True


_MASCARAS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
             lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
             lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
             lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]


def _penalidade(m):
    n, pen = len(m), 0
    for linhas in (m, [list(c) for c in zip(*m)]):
        for lin in linhas:
            corrida, cor = 1, lin[0]
            for x in range(1, n):
                if lin[x] == cor:
                    corrida += 1
                else:
                    pen += corrida - 2 if corrida >= 5 else 0
                    corrida, cor = 1, lin[x]
            pen += corrida - 2 if corrida >= 5 else 0
            s = "".join("1" if c else "0" for c in lin)
            pen += 40 * (s.count("10111010000") + s.count("00001011101"))
    for y in range(n - 1):
        for x in range(n - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                pen += 3
    escuros = sum(map(sum, m))
    pen += 10 * (abs(escuros * 20 - n * n * 10) // (n * n))
    return pen


def matriz(texto: str):
    dados = texto.encode("utf-8")
    v = _versao(len(dados))
    cw = _codewords(dados, v)
    base, func = _base(v)
    n = len(base)
    colocado = [lin[:] for lin in base]
    i, total = 0, len(cw) * 8
    direita = n - 1
    while direita >= 1:
        if direita == 6:
            direita = 5
        for vert in range(n):
            for j in range(2):
                x = direita - j
                subindo = ((direita + 1) & 2) == 0
                y = n - 1 - vert if subindo else vert
                if not func[y][x] and i < total:
                    colocado[y][x] = (cw[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        direita -= 2
    melhor = None
    for k, fn in enumerate(_MASCARAS):
        m = [[colocado[y][x] ^ (not func[y][x] and fn(x, y)) for x in range(n)] for y in range(n)]
        _formato(m, [[False] * n for _ in range(n)], k, n)
        pen = _penalidade(m)
        if melhor is None or pen < melhor[0]:
            melhor = (pen, m)
    return melhor[1]


def caminho(texto: str, lado_mm: float) -> QPainterPath:
    """Símbolo com `lado_mm` de lado (sem a margem de silêncio de 4 módulos, que deve ficar livre)."""
    m = matriz(texto)
    n = len(m)
    t = lado_mm / n
    p = QPainterPath()
    for y, lin in enumerate(m):
        x = 0
        while x < n:
            if lin[x]:
                x0 = x
                while x < n and lin[x]:
                    x += 1
                p.addRect(QRectF(x0 * t, y * t, (x - x0) * t, t))
            else:
                x += 1
    return p
