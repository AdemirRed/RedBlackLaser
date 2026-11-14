"""Contas para gravar em cilindros e copos (retos ou cônicos) no rotativo.

Medidas em mm. Copo cônico = tronco de cone: diâmetro da boca (topo), da base e altura. A arte fica numa faixa
que começa `inicio` mm abaixo da boca e tem `altura_arte` mm.

- circunferência = π × diâmetro no ponto (no cone, o diâmetro muda linearmente com a altura);
- largura útil = circunferência − alça (em mm de arco) − margens;
- no cone a arte "abre" para cima: diferença entre as circunferências do topo e da base da faixa = distorção;
- molde em leque (planificação do tronco de cone) para papel/vinil/sublimação: raios a partir do vértice e ângulo.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Peca:
    diametro_topo: float = 80.0
    diametro_base: float = 80.0   # igual ao topo = cilindro reto
    altura: float = 100.0
    inicio: float = 15.0          # distância da boca até o topo da arte
    altura_arte: float = 50.0
    alca_mm: float = 0.0          # largura ocupada pela alça (caneca), em mm medidos na superfície
    margem_mm: float = 5.0        # folga de cada lado da arte (perto da alça / emenda)
    repeticoes: int = 1           # artes iguais em volta (ex.: 2 = frente e verso)
    foco_mm: float = 1.5          # quanto o foco do laser tolera de variação de altura (diodo ~1–2 mm)
    pontos: tuple = ()            # pontos do perfil entre boca e base: ((mm abaixo da boca, diâmetro), …)
    diametro_meio: float = 0.0    # (versão anterior: 1 ponto só) — lido como um ponto em `pontos`
    altura_meio: float = 0.0


def nos(p: Peca) -> list:
    """Pontos do perfil, de cima para baixo: boca, pontos do meio (ordenados) e base."""
    meio = list(p.pontos)
    if not meio and p.diametro_meio > 0:
        meio = [(p.altura_meio if p.altura_meio > 0 else p.altura / 2, p.diametro_meio)]
    meio = sorted((float(z), float(d)) for z, d in meio if 0 < z < p.altura)
    return [(0.0, p.diametro_topo)] + meio + [(p.altura, p.diametro_base)]


def _inclinacoes(xs, ys):
    """Derivadas que não deixam a curva passar além dos pontos (Fritsch–Butland, monotônica por trecho)."""
    n = len(xs)
    h = [xs[k + 1] - xs[k] for k in range(n - 1)]
    dl = [(ys[k + 1] - ys[k]) / h[k] if h[k] else 0.0 for k in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = dl[0], dl[-1]
    for k in range(1, n - 1):
        if dl[k - 1] * dl[k] <= 0:
            m[k] = 0.0  # ponto de máximo/mínimo (barriga da taça, haste): fica "deitado"
        else:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / dl[k - 1] + w2 / dl[k])
    return m


def diametro_em(p: Peca, z):
    """Diâmetro a `z` mm abaixo da boca: curva suave passando por todos os pontos do perfil."""
    pts = nos(p)
    z = min(max(z, 0.0), p.altura)
    if len(pts) == 2:
        (z0, d0), (z1, d1) = pts
        return d0 + (d1 - d0) * (z - z0) / (z1 - z0) if z1 > z0 else d0
    xs, ys = [a for a, _ in pts], [b for _, b in pts]
    m = _inclinacoes(xs, ys)
    k = max(0, min(len(xs) - 2, next((i for i in range(len(xs) - 1) if z <= xs[i + 1]), len(xs) - 2)))
    hk = xs[k + 1] - xs[k]
    if hk <= 0:
        return ys[k]
    t = (z - xs[k]) / hk
    h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return h00 * ys[k] + h10 * hk * m[k] + h01 * ys[k + 1] + h11 * hk * m[k + 1]


def diametro_max(p: Peca):
    return max([diametro_em(p, p.altura * k / 80) for k in range(81)] + [d for _, d in nos(p)])


def curvo(p: Peca) -> bool:
    """Parede curva (algum ponto fora da reta entre boca e base)."""
    linha = lambda z: p.diametro_topo + (p.diametro_base - p.diametro_topo) * z / p.altura  # noqa: E731
    return any(abs(d - linha(z)) > 1e-6 for z, d in nos(p)[1:-1])


def erros(p: Peca) -> list:
    out = []
    for nome, v, lo in (("diâmetro da boca", p.diametro_topo, 1), ("diâmetro da base", p.diametro_base, 1),
                        ("altura", p.altura, 1), ("altura da arte", p.altura_arte, 0.5)):
        if v < lo:
            out.append(f"{nome} precisa ser maior que {lo:g} mm")
    if p.inicio < 0 or p.inicio + p.altura_arte > p.altura + 1e-9:
        out.append("a arte sai da peça (início + altura da arte maior que a altura)")
    if p.repeticoes < 1:
        out.append("repetições: pelo menos 1")
    if len(nos(p)) > 2 and min(diametro_em(p, p.altura * k / 80) for k in range(81)) < 1:
        out.append("algum ponto do perfil deixa a peça fina demais")
    return out


def calcular(p: Peca) -> dict:
    d_cima, d_baixo = diametro_em(p, p.inicio), diametro_em(p, p.inicio + p.altura_arte)
    d_meio = (d_cima + d_baixo) / 2
    circ = math.pi * d_meio
    util = max(circ - p.alca_mm - 2 * p.margem_mm, 0.0)
    por_arte = util / p.repeticoes if p.repeticoes else 0.0
    if p.repeticoes > 1:  # cada arte com a própria folga dos dois lados
        por_arte = max((circ - p.alca_mm) / p.repeticoes - 2 * p.margem_mm, 0.0)
    conico = abs(p.diametro_topo - p.diametro_base) > 1e-6 or curvo(p)
    ds = [diametro_em(p, p.inicio + p.altura_arte * k / 20) for k in range(21)]
    variacao_raio = (max(ds) - min(ds)) / 2  # parede curva: o ponto mais "fora" e o mais "dentro" da faixa  # quanto a superfície "foge" do foco ao longo da altura da arte
    r = {"d_cima": d_cima, "d_baixo": d_baixo, "d_meio": d_meio, "circ": circ,
         "circ_cima": math.pi * d_cima, "circ_baixo": math.pi * d_baixo, "util": util, "por_arte": por_arte,
         "passo_graus": 360.0 / p.repeticoes, "passo_mm": circ / p.repeticoes, "conico": conico,
         "distorcao_pct": (abs(d_cima - d_baixo) / d_meio * 100) if d_meio else 0.0,
         "variacao_foco": variacao_raio, "foco_ok": variacao_raio <= p.foco_mm,
         "inclinacao_graus": math.degrees(math.atan2(abs(p.diametro_topo - p.diametro_base) / 2, p.altura))}
    if conico:
        try:  # parede curva: leque pela reta entre topo e base da faixa (aproximado)
            r["leque"] = leque(p)
        except ValueError:
            pass
    return r


def leque(p: Peca, so_arte=True) -> dict:
    """Planificação do tronco de cone (faixa da arte, ou a peça toda): raio interno/externo a partir do vértice e
    ângulo do arco. Arco externo = circunferência da borda maior; interno = da menor."""
    z0, z1 = (p.inicio, p.inicio + p.altura_arte) if so_arte else (0.0, p.altura)
    r_a, r_b = diametro_em(p, z0) / 2, diametro_em(p, z1) / 2
    grande, pequeno = max(r_a, r_b), min(r_a, r_b)
    if grande - pequeno < 1e-9:
        raise ValueError("cilindro reto: o molde é um retângulo (circunferência × altura)")
    geratriz = math.hypot(z1 - z0, grande - pequeno)  # comprimento inclinado da faixa
    R = geratriz * grande / (grande - pequeno)       # raio externo do leque (do vértice do cone até a borda grande)
    Rin = R - geratriz
    ang = 2 * math.pi * grande / R                    # radianos
    return {"R": R, "Rin": Rin, "angulo_graus": math.degrees(ang), "geratriz": geratriz, "boca_maior": r_a >= r_b}


def caminho_leque(p: Peca, so_arte=True):
    """QPainterPath do molde em leque, em mm, canto superior esquerdo da caixa em (0, 0)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPainterPath
    lq = leque(p, so_arte)
    R, Rin, ang = lq["R"], lq["Rin"], lq["angulo_graus"]
    ini = 270 - ang / 2  # arco simétrico em volta da vertical, abrindo para baixo (Qt: graus anti-horários, Y p/ baixo)
    cam = QPainterPath()
    cam.arcMoveTo(QRectF(-R, -R, 2 * R, 2 * R), ini)
    cam.arcTo(QRectF(-R, -R, 2 * R, 2 * R), ini, ang)
    fim_int = QPainterPath()
    fim_int.arcMoveTo(QRectF(-Rin, -Rin, 2 * Rin, 2 * Rin), ini + ang)
    cam.lineTo(fim_int.currentPosition())
    cam.arcTo(QRectF(-Rin, -Rin, 2 * Rin, 2 * Rin), ini + ang, -ang)
    cam.closeSubpath()
    if not lq["boca_maior"]:  # boca menor que a base: o leque fica de cabeça para baixo
        from PySide6.QtGui import QTransform
        cam = QTransform.fromScale(1, -1).map(cam)
    b = cam.boundingRect()
    return cam.translated(QPointF(-b.left(), -b.top()))
