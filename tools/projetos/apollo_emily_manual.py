"""Manual de montagem do porta-retratos Apollo e Emily (PDF, A4), passo a passo, com os desenhos tirados das
próprias peças do PDF de corte.

Executar:  python tools/projetos/apollo_emily_manual.py <Apollo_Emily_MDF3mm_2_Chapas.pdf> <saida.pdf>
Medidas da montagem (vista de TRÁS, origem no canto de cima à esquerda do quadro 360 × 270) tiradas do PDF original:
janelas em x 26–170 e 190–334 (y 33–237); canais das fotos de 152 centrados nelas.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QTransform  # noqa: E402

import apollo_emily as ae  # noqa: E402
from carroca_manual import AZUL, CINZA, M, MADEIRA, TINTA, VERDE, VERM, W, Pagina, nota, seta  # noqa: E402

QX, QY = 5.0, 10.0                  # canto do quadro no PDF (chapa 1 e 2)
FAIXA_Y = {"Apollo": 288.0, "Emily": 333.0}  # topo de cada faixa no PDF (chapa 2)
# espaçadores na vista de trás: (código, x, y, largura, altura)
ESPACADORES = [("C", 8, 5, 14, 235), ("D", 174, 5, 12, 235), ("C", 338, 5, 14, 235), ("E", 20, 240, 320, 14)]
PES = (55.0, 305.0)                 # centro dos pés, da borda esquerda
TESTES = (8.9, 9.1, 9.3, 9.5, 9.7)  # encaixe dos 5 corpos de prova (mesmo formato do pé)
FOTO, ESCURO, CLARO, VERDE_CL = "#dfe8f3", "#c9a46a", "#e8d3a8", "#b9dcb6"
LARG = W - 2 * M


def junta(paths):
    out = QPainterPath()
    for p in paths:
        out.addPath(p)
    return out


def ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def pecas(pdf):
    it = ae.ler(pdf)
    sel = lambda n, lid, f=lambda r: True: [p for m, p, l in it if m == n and l == lid and f(p.boundingRect())]  # noqa
    faixas, coracoes = {}, {}
    for nome, topo in FAIXA_Y.items():
        dentro = lambda r, t=topo: t - 1 < r.top() < t + 30  # noqa: E731
        faixas[nome] = sel(2, "C01", dentro)[0]
        coracoes[nome] = junta(sel(2, "C05", dentro))
    gab = {}
    volta = QTransform(0, -1, 1, 0, 0, ae.CHAPA_W).inverted()[0]
    for p, lid, nome in ae.gabaritos(it):
        g = gab.setdefault(nome.split()[1].rstrip(":"), [QPainterPath(), QPainterPath()])
        g[lid == "C03"].addPath(volta.map(p))
    pes = sel(1, "C03", lambda r: round(r.width()) == 80) + sel(1, "C02")
    assert len(pes) == 11, len(pes)  # 6 pés + 5 corpos de prova
    return {
        "frente": sel(1, "C01")[0], "janelas": junta(sel(1, "C04")),
        "fundo": sel(2, "C01", lambda r: r.height() > 200)[0],
        "faixas": faixas, "coracoes": coracoes,
        "espacadores": sel(1, "C03", lambda r: r.width() > 200),
        "pe": pes[0],
        "letras": {n: junta(g) for n, g in ae.nomes_na_faixa(it).items()},
        "gabarito": gab,
    }


def em(s, x, y, ox=0.0, oy=0.0):
    """Do sistema da peça (deslocada de ox, oy) para a página: escala s, canto em (x, y)."""
    return QTransform.fromTranslate(-ox, -oy) * QTransform.fromScale(s, s) * QTransform.fromTranslate(x, y)


# ---------- blocos de texto ----------
def cabecalho(pg, titulo, sub=None):
    y = M
    y += pg.texto(M, y, LARG, titulo, 15, True) + 1
    if sub:
        y += pg.texto(M, y, LARG, sub, 9, cor="#444444") + 1
    linha = QPainterPath(QPointF(M, y + 1))
    linha.lineTo(W - M, y + 1)
    pg.forma(linha, QTransform(), cor=VERM, larg=0.5)
    return y + 5


def passo(pg, y, n, titulo, itens, x=M, w=LARG):
    """Passo numerado com subitens (lista de frases curtas). Devolve o y seguinte."""
    pg.texto(x, y - 1, 12, f"{n}", 16, True, VERM)
    y += pg.texto(x + 11, y, w - 11, titulo, 11, True) + 1
    for t in itens:
        cor = VERM if t.startswith("ATENÇÃO") else TINTA
        pg.texto(x + 11, y, 4, "•", 9, True, cor)
        y += pg.texto(x + 15, y, w - 15, t, 9, cor=cor) + 0.8
    return y + 3


def caixa(pg, y, titulo, txt, cor=VERM):
    h = pg.texto(M + 3, y + 8, LARG - 6, txt, 9) + 11
    pg.forma(ret(M, y, LARG, h), QTransform(), cor=cor, larg=0.5)
    pg.texto(M + 3, y + 2, LARG - 6, titulo, 10, True, cor)
    pg.texto(M + 3, y + 8, LARG - 6, txt, 9)
    return y + h + 4


# ---------- desenhos ----------
def vista_tras(pg, pc, x0, y0, s, espacadores=True, fotos=False, cotas=False):
    pg.forma(pc["frente"], em(s, x0, y0, QX, QY), fundo=MADEIRA)
    pg.forma(pc["janelas"], em(s, x0, y0, QX, QY), fundo="#ffffff", cor=CINZA, tracejado=True)
    q = em(s, x0, y0)
    if fotos:
        for x in (23, 187):
            pg.forma(ret(x, 30, 150, 210), q, cor=AZUL, fundo=FOTO, tracejado=True)
    if espacadores:
        for cod, x, y, w, h in ESPACADORES:
            pg.forma(ret(x, y, w, h), q, cor=VERDE, fundo=VERDE_CL, larg=0.4)
            pg.texto(x0 + x * s, y0 + (y + h / 2) * s - 2, w * s, cod, 8, True, VERDE, Qt.AlignHCenter)
    if cotas:
        px = lambda v: x0 + v * s  # noqa: E731
        py = lambda v: y0 + v * s  # noqa: E731
        for v in (8, 22, 174, 186, 338, 352):
            nota(pg, px(v) - 5, py(0) - 4, f"{v}", AZUL, 6.5, 10, Qt.AlignHCenter)
        for v in (5, 240, 254):
            nota(pg, px(0) - 15, py(v) - 1.5, f"{v}", AZUL, 6.5, 13, Qt.AlignRight)
        nota(pg, px(0), py(0) - 11, "↑ CIMA (as fotos entram por aqui)", VERM, 7.5, 360 * s, Qt.AlignHCenter)


def vista_frente(pg, pc, x0, y0, s, letras=True, pes=True):
    q = em(s, x0, y0)
    pg.forma(pc["frente"], em(s, x0, y0, QX, QY), fundo=MADEIRA)
    pg.forma(pc["janelas"], em(s, x0, y0, QX, QY), fundo=FOTO)
    for nome, yq in (("Apollo", 0.0), ("Emily", 240.0)):
        t = em(s, x0, y0 + yq * s, QX, FAIXA_Y[nome])
        pg.forma(pc["faixas"][nome], t, fundo=CLARO)
        pg.forma(pc["coracoes"][nome], t, cor=CINZA, larg=0.2)
        if letras:
            pg.forma(pc["letras"][nome], t, fundo="#ffffff", larg=0.25)
    if pes:
        for c in PES:
            pg.forma(ret(c - 4.5, 270 - 11.5, 9, 22.5), q, fundo=ESCURO)
        mesa = QPainterPath(QPointF(-10, 281))
        mesa.lineTo(370, 281)
        pg.forma(mesa, q, cor=CINZA, larg=0.5)


def corte_lateral(pg, pc, x0, y0, s):
    """Vista de lado: pé (ponta curta para a frente), corpo de 9 mm no encaixe, faixa e letra na frente."""
    r = pc["pe"].boundingRect()
    q = em(s, x0, y0, r.left(), r.top())         # sistema do pé: x 0–80, y 0 (topo) a 22 (mesa)
    pg.forma(pc["pe"], q, fundo=MADEIRA)
    alto = -30
    for k, cor in enumerate((ESCURO, VERDE_CL, ESCURO)):  # frente, espaçador, fundo
        pg.forma(ret(r.left() + 25 + 3 * k, r.top() + alto, 3, 11 - alto), q, fundo=cor)
    pg.forma(ret(r.left() + 22, r.top() + alto, 3, 29.5), q, fundo=CLARO)       # faixa
    pg.forma(ret(r.left() + 19, r.top() + alto + 8, 3, 14), q, fundo="#ffffff", cor=VERM)  # letra
    mesa = QPainterPath(QPointF(r.left() - 8, r.top() + 22))
    mesa.lineTo(r.left() + 84, r.top() + 22)
    pg.forma(mesa, q, cor=CINZA, larg=0.5)
    P = lambda u, v: q.map(QPointF(r.left() + u, r.top() + v))  # noqa: E731
    nota(pg, P(25, alto).x() - 2, P(0, alto).y() - 9, "frente · espaçador · fundo\n(corpo 9 mm)", TINTA, 6.5, 40)
    nota(pg, P(-30, alto + 10).x(), P(0, alto + 10).y(), "letra", VERM, 7, 22, Qt.AlignRight)
    seta(pg, P(-2, alto + 12).x(), P(0, alto + 12).y(), P(19, alto + 13).x(), P(0, alto + 13).y(), VERM)
    nota(pg, P(-30, alto + 22).x(), P(0, alto + 22).y(), "faixa", TINTA, 7, 22, Qt.AlignRight)
    seta(pg, P(-2, alto + 24).x(), P(0, alto + 24).y(), P(22, alto + 24).x(), P(0, alto + 24).y(), TINTA)
    nota(pg, P(40, 5).x(), P(0, 5).y(), "encaixe\n11 fundo", AZUL, 6.5, 20)
    nota(pg, P(-8, 23).x(), P(0, 23).y() + 0.5, "← FRENTE (ponta curta)", VERM, 7, 50)
    nota(pg, P(60, 23).x(), P(0, 23).y() + 0.5, "TRÁS →", VERM, 7, 20)


def explodido_corpo(pg, x0, y0, s):
    """Vista pela borda de baixo, camadas afastadas: frente embaixo, espaçadores, fundo em cima."""
    e = 3 * 1.6  # espessura desenhada exagerada para enxergar
    camadas = [("FUNDO — rebaixos para CIMA (lado das fotos)", [(0, 360)], ESCURO, 0),
               ("ESPAÇADORES C, D, C (e o batente E atrás deles)", [(8, 22), (174, 186), (338, 352)], VERDE_CL, 12),
               ("FRENTE — face bonita PARA BAIXO", [(0, 360)], ESCURO, 24)]
    for t, partes, cor, dy in camadas:
        for a, b in partes:
            pg.forma(ret(x0 + a * s, y0 + dy, (b - a) * s, e), QTransform(), fundo=cor)
        if len(partes) > 1:
            pg.forma(ret(x0 + 20 * s, y0 + dy + 0.6, 320 * s, e - 1.2), QTransform(), fundo=VERDE_CL,
                     cor=VERDE, tracejado=True)
            for a, b in partes:
                pg.forma(ret(x0 + a * s, y0 + dy, (b - a) * s, e), QTransform(), fundo=cor)
        nota(pg, x0 + 360 * s + 3, y0 + dy + 0.5, t, TINTA, 7, LARG - 360 * s - 3)
    for k in (0.15, 0.85):
        seta(pg, x0 + 360 * s * k, y0 + e + 1, x0 + 360 * s * k, y0 + 11, VERM)
        seta(pg, x0 + 360 * s * k, y0 + 12 + e + 1, x0 + 360 * s * k, y0 + 23, VERM)
    mesa = QPainterPath(QPointF(x0 - 3, y0 + 24 + e + 0.4))
    mesa.lineTo(x0 + 360 * s + 3, y0 + 24 + e + 0.4)
    pg.forma(mesa, QTransform(), cor=CINZA, larg=0.6)
    return y0 + 24 + e + 4


def faixa_etapa(pg, pc, nome, x, y, s, etapa):
    """Etapas da colagem das letras: 0 linhas, 1 gabarito preso, 2 cola nos furos, 3 letras coladas."""
    tf = em(s, x, y, QX, FAIXA_Y[nome])
    pg.forma(pc["faixas"][nome], tf, fundo=MADEIRA)
    pg.forma(pc["coracoes"][nome], tf, cor=CINZA, larg=0.2)
    letras = pc["letras"][nome]
    gp, gl = pc["gabarito"][nome]
    c = letras.boundingRect().center() - gp.boundingRect().center()
    g = QTransform.fromTranslate(c.x(), c.y())
    if etapa < 3:
        pg.forma(letras, tf, cor=CINZA, larg=0.2, tracejado=True)  # marca gravada fraca
    meio = FAIXA_Y[nome] + 15
    linha = QPainterPath(QPointF(QX + 5, meio))
    linha.lineTo(QX + 355, meio)
    linha.moveTo(QX + 180, FAIXA_Y[nome] + 2)
    linha.lineTo(QX + 180, FAIXA_Y[nome] + 28)
    if etapa < 3:
        pg.forma(linha, tf, cor=AZUL, larg=0.25, tracejado=True)
    if etapa in (1, 2):
        pg.forma(g.map(gp), tf, fundo=CLARO, cor=VERM, larg=0.4)
        pg.forma(g.map(gl), tf, fundo="#7fb2e8" if etapa == 2 else MADEIRA, cor=VERM, larg=0.25)
        b = g.map(gp).boundingRect()
        for xx in (b.left() - 4, b.right() - 8):  # fita crepe nos cantos (deixa os dentes à vista)
            for yy in (b.top() - 3, b.bottom() - 4):
                pg.forma(ret(xx, yy, 12, 7), tf, fundo="#f6efb4", cor="#b8a94a", larg=0.2)
    if etapa == 3:
        pg.forma(letras, tf, fundo=ESCURO, larg=0.25)


def pe_teste(pg, pc, x0, y0, s, corpo, entra, rotulo, cor):
    """Plaquinha de pé com o corpo do quadro (largura desenhada `corpo`, exagerada) no encaixe de 9,3."""
    r = pc["pe"].boundingRect()
    q = em(s, x0, y0, r.left(), r.top())
    pg.forma(pc["pe"], q, fundo=MADEIRA)
    fundo = 11 if entra else 0  # não entra: fica parado em cima do encaixe
    pg.forma(ret(r.left() + 29.65 - corpo / 2, r.top() + fundo - 23, corpo, 23), q, fundo=VERDE_CL, cor=VERDE)
    pg.texto(x0, y0 + 23 * s, 80 * s, rotulo, 8, True, cor, Qt.AlignHCenter)


def pe_explodido(pg, pc, x0, y0, s):
    r = pc["pe"].boundingRect()
    for k in range(3):
        pg.forma(pc["pe"], em(s, x0 + k * 4, y0 + k * 5, r.left(), r.top()), fundo=MADEIRA)
    nota(pg, x0, y0 + 22 * s + 11, "3 lâminas, uma em cima da outra,\nencaixes e bordas certinhos", TINTA, 7.5, 70)
    # vista de cima do pé pronto: 3 camadas de 3 mm
    xs, ys = x0 + 80 * s + 22, y0 + 4
    for k in range(3):
        pg.forma(ret(xs, ys + k * 3 * s, 80 * s, 3 * s), QTransform(), fundo=MADEIRA if k != 1 else CLARO)
    pg.forma(ret(xs + 25 * s, ys, 9.3 * s, 9 * s), QTransform(), fundo="#ffffff", cor=TINTA)
    nota(pg, xs, ys + 9 * s + 1.5, "pé pronto visto de cima: 9 mm de grossura,\no encaixe é o vão branco", TINTA,
         7.5, 70)
    seta(pg, x0 + 80 * s + 10, y0 + 8, xs - 2, y0 + 8, VERM)


# ---------- páginas ----------
def pagina_capa(pg, pc):
    y = M
    y += pg.texto(M, y, LARG, "Porta-retratos Apollo e Emily", 22, True)
    y += pg.texto(M, y, LARG, "Manual de montagem e colagem — passo a passo", 12, cor="#444444") + 4
    s = 0.42
    vista_frente(pg, pc, M + (LARG - 360 * s) / 2, y, s)
    y += 282 * s + 4
    y += pg.texto(M, y, LARG, "Pronto: 360 × 281 mm, 2 fotos 15 × 21 (150 × 210 mm). MDF 3 mm.", 9, True,
                  alinhar=Qt.AlignHCenter) + 6
    meio = M + LARG / 2 + 3
    y0 = y
    y += pg.texto(M, y, LARG / 2, "O que você precisa", 12, True) + 2
    for t in ("Cola branca de madeira (PVA)", "Palito de dente ou pincel fino (para espalhar a cola)",
              "Pano úmido (limpar cola que escorrer)", "Régua de metal e lápis", "Esquadro (ou uma folha A4 "
              "para conferir 90°)", "Fita crepe", "Lixa fina (150 ou 220)", "Peso (livros) ou grampos/prendedores",
              "Uma foto ou papel 15 × 21 para testar", "Paquímetro (ajuda, mas não é obrigatório)"):
        y += pg.texto(M + 3, y, LARG / 2 - 3, "☐  " + t, 9) + 0.8
    y2 = y0 + pg.texto(meio, y0, LARG / 2 - 3, "Regras de ouro", 12, True) + 2
    for t in ("Monte SEMPRE a seco primeiro (sem cola), confira, e só depois cole.",
              "Cola é POUCA: um fio fino. Cola demais escorre, mancha e trava as fotos.",
              "Limpe a cola que escorrer na hora, com pano úmido.",
              "Depois de colar: peso ou grampo por 30 minutos sem mexer. Uso normal só no dia seguinte (24 h).",
              "Face bonita = o lado sem manchas de fumaça. Escolha antes de começar e marque o lado de trás com "
              "lápis (um X pequeno).",
              "As letras e o gabarito NÃO podem ser virados: se virar, o nome fica espelhado (de trás para frente)."):
        y2 += pg.texto(meio, y2, LARG / 2 - 3, "→ " + t, 9) + 1.2
    y = max(y, y2) + 4
    pg.texto(M, y, LARG, "Ordem do manual: 1 conhecer as peças · 2 corpo do quadro · 3 fundo · 4 nomes nas faixas · "
             "5 faixas no quadro · 6 escolher as plaquinhas dos pés · 7 montar os pés · 8 colocar nos pés · "
             "9 fotos.", 9, cor="#444444")


def pagina_pecas(pg, pc):
    y = cabecalho(pg, "Passo 1 — Conheça e separe as peças",
                  "Separe as peças em cima da mesa, em grupos, como na lista. Confira se não falta nada.")
    s = 0.2
    linhas = [
        ("A", "Frente — 1 peça", "360 × 270, com 2 janelas. A peça maior com buracos.",
         lambda x, yy: (pg.forma(pc["frente"], em(s, x, yy, QX, QY), fundo=MADEIRA),
                        pg.forma(pc["janelas"], em(s, x, yy, QX, QY), fundo="#ffffff")), 270 * s),
        ("B", "Fundo — 1 peça", "360 × 270, inteira, com 2 meias-luas em cima (para puxar as fotos).",
         lambda x, yy: pg.forma(pc["fundo"], em(s, x, yy, QX, QY), fundo=MADEIRA), 270 * s),
    ]
    for cod, nome, desc, desenho, h in linhas:
        pg.texto(M, y, 8, cod, 14, True, VERM)
        desenho(M + 10, y)
        pg.texto(M + 10 + 360 * s + 5, y + 2, LARG - 360 * s - 15, nome, 10, True)
        pg.texto(M + 10 + 360 * s + 5, y + 7, LARG - 360 * s - 15, desc, 9)
        y += h + 4
    sp = sorted(pc["espacadores"], key=lambda p: (-p.boundingRect().width(), -p.boundingRect().height()))
    for cod, nome, desc, p in (("C", "Laterais — 2 peças", "235 × 14 (meça: 14 mm de largura).", sp[1]),
                               ("D", "Divisor — 1 peça", "235 × 12. Igual à lateral, mas MAIS FINA: 12 mm. Meça "
                                "com a régua para não trocar.", sp[3]),
                               ("E", "Batente — 1 peça", "320 × 14. A ripa MAIS COMPRIDA.", sp[0])):
        r = p.boundingRect()
        pg.texto(M, y - 1, 8, cod, 14, True, VERM)
        pg.forma(p, em(0.25, M + 10, y, r.left(), r.top()), fundo=VERDE_CL, cor=VERDE)
        pg.texto(M + 10 + 82, y - 1, LARG - 92, f"{nome}: {desc}", 9)
        y += 9
    y += 1
    for cod, nome, desc in (("F", "Apollo", "Faixa de CIMA — 360 × 30, reta embaixo, 2 corações gravados."),
                            ("G", "Emily", "Faixa de BAIXO — 360 × 30, com 2 recortes quadrados (alívios) na borda.")):
        pg.texto(M, y - 1, 8, cod, 14, True, VERM)
        t = em(0.25, M + 10, y, QX, FAIXA_Y[nome])
        pg.forma(pc["faixas"][nome], t, fundo=MADEIRA)
        pg.forma(pc["coracoes"][nome], t, cor=CINZA, larg=0.2)
        pg.texto(M + 10 + 95, y, LARG - 105, desc, 9)
        y += 11
    for k, nome in enumerate(("Apollo", "Emily")):
        p = pc["letras"][nome]
        r = p.boundingRect()
        pg.forma(p, em(0.5, M + 10 + k * 50, y, r.left(), r.top()), fundo=ESCURO)
    pg.texto(M, y - 1, 8, "L", 14, True, VERM)
    pg.texto(M + 112, y, LARG - 112, "Letras — A p o l l o  e  E m i l y (11 letras). Os miolos de dentro do "
             "A, p e o são lixo.", 9)
    y += 14
    for k, nome in enumerate(("Apollo", "Emily")):
        gp, gl = pc["gabarito"][nome]
        r = gp.boundingRect()
        pg.forma(gp, em(0.45, M + 10 + k * 52, y, r.left(), r.top()), fundo=CLARO)
        pg.forma(gl, em(0.45, M + 10 + k * 52, y, r.left(), r.top()), fundo="#ffffff")
    pg.texto(M, y - 1, 8, "J", 14, True, VERM)
    pg.texto(M + 112, y, LARG - 112, "Gabaritos (chapa 3) — placa com o nome vazado e um dente em cada ponta. "
             "Só servem para colar as letras; depois sobram.", 9)
    y += 19
    r = pc["pe"].boundingRect()
    for k in range(6):
        pg.forma(pc["pe"], em(0.25, M + 10 + k * 22, y, r.left(), r.top()), fundo=MADEIRA)
    pg.texto(M, y - 1, 8, "P", 14, True, VERM)
    pg.texto(M + 10 + 6 * 22 + 2, y - 1, LARG - 144, "Plaquinhas de pé — 11 peças iguais (80 × 22).", 9, True)
    y += 9
    y = caixa(pg, y, "Por que vieram 11 plaquinhas de pé?",
              "O projeto precisa de só 6 (3 para cada pé). As outras 5 são PEÇAS DE TESTE: o mesmo desenho, mas cada "
              "uma com o encaixe de uma largura — 8,9 / 9,1 / 9,3 / 9,5 / 9,7 mm (as 6 de verdade são 9,3). Servem "
              "para descobrir qual encaixe fica justo no SEU MDF, que nunca tem 3,00 mm exatos. Como agora elas já "
              "estão misturadas, NÃO precisa medir: no passo 6 você testa todas as 11 no próprio quadro e fica com "
              "as 6 que encaixam melhor. As que sobrarem vão para o lixo.")


def pagina_corpo(pg, pc):
    y = cabecalho(pg, "Passo 2 — Corpo do quadro: espaçadores C, D e E",
                  "Os espaçadores fazem 2 \"gavetas\" entre a frente e o fundo, onde as fotos deslizam.")
    s = 0.46
    x0 = M + (LARG - 360 * s) / 2
    vista_tras(pg, pc, x0, y + 12, s, fotos=True, cotas=True)
    nota(pg, x0 + 23 * s, y + 12 + 120 * s, "foto 1", AZUL, 8, 150 * s, Qt.AlignHCenter)
    nota(pg, x0 + 187 * s, y + 12 + 120 * s, "foto 2", AZUL, 8, 150 * s, Qt.AlignHCenter)
    y += 12 + 270 * s + 3
    pg.texto(M, y, LARG, "Visto por TRÁS. Números azuis em mm, medidos a partir do canto de CIMA à ESQUERDA. "
             "Verde = espaçadores · azul = fotos · cinza = janelas.", 8, cor=CINZA)
    y += 8
    y = passo(pg, y, "2.1", "Vire a frente (A) com a face bonita PARA BAIXO", [
        "Coloque em cima de uma mesa lisa e limpa (um pano por baixo para não riscar).",
        "Gire até as janelas ficarem em pé (mais altas que largas)."])
    y = passo(pg, y, "2.2", "Marque a lápis onde vai cada espaçador", [
        "Com a régua, a partir da borda ESQUERDA: risque linhas verticais em 8, 22, 174, 186, 338 e 352 mm.",
        "A partir da borda de CIMA: risque linhas horizontais em 5, 240 e 254 mm.",
        "Coloque as peças A SECO (sem cola) em cima das marcas e confira com o desenho."])
    y = passo(pg, y, "2.3", "Cole as laterais C e o divisor D", [
        "Fio fino de cola no meio da peça (não na beirada), deite na marca e aperte 10 segundos.",
        "Laterais C (14 mm) nas pontas: de 8 a 22 e de 338 a 352. Divisor D (12 mm) no meio: de 174 a 186.",
        "Todas em pé, começando 5 mm abaixo da borda de cima e terminando em 240."])
    y = passo(pg, y, "2.4", "Cole o batente E (a ripa comprida)", [
        "Deitado, de 240 a 254, encostado embaixo das 3 ripas, de 20 a 340 (sobra 20 mm de cada lado).",
        "É nele que a foto para quando desce."])
    passo(pg, y, "2.5", "Teste já com a foto (antes de a cola secar)", [
        "Coloque a foto (ou papel 15 × 21) em cada gaveta: tem que deitar entre as ripas e encostar no batente "
        "sem dobrar. Sobra 1 mm de cada lado.",
        "Se apertou, empurre a ripa um pouquinho agora, enquanto a cola está mole.",
        "ATENÇÃO: limpe com pano úmido toda cola que escorreu para dentro das gavetas. Deixe secar 30 min."])


def pagina_fundo(pg, pc):
    y = cabecalho(pg, "Passo 3 — Colar o fundo (B)", "Fecha as gavetas. Depois disso as fotos só entram por cima.")
    y = explodido_corpo(pg, M, y + 4, 0.3) + 4
    y = passo(pg, y, "3.1", "Teste a seco", [
        "Coloque o fundo B por cima dos espaçadores, sem cola. As bordas do fundo têm que coincidir com as da frente "
        "em volta toda.",
        "As 2 meias-luas do fundo ficam em CIMA (do mesmo lado em que as gavetas estão abertas)."])
    y = passo(pg, y, "3.2", "Cole", [
        "Tire o fundo. Passe um fio fino de cola em cima das ripas C, D e E (só nelas).",
        "ATENÇÃO: nada de cola perto da borda de dentro das gavetas — se escorrer, a foto gruda.",
        "Coloque o fundo, alinhe as bordas e ponha livros por cima, bem distribuídos. 30 min sem mexer.",
        "Corpo pronto: 3 camadas = 9 mm de grossura."])
    s = 0.36
    x0 = M + (LARG - 360 * s) / 2
    for x in (23, 187):
        pg.forma(ret(x, -18, 150, 210), em(s, x0, y + 8), cor=AZUL, fundo=FOTO, tracejado=True)
    pg.forma(pc["fundo"], em(s, x0, y + 8, QX, QY), fundo=MADEIRA)
    for x in (23, 187):
        pg.forma(ret(x, -18, 150, 210), em(s, x0, y + 8), cor=AZUL, tracejado=True)  # foto atrás do fundo
        seta(pg, x0 + (x + 75) * s, y + 3, x0 + (x + 75) * s, y + 8 + 40 * s, AZUL)
    nota(pg, x0, y + 8 + 270 * s + 1, "Visto por trás, com o fundo colado: a foto entra pela abertura de cima e "
         "desce até o batente. A meia-lua serve para pegar a foto com o dedo e puxar.", TINTA, 8, 360 * s,
         Qt.AlignHCenter)


def pagina_letras(pg, pc):
    y = cabecalho(pg, "Passo 4 — Colar os nomes nas faixas (com o gabarito J)",
                  "Faça com as faixas SOLTAS, deitadas na mesa. Apollo na faixa F (cima), Emily na faixa G (baixo).")
    s = 0.44
    etapas = [
        ("4.1", "Marque o meio", ["Faixa com os corações para CIMA. Risque a lápis uma linha no meio da altura "
                                  "(15 mm da borda) e uma no meio do comprimento (180 mm).",
                                  "A marca cinza gravada fraca mostra o lugar exato de cada letra."]),
        ("4.2", "Prenda o gabarito", ["Gabarito com o nome LEGÍVEL (não espelhado), com os 2 dentes em cima da "
                                      "linha do meio e os furos em cima da marca gravada.",
                                      "Prenda as duas pontas com fita crepe para não sair do lugar."]),
        ("4.3", "Cola dentro dos furos", ["Com o palito, passe uma camada FINA de cola na faixa, só dentro de cada "
                                          "furo (azul no desenho). Pouca: senão escorre por baixo do gabarito."]),
        ("4.4", "Letras no lugar", ["Coloque cada letra no furo dela, do lado certo (lendo normal), e aperte com o "
                                    "dedo. Tire o gabarito com cuidado, levantando reto, em até 5 minutos.",
                                    "Limpe a cola que saiu. Repita com Emily na faixa G. Peso leve, 30 min."]),
    ]
    for k, (n, t, itens) in enumerate(etapas):
        faixa_etapa(pg, pc, "Apollo" if k != 3 else "Apollo", M, y, s, k)
        y += 30 * s + 3
        y = passo(pg, y, n, t, itens) + 1
    caixa(pg, y, "Não deu certo?", "Letra torta: com a cola ainda mole, empurre de leve. Se a cola já secou, use "
          "uma lâmina para soltar e cole de novo. A marca gravada fica escondida debaixo da letra (é 0,4 mm menor).")


def pagina_faixas(pg, pc):
    y = cabecalho(pg, "Passo 5 — Colar as faixas no quadro",
                  "Agora o quadro fica com a face bonita (a frente) para CIMA.")
    s = 0.46
    x0 = M + (LARG - 360 * s) / 2
    vista_frente(pg, pc, x0, y + 4, s, pes=False)
    nota(pg, x0 - 15, y + 4 + 9 * s, "F →", VERM, 10, 13, Qt.AlignRight)
    nota(pg, x0 - 15, y + 4 + 249 * s, "G →", VERM, 10, 13, Qt.AlignRight)
    for c in PES:
        seta(pg, x0 + c * s, y + 4 + 290 * s, x0 + c * s, y + 4 + 271 * s, VERM)
        nota(pg, x0 + (c - 20) * s, y + 4 + 291 * s, f"alívio {c:g} mm", VERM, 7, 40 * s, Qt.AlignHCenter)
    y += 4 + 300 * s
    y = passo(pg, y, "5.1", "Faixa F (Apollo) em cima", [
        "Fio fino de cola atrás da faixa, longe das bordas.",
        "Encoste na borda de CIMA da frente, rente: a borda da faixa e a do quadro ficam niveladas, e as pontas "
        "arredondadas por cima das pontas do quadro."])
    y = passo(pg, y, "5.2", "Faixa G (Emily) embaixo", [
        "Rente à borda de BAIXO, com os 2 recortes quadrados abertos PARA BAIXO.",
        "ATENÇÃO: os recortes têm que ficar onde vão os pés, a 55 mm e 305 mm da borda esquerda. Se a faixa "
        "estiver virada, os recortes ficam fora do lugar e o quadro não entra nos pés.",
        "Peso por cima, 30 min. Não deixe a cola escorrer para dentro das janelas."])


def pagina_pes(pg, pc):
    y = cabecalho(pg, "Passo 6 — Escolher as 6 plaquinhas dos pés",
                  "Use a borda de BAIXO do quadro (já com o fundo colado, 9 mm) para testar as 11 plaquinhas.")
    s = 0.62
    for k, (corpo, entra, rot, cor) in enumerate(((9.3, True, "JUSTO ✔ use", VERDE),
                                                  (6.5, True, "FOLGADO (sobra vão) ✘ lixo", VERM),
                                                  (11.0, False, "NÃO ENTRA ✘ reserva", VERM))):
        pe_teste(pg, pc, M + 4 + k * 60, y + 18, s, corpo, entra, rot, cor)
    y += 18 + 22 * s + 10
    y = passo(pg, y, "6.1", "Teste uma por uma", [
        "Encaixe cada plaquinha na borda de baixo do quadro, entre os recortes da faixa G.",
        "JUSTO: entra com a mão, sem martelar, e fica parada sem cair. Separe estas.",
        "FOLGADO: balança ou cai sozinha. Não use.",
        "NÃO ENTRA: guarde de reserva — dá para lixar o encaixe por dentro se faltar plaquinha.",
        "Você precisa de 6 justas. Normalmente são as 6 de 9,3 + a de teste 9,3 (sobra 1)."])
    y = passo(pg, y, "6.2", "Se não deu 6 justas", [
        "Se TODAS ficaram duras: lixe por dentro o encaixe das que estão quase entrando (lixa enrolada num palito "
        "de picolé), até entrarem justas.",
        "Se TODAS ficaram folgadas: use as mais justas e, no passo 8, uma gota de cola no encaixe resolve."])
    y = cabecalho_inline(pg, y, "Passo 7 — Montar os 2 pés")
    pe_explodido(pg, pc, M + 4, y + 2, 0.6)
    y += 22 * 0.6 + 26
    passo(pg, y, "7.1", "Cole 3 plaquinhas juntas para cada pé", [
        "Cola fina na face de uma, a outra em cima, depois a terceira: todas viradas para o MESMO lado.",
        "ATENÇÃO: os encaixes têm que ficar exatamente alinhados. Para garantir, encaixe o pé no quadro enquanto "
        "a cola está mole (sem cola no encaixe!), alinhe, e tire. Aperte com prendedor, 30 min.",
        "Depois de seco, lixe de leve as bordas para tirar rebarba."])


def cabecalho_inline(pg, y, titulo):
    y += pg.texto(M, y, LARG, titulo, 15, True) + 1
    linha = QPainterPath(QPointF(M, y + 1))
    linha.lineTo(W - M, y + 1)
    pg.forma(linha, QTransform(), cor=VERM, larg=0.5)
    return y + 5


def pagina_final(pg, pc):
    y = cabecalho(pg, "Passo 8 — Colocar o quadro nos pés", "Visto de lado e de frente, já montado.")
    corte_lateral(pg, pc, M + 26, y + 36, 0.8)
    s = 0.24
    xf = W - M - 360 * s
    vista_frente(pg, pc, xf, y + 8, s)
    for c in PES:
        nota(pg, xf + (c - 25) * s, y + 8 + 283 * s, f"pé {c:g}", VERM, 7, 50 * s, Qt.AlignHCenter)
    y += 84
    y = passo(pg, y, "8.1", "Pés no quadro", [
        "Fique com o quadro em pé, de frente para você.",
        "Encaixe um pé em cada recorte da faixa G (55 mm e 305 mm da borda esquerda).",
        "ATENÇÃO: a PONTA CURTA do pé vai para a FRENTE (lado das letras). A ponta comprida vai para trás e é ela "
        "que segura o quadro em pé.",
        "Empurre até o quadro bater no fundo do encaixe (entra 11 mm). Confira se ficou reto (90°) com o "
        "esquadro ou com a quina de uma folha A4.",
        "Quer fixo? Uma gota de cola dentro do encaixe antes de encaixar. Quer desmontável? Sem cola."])
    y = passo(pg, y, "9", "Fotos", [
        "Espere 24 h para a cola curar. Deslize cada foto 15 × 21 pela abertura de CIMA, com a imagem virada para "
        "a FRENTE, até encostar no batente.",
        "Para trocar: puxe pela meia-lua do fundo."])
    caixa(pg, y, "Problemas e soluções",
          "Foto não entra: cola dentro da gaveta — raspe com uma régua fina.  ·  Quadro torto nos pés: lixe o "
          "fundo do encaixe do pé mais alto.  ·  Pé balança: gota de cola no encaixe.  ·  Faixa não fecha com o "
          "quadro: lixe a ponta da faixa que passou.  ·  Letra soltou: cola branca de novo, peso leve 30 min.")


def gerar(pdf_entrada, saida):
    pc = pecas(pdf_entrada)
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Porta-retratos Apollo e Emily — manual de montagem")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    for k, pagina in enumerate((pagina_capa, pagina_pecas, pagina_corpo, pagina_fundo, pagina_letras,
                                pagina_faixas, pagina_pes, pagina_final)):
        if k:
            pg.nova()
        pagina(pg, pc)
        pg.texto(M, 287, LARG, f"Apollo e Emily — montagem · página {k + 1} de 8", 7, cor=CINZA,
                 alinhar=Qt.AlignRight)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
