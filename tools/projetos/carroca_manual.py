"""Manual de montagem e colagem da carroça colonial (PDF, A4), com os desenhos tirados das próprias peças.

Executar:  python tools/projetos/carroca_manual.py <projeto_com_letras.rbl> <saida.pdf>
O .rbl (opcional na prática, mas pedido aqui) fornece o mapa da chapa com as letras gravadas, como foi cortada.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QFont, QPageLayout, QPageSize, QPainter, QPainterPath,  # noqa: E402
                           QPdfWriter, QPen, QTransform)

import carroca_colonial as cc  # noqa: E402
import etiquetas as et  # noqa: E402

TINTA, CINZA, VERM, AZUL, VERDE, MADEIRA = "#222222", "#8a8f99", "#c62828", "#1565c0", "#2e7d32", "#f3e3c3"
W, H, M = 210.0, 297.0, 14.0  # A4 em mm, margem


class Pagina:
    """QPainter em milímetros (Y para baixo) sobre o PDF."""

    def __init__(self, pdf, painter):
        self.pdf, self.p = pdf, painter
        self.k = pdf.resolution() / 25.4

    def nova(self):
        self.pdf.newPage()

    def texto(self, x, y, w, s, tam=10, negrito=False, cor=TINTA, alinhar=Qt.AlignLeft):
        """Bloco de texto com quebra de linha; devolve a altura usada (mm)."""
        p = self.p
        f = QFont("Arial")
        f.setPixelSize(max(1, round(tam * 0.3528 * self.k)))  # pontos -> pixels do PDF
        f.setBold(negrito)
        p.setFont(f)
        p.setPen(QColor(cor))
        r = QRectF(x * self.k, y * self.k, w * self.k, 400 * self.k)
        usado = p.boundingRect(r, int(alinhar | Qt.TextWordWrap), s)
        p.drawText(r, int(alinhar | Qt.TextWordWrap), s)
        return usado.height() / self.k

    def forma(self, path, tf, cor=TINTA, fundo=None, larg=0.35, tracejado=False):
        caneta = QPen(QColor(cor), larg * self.k)
        if tracejado:
            caneta.setStyle(Qt.DashLine)
        self.p.setPen(caneta)
        self.p.setBrush(QBrush(QColor(fundo)) if fundo else Qt.NoBrush)
        self.p.drawPath((tf * QTransform.fromScale(self.k, self.k)).map(path))


def caminho(partes, lids):
    out = QPainterPath()
    for p, lid in partes:
        if lid in lids:
            out.addPath(p)
    return out


def desenhar_peca(pg, partes, tf, fundo=MADEIRA, rotulo=None, tam=9, cor_rot=AZUL):
    pg.forma(caminho(partes, {cc.CONT}), tf, fundo=fundo)
    pg.forma(caminho(partes, {cc.FURO}), tf, fundo="#ffffff")
    pg.forma(caminho(partes, {cc.GRAV}), tf, cor=CINZA, larg=0.2)
    if rotulo:
        r = tf.mapRect(caminho(partes, {cc.CONT}).boundingRect())
        pg.texto(r.left(), r.center().y() - tam * 0.2, r.width(), rotulo, tam, True, cor_rot, Qt.AlignHCenter)


def seta(pg, x0, y0, x1, y1, cor=VERM):
    path = QPainterPath(QPointF(x0, y0))
    path.lineTo(x1, y1)
    a = math.atan2(y1 - y0, x1 - x0)
    for s in (2.6, -2.6):
        path.moveTo(x1, y1)
        path.lineTo(x1 - 2.2 * math.cos(a + s / 6), y1 - 2.2 * math.sin(a + s / 6))
    pg.forma(path, QTransform(), cor=cor, larg=0.35)


def nota(pg, x, y, s, cor=VERM, tam=7.5, w=40, alinhar=Qt.AlignLeft):
    return pg.texto(x, y, w, s, tam, True, cor, alinhar)


# ---------- páginas ----------
PECAS = [("L1, L2", "Laterais", 2, "em pé nos rasgos da borda do assoalho, inclinadas 10° para fora"),
         ("P1", "Assoalho", 1, "fundo da caixa; \"FRENTE →\" aponta para a frente (lado do banco)"),
         ("B1, B2", "Berços", 2, "por baixo do assoalho: B1 atrás (x 36), B2 na frente (x 137)"),
         ("E1, E2", "Mancais traseiros (menores)", 2, "por baixo, cruzando o B1; furo do eixo de trás"),
         ("E3, E4", "Mancais dianteiros (maiores)", 2, "por baixo, cruzando o B2; furo do eixo da frente"),
         ("RT1, RT2", "Rodas traseiras Ø58", 2, "nas pontas da vareta de trás"),
         ("RD1, RD2", "Rodas dianteiras Ø46", 2, "nas pontas da vareta da frente"),
         ("G1 a G8", "Guias 52 × 5", 8, "dentro das laterais, em pares (trilho das tampas)"),
         ("T1, T2", "Tampas", 2, "deslizam entre as guias: T1 atrás, T2 na frente (NÃO colar)"),
         ("R1 a R4", "Colunas 53 × 7", 4, "por fora das laterais, 2 de cada lado"),
         ("D1 a D4", "Diagonais 48 × 5,5", 4, "por fora das laterais, entre as colunas"),
         ("A2, A3", "Suportes do banco", 2, "em pé nos rasgos 5 × 3 da frente do assoalho"),
         ("A1", "Banco", 1, "colado em cima de A2 e A3"),
         ("V1", "Lança", 1, "colada por baixo da frente do assoalho")]


def capa(pg, rbl):
    y = M
    y += pg.texto(M, y, W - 2 * M, "Carroça colonial — manual de montagem", 20, True)
    y += pg.texto(M, y + 1, W - 2 * M, "MDF 3 mm · 35 peças · cada peça tem o seu código gravado (L1, P1, G3…). "
                  "Monte tudo A SECO primeiro; cole só depois de conferir.", 9.5, cor="#444444") + 4
    y += pg.texto(M, y, W - 2 * M, "Você vai precisar", 12, True) + 1
    y += pg.texto(M, y, W - 2 * M, "• Cola PVA (branca) ou cianoacrilato   • 2 varetas Ø4 mm × 104 mm (eixos)   "
                  "• Lixa fina   • Esquadro   • Prendedores ou elásticos para segurar enquanto seca", 9) + 4
    y += pg.texto(M, y, W - 2 * M, "Lista de peças", 12, True) + 1
    for cod, nome, qtd, onde in PECAS:
        pg.texto(M, y, 22, cod, 9, True, AZUL)
        pg.texto(M + 22, y, 50, f"{nome} ({qtd})", 9, True)
        y += max(pg.texto(M + 74, y, W - 2 * M - 74, onde, 9), 4.2) + 0.6
    y += 4
    y += pg.texto(M, y, W - 2 * M, "Mapa da chapa (como foi cortada)", 12, True) + 1
    with open(rbl, encoding="utf-8") as f:
        d = json.load(f)
    objs = d["objetos"] if not d.get("paginas") or d["paginas"][0] is None else d["paginas"][0]["objetos"]
    escala = min((W - 2 * M) / 365, (H - M - y) / 300)
    tf = QTransform.fromScale(escala, escala) * QTransform.fromTranslate(M, y)
    for o in objs:
        for path, lid in et.folhas(o, et.matriz(o)):
            if o["tipo"] == "texto" or lid == et.CAMADA:
                pg.forma(path, tf, cor=AZUL, fundo=AZUL, larg=0.1)
            else:
                pg.forma(path, tf, cor=CINZA, larg=0.15)


def assoalho(pg):
    y = M
    y += pg.texto(M, y, W - 2 * M, "1. O assoalho (P1) é o mapa de tudo", 15, True) + 1
    y += pg.texto(M, y, W - 2 * M, "Visto de CIMA, com a gravação \"P1 FRENTE →\" para cima e a seta apontando para "
                  "a frente. Cada rasgo recebe uma peça: as cores abaixo mostram qual.", 9.5) + 3
    s = 1.0
    x0 = (W - 170 * s) / 2
    tf = QTransform.fromScale(s, s) * QTransform.fromTranslate(x0, y + 14)
    desenhar_peca(pg, cc.assoalho(), tf, rotulo=None)
    # destaque dos rasgos por função
    grupos = {VERM: [], VERDE: [], AZUL: [], "#8e24aa": []}
    for p, lid in cc.assoalho():
        if lid != cc.FURO:
            continue
        r = p.boundingRect()
        cor = (VERM if round(r.width(), 1) == 7 else VERDE if round(r.height(), 1) == 7 else
               AZUL if round(r.width(), 1) == 6 else "#8e24aa")
        grupos[cor].append(p)
    for cor, ps in grupos.items():
        for p in ps:
            pg.forma(p, tf, cor=cor, fundo=cor, larg=0.2)
    yt = y + 14
    nota(pg, x0, yt - 9, "TRÁS (x = 0)", TINTA, 8)
    nota(pg, x0 + 170 - 40, yt - 9, "FRENTE →", TINTA, 8, 40, Qt.AlignRight)
    y = yt + 66 + 4
    legenda = [(VERM, "Vermelho (7 × 3, 8 rasgos): abas das laterais L1 e L2 — uma em cada borda comprida."),
               (VERDE, "Verde (3 × 7): abas dos berços por BAIXO — B1 no par de trás (x 36), B2 no da frente (x 137)."),
               (AZUL, "Azul (6 × 3): abas dos mancais por BAIXO — E1/E2 (menores) atrás, E3/E4 (maiores) na frente."),
               ("#8e24aa", "Roxo (5 × 3): suportes do banco A2 e A3, em pé, por CIMA.")]
    for cor, s_ in legenda:
        q = QPainterPath()
        q.addRect(QRectF(M, y + 0.8, 4, 3))
        pg.forma(q, QTransform(), cor=cor, fundo=cor)
        y += pg.texto(M + 6, y, W - 2 * M - 6, s_, 9) + 1.2
    y += 3
    y += pg.texto(M, y, W - 2 * M, "Onde vão as peças de dentro (medidas a partir da TRASEIRA, x = 0)", 11, True) + 1
    s2 = 1.0
    tf2 = QTransform.fromScale(s2, s2) * QTransform.fromTranslate(x0, y + 6)
    q = QPainterPath()
    q.addRect(QRectF(0, 0, 170, 20))
    pg.forma(q, tf2, cor=CINZA, fundo="#fafafa", larg=0.2)
    for a, b, cor, txt in ((3, 8, AZUL, "G"), (11.4, 16.4, AZUL, "G"), (131, 136, AZUL, "G"), (139.4, 144.4, AZUL, "G"),
                           (8, 11.4, VERM, "T1"), (136, 139.4, VERM, "T2"), (148, 165, "#8e24aa", "A1")):
        r = QPainterPath()
        r.addRect(QRectF(a, 2, b - a, 16))
        pg.forma(r, tf2, cor=cor, fundo=cor if txt != "A1" else None, larg=0.25)
    yl = y + 6 + 21
    nota(pg, x0 - 2, yl, "G1 G2 | T1 | G3 G4\nx 3-8 e 11,4-16,4", AZUL, 7, 50)
    nota(pg, x0 + 112, yl, "G5 G6 | T2 | G7 G8\nx 131-136 e 139,4-144,4", AZUL, 7, 40)
    nota(pg, x0 + 146, y + 6 - 6, "banco A1\nx 148-165", "#8e24aa", 7, 30)
    y = yl + 10
    y += pg.texto(M, y, W - 2 * M,
                  "As guias G (5 × 52) ficam em pé, coladas DENTRO das laterais, em pares. Entre cada par fica um "
                  "vão livre de 3,4 mm: é o trilho da tampa. Use a própria tampa T como gabarito: ela tem que "
                  "deslizar sem forçar. Repita do outro lado (8 guias = 2 pares atrás + 2 pares na frente).", 9)


def montagem(pg):
    y = M
    y += pg.texto(M, y, W - 2 * M, "2. Passo a passo", 15, True) + 2
    passos = [
        ("Laterais", "Encaixe L1 e L2 nos 8 rasgos vermelhos do P1, com as abas para baixo e a gravação das tábuas "
         "para fora. Elas ficam inclinadas 10° para fora (a parte de cima mais aberta). Cole por baixo."),
        ("Berços", "Vire a caixa de cabeça para baixo. B1 TRÁS entra nos rasgos verdes de trás (x 36) e B2 FRENTE nos "
         "da frente (x 137), com os braços subindo POR FORA das laterais."),
        ("Mancais", "E1 e E2 (menores, furo mais alto) atrás; E3 e E4 (maiores) na frente. As abas entram nos rasgos "
         "azuis e o corte do meio do mancal se cruza com o corte de baixo do berço (meio-encaixe), como na figura. "
         "Confira que os 2 furos de cada eixo ficam alinhados (passe a vareta) e cole."),
        ("Colunas e diagonais", "POR FORA de cada lateral: R em pé de 41,5 a 48,5 e de 121,5 a 128,5 mm da "
         "traseira; D inclinadas entre elas, topo para a frente. Use o gabarito 1:1 da página 4."),
        ("Guias", "POR DENTRO de cada lateral, rentes à borda de baixo: pares em 3-8 / 11,4-16,4 (trás) e "
         "131-136 / 139,4-144,4 mm (frente). Cole com a tampa entre o par como espaçador. Gabarito na página 4."),
        ("Tampas", "T1 TRÁS e T2 FRENTE descem de cima para baixo entre as guias. NÃO cole: elas saem para abrir."),
        ("Banco", "A2 e A3 em pé nos rasgos roxos; cole o banco A1 por cima. A frente (T2) fica ATRÁS do banco."),
        ("Lança", "Cole V1 por baixo da frente do assoalho, com o garfo (Y) para dentro e a ponta com furo para "
         "a frente, no meio da largura."),
        ("Rodas", "Passe uma vareta Ø4 × 104 em cada par de mancais. Cole as rodas nas pontas: RT1/RT2 (Ø58) atrás, "
         "RD1/RD2 (Ø46) na frente. Furos sem folga: se a vareta não entrar, lixe a ponta dela, não o furo. "
         "Não cole a vareta no mancal se quiser tentar girar."),
    ]
    for i, (t, s) in enumerate(passos, 1):
        pg.texto(M, y, 8, f"{i}", 13, True, VERM)
        pg.texto(M + 8, y, 50, t, 10.5, True)
        y += pg.texto(M + 8, y + 4.6, W - 2 * M - 8, s, 9) + 7
    y += 2
    # vista lateral
    y += pg.texto(M, y, W - 2 * M, "Vista lateral (lado esquerdo; frente à direita)", 11, True) + 2
    s = 0.72
    ox = (W - 231 * s) / 2
    piso = y + 4 + cc.H_LAT * s  # topo do assoalho = base da lateral (as abas atravessam os 3 mm)
    tf_l = QTransform.fromScale(s, s) * QTransform.fromTranslate(ox, y + 4)
    desenhar_peca(pg, cc.lateral(), tf_l)
    nota(pg, ox + 2, y + 5, "L1 / L2 (lateral)", AZUL, 7.5, 40)
    for cx in COLUNAS:
        pg.forma(_ret(cx - 3.5, 2, 7, 53), tf_l, cor=TINTA, fundo="#d9b98a", larg=0.25)
        nota(pg, ox + cx * s - 3, y + 1, "R", AZUL, 7, 6)
    for pe, topo in DIAGONAIS:
        pg.forma(_diagonal(pe, topo)[0], tf_l, cor=TINTA, fundo="#8d6e63", larg=0.2)
    nota(pg, ox + 92 * s, y + 1, "D  D", AZUL, 7, 12)
    tf_base = QTransform.fromScale(s, s) * QTransform.fromTranslate(ox, piso)
    q = QPainterPath()
    q.addRect(QRectF(0, 0, 170, 3))
    pg.forma(q, tf_base, cor=TINTA, fundo="#c8a46e", larg=0.25)
    for ex, (dy, r_, cod) in ((36, (3 + 14, 29, "RT")), (137, (3 + 20, 23, "RD"))):
        c = QPainterPath()
        c.addEllipse(QPointF(ex, dy), r_, r_)
        pg.forma(c, tf_base, cor=TINTA, larg=0.3)
        c2 = QPainterPath()
        c2.addEllipse(QPointF(ex, dy), 2, 2)
        pg.forma(c2, tf_base, cor=TINTA, fundo=TINTA)
        m = QPainterPath()
        m.addRect(QRectF(ex - 15, 3, 30, (22 if cod == "RT" else 28)))
        pg.forma(m, tf_base, cor=AZUL, larg=0.25, tracejado=True)
        pg.texto(ox + (ex - 10) * s, piso + (dy + r_ + 1) * s, 20 * s, cod, 7.5, True, AZUL, Qt.AlignHCenter)
    lan = QTransform.fromScale(s, s) * QTransform.fromTranslate(ox + 148.5 * s, piso + 3 * s)
    pg.forma(QTransform().scale(1, 0.25).map(caminho(cc.lanca(), {cc.CONT})), lan, cor=TINTA, fundo="#c8a46e")
    nota(pg, ox + 200 * s, piso + 6 * s, "V1", AZUL, 7.5, 10)
    nota(pg, ox, piso + 52 * s, "mancais (tracejado) por baixo, um de cada lado; eixo atravessa os furos", CINZA, 7,
         W - 2 * M)


# posições na lateral (mm), x a partir da ponta de TRÁS, y a partir da borda de CIMA (como na vista do PDF p. 1)
COLUNAS = (45.0, 125.0)                      # centro das colunas R (7 × 53), de y 2 a 55
DIAGONAIS = (((73.0, 51.5), (89.7, 6.5)),    # (pé, topo) da linha do meio das diagonais D (5,5 × 48)
             ((100.0, 51.5), (116.7, 6.5)))
GUIAS = ((3, 8), (11.4, 16.4), (131, 136), (139.4, 144.4))  # x das guias G (5 × 52), do piso para cima
TAMPAS = ((8, 11.4, "T1"), (136, 139.4, "T2"))


def _ret(x, y, w, h):
    q = QPainterPath()
    q.addRect(QRectF(x, y, w, h))
    return q


def _diagonal(pe, topo):
    (x0, y0), (x1, y1) = pe, topo
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    tf = QTransform().rotate(ang) * QTransform.fromTranslate((x0 + x1) / 2, (y0 + y1) / 2)
    return tf.map(_ret(-24, -2.75, 48, 5.5)), ang


def _cota_x(pg, ox, y, x, txt, cor=AZUL, acima=True, nivel=0):
    """Tracinho na posição x da lateral (1:1) com o número em cima ou embaixo; nivel 1 = uma linha mais longe."""
    h = 3 + 3.6 * nivel
    pg.forma(_ret(x, 0, 0, h), QTransform.fromTranslate(ox, y - h if acima else y), cor=cor, larg=0.2)
    pg.texto(ox + x - 6, y - h - 3.6 if acima else y + h + 0.2, 12, txt, 6.5, True, cor, Qt.AlignHCenter)


def laterais(pg):
    y = M
    y += pg.texto(M, y, W - 2 * M, "4. Laterais em TAMANHO REAL (gabarito)", 15, True) + 1
    y += pg.texto(M, y, W - 2 * M,
                  "Imprima esta página em 100 % (sem \"ajustar à página\") e confira a régua de 50 mm. Deite a lateral "
                  "sobre o desenho, com as bordas em cima das linhas, e cole cada peça sobre a sua mancha. Marque a "
                  "lápis a ponta de TRÁS de L1 e L2 antes: as duas laterais usam as mesmas medidas a partir da "
                  "traseira (x = 0, o lado das rodas grandes e da tampa T1).", 9) + 3
    regua = QPainterPath()
    regua.moveTo(0, 0)
    regua.lineTo(50, 0)
    for k in range(0, 51, 10):
        regua.moveTo(k, 0)
        regua.lineTo(k, -2 if k % 50 else -3)
    pg.forma(regua, QTransform.fromTranslate(M, y + 3), larg=0.25)
    pg.texto(M + 52, y, 60, "50 mm (confira com a régua)", 7.5, cor=CINZA)
    y += 10
    ox = (W - 170) / 2

    # --- vista de FORA: colunas e diagonais
    y += pg.texto(M, y, W - 2 * M, "Lado de FORA (face com as linhas de tábua): colunas R e diagonais D", 11, True)
    y += 12
    for cx in COLUNAS:
        _cota_x(pg, ox, y, cx - 3.5, f"{cx - 3.5:g}".replace(".", ","))
        _cota_x(pg, ox, y, cx + 3.5, f"{cx + 3.5:g}".replace(".", ","))
    for pe, topo in DIAGONAIS:
        _cota_x(pg, ox, y, topo[0], f"{topo[0]:g}".replace(".", ","), VERM, nivel=1)
    tf = QTransform.fromTranslate(ox, y)
    desenhar_peca(pg, cc.lateral(), tf)
    for i, cx in enumerate(COLUNAS):
        pg.forma(_ret(cx - 3.5, 2, 7, 53), tf, cor=TINTA, fundo="#d9b98a", larg=0.25)
        pg.texto(ox + cx - 3.5, y + 26, 7, "R", 8, True, AZUL, Qt.AlignHCenter)
    for pe, topo in DIAGONAIS:
        path, _ = _diagonal(pe, topo)
        pg.forma(path, tf, cor=VERM, fundo="#f2b8b5", larg=0.25)
        pg.texto(ox + (pe[0] + topo[0]) / 2 - 3, y + 26, 6, "D", 8, True, VERM, Qt.AlignHCenter)
    for pe, topo in DIAGONAIS:
        _cota_x(pg, ox, y + cc.H_LAT + 3, pe[0], f"{pe[0]:g}".replace(".", ","), VERM, acima=False)
    nota(pg, ox - 13, y + 24, "TRÁS\nx = 0", TINTA, 7, 12)
    nota(pg, ox + 171, y + 24, "FRENTE", TINTA, 7, 14)
    y += cc.H_LAT + 12
    y += pg.texto(M, y, W - 2 * M,
                  "Colunas R1–R4 (7 × 53): em pé, de 41,5 a 48,5 mm e de 121,5 a 128,5 mm da traseira, 2 mm abaixo "
                  "da borda de cima (sobra ~2 mm embaixo). Diagonais D1–D4 (5,5 × 48): o pé fica 5,4 mm acima da "
                  "borda de baixo, com o meio a 73 e 100 mm; o topo fica 6,5 mm abaixo da borda de cima, com o meio "
                  "a 89,7 e 116,7 mm (inclinadas ~70°, o topo para a FRENTE). Na outra lateral, as mesmas medidas a "
                  "partir da traseira (o desenho fica espelhado).", 8.5) + 6

    # --- vista de DENTRO: guias (espelhada: virando a peça, a traseira vai para a direita)
    y += pg.texto(M, y, W - 2 * M, "Lado de DENTRO (face lisa): guias G e trilho das tampas", 11, True)
    y += 16
    espelho = QTransform(-1, 0, 0, 1, 170, 0)
    tf = espelho * QTransform.fromTranslate(ox, y)
    for a, b in GUIAS:  # bordas que encostam na tampa numa segunda linha, para os números não se encavalarem
        _cota_x(pg, ox, y, 170 - a, f"{a:g}".replace(".", ","), nivel=a in (11.4, 139.4))
        _cota_x(pg, ox, y, 170 - b, f"{b:g}".replace(".", ","), nivel=2 * (b in (8, 136)))
    pg.forma(caminho(cc.lateral(), {cc.CONT}), tf, fundo=MADEIRA)
    piso = cc.H_LAT - 52
    for a, b in GUIAS:
        pg.forma(_ret(a, piso, b - a, 52), tf, cor=TINTA, fundo="#bbdefb", larg=0.25)
    for a, b, cod in TAMPAS:
        pg.forma(_ret(a, piso, b - a, 52), tf, cor=VERM, larg=0.2, tracejado=True)
        pg.texto(ox + 170 - b - 3, y + 26, b - a + 6, cod, 7, True, VERM, Qt.AlignHCenter)
    for a, b in ((3, 16.4), (131, 144.4)):
        pg.texto(ox + 170 - b, y + cc.H_LAT + 3.5, b - a, "G G", 7, True, AZUL, Qt.AlignHCenter)
    nota(pg, ox - 15, y + 24, "FRENTE", TINTA, 7, 14)
    nota(pg, ox + 171, y + 24, "TRÁS\nx = 0", TINTA, 7, 12)
    y += cc.H_LAT + 12
    y += pg.texto(M, y, W - 2 * M,
                  f"Guias G1–G8 (5 × 52), em pé, rentes à borda de baixo da lateral (o topo fica {str(round(piso, 1)).replace('.', ',')} mm abaixo da borda de "
                  "cima). Atrás: de 3 a 8 e de 11,4 a 16,4 mm da traseira; na frente: de 131 a 136 e de 139,4 a "
                  "144,4 mm. Entre cada par sobra o vão de 3,4 mm (tracejado vermelho) onde a tampa desce. Cole uma "
                  "guia, encoste a tampa nela, encoste a segunda guia na tampa e cole: assim o vão fica certo mesmo "
                  "se o MDF não tiver 3,00. Tire a tampa antes da cola secar.", 8.5) + 4
    pg.texto(M, y, W - 2 * M,
             "Ordem: cole as guias ANTES de encaixar as laterais no assoalho (a peça deitada fica mais fácil); as "
             "colunas e diagonais podem ser coladas antes ou depois, sempre por fora.", 8.5, cor=VERM)


def corte(pg):
    y = M
    y += pg.texto(M, y, W - 2 * M, "5. Vista de frente (corte no eixo de trás)", 15, True) + 1
    y += pg.texto(M, y, W - 2 * M, "Assim ficam laterais, assoalho, berço, mancais, eixo e rodas olhando de frente. "
                  "Coordenadas da figura: u = largura (0 no meio), v = altura (para baixo; assoalho entre v 30 e 33).",
                  9.5) + 4
    s = 1.15
    cx = W / 2
    tfc = QTransform.fromScale(s, s) * QTransform.fromTranslate(cx, y + 30 * s)  # v = -27 fica logo abaixo do texto

    def em(u, v):
        q = tfc.map(QPointF(u, v))
        return q.x(), q.y()

    desenhar_peca(pg, cc.berco(), QTransform.fromTranslate(-40.82, 0) * tfc, fundo="#e8d2a8")
    piso = QPainterPath()
    piso.addRect(QRectF(-33, 30, 66, 3))
    pg.forma(piso, tfc, cor=TINTA, fundo="#c8a46e")
    for lado in (-1, 1):  # laterais de 3 mm no rasgo a 3,5-6,5 mm da borda, 10° para fora
        a = math.radians(10) * lado
        b0 = 26.5 if lado > 0 else -29.5
        pts = [(b0, 30), (b0 + 3, 30)]
        pts += [(pts[1][0] + 56.9 * math.sin(a), 30 - 56.9 * math.cos(a)),
                (pts[0][0] + 56.9 * math.sin(a), 30 - 56.9 * math.cos(a))]
        lp = QPainterPath(QPointF(*pts[0]))
        for p_ in pts[1:]:
            lp.lineTo(*p_)
        lp.closeSubpath()
        pg.forma(lp, tfc, cor=TINTA, fundo="#d9b98a")
        m = QPainterPath()  # mancal visto de lado (3 mm)
        m.addRect(QRectF(lado * 20 - 1.5, 33, 3, 22))
        pg.forma(m, tfc, cor=AZUL, fundo="#bbdefb")
        rd = QPainterPath()
        rd.addRect(QRectF(lado * 52 - (3 if lado > 0 else 0), 47 - 29, 3, 58))
        pg.forma(rd, tfc, cor=TINTA, fundo="#d9b98a")
    eixo = QPainterPath()
    eixo.addRect(QRectF(-52, 45, 104, 4))
    pg.forma(eixo, tfc, cor=TINTA, fundo="#9e9e9e")
    for (u, v), t in (((-48, -20), "L1"), ((40, -20), "L2"), ((-4, 24), "P1"), ((-26, 52), "E"), ((17, 52), "E"),
                      ((-14, 37), "B1"), ((-66, 20), "RT1"), ((55, 20), "RT2"), ((-13, 50), "vareta Ø4")):
        x_, y_ = em(u, v)
        pg.texto(x_, y_, 30, t, 8.5, True, AZUL if t != "vareta Ø4" else CINZA)
    y = em(0, 78)[1] + 4
    y += pg.texto(M, y, W - 2 * M, "Meio-encaixe do mancal no berço", 11, True) + 2
    s2 = 1.3
    tfb = QTransform.fromScale(s2, s2) * QTransform.fromTranslate(M + 4, y + 4)
    desenhar_peca(pg, cc.berco(), tfb, fundo="#e8d2a8", rotulo="B1 / B2", tam=8)
    tfe = QTransform.fromScale(s2, s2) * QTransform.fromTranslate(M + 4 + 100 * s2, y + 4)
    desenhar_peca(pg, cc.mancal(22, 14), tfe, fundo=MADEIRA, rotulo="E1 / E2", tam=8)
    for tf_, (u, v0, v1) in ((tfb, (40.82 + 20, 51, 41)), (tfe, (15, -4, 6))):
        a0, a1 = tf_.map(QPointF(u, v0)), tf_.map(QPointF(u, v1))
        seta(pg, a0.x(), a0.y(), a1.x(), a1.y())
    y = tfb.map(QPointF(0, 56)).y()
    pg.texto(M, y, W - 2 * M, "As setas vermelhas mostram os dois cortes de 3 × 5 mm que se encaixam. Primeiro o berço "
             "entra nos rasgos verdes; depois o mancal sobe POR BAIXO, de lado (cruzado), até as duas abas de cima "
             "entrarem nos rasgos azuis: o corte de cima do mancal abraça o berço e o corte de baixo do berço abraça o "
             "mancal.", 9)


def gerar(rbl, saida):
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Carroça colonial — manual de montagem")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    for i, f in enumerate((capa, assoalho, montagem, laterais, corte)):
        if i:
            pg.nova()
        f(pg, rbl) if f is capa else f(pg)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
