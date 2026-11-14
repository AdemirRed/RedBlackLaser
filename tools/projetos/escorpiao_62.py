"""Gera o projeto "Escorpião em relevo 62" (R02, MDF 6 mm) como .rbl, e o JSON de geometria para o render 3D.

Base: prancha_escorpiao_62.pdf. O corpo (P01) e os apliques (P03–P12) vêm dos vetores da prancha 02 (gabarito 1:1,
mesma origem da lista de peças); a base (P02, prancha 06) e o cupom de encaixe (prancha 10) são redesenhados pelas
cotas. Furos e rasgos = camada C02 (cortada primeiro); contornos = C01.

Executar:  python tools/projetos/escorpiao_62.py prancha.pdf [saida.rbl] [geometria.json]
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import importar_pdf  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

T = 6.0
_N = lambda *c: [(k, n, "natural") for k, n in c]  # noqa: E731
_G = lambda *c: [(k, n, "grafite") for k, n in c]  # noqa: E731
_CARAPACA = _N(("P03", "Placa da cabeça"), ("P04", "Carapaça A"), ("P05", "Carapaça B"), ("P06", "Carapaça C"),
               ("P07", "Carapaça D"), ("P08", "Ferrão em relevo"))
_CAUDA = _G(("P09", "Cauda 1"), ("P10", "Cauda 2"), ("P11", "Cauda 3"), ("P12", "Cauda 4"))
# Por revisão do PDF: apliques, canto sup. esquerdo na montagem (pranchas de apliques — confere a leitura dos
# vetores), rasgos da base (X esq./dir.), largura do macho/rasgo do cupom e tamanho da chapa.
REVISOES = {
    "R02": dict(apliques=_CARAPACA + _CAUDA,
                pos={"P03": (79.93, 106.76), "P04": (121.52, 102.87), "P05": (144.86, 97.41), "P06": (166.26, 91.39),
                     "P07": (185.38, 71.46), "P08": (118.95, 19.06), "P09": (144.86, 2.86), "P10": (172.26, 2.86),
                     "P11": (193.61, 15.73), "P12": (200.67, 45.44)},
                rasgos=((153.80, 168.00), (201.50, 215.70)), macho=14.0, rasgo=14.2, chapa=(360, 300)),
    "R03": dict(apliques=_CARAPACA + _CAUDA + _G(
                    ("P13", "Pinça alta"), ("P14", "Junta alta"), ("P15", "Pinça baixa"), ("P16", "Junta baixa"),
                    ("P17", "Pata 1 · coxa"), ("P18", "Pata 1 · pé"), ("P19", "Pata 2 · coxa"), ("P20", "Pata 2 · pé"),
                    ("P21", "Pata 3 · coxa"), ("P22", "Pata 3 · pé"), ("P23", "Pata 4 · coxa"), ("P24", "Pata 4 · pé")),
                pos={"P03": (85.28, 96.77), "P04": (118.65, 91.09), "P05": (138.15, 84.53), "P06": (157.26, 76.41),
                     "P07": (174.46, 69.54), "P08": (106.23, 5.53), "P09": (127.96, 1.32), "P10": (156.48, 3.93),
                     "P11": (174.68, 15.86), "P12": (186.57, 39.71), "P13": (5.04, 99.35), "P14": (53.43, 97.69),
                     "P15": (27.31, 146.36), "P16": (89.10, 132.40), "P17": (117.51, 133.94),
                     "P18": (126.05, 161.97), "P19": (140.06, 127.91), "P20": (160.99, 157.20),
                     "P21": (165.54, 120.64), "P22": (190.39, 153.62), "P23": (185.69, 112.69),
                     "P24": (210.77, 140.50)},
                rasgos=((136.50, 144.70), (200.20, 208.40)), macho=8.0, rasgo=8.2, chapa=(380, 360)),
}
REV = dict(REVISOES["R02"], nome="R02")
APLIQUES = REV["apliques"]


def ler_gabarito(pdf):
    """Corpo e apliques da prancha 02, já na origem do corpo (X 0 na ponta esquerda, Y 0 no topo), em mm."""
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    w.add_page(PdfReader(pdf).pages[1])
    with tempfile.TemporaryDirectory() as tmp:
        arq = os.path.join(tmp, "p2.pdf")
        w.write(arq)
        caminhos = [c for _, c in importar_pdf.load(arq).objetos if c.elementCount() > 20]  # tira cotas/eixos
    global REV, APLIQUES
    nome = "R03" if len(caminhos) > 15 else "R02"
    REV = dict(REVISOES[nome], nome=nome)
    APLIQUES = REV["apliques"]
    pos = REV["pos"]
    corpo = max(caminhos, key=lambda c: c.boundingRect().width())
    r = corpo.boundingRect()
    assert abs(r.width() - 220) < 0.05 and abs(r.height() - 195.8) < 0.05, r
    tf = QTransform.fromTranslate(-r.left(), -r.top())
    pecas = {"P01": tf.map(corpo)}
    for c in caminhos:
        if c is corpo:
            continue
        b = tf.map(c).boundingRect()
        cod = min(pos, key=lambda k: abs(pos[k][0] - b.left()) + abs(pos[k][1] - b.top()))
        assert abs(pos[cod][0] - b.left()) < 0.1 and abs(pos[cod][1] - b.top()) < 0.1, (cod, b)
        assert cod not in pecas, cod
        pecas[cod] = tf.map(c)
    assert len(pecas) == len(pos) + 1, sorted(pecas)
    return pecas


def subcaminhos(path):
    """Separa os contornos de um caminho (mantendo as curvas)."""
    out, atual = [], None
    for i in range(path.elementCount()):
        e = path.elementAt(i)
        if e.isMoveTo():
            atual = QPainterPath()
            atual.moveTo(e.x, e.y)
            out.append(atual)
        elif e.isLineTo():
            atual.lineTo(e.x, e.y)
        elif e.isCurveTo():
            c2, fim = path.elementAt(i + 1), path.elementAt(i + 2)
            atual.cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
    return [p for p in out if p.elementCount() > 2]


def base():
    """P02 244 × 68, cantos R6, rasgos R1/R2 (comprimento da revisão) × 5,90 (origem no canto sup. esquerdo)."""
    contorno = QPainterPath()
    contorno.addRoundedRect(QRectF(0, 0, 244, 68), 6, 6)
    rasgos = []
    for x0, x1 in REV["rasgos"]:
        p = QPainterPath()
        p.addRect(QRectF(x0, 31.05, x1 - x0, 36.95 - 31.05))
        rasgos.append(p)
    return contorno, rasgos


def cupom():
    """Placa 114 × 24 com rasgos T1–T5 (5,60 … 6,20 × comprimento) e o macho de teste 26 × 19 + macho × 5,8."""
    placa = QPainterPath()
    placa.addRect(QRectF(0, 0, 114, 24))
    rasgos = []
    for k, alt in enumerate((5.60, 5.75, 5.90, 6.05, 6.20)):
        p = QPainterPath()
        p.addRect(QRectF(9 + 22 * k, 12 - alt / 2, REV["rasgo"], alt))
        rasgos.append(p)
    macho = QPainterPath()
    macho.moveTo(0, 0)
    o = (26 - REV["macho"]) / 2  # ombro de cada lado
    for x, y in ((26, 0), (26, 19), (26 - o, 19), (26 - o, 24.8), (o, 24.8), (o, 19), (0, 19)):
        macho.lineTo(x, y)
    macho.closeSubpath()
    return placa, rasgos, macho


def item(path, nome, camada, dx, dy):
    return ob.Shape(QTransform.fromTranslate(dx, dy).map(path), nome, camada, cm.cor(camada))


def grupo(itens, nome):
    g = ob.group(itens)
    g.name = nome
    return g.snapshot()


def folhas(pecas):
    M = 5.0
    corpo = subcaminhos(pecas["P01"])
    externo = max(corpo, key=lambda c: c.boundingRect().width())
    furos = [c for c in corpo if c is not externo]  # vão entre as pinças
    marcas = [item(pecas[cod], f"P01 — marca de colagem {cod}", "C03", M, M) for cod, _, _ in APLIQUES]
    f1 = [grupo(marcas + [item(c, "P01 — vão interno", "C02", M, M) for c in furos]
                + [item(externo, "P01 — contorno", "C01", M, M)], "P01 Corpo com machos")]
    contorno, rasgos = base()
    yb = M + 195.8 + 8
    f1.append(grupo([item(r, f"P02 — rasgo R{k}", "C02", M, yb) for k, r in enumerate(rasgos, 1)]
                    + [item(contorno, "P02 — contorno", "C01", M, yb)], "P02 Base"))
    # apliques em prateleiras: à direita do corpo e, se faltar lugar, embaixo da base
    W, H = REV["chapa"]
    regioes = [[M + 220 + 8, M, W - M, H - M], [M, yb + 68 + 8, M + 220, H - M]]  # x0, y0, x1, y1
    estado = [[r[0], r[1], 0.0] for r in regioes]  # cursor x, y da prateleira, altura da prateleira
    for cod, nome, _ in sorted(APLIQUES, key=lambda a: -pecas[a[0]].boundingRect().height()):
        p = pecas[cod]
        b = p.boundingRect()
        for (x0, _y0, x1, y1), st in zip(regioes, estado):
            if st[0] + b.width() > x1:  # nova prateleira
                st[0], st[1], st[2] = x0, st[1] + st[2] + 4, 0.0
            if st[1] + b.height() <= y1 and st[0] + b.width() <= x1:
                break
        else:
            raise AssertionError(f"{cod} não coube na chapa {W} × {H}")
        f1.append(grupo([item(QTransform.fromTranslate(-b.left(), -b.top()).map(p), f"{cod} {nome}", "C01",
                              st[0], st[1])], f"{cod} {nome}"))
        st[0] += b.width() + 4
        st[2] = max(st[2], b.height())
    placa, rasgos_t, macho = cupom()
    f2 = [grupo([item(r, f"Cupom — rasgo T{k}", "C02", M, M) for k, r in enumerate(rasgos_t, 1)]
                + [item(placa, "Cupom — contorno", "C01", M, M)], "Cupom de encaixe (T1 5,60 … T5 6,20)"),
          grupo([item(macho, "Macho de teste — contorno", "C01", M + 114 + 10, M)], "Macho de teste")]
    return [(f"01 Peças ({W} × {H})", f1), ("02 Cupom de encaixe", f2)]


def notas():
    ult = APLIQUES[-1][0]
    r = f"{REV['rasgo']:.2f}".replace(".", ",")
    return f"""ESCORPIÃO EM RELEVO — PROJETO 62 / {REV['nome']} — MDF 6 mm (protótipo; ajuste e teste antes do lote)
