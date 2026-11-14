"""Gera o projeto "Carroça colonial de mesa" (MDF 3 mm) como .rbl, nas medidas da mesa RedBlack (365 × 370).

Base: PDF carroca_colonial_guia_medidas_montagem.pdf. O plano de corte do PDF é só uma IMAGEM (1600 × 1500 px para
400 × 375 mm = 4 px/mm, sem SVG/DXF): as peças foram redesenhadas em vetor com as cotas da tabela "Medidas e
ângulos" e, onde a tabela não diz, com as medidas tiradas da imagem (precisão de 0,25 mm), arredondadas para
fechar os encaixes entre si (abas × rasgos, meios-encaixes, eixos a x = 36 e 137).

Correção ao PDF: os braços dos berços (B1-B2) encostam por fora das laterais, a 29 mm do centro, mas o assoalho
tem 33 mm de meia-largura (passa 3,5 mm das laterais) — os dois se cruzariam. O assoalho ganhou 4 recortes de
3 × 4 mm na borda, na linha de cada berço.

Camadas: C03 = gravação das linhas de tábuas (1º); C02 = furos, rasgos e janelas das rodas (2º); C01 = contornos
(por último). Peças desenhadas com Y para baixo e o canto superior esquerdo da caixa em (0, 0).

Executar:  python tools/projetos/carroca_colonial.py [saida.rbl]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

GRAV, FURO, CONT = "C03", "C02", "C01"
H_LAT = 56.9                                  # altura da lateral (sem as abas)
ABAS_LAT = (12.5, 58.5, 104.5, 150.5)         # início (x) das 4 abas 7 × 4 da lateral = rasgos do assoalho
EIXOS = (36.0, 137.0)                         # berços/eixos no assoalho (x = 0 no fundo traseiro)
T = 3.0                                       # espessura do MDF: rasgos e abas = T, sem folga
VARETA = 4.0                                  # eixos Ø4: furos das rodas e mancais = Ø4, sem folga


def poligono(pts):
    p = QPainterPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.closeSubpath()
    return p


def ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def circulo(cx, cy, d):
    p = QPainterPath()
    p.addEllipse(QPointF(cx, cy), d / 2, d / 2)
    return p


def linha(x0, y0, x1, y1):
    p = QPainterPath()
    p.moveTo(x0, y0)
    p.lineTo(x1, y1)
    return p


# ---------- peças ----------
def lateral():
    """L1-L2: 170 × 56,9 com 4 abas 7 × 4 embaixo; 2 linhas de tábua gravadas."""
    pts = [(0, 0), (170, 0), (170, H_LAT)]
    for x in reversed(ABAS_LAT):
        pts += [(x + 7, H_LAT), (x + 7, H_LAT + T), (x, H_LAT + T), (x, H_LAT)]
    pts.append((0, H_LAT))
    return [(linha(4, H_LAT * k / 3, 166, H_LAT * k / 3), GRAV) for k in (1, 2)] + [(poligono(pts), CONT)]


def assoalho():
    """P1: 170 × 66; rasgos das laterais, berços, mancais e banco; recortes 3 × 4 para os braços dos berços."""
    pts = [(0, 0)]
    for e in EIXOS:  # borda de cima, da esquerda para a direita
        pts += [(e - 1.5, 0), (e - 1.5, 4), (e + 1.5, 4), (e + 1.5, 0)]
    pts += [(170, 0), (170, 66)]
    for e in reversed(EIXOS):  # borda de baixo, da direita para a esquerda
        pts += [(e + 1.5, 66), (e + 1.5, 62), (e - 1.5, 62), (e - 1.5, 66)]
    cont = poligono(pts + [(0, 66)])
    furos = []
    for x in ABAS_LAT:                                                    # laterais: 7 × 3
        furos += [ret(x, 3.5, 7, 3), ret(x, 59.5, 7, 3)]
    for e in EIXOS:
        furos += [ret(e - 1.5, 22.5, 3, 7), ret(e - 1.5, 36.5, 3, 7)]      # abas dos berços: 3 × 7
        for dx in (-11, 5):                                               # abas dos mancais: 6 × 3
            furos += [ret(e + dx, 11.5, 6, 3), ret(e + dx, 51.5, 6, 3)]
    furos += [ret(152.5, 13.5, 5, 3), ret(152.5, 49.5, 5, 3)]            # suportes do banco: 5 × 3
    return ([(linha(2, y, 168, y), GRAV) for y in (22, 44)] + [(f, FURO) for f in furos] + [(cont, CONT)])


def tampa():
    """T1-T2: trapézio, topo 71,8, base 52, altura 56 (bordas ~10,1°); 2 linhas a 2 mm das bordas."""
    m = (71.8 - 52) / 2
    linhas = []
    for k in (1, 2):
        y = 56 * k / 3
        i = m * y / 56 + 2
        linhas.append((linha(i, y, 71.8 - i, y), GRAV))
    return linhas + [(poligono([(0, 0), (71.8, 0), (71.8 - m, 56), (m, 56)]), CONT)]


def roda(d, ri, ro):
    """Roda inteiriça: Ø d, furo Ø4 (= vareta, sem folga), 8 janelas (setor de anel ri..ro, 21° de abertura) entre 8 raios."""
    c = d / 2
    furos = [circulo(c, c, VARETA)]
    for k in range(8):
        a0, a1 = 12 + 45 * k, 33 + 45 * k  # graus a partir do topo, sentido horário
        pts = []
        for a in [a0 + (a1 - a0) * i / 42 for i in range(43)]:
            pts.append((c + ro * math.sin(math.radians(a)), c - ro * math.cos(math.radians(a))))
        for a in [a1 - (a1 - a0) * i / 14 for i in range(15)]:
            pts.append((c + ri * math.sin(math.radians(a)), c - ri * math.cos(math.radians(a))))
        furos.append(poligono(pts))
    return [(f, FURO) for f in furos] + [(circulo(c, c, d), CONT)]


def berco():
    """B1-B2: base 71 × 10 com 2 abas 7 × 3 (assoalho) e 2 meios-encaixes 3 × 5 (mancais); braços 6 mm a 10°."""
    u = [(-40.82, 0), (-34.82, 0), (-29, 33),
         (-10.5, 33), (-10.5, 30), (-3.5, 30), (-3.5, 33), (3.5, 33), (3.5, 30), (10.5, 30), (10.5, 33),
         (29, 33), (34.82, 0), (40.82, 0), (35, 33), (35.5, 33), (35.5, 43),
         (21.5, 43), (21.5, 38), (18.5, 38), (18.5, 43), (-18.5, 43), (-18.5, 38), (-21.5, 38), (-21.5, 43),
         (-35.5, 43), (-35.5, 33), (-35, 33)]
    return [(poligono([(x + 40.82, y) for x, y in u]), CONT)]


def mancal(corpo, furo_y):
    """E1-E4: 30 × corpo + 2 abas 6 × 3 em cima; meio-encaixe 3 × 5 no centro; furo Ø4 (vareta) a furo_y do topo."""
    pts = [(0, 3), (4, 3), (4, 0), (10, 0), (10, 3), (13.5, 3), (13.5, 8), (16.5, 8), (16.5, 3), (20, 3),
           (20, 0), (26, 0), (26, 3), (30, 3), (30, 3 + corpo), (0, 3 + corpo)]
    return [(circulo(15, 3 + furo_y, VARETA), FURO), (poligono(pts), CONT)]


def lanca():
    """V1: lança em Y, 82,5 × 24, furo Ø3,5 na ponta."""
    pts = [(1, 0), (36, 6.2), (82.5, 9.2), (82.5, 14.8), (36, 17.8), (1, 24), (0, 18), (32, 12), (0, 6)]
    return [(circulo(78.5, 12, 3.5), FURO), (poligono(pts), CONT)]


def banco():
    """A1: tábua 60 × 17 com uma linha gravada."""
    return [(linha(3, 5, 57, 5), GRAV), (ret(0, 0, 60, 17), CONT)]


def suporte_banco():
    """A2-A3: 15 × 23 + aba 5 × 3 (entra no rasgo 5 × 3 do assoalho; aba = espessura, sem sobra)."""
    return [(poligono([(5, 0), (10, 0), (10, T), (15, T), (15, 23 + T), (0, 23 + T), (0, T), (5, T)]), CONT)]


def tira(w, h):
    return [(ret(0, 0, w, h), CONT)]


RANHURAS_Q1 = (2.8, 2.9, 3.0, 3.1)
FUROS_Q1 = (3.85, 4.0, 4.3)


def calibrador():
    """Q1: 48 × 31; ranhuras 2,80 / 2,90 / 3,00 / 3,10 × 9 e furos Ø3,85 (roda) / 4,00 / 4,30 (mancal)."""
    furos = [ret(cx - w / 2, 5.5, w, 9) for cx, w in zip((7, 18, 29, 40), RANHURAS_Q1)]
    furos += [circulo(cx, 23, d) for cx, d in zip((10, 24, 38), FUROS_Q1)]
    return [(f, FURO) for f in furos] + [(ret(0, 0, 48, 31), CONT)]


# ---------- folhas (mesa 365 × 370, margem 5) ----------
def _faixas():
    itens = []
    for i in range(4):
        itens.append((tira(53, 7), f"R{i + 1} Coluna externa 53 × 7", 5, 249 + 10 * i))
        itens.append((tira(52, 5), f"G{i + 1} Guia 52 × 5", 5, 289 + 8 * i))
        itens.append((tira(48, 5.5), f"D{i + 1} Diagonal 48 × 5,5", 63, 249 + 8.5 * i))
        itens.append((tira(52, 5), f"G{i + 5} Guia 52 × 5", 63, 283 + 8 * i))
    return itens


FOLHAS = [
    ("00 Calibrador Q1", [(calibrador(), "Q1 Calibrador do MDF", 5, 5)]),
    ("01 Carroça", [
        (lateral(), "L1 Lateral", 5, 5), (lateral(), "L2 Lateral", 179, 5),
        (assoalho(), "P1 Assoalho", 5, 70),
        (tampa(), "T1 Tampa", 179, 70), (tampa(), "T2 Tampa", 255, 70),
        (roda(58, 9, 23.25), "RT1 Roda traseira Ø58", 5, 140), (roda(58, 9, 23.25), "RT2 Roda traseira Ø58", 67, 140),
        (roda(46, 8.1, 17.9), "RD1 Roda dianteira Ø46", 129, 140),
        (roda(46, 8.1, 17.9), "RD2 Roda dianteira Ø46", 179, 140),
        (berco(), "B1 Berço", 229, 140), (berco(), "B2 Berço", 5, 202),
        (mancal(22, 14), "E1 Mancal traseiro", 91, 202), (mancal(22, 14), "E2 Mancal traseiro", 125, 202),
        (mancal(28, 20), "E3 Mancal dianteiro", 159, 202), (mancal(28, 20), "E4 Mancal dianteiro", 193, 202),
        (lanca(), "V1 Lança", 227, 202),
        (suporte_banco(), "A2 Suporte do banco", 313, 202), (suporte_banco(), "A3 Suporte do banco", 332, 202),
        (banco(), "A1 Banco", 115, 249),
    ] + _faixas()),
]

NOTAS = """CARROÇA COLONIAL DE MESA — MDF cru 3 mm (redesenhado do PDF carroca_colonial_guia_medidas_montagem.pdf)
Carroceria 170 × 79 × 102 mm; comprimento ~231 mm. 35 peças + calibrador Q1. Mesa 365 × 370.
O PDF só trazia o plano como imagem: vetores refeitos pelas cotas da tabela (precisão da imagem 0,25 mm).
Mudança: assoalho com 4 recortes 3 × 4 na borda para os braços dos berços (no PDF eles se cruzavam).

