"""Gera o projeto "Porta-retrato Isabella e Nathan" (.rbl) a partir das folhas 1:1 do PDF (páginas 5 a 9),
com as sobras das janelas aproveitadas.

O PDF traz os vetores em escala 1:1 (folhas de 370 × 365 mm, cabem na mesa 365 × 370). Cada folha vira uma aba;
cada contorno fechado é classificado pela profundidade (quantos contornos o envolvem):
  0 = contorno do módulo (por último); 1 = janela/vazado/rasgo; 2 = peça cortada DENTRO de uma janela;
  3 = furo/rasgo dessa peça. Corta-se do mais fundo para fora: se a janela sai antes, a sobra cai e a peça de
  dentro sai torta.

TUDO EM MDF 3 mm, SEM FOLGA (o PDF foi desenhado com frente de 6 mm): os encaixes somam as espessuras.
- Área das fotos: frente 3 + guia 3 + fundo 3 = 9 mm -> rasgos da base 26 × 9 (no PDF, 26 × 12).
- Base 426 × 62 × 9 = 3 camadas de 3 mm: cima e meio com os 4 rasgos (as linguetas entram 6 mm), baixo lisa.
APROVEITAMENTO das sobras das janelas (tudo é 3 mm, então qualquer peça cabe nelas):
- Janela direita: camada de CIMA da base, partes 0-100 e 100-290 + 1 par de triângulos (apoios).
- Janela esquerda: os 18 corações + parte 290-426 da camada de cima.
  (emendas da camada de cima em 100 e 290, fora dos rasgos e longe das de baixo: 142 e meio: 205)
- Aba 8: fundos, base lisa 284, guias, batentes, chapinhas e coroa. Aba 9: base lisa 142, camada do meio
  (205 + 221, do PDF) e o outro par de triângulos.
Camadas (todas 3 mm, corte 800 mm/min, 85 %, 2 passadas): C07 → C03 → C02 → C01.

Executar:  python tools/projetos/porta_retrato_isabella_nathan.py <arquivo.pdf> [saida.rbl]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import importar_pdf as ip  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

# (página do PDF, 1 = primeira; nome da aba; espessura)
FOLHAS = [(5, "5 Frente esquerda + sobras (MDF 3)", 3), (6, "6 Frente direita NATHAN + sobras (MDF 3)", 3),
          (7, "7 Faixa ISABELLA (MDF 3)", 3), (8, "8 Fundos, base, guias e coroa (MDF 3)", 3),
          (9, "9 Base meio, base 142 e apoios (MDF 3)", 3)]
# por profundidade 0, 1, 2, 3+
CAMADAS = {3: ("C01", "C02", "C03", "C07")}
T = 3.0                       # MDF 3 mm em todas as peças
RASGO = 3 * T                 # frente + guia + fundo empilhados: sem folga, só a soma das espessuras
BASE = 426.0
RASGOS_BASE = (49.0, 123.0, 231.0, 357.0)  # início (x) dos rasgos 26 × RASGO, a 13 mm da borda (PDF p. 3)
CORTES_BASE = (0.0, 100.0, 290.0, BASE)     # partes da camada de cima da base (nas janelas)


def profundidades(subs):
    """Quantos outros contornos envolvem cada um (ponto do próprio contorno dentro do outro)."""
    areas = [s.boundingRect().width() * s.boundingRect().height() for s in subs]
    out = []
    for i, s in enumerate(subs):
        p = s.pointAtPercent(0.37)
        out.append(sum(1 for j, t in enumerate(subs) if j != i and areas[j] > areas[i] and t.contains(p)))
    return out


def classificar(subs, esp):
    """[(caminho, camada, índice do dono)]: o dono é o contorno de peça (profundidade par) que contém o caminho."""
    prof = profundidades(subs)
    ids = CAMADAS[esp]
    res = []
    for i, (s, d) in enumerate(zip(subs, prof)):
        dono = i
        if d % 2:  # vazado: pertence à peça que o envolve logo acima (profundidade d - 1)
            p = s.pointAtPercent(0.37)
            dono = next(j for j, t in enumerate(subs) if prof[j] == d - 1 and t.contains(p))
        res.append((s, ids[min(d, 3)], dono))
    return res


# ---------- otimização ----------
def _ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def _mover(paths, x, y):
    """Leva o conjunto (canto superior esquerdo da caixa) para (x, y)."""
    r = QRectF()
    for p in paths:
        r = r.united(p.boundingRect())
    tf = QTransform.fromTranslate(x - r.left(), y - r.top())
    return [tf.map(p) for p in paths]


def _girar(paths):
    """90° (a caixa continua começando em 0, 0 depois do _mover)."""
    return [QTransform().rotate(90).map(p) for p in paths]


def _tirar(subs, w, h, n=None):
    """Remove e devolve os contornos com caixa w × h (todos, ou os n primeiros)."""
    achados = [s for s in subs if abs(s.boundingRect().width() - w) < 0.05 and abs(s.boundingRect().height() - h) < 0.05]
    achados = achados[:n] if n else achados
    for s in achados:
        subs.remove(s)
    return achados


def _peca_com_furos(subs, w, h):
    """Remove a peça w × h e os furos dentro dela; devolve [contorno, furos...]."""
    cont = _tirar(subs, w, h, 1)[0]
    furos = [s for s in subs if s is not cont and cont.contains(s.boundingRect().center())
             and s.boundingRect().width() < w]
    for f in furos:
        subs.remove(f)
    return [cont] + furos


def parte_base(x0, x1):
    """Parte da camada de cima da base, de x0 a x1 (mm ao longo dos 426), com os rasgos que caem nela."""
    rasgos = [_ret(r - x0, 13, 26, RASGO) for r in RASGOS_BASE if x0 <= r and r + 26 <= x1]
    assert all(not (r < x < r + 26) for r in RASGOS_BASE for x in (x0, x1)), "emenda dentro de um rasgo"
    return [_ret(0, 0, x1 - x0, 62)] + rasgos


def otimizar(subs):
    """subs: {página: [contornos]} lidos do PDF. Devolve o mesmo dicionário com as peças realocadas."""
    s5, s6, s8, s9 = subs[5], subs[6], subs[8], subs[9]
    # janela direita: sai os 6 corações (profundidade 2), entram as duas partes maiores da base + 2 triângulos
    janela6 = max((s for s in s6 if s.boundingRect().width() < 230), key=lambda s: s.boundingRect().width())
    coracoes = [s for s in s6 if s is not janela6 and janela6.boundingRect().contains(s.boundingRect())]
    for c in coracoes:
        s6.remove(c)
    p1, p2, p3 = (parte_base(a, b) for a, b in zip(CORTES_BASE, CORTES_BASE[1:]))
    s6 += _mover(p2, 32, 81) + _mover(p1, 32, 147)
    triangulos = sorted(_tirar(s9, 36, 36), key=lambda t: t.boundingRect().x())  # 4 de 3 mm (2 pares)
    par, outro_par = triangulos[:2], triangulos[2:]  # cada par = 2 triângulos complementares
    s6 += _mover(par, 140, 160)
    # janela esquerda: os 6 corações ao lado dos 12 e a terceira parte da base embaixo
    destino = {43.96: (112, 21), 30.87: (110, 67), 18.91: (143, 67), 18.89: (143, 87), 24.9: (110, 98),
               23.93: (138, 107)}
    for c in coracoes:
        w = round(c.boundingRect().width(), 2)
        s5 += _mover([c], *destino[w])
    s5 += _mover(p3, 25, 148)
    # aba 9: sai a camada de cima do PDF (280 + 146, refeita nas janelas); a do meio (205 + 221) fica, rasgos 26 × 9
    for w in (146, 280):
        _peca_com_furos(s9, w, 62)
    meio = [_peca_com_furos(s9, w, 62) for w in (205, 221)]
    for pecas in meio:
        for i, f in enumerate(pecas[1:], 1):
            r = f.boundingRect()
            pecas[i] = _ret(r.x(), r.y(), r.width(), RASGO)  # 26 × 12 -> 26 × 9, mesma borda de cima
    guias = [_peca_com_furos(s9, w, h) for w, h in ((14.4, 159.5), (10.4, 159.5), (4.4, 223.5), (10.4, 223.5))]
    y = 316.0
    for g in guias:  # deitadas embaixo da base de 284
        g = _mover(_girar(g), 5, y)
        s8 += g
        y += min(p.boundingRect().height() for p in g[:1]) + 3
    batentes = [_peca_com_furos(s9, 31, 22) for _ in range(3)]
    chapinhas = [_peca_com_furos(s9, 11, 32) for _ in range(2)]
    coroa = _peca_com_furos(s9, 37, 22)
    for pecas, (x, yy) in ((batentes[0], (293, 246)), (batentes[1], (327, 246)), (batentes[2], (293, 271)),
                           (chapinhas[0], (327, 271)), (chapinhas[1], (342, 271)), (coroa, (293, 306))):
        s8 += _mover(pecas, x, yy)
    sobra = _peca_com_furos(s9, 142, 62)
    assert not s9, f"peças da folha 9 não realocadas: {[s.boundingRect() for s in s9]}"
    s9 += _mover(sobra, 5, 5) + _mover(meio[0], 5, 71) + _mover(meio[1], 5, 137) + _mover(outro_par, 151, 5)
    return subs


def ler_pdf(pdf):
    return {n: [s for _, p in ip.load(pdf, n - 1).objetos for s in fm.subcaminhos(p)] for n, _, _ in FOLHAS}


def folha(subs, esp):
    grupos = {}
    for s, lid, dono in classificar(subs, esp):
        grupos.setdefault(dono, []).append((s, lid))
    snaps = []
    for k, (dono, partes) in enumerate(sorted(grupos.items())):
        shapes = [ob.Shape(s, f"Peça {k + 1} — {'contorno' if lid in ('C01', 'C04') else 'vazado/peça interna'}",
                           lid, cm.cor(lid)) for s, lid in partes]
        if len(shapes) == 1:
            shapes[0].name = f"Peça {k + 1}"
            snaps.append(shapes[0].snapshot())
        else:
            g = ob.group(shapes)
            g.name = f"Peça {k + 1}"
            snaps.append(g.snapshot())
    return tuple(snaps)


NOTAS = """PORTA-RETRATO ISABELLA E NATHAN — TUDO EM MDF 3 mm — fotos 15 × 21 (esquerda) e 21 × 15 (direita)
Vetores 1:1 do PDF (desenhado para frente de 6 mm), adaptados para 3 mm SEM folga: os encaixes somam as espessuras.