Corpo 220 × 195,8 (com machos), base 244 × 68 R6, altura montada 196 mm. {len(APLIQUES) + 2} peças + cupom.

ANTES DE CORTAR
1. Corte a aba "02 Cupom de encaixe": rasgos T1–T5 = 5,60 / 5,75 / 5,90 / 6,05 / 6,20 × {r}.
   Escolha o rasgo em que o macho desliza até o ombro sem forçar.
2. Se não for o T3 (5,90), ajuste só a LARGURA (5,90) dos dois rasgos R1/R2 da base
   (Organizar → Redimensionar slots). Abertura = espessura medida + folga − kerf (6,00 + 0,10 − 0,20 = 5,90).
3. Velocidade/potência/passadas são ponto de partida NÃO validado na máquina: faça a matriz de testes.
Camada C03 = MARCAÇÃO de colagem (risco fraco, não corta) na face do corpo, feita antes dos cortes.
Camada C02 (vermelha) = rasgos e vão interno, cortados antes dos contornos. C01 (azul) = contornos, por último.
A marca fraca some sob tinta: pinte o corpo com fita nas áreas marcadas, ou cole os apliques antes de pintar.

ACABAMENTO
P01 e P02 preto fosco. P03 a P08 MDF natural. P09 a {ult} preto ou grafite.