ANTES DE CORTAR
1. Encaixes SEM folga: rasgos e abas = 3,00 (espessura); furos das rodas e mancais Ø4,00 (vareta de 4 mm).
   Calibrador Q1 (aba 00, opcional): ranhuras 2,80 a 3,10 e furos Ø3,85 / 4,00 / 4,30 para conferir a chapa.
2. Se a chapa real não tiver 3,00, use Organizar → Redimensionar slots e/ou o Kerf da camada.
3. Corte: 800 mm/min, 85 %, 2 passadas (nunca 100 %); gravação 3000 mm/min, 15 %. Teste antes.
C03 = gravação das tábuas (1º), C02 = furos/rasgos/janelas (2º), C01 = contornos (por último).

MONTAGEM (não colar tampas nem eixos)
01 Encaixe L1/L2 no assoalho P1, inclinadas 10° para fora.
02 B1 e B2 nos rasgos 3 × 7 (x = 36 e 137); braços por fora das laterais.
03 Mancais E1-E4 nos rasgos 6 × 3 e nos meios-encaixes dos berços (E1-E2 atrás, E3-E4 na frente); cole.
04 R1-R4 por fora, mais ao centro; diagonais D1-D4 fora das guias.
05 G1-G8 dentro das laterais, vão de 3,4 mm entre cada par: trás x = 3-8 e 11,4-16,4; frente x = 131-136 e
   139,4-144,4. Tampas T1/T2 deslizam de cima (sem cola).