O QUE MUDOU PARA 3 mm
- Frentes, faixa ISABELLA e corações em 3 mm. Espessura na área das fotos: frente 3 + guia 3 + fundo 3 = 9 mm.
- Rasgos da base: 26 × 9 (antes 26 × 12), em X 49, 123, 231, 357 / Y 13. Linguetas das frentes entram 6 mm
  (as duas camadas de cima da base).
- Base 426 × 62 × 9 = 3 camadas de 3 mm:
  cima (com rasgos) = 3 partes nas janelas: 0-100 e 100-290 (janela direita), 290-426 (janela esquerda);
  meio (com rasgos) = 0-205 e 205-426 (aba 9);
  baixo (lisa) = 284 (aba 8) + 142 (aba 9). Emendas desencontradas: 100/290, 205, 142.
- Apoios: 4 triângulos de 3 mm colados aos pares (2 na janela direita, 2 na aba 9).

CORTE (todas as camadas de corte): 800 mm/min, 85 %, 2 passadas — teste antes; ordem em cada aba: rasgos das
peças internas → peças internas → janelas/letras/rasgos → contornos.

MONTAGEM (do PDF)
1 Frente modular: una os módulos com A1, C1-C3 e D1/D2. As 2 linguetas superiores da faixa ISABELLA entram no
  quadro vertical. A1 0/-10 (159,5 × 14,4); A2 0/215,6; B1 190,5/60; B2 190,5/215,6 (223,5 × 4,4);
  C1-C3 em X 159,5, Y 78/130/182 (31 × 22); D1-D2 em X 178 e 403, Y -10 (11 × 32). Ref.: topo esquerdo do
  quadro em pé.