MONTAGEM
1. Confira o encaixe do corpo na base a seco (machos M1/M2 nos rasgos R1/R2).
2. Separe os apliques pela posição do gabarito (prancha 02) e faça o acabamento.
3. Cole P03 a {ult} na face frontal do corpo, cada um dentro do seu risco (camada C03), com cola para MDF.
4. Encaixe P01 em P02 e cole pelos rasgos. Deixe curar com a peça na vertical."""


def camadas():
    b = dict(modo="linha", velocidade_mm_min=300.0, potencia_max=100.0, potencia_min=0.0, passadas=2, air=True)
    marca = dict(modo="linha", velocidade_mm_min=3000.0, potencia_max=12.0, potencia_min=0.0, passadas=1, air=False)
    return [cm.alterar(cm.Camada("C03", "Marcação de colagem (risco fraco, 1º)"), **marca),
            cm.alterar(cm.Camada("C02", "Internos: rasgos e vão (corte, 2º)"), **b),
            cm.alterar(cm.Camada("C01", "Contornos (corte, por último)"), **b)]


def geometria(pecas):
    """Polígonos (curvas achatadas a 0,02 mm) por peça, no sistema do corpo, para o render 3D."""
    def polis(path):
        z = QTransform.fromScale(20, 20)
        return [[(round(p.x() / 20, 4), round(p.y() / 20, 4)) for p in poly] for poly in z.map(path).toSubpathPolygons()]
    contorno, rasgos = base()
    out = {"corpo": polis(pecas["P01"]), "base": polis(contorno) + [pol for r in rasgos for pol in polis(r)],
           "apliques": [{"cod": c, "nome": n, "cor": cor, "polis": polis(pecas[c])} for c, n, cor in APLIQUES]}
    return out


def gerar(pdf, destino, destino_json=None):
    pecas = ler_gabarito(pdf)
    fl = folhas(pecas)
    pj.save(destino, tuple(fl[0][1]), camadas(), notas=notas(), paginas=[None] + [(tuple(p), (), ()) for _, p in fl[1:]],
            pagina_atual=0, nomes_paginas=[n for n, _ in fl])
    if destino_json:
        with open(destino_json, "w", encoding="utf-8") as f:
            json.dump(geometria(pecas), f)
    return destino


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "escorpiao_62.rbl",
                sys.argv[3] if len(sys.argv) > 3 else None))
