"""Disposição automática na mesa (nesting por retângulos): MaxRects, encaixe pelo lado mais curto (BSSF).

Cada peça entra pelo retângulo que a envolve (não pela forma exata): é simples, previsível e nunca sobrepõe.
shortcut: retângulos envolventes desperdiçam espaço em peças redondas/em L; para encaixe pela forma real
(peças dentro de furos/reentrâncias), trocar por um nesting de polígonos (no-fit polygon).
"""

EPS = 1e-9


def _cabe(f, w, h):
    return w <= f[2] + EPS and h <= f[3] + EPS


def _cortar(livres, r):
    """Tira o retângulo r (x, y, w, h) dos livres: cada livre que cruza r vira até 4 sobras (MaxRects)."""
    x, y, w, h = r
    novos = []
    for f in livres:
        fx, fy, fw, fh = f
        if x >= fx + fw - EPS or x + w <= fx + EPS or y >= fy + fh - EPS or y + h <= fy + EPS:
            novos.append(f)
            continue
        if x > fx + EPS:
            novos.append((fx, fy, x - fx, fh))
        if x + w < fx + fw - EPS:
            novos.append((x + w, fy, fx + fw - x - w, fh))
        if y > fy + EPS:
            novos.append((fx, fy, fw, y - fy))
        if y + h < fy + fh - EPS:
            novos.append((fx, y + h, fw, fy + fh - y - h))
    # remove os contidos em outro (mantém a lista pequena)
    out = []
    for i, a in enumerate(novos):
        dentro = any(j != i and a[0] >= b[0] - EPS and a[1] >= b[1] - EPS and a[0] + a[2] <= b[0] + b[2] + EPS
                     and a[1] + a[3] <= b[1] + b[3] + EPS and (a != b or j < i) for j, b in enumerate(novos))
        if not dentro:
            out.append(a)
    return out


def dispor(tamanhos, largura, altura, espaco=2.0, margem=0.0, girar=True, ocupados=()):
    """Posições para peças de `tamanhos` [(w, h)] dentro da mesa largura × altura (mm).

    espaco: vão mínimo entre peças; margem: vão até a borda da mesa; girar: permite 90°;
    ocupados: retângulos (x, y, w, h) já usados (outras peças), que também recebem o vão.
    Devolve, na ordem de entrada, (x, y, girada) do canto superior esquerdo da peça (já girada), ou None se
    não coube.
    """
    if espaco < 0 or margem < 0:
        raise ValueError("espaço e margem não podem ser negativos")
    # cada peça ocupa w+espaco × h+espaco; a área útil ganha +espaco para a última coluna/linha não perder o vão
    livres = [(margem, margem, largura - 2 * margem + espaco, altura - 2 * margem + espaco)]
    if livres[0][2] <= EPS or livres[0][3] <= EPS:
        return [None] * len(tamanhos)
    for x, y, w, h in ocupados:
        livres = _cortar(livres, (x - espaco, y - espaco, w + 2 * espaco, h + 2 * espaco))
    ordem = sorted(range(len(tamanhos)), key=lambda i: (-max(tamanhos[i]), -tamanhos[i][0] * tamanhos[i][1]))
    res = [None] * len(tamanhos)
    for i in ordem:
        w0, h0 = tamanhos[i][0] + espaco, tamanhos[i][1] + espaco
        melhor = None  # (lado curto que sobra, lado longo que sobra, y, x, w, h, girada)
        for w, h, gir in ((w0, h0, False), (h0, w0, True)) if girar else ((w0, h0, False),):
            for f in livres:
                if _cabe(f, w, h):
                    sobra = (min(f[2] - w, f[3] - h), max(f[2] - w, f[3] - h), f[1], f[0])
                    if melhor is None or sobra < melhor[:4]:
                        melhor = (*sobra, w, h, gir)
        if melhor is None:
            continue
        _, _, y, x, w, h, gir = melhor
        res[i] = (x, y, gir)
        livres = _cortar(livres, (x, y, w, h))
    return res