2 Canais e fundos: cole guias e fundos alinhados às linguetas. Canal esquerdo 211,2 mm; direito 151,2 mm.
3 Base: cole as 3 camadas (lisa embaixo), rasgos alinhados. Teste o encaixe das linguetas antes de colar.
4 Apoios: cole os triângulos aos pares; apoios centrados a 62 e 244 mm da esquerda da base.
  Corações conforme a vista frontal. Coroa colada sobre o último A."""


def camadas():
    corte = dict(modo="linha", velocidade_mm_min=800.0, potencia_max=85.0, potencia_min=0.0, passadas=2, air=True)
    return [cm.alterar(cm.Camada("C07", "MDF 3: rasgos das peças nas janelas (1º)"), **corte),
            cm.alterar(cm.Camada("C03", "MDF 3: peças dentro das janelas (2º)"), **corte),
            cm.alterar(cm.Camada("C02", "MDF 3: janelas, letras, furos e rasgos (3º)"), **corte),
            cm.alterar(cm.Camada("C01", "MDF 3: contornos (por último)"), **corte)]


def gerar(pdf, destino):
    subs = otimizar(ler_pdf(pdf))
    paginas = [folha(subs[n], esp) for n, _, esp in FOLHAS]
    pj.save(destino, paginas[0], camadas(), notas=NOTAS, paginas=[None] + [(p, (), ()) for p in paginas[1:]],
            pagina_atual=0, nomes_paginas=[nome for _, nome, _ in FOLHAS])
    return destino


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "porta_retrato_isabella_nathan.rbl"))
