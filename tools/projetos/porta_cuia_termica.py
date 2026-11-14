"""Gera o projeto "Porta-cuia e térmica" como .rbl, com uma aba por folha de produção, para QUALQUER espessura.

Base: PDF projeto_porta_cuia_e_termica.pdf (R03, desenhado em MDF 6 mm). As medidas dependem da espessura t da
chapa; com t = 6 as fórmulas abaixo dão exatamente as cotas do PDF (conferido em tests/test_projeto_porta_cuia.py).

Fixos do desenho (não dependem de t): base 310 × 170 (R4); paredes a 4 mm da borda; altura total 340 mm; topo da
bandeja a 160 mm da mesa; centro da cuia a X 79,5 / Y 85 e da térmica a X 230,5 / Y 85; posições absolutas dos
machos e rasgos (centros); costelas a 19 e 151 mm da frente; centro dos rasgos F a 183 mm da mesa.
Dependem de t: rasgo de uma chapa = t + folga, de duas = 2t + folga; machos que entram no piso/bandeja = t, na
divisória (dupla) = 2t; largura interna = 170 − 8 − 2t; corpo da bandeja/costela = 151 − 2t; ombros em Y = t.

Cada peça é desenhada no sistema do PDF (X para a direita, Y para cima, Y = 0 na ponta dos machos) e posicionada
na mesa. Furos e rasgos = camada C02 (cortada primeiro); contornos = C01.

Executar:  python tools/projetos/porta_cuia_termica.py [saida.rbl] [espessura_mm]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

K = 0.5522847498  # quarto de círculo por Bézier cúbica (erro < 0,03 % do raio)
MARGEM = 5.0      # da borda superior esquerda da mesa
FOLGA = 0.15      # folga nominal dos rasgos (PDF)
PAREDE = 4.0      # face externa das paredes até a borda da base


# ---------- desenho no sistema do PDF (Y para cima) ----------
def poligono(pts):
    p = QPainterPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.closeSubpath()
    return p


def retangulo(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def rasgo_centro(cx, cy, w, h):
    return retangulo(cx - w / 2, cy - h / 2, w, h)


def circulo(cx, cy, r):
    p = QPainterPath()
    p.addEllipse(QPointF(cx, cy), r, r)
    return p


def canto(p, de, quina, para):
    """Arco de quarto de círculo de `de` a `para` contornando `quina` (p já está em `de`)."""
    c1 = (de[0] + K * (quina[0] - de[0]), de[1] + K * (quina[1] - de[1]))
    c2 = (para[0] + K * (quina[0] - para[0]), para[1] + K * (quina[1] - para[1]))
    p.cubicTo(*c1, *c2, *para)


def _abas_embaixo(p, abas, ombro):
    """Da direita para a esquerda pela borda Y = ombro, descendo nas linguetas [(x_dir, x_esq)] até Y = 0."""
    for a, b in abas:
        p.lineTo(a, ombro)
        p.lineTo(a, 0)
        p.lineTo(b, 0)
        p.lineTo(b, ombro)
    p.closeSubpath()


class Projeto:
    def __init__(self, t=6.0, folga=FOLGA):
        if not 1.0 <= t <= 12.0:
            raise ValueError("espessura entre 1 e 12 mm")
        self.t, self.f = float(t), float(folga)
        self.interno = 170 - 2 * PAREDE - 2 * self.t   # largura da divisória/bandeja/parede curta
        self.y0 = PAREDE + self.t                       # face interna da parede da frente (Y absoluto)
        self.corpo = (155 - self.t) - self.y0           # bandeja e costela: da parede curta até a divisória

    # P01 / P02 -----------------------------------------------------------
    @staticmethod
    def base_r4():
        p = QPainterPath()
        p.addRoundedRect(QRectF(0, 0, 310, 170), 4, 4)
        return p

    def p01(self):
        return [(self.base_r4(), "C01")]

    def p02(self):
        t, f = self.t, self.f
        um, dois = t + f, 2 * t + f
        furos = [rasgo_centro(155, cy, dois, 24.15) for cy in (37, 85, 133)]                        # A
        frente, tras = PAREDE + t / 2, 170 - PAREDE - t / 2
        furos += [rasgo_centro(cx, cy, 28.15, um) for cx in (36, 155, 274) for cy in (frente, tras)]  # B
        furos += [rasgo_centro(cx, cy, um, 26.15) for cx in (frente, 310 - frente) for cy in (47.5, 122.5)]  # C
        return [(f_, "C02") for f_ in furos] + [(self.base_r4(), "C01")]

    # P03 divisória e alça (2 lâminas) -------------------------------------
    def p03(self):
        t, f, W = self.t, self.f, self.interno
        H = 340 - t  # ponta do macho (sobre P01) até o topo: topo a 340 mm da mesa
        p = QPainterPath()
        p.moveTo(0, t)
        p.lineTo(0, H - 18)
        canto(p, (0, H - 18), (0, H), (18, H))
        p.lineTo(W - 18, H)
        canto(p, (W - 18, H), (W, H), (W, H - 18))
        p.lineTo(W, t)
        abas = [(c + 12 - self.y0, c - 12 - self.y0) for c in (133, 85, 37)]  # machos A (24) nos centros do piso
        _abas_embaixo(p, abas, t)
        pega = QPainterPath()
        pega.addRoundedRect(QRectF(W / 2 - 50, 310 - t - 14, 100, 28), 14, 14)  # centro a 310 mm da mesa
        y_d = (160 - t / 2) - t  # rasgo da bandeja: centro na espessura da bandeja
        furos = [pega] + [rasgo_centro(c - self.y0, y_d, 28.15, t + f) for c in (56, 114)]         # D
        furos += [rasgo_centro(c - self.y0, 183 - t, t + f, 22.15) for c in (19, 151)]            # F
        return [(f_, "C02") for f_ in furos] + [(p, "C01")]

    # P04 parede longa ondulada --------------------------------------------
    def p04(self):
        t = self.t
        d = t - 6  # o desenho do PDF tem o ombro em Y = 6
        p = QPainterPath()
        p.moveTo(0, t)
        p.lineTo(0, 66 + d)
        p.cubicTo(32, 66 + d, 43, 83 + d, 71, 83 + d)
        p.cubicTo(101, 83 + d, 120, 68 + d, 151, 68 + d)
        p.cubicTo(182, 68 + d, 201, 83 + d, 231, 83 + d)
        p.cubicTo(259, 83 + d, 270, 66 + d, 302, 66 + d)
        p.lineTo(302, t)
        _abas_embaixo(p, [(c + 14 - PAREDE, c - 14 - PAREDE) for c in (274, 155, 36)], t)  # machos B (28)
        return [(p, "C01")]

    # P05 parede curta ------------------------------------------------------
    def p05(self):
        t, L = self.t, self.interno
        p = QPainterPath()
        p.moveTo(0, t)
        p.lineTo(0, 60 + t)
        p.lineTo(L, 60 + t)
        p.lineTo(L, t)
        _abas_embaixo(p, [(c + 13 - self.y0, c - 13 - self.y0) for c in (122.5, 47.5)], t)  # machos C (26)
        return [(p, "C01")]

    # P06 bandeja -----------------------------------------------------------
    def p06(self):
        t, f, L, W = self.t, self.f, self.corpo, self.interno
        pts = [(0, 0), (L, 0)]
        for c in (56, 114):  # machos D (28 × 2t) que atravessam a divisória
            y = c - self.y0
            pts += [(L, y - 14), (L + 2 * t, y - 14), (L + 2 * t, y + 14), (L, y + 14)]
        pts += [(L, W), (0, W)]
        furos = [circulo(79.5 - self.y0, 85 - self.y0, 41)]  # cuia Ø82
        furos += [rasgo_centro(c - self.y0, y - self.y0, 22.15, t + f) for y in (19, 151) for c in (41, 111)]  # E
        return [(f_, "C02") for f_ in furos] + [(poligono(pts), "C01")]

    # P07 costela -----------------------------------------------------------
    def p07(self):
        t, L = self.t, self.corpo
        d, s = t - 6, L / 139  # ombro do PDF em Y = 6; curva esticada ao comprimento do corpo
        p = QPainterPath()
        p.moveTo(0, t)
        p.lineTo(0, 22 + d)
        p.cubicTo(25 * s, 22 + d, 67 * s, 30 + d, 90 * s, 45 + d)
        p.cubicTo(106 * s, 54 + d, 117 * s, 54 + d, L, 54 + d)
        yf = 23 + t  # macho F: centro a 183 mm da mesa (o ombro apoia a 160 − t + t)
        p.lineTo(L, yf + 11)
        p.lineTo(L + 2 * t, yf + 11)
        p.lineTo(L + 2 * t, yf - 11)
        p.lineTo(L, yf - 11)
        p.lineTo(L, t)
        _abas_embaixo(p, [(c + 11 - self.y0, c - 11 - self.y0) for c in (111, 41)], t)  # machos E (22)
        return [(p, "C01")]

    @staticmethod
    def p08():
        return [(circulo(67, 67, 60), "C02"), (circulo(67, 67, 67), "C01")]  # Ø120 interno, Ø134 externo

    # gabarito ---------------------------------------------------------------
    def larguras_teste(self):
        um = [round(self.t - 0.30 + 0.15 * i, 2) for i in range(5)]
        return um, [round(v + self.t, 2) for v in um]

    def gabarito(self):
        """Teste de encaixes (pág. 4): rasgos de 20,15 mm de comprimento, da esquerda para a direita."""
        um, dois = self.larguras_teste()
        alto = 18 + max(dois) + 12
        furos = []
        for i, (u, d2) in enumerate(zip(um, dois)):
            x = 6 + i * 24.5
            furos.append(retangulo(x, 8, 20.15, u))     # fileira de baixo: uma tira
            furos.append(retangulo(x, 18 + max(um), 20.15, d2))  # fileira de cima: duas tiras coladas
        return [(f_, "C02") for f_ in furos] + [(retangulo(0, 0, 130, alto), "C01")]

    @staticmethod
    def tira():
        return [(retangulo(0, 0, 20, 50), "C01")]

    @staticmethod
    def quadrado20():
        return [(retangulo(0, 0, 20, 20), "C01")]

    # folhas -----------------------------------------------------------------
    def folhas(self):
        M, W = MARGEM, self.interno
        um, dois = self.larguras_teste()
        txt = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
        return [
            (f"00 Gabarito de encaixes ({txt(self.t)} mm)", [
                (self.gabarito(), f"Gabarito de encaixes (rasgos {txt(um[0])} a {txt(dois[-1])})", M, M),
                (self.tira(), "Tira de teste 1", M + 140, M), (self.tira(), "Tira de teste 2", M + 165, M),
                (self.tira(), "Tira de teste 3", M + 190, M),
                (self.quadrado20(), "Quadrado 20 mm (perda do corte)", M + 220, M)]),
            ("01 Divisória e alça", [(self.p03(), "P03 Divisória e alça (lâmina 1)", M, M),
                                     (self.p03(), "P03 Divisória e alça (lâmina 2)", M + W + 10, M)]),
            ("02 Bases", [(self.p01(), "P01 Base inferior lisa", M, M),
                          (self.p02(), "P02 Piso com rasgos", M, M + 180)]),
            ("03 Paredes e costelas", [(self.p04(), "P04 Parede longa ondulada (1)", M, M),
                                       (self.p04(), "P04 Parede longa ondulada (2)", M, M + 93),
                                       (self.p05(), "P05 Parede curta de ponta (1)", M, M + 186),
                                       (self.p05(), "P05 Parede curta de ponta (2)", M + W + 10, M + 186),
                                       (self.p07(), "P07 Costela curva da bandeja (1)", M, M + 262),
                                       (self.p07(), "P07 Costela curva da bandeja (2)", M + W + 10, M + 262)]),
            ("04 Bandeja e anel", [(self.p06(), "P06 Bandeja da cuia", M, M),
                                   (self.p08(), "P08 Anel da térmica", M + self.corpo + 2 * self.t + 15, M)]),
        ]

    def notas(self):
        t = self.t
        n = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
        um, dois = self.larguras_teste()
        return f"""PORTA-CUIA E TÉRMICA — chapa de {n(t)} mm (adaptado do R03 de 6 mm; protótipo para ajuste e teste)