06 A2-A3 nos rasgos 5 × 3 do piso; A1 colado em cima (topo 30 mm abaixo da borda).
07 Lança V1 colada sob o assoalho, na frente.
08 Duas varetas Ø4 × 104 nos mancais; rodas coladas nas pontas (Ø58 atrás, Ø46 na frente)."""


def camadas():
    corte = dict(modo="linha", velocidade_mm_min=800.0, potencia_max=85.0, potencia_min=0.0, passadas=2, air=True)
    return [cm.alterar(cm.Camada(GRAV, "Gravação: linhas das tábuas (1º)"), modo="linha", velocidade_mm_min=3000.0,
                       potencia_max=15.0, potencia_min=0.0, passadas=1),
            cm.alterar(cm.Camada(FURO, "Internos: furos, rasgos e janelas (corte, 2º)"), **corte),
            cm.alterar(cm.Camada(CONT, "Contornos (corte, por último)"), **corte)]


def peca(partes, nome, x, y):
    """Peça com o canto superior esquerdo da caixa em (x, y) da mesa, agrupada."""
    caixa = QRectF()
    for path, _ in partes:
        caixa = caixa.united(path.boundingRect())
    tf = QTransform.fromTranslate(x - caixa.left(), y - caixa.top())
    tipo = {GRAV: "gravação", FURO: "furo/rasgo", CONT: "contorno"}
    itens = [ob.Shape(tf.map(path), f"{nome} — {tipo[lid]}", lid, cm.cor(lid)) for path, lid in partes]
    g = ob.group(itens)
    g.name = nome
    return g.snapshot()


LETRAS_EXTRAS = {"P1": "P1  FRENTE →", "B1": "B1 TRÁS", "B2": "B2 FRENTE", "T1": "T1 TRÁS", "T2": "T2 FRENTE"}


def gerar(destino):
    paginas = [tuple(peca(*p) for p in pecas) for _, pecas in FOLHAS]
    atual = 1  # abre na folha da carroça; None marca a página atual (vai em snapshots)
    pj.save(destino, paginas[atual], camadas(), notas=NOTAS,
            paginas=[None if i == atual else (p, (), ()) for i, p in enumerate(paginas)],
            pagina_atual=atual, nomes_paginas=[n for n, _ in FOLHAS])
    import etiquetas  # código gravado em cada peça (15 %, 3000 mm/min, antes dos cortes) + abas "SÓ LETRAS"
    etiquetas.etiquetar(destino, destino, LETRAS_EXTRAS)
    return destino


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else "carroca_colonial_3mm.rbl"))