Medidas externas montado: 310 × 170 × 340 mm. 12 peças em 4 folhas + gabarito.
Rasgos: uma chapa {n(t + self.f)} mm, duas chapas {n(2 * t + self.f)} mm (folga {n(self.f)}).

ANTES DE CORTAR
1. Meça a espessura real da chapa e corte a aba "00 Gabarito" (rasgos de {n(um[0])} a {n(um[-1])} para uma tira e
   de {n(dois[0])} a {n(dois[-1])} para duas coladas). Escolha o rasgo em que a tira entra firme à mão.
2. Meça o quadrado de 20 mm: perda do corte k ≈ 20 − média da largura e altura medidas.
3. Se precisar, use Organizar → Redimensionar slots ({n(t + self.f)} → medida escolhida; {n(2 * t + self.f)} para
   os rasgos A do piso) e/ou o Kerf da camada.
4. Velocidade/potência/passadas das camadas são PONTO DE PARTIDA não validado: faça a matriz de testes antes.
Camada C02 (vermelha) = furos e rasgos, cortada primeiro. C01 (azul) = contornos, por último. Corte uma aba
(folha) por vez.

MONTAGEM
01 Ensaie os encaixes a seco antes de colar.
02 Base: cole P01 sob P02, com os rasgos de P02 para cima. Alinhe as bordas.
03 Alça: cole as duas P03 face a face (espessura {n(2 * t)} mm). Alinhe pega, 4 rasgos e linguetas.
04 Encaixe P03 no piso. Cole as duas P04 e as duas P05, incluindo as juntas dos cantos.
05 Cole as duas P07 na P06. Depois encaixe as quatro linguetas do conjunto em P03.
06 Anel P08 no lado da térmica: centro a 230,50 mm da esquerda e 85,00 mm da frente da base.
Cuia: furo Ø82, centro a 79,50 mm da esquerda e 85,00 mm da frente. Topo da bandeja a 160 mm da mesa.
Deixe a cola curar. Teste a alça com carga equivalente fria antes de usar com a térmica cheia."""

    def camadas(self):
        base = dict(modo="linha", velocidade_mm_min=300.0, potencia_max=100.0, potencia_min=0.0,
                    passadas=1 if self.t <= 4 else 2, air=True)
        return [cm.alterar(cm.Camada("C02", "Internos: furos e rasgos (corte, 1º)"), **base),
                cm.alterar(cm.Camada("C01", "Contornos (corte, por último)"), **base)]

    def gerar(self, destino):
        paginas = [tuple(peca(*p) for p in pecas) for _, pecas in self.folhas()]
        nomes = [nm for nm, _ in self.folhas()]
        pj.save(destino, paginas[0], self.camadas(), notas=self.notas(),
                paginas=[None] + [(p, (), ()) for p in paginas[1:]], pagina_atual=0, nomes_paginas=nomes)
        return destino


# ---------- montagem das folhas ----------
def peca(partes, nome, x, y):
    """Peça com o canto superior esquerdo da caixa em (x, y) da mesa (mm, Y para baixo), agrupada."""
    caixa = QRectF()
    for path, _ in partes:
        caixa = caixa.united(path.boundingRect())
    tf = QTransform(1, 0, 0, -1, x - caixa.left(), y + caixa.bottom())  # vira Y e posiciona
    itens = [ob.Shape(tf.map(path), f"{nome} — {'furo/rasgo' if lid == 'C02' else 'contorno'}", lid, cm.cor(lid))
             for path, lid in partes]
    g = ob.group(itens)
    g.name = nome
    return g.snapshot()


# compatibilidade: o projeto original (6 mm) em funções soltas
_P6 = Projeto(6.0)
p01, p02, p03, p04, p05, p06, p07, p08 = _P6.p01, _P6.p02, _P6.p03, _P6.p04, _P6.p05, _P6.p06, _P6.p07, _P6.p08
FOLHAS = _P6.folhas()
NOTAS = _P6.notas()


def gerar(destino, t=6.0):
    return Projeto(t).gerar(destino)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    t = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else f"porta_cuia_e_termica_{t:g}mm.rbl", t))
