"""Manual de montagem do porta-retratos Apollo e Emily (PDF, A4), com os desenhos tirados das próprias peças do PDF.

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
# espaçadores na vista de trás: (nome, x, y, largura, altura)
ESPACADORES = [("lateral", 8, 5, 14, 235), ("divisor", 174, 5, 12, 235), ("lateral", 338, 5, 14, 235),
               ("batente", 20, 240, 320, 14)]
PES = (55.0, 305.0)                 # centro dos pés, da borda esquerda
FOTO = "#dfe8f3"


def junta(paths):
    out = QPainterPath()
    for p in paths:
        out.addPath(p)
    return out


def pecas(pdf):
    it = ae.ler(pdf)
    sel = lambda n, lid, f=lambda r: True: [p for m, p, l in it if m == n and l == lid and f(p.boundingRect())]  # noqa
    faixas, coracoes = {}, {}
    for nome, topo in FAIXA_Y.items():
        dentro = lambda r, t=topo: t - 1 < r.top() < t + 30  # noqa: E731
        faixas[nome] = sel(2, "C01", dentro)[0]
        coracoes[nome] = junta(sel(2, "C05", dentro))
    gab = {}
    volta = ae.QTransform(0, -1, 1, 0, 0, ae.CHAPA_W).inverted()[0]
    for p, lid, nome in ae.gabaritos(it):
        g = gab.setdefault(nome.split()[1].rstrip(":"), [QPainterPath(), QPainterPath()])
        g[lid == "C03"].addPath(volta.map(p))
    return {
        "frente": sel(1, "C01")[0], "janelas": junta(sel(1, "C04")),
        "fundo": sel(2, "C01", lambda r: r.height() > 200)[0],
        "faixas": faixas, "coracoes": coracoes,
        "espacadores": sel(1, "C03", lambda r: r.width() > 200),
        "pe": sel(1, "C03", lambda r: round(r.width()) == 80)[0],
        "teste": sel(1, "C02"),
        "letras": {n: junta(g) for n, g in ae.nomes_na_faixa(it).items()},
        "gabarito": gab,
    }


def em(s, x, y, ox=0.0, oy=0.0):
    """Transforma do sistema da peça (deslocada de ox, oy) para a página: escala s, canto em (x, y)."""
    return QTransform.fromTranslate(-ox, -oy) * QTransform.fromScale(s, s) * QTransform.fromTranslate(x, y)


def titulo_passos(pg, y, passos, num0=1):
    for i, (t, txt) in enumerate(passos, num0):
        pg.texto(M, y, 8, str(i), 13, True, VERM)
        pg.texto(M + 8, y, W - 2 * M - 8, t, 10.5, True)
        y += 5 + pg.texto(M + 8, y + 5, W - 2 * M - 8, txt, 9) + 2.5
    return y


# ---------- página 1: peças ----------
def pagina_pecas(pg, pc):
    y = M
    y += pg.texto(M, y, W - 2 * M, "Porta-retratos Apollo e Emily — montagem", 18, True)
    y += pg.texto(M, y + 1, W - 2 * M, "MDF 3 mm · 2 fotos 15 × 21 (150 × 210 mm) · altura final ≈ 281 mm. "
                  "Monte tudo A SECO primeiro, confira com as fotos e só depois cole. Medidas em mm.", 9,
                  cor="#444444") + 6
    y += pg.texto(M, y, W - 2 * M, "Peças", 13, True) + 3
    s = 0.24
    for k, (nome, p, extra) in enumerate((("Frente (chapa 1)", pc["frente"], pc["janelas"]),
                                          ("Fundo (chapa 2)", pc["fundo"], None))):
        x = M + k * (360 * s + 9)
        tf = em(s, x, y + 5, QX, QY)
        pg.texto(x, y, 360 * s, nome, 9, True)
        pg.forma(p, tf, fundo=MADEIRA)
        if extra is not None:
            pg.forma(extra, tf, fundo="#ffffff")
    nota(pg, M, y + 5 + 270 * s + 1, "360 × 270, 2 janelas 144 × 204", CINZA, 7, 360 * s)
    nota(pg, M + 360 * s + 9, y + 5 + 270 * s + 1, "360 × 270, rebaixos em cima para puxar as fotos", CINZA, 7,
         360 * s)
    y += 5 + 270 * s + 8
    for nome in ("Apollo", "Emily"):
        tf = em(s, M, y, QX, FAIXA_Y[nome])
        pg.forma(pc["faixas"][nome], tf, fundo=MADEIRA)
        pg.forma(pc["coracoes"][nome], tf, cor=CINZA, larg=0.2)
        nota(pg, M + 360 * s + 3, y + 1, f"Faixa {'de cima' if nome == 'Apollo' else 'de baixo (com 2 alívios)'} "
             f"— leva {nome}", TINTA, 7.5, 80)
        y += 30 * s + 3
    y += 3
    x = M
    for p in pc["espacadores"]:
        r = p.boundingRect()
        pg.forma(p, em(0.16, x, y, r.left(), r.top()), fundo=MADEIRA)
        x += r.width() * 0.16 + 4
    nota(pg, M, y + 5, "Espaçadores: 2 laterais 235 × 14 · 1 divisor 235 × 12 · 1 batente 320 × 14", TINTA, 7.5,
         W - 2 * M)
    y += 13
    r = pc["pe"].boundingRect()
    for k in range(3):
        pg.forma(pc["pe"], em(0.45, M + k * 40, y, r.left(), r.top()), fundo=MADEIRA)
    nota(pg, M + 122, y, "6 lâminas de pé 80 × 22 (encaixe 9,3 × 11): colam 3 a 3 = 2 pés de 9 mm", TINTA, 7.5, 60)
    y += 22 * 0.45 + 6
    for k, nome in enumerate(("Apollo", "Emily")):
        p = pc["letras"][nome]
        r = p.boundingRect()
        pg.forma(p, em(0.6, M + k * 70, y, r.left(), r.top()), fundo=MADEIRA)
        gp, gl = pc["gabarito"][nome]
        gr = gp.boundingRect()
        tf = em(0.6, M + k * 70, y + 16, gr.left(), gr.top())
        pg.forma(gp, tf, fundo="#e8d3a8")
        pg.forma(gl, tf, fundo="#ffffff")
    nota(pg, M + 140, y, "Letras (chapa 1) e o gabarito vazado de cada nome (chapa 3, retalho)", TINTA, 7.5, 42)
    y += 40
    y += pg.texto(M, y, W - 2 * M, "Antes de cortar a chapa toda: teste do encaixe dos pés", 11, True, VERM) + 1
    y += pg.texto(M, y, W - 2 * M,
                  "Os 5 corpos de prova (roxo, dentro das janelas) têm encaixe 8,9 / 9,1 / 9,3 / 9,5 / 9,7 mm. "
                  "Empilhe 3 retalhos do mesmo MDF (o quadro tem 3 camadas) e veja qual entra justo, sem forçar e "
                  "sem folga. Se não for o 9,3, ajuste o encaixe dos 6 pés antes de cortar. As letras A, p, o, l, "
                  "E, m, i, y: os miolos (dentro do o, p, A) são descarte.", 9) + 4


# ---------- página 2: corpo do quadro ----------
def vista_tras(pg, pc, x0, y0, s, com_espacadores=True, com_fotos=False):
    tf = em(s, x0, y0, QX, QY)
    pg.forma(pc["frente"], tf, fundo=MADEIRA)
    pg.forma(pc["janelas"], tf, fundo="#ffffff", cor=CINZA, tracejado=True)
    q = em(s, x0, y0)
    if com_fotos:
        for x in (23, 187):
            pg.forma(ae_ret(x, 30, 150, 210), q, cor=AZUL, fundo=FOTO, tracejado=True)
    if com_espacadores:
        for nome, x, y, w, h in ESPACADORES:
            pg.forma(ae_ret(x, y, w, h), q, cor=VERDE, fundo="#b9dcb6", larg=0.4)


def ae_ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def pagina_corpo(pg, pc):
    y = M
    y += pg.texto(M, y, W - 2 * M, "1. Corpo do quadro (frente + espaçadores + fundo = 9 mm)", 13, True) + 2
    y += pg.texto(M, y, W - 2 * M, "Frente deitada com a face bonita PARA BAIXO: você está olhando por TRÁS. "
                  "Medidas a partir do canto de CIMA à ESQUERDA (o desenho é simétrico, servem dos dois lados).",
                  9, cor="#444444") + 7
    s = 0.5
    x0 = M + (W - 2 * M - 360 * s) / 2
    vista_tras(pg, pc, x0, y, s, com_fotos=True)
    px = lambda v: x0 + v * s  # noqa: E731
    py = lambda v: y + v * s  # noqa: E731
    for v in (8, 22, 174, 186, 338, 352):
        nota(pg, px(v) - 5, py(0) - 3.6, f"{v}", AZUL, 6, 10, Qt.AlignHCenter)
    nota(pg, px(-1) - 14, py(5) - 1.5, "y 5", AZUL, 6.5, 12, Qt.AlignRight)
    nota(pg, px(-1) - 14, py(240) - 1.5, "y 240", AZUL, 6.5, 12, Qt.AlignRight)
    nota(pg, px(-1) - 14, py(254) - 1.5, "y 254", AZUL, 6.5, 12, Qt.AlignRight)
    nota(pg, px(20), py(255) + 1, "batente 320 × 14: x 20 a 340", VERDE, 7, 60)
    nota(pg, px(23), py(120), "foto 1\n150 × 210", AZUL, 7.5, 150 * s, Qt.AlignHCenter)
    nota(pg, px(187), py(120), "foto 2\n150 × 210", AZUL, 7.5, 150 * s, Qt.AlignHCenter)
    nota(pg, px(0), py(-14), "↑ CIMA (as fotos entram por aqui)", VERM, 7.5, 360 * s, Qt.AlignHCenter)
    y += 270 * s + 12
    y = titulo_passos(pg, y, [
        ("Laterais e divisor", "Cole as 2 laterais (14 de largura) de x 8 a 22 e de x 338 a 352, e o divisor (12) de "
         "x 174 a 186 — todos de y 5 a y 240 (comprimento 235). Ficam 152 mm livres para cada foto."),
        ("Batente", "Cole o batente 320 × 14 de x 20 a 340, de y 240 a 254, encostado no pé das laterais e do "
         "divisor. É nele que a foto apoia."),
        ("Teste com as fotos", "Antes de a cola secar, deslize uma foto (ou papel 15 × 21) em cada canal pelo lado de "
         "CIMA: tem que descer até o batente sem prender (folga de 1 mm de cada lado). Ajuste o que precisar."),
        ("Fundo", "Depois da cola seca, cole o fundo por cima dos espaçadores, bordas alinhadas com a frente e os 2 "
         "rebaixos virados para CIMA. Cola SÓ nos espaçadores — nada de cola escorrendo para os canais. Peso por "
         "cima até secar. Corpo pronto: 9 mm."),
    ])
    pg.texto(M, y + 2, W - 2 * M, "Verde = espaçadores · azul tracejado = onde ficam as fotos · cinza tracejado = "
             "janelas da frente.", 8, cor=CINZA)


# ---------- página 3: faixas, nomes e pés ----------
def faixa_com_gabarito(pg, pc, nome, x, y, s):
    tf = em(s, x, y, QX, FAIXA_Y[nome])
    pg.forma(pc["faixas"][nome], tf, fundo=MADEIRA)
    pg.forma(pc["coracoes"][nome], tf, cor=CINZA, larg=0.2)
    p = pc["letras"][nome]  # já no centro da faixa certa (sistema do PDF)
    pg.forma(p, tf, cor=CINZA, larg=0.2, tracejado=True)
    gp, gl = pc["gabarito"][nome]
    c = p.boundingRect().center() - gp.boundingRect().center()
    g = QTransform.fromTranslate(c.x(), c.y())
    pg.forma(g.map(gp), tf, cor=VERM, larg=0.4)
    pg.forma(g.map(gl), tf, cor=VERM, larg=0.25)
    meio = FAIXA_Y[nome] + 15
    linha = QPainterPath(QPointF(QX, meio))
    linha.lineTo(QX + 360, meio)
    linha.moveTo(QX + 180, FAIXA_Y[nome])
    linha.lineTo(QX + 180, FAIXA_Y[nome] + 30)
    pg.forma(linha, tf, cor=AZUL, larg=0.2, tracejado=True)


def corte_lateral(pg, pc, x0, y0, s):
    """Vista de lado: pé (ponta curta para a frente), corpo de 9 mm no encaixe, faixa e letra na frente."""
    r = pc["pe"].boundingRect()
    q = em(s, x0, y0, r.left(), r.top())         # sistema do pé: x 0–80, y 0 (topo) a 22 (mesa)
    pg.forma(pc["pe"], q, fundo=MADEIRA)
    alto = -30
    for k, cor in enumerate(("#c9a46a", "#b9dcb6", "#c9a46a")):  # frente, espaçador, fundo
        pg.forma(ae_ret(r.left() + 25 + 3 * k, r.top() + alto, 3, 11 - alto), q, fundo=cor)
    pg.forma(ae_ret(r.left() + 22, r.top() + alto, 3, 30 - 0.5), q, fundo="#e8d3a8", cor=TINTA)  # faixa
    pg.forma(ae_ret(r.left() + 19, r.top() + alto + 8, 3, 14), q, fundo="#ffffff", cor=VERM)    # letra
    mesa = QPainterPath(QPointF(r.left() - 8, r.top() + 22))
    mesa.lineTo(r.left() + 82, r.top() + 22)
    pg.forma(mesa, q, cor=CINZA, larg=0.5)
    P = lambda u, v: q.map(QPointF(r.left() + u, r.top() + v))  # noqa: E731
    nota(pg, P(25, alto).x() - 2, P(0, alto).y() - 9, "frente · espaçador · fundo\n(corpo 9 mm)", TINTA, 6.5, 40)
    nota(pg, P(-30, alto + 10).x(), P(0, alto + 10).y(), "letra", VERM, 7, 22, Qt.AlignRight)
    seta(pg, P(-2, alto + 12).x(), P(0, alto + 12).y(), P(19, alto + 13).x(), P(0, alto + 13).y(), VERM)
    nota(pg, P(-30, alto + 22).x(), P(0, alto + 22).y(), "faixa", TINTA, 7, 22, Qt.AlignRight)
    seta(pg, P(-2, alto + 24).x(), P(0, alto + 24).y(), P(22, alto + 24).x(), P(0, alto + 24).y(), TINTA)
    nota(pg, P(40, 5).x(), P(0, 5).y(), "encaixe\n9,3 × 11", AZUL, 6.5, 20)
    nota(pg, P(-8, 23).x(), P(0, 23).y() + 0.5, "← FRENTE (ponta curta)", VERM, 7, 50)
    nota(pg, P(60, 23).x(), P(0, 23).y() + 0.5, "TRÁS →", VERM, 7, 20)


def vista_frente(pg, pc, x0, y0, s):
    """Quadro pronto visto de frente (espelhado da vista de trás — simétrico)."""
    tf = em(s, x0, y0, QX, QY)
    for c in PES:
        pg.forma(ae_ret(c - 4.5, 270 - 11, 9, 22), em(s, x0, y0), fundo="#c9a46a")
    pg.forma(pc["frente"], tf, fundo=MADEIRA)
    pg.forma(pc["janelas"], tf, fundo=FOTO)
    for nome, yq in (("Apollo", 0.0), ("Emily", 240.0)):
        t = em(s, x0, y0 + yq * s, QX, FAIXA_Y[nome])
        pg.forma(pc["faixas"][nome], t, fundo="#e8d3a8")
        pg.forma(pc["coracoes"][nome], t, cor=CINZA, larg=0.2)
        pg.forma(pc["letras"][nome], t, fundo="#ffffff", larg=0.25)
    for c in PES:
        pg.forma(ae_ret(c - 4.5, 270 - 11.5, 9, 11.5 + 11), em(s, x0, y0), fundo="#c9a46a")
        nota(pg, x0 + (c - 15) * s, y0 + 284 * s, f"pé, centro {c:g}", VERM, 6.5, 30 * s, Qt.AlignHCenter)


def pagina_acabamento(pg, pc):
    y = M
    y += pg.texto(M, y, W - 2 * M, "2. Nomes nas faixas (com o gabarito)", 13, True) + 2
    s = 0.48
    for nome in ("Apollo", "Emily"):
        faixa_com_gabarito(pg, pc, nome, M, y, s)
        y += 30 * s + 4
    y += pg.texto(M, y, W - 2 * M, "Vermelho = gabarito por cima da faixa · azul tracejado = meio da faixa (15 mm "
                  "da borda) e centro (180 mm) · cinza = marca gravada fraca onde vai cada letra.", 8,
                  cor=CINZA) + 3
    y = titulo_passos(pg, y, [
        ("Colar as letras (com a faixa ainda solta)", "Apollo na faixa de CIMA, Emily na de BAIXO (a com os 2 "
         "alívios), lado dos corações para fora. Trace a lápis o meio da faixa (15 mm) e o centro (180 mm). Ponha o "
         "gabarito com os 2 dentes sobre a linha do meio e os furos em cima da marca gravada; prenda com fita. "
         "Passe pouca cola na faixa dentro de cada furo, encaixe as letras, aperte e tire o gabarito com cuidado "
         "antes de a cola puxar. Limpe o excesso."),
        ("Faixas no quadro", "Cole na FRENTE (face bonita): a faixa Apollo rente à borda de cima, a faixa Emily rente "
         "à de baixo com os alívios abertos para baixo, nas pontas alinhadas com o quadro. Confira com um pé "
         "encaixado que os alívios (centros 55 e 305) ficam bem em cima dos pés antes de a cola secar."),
        ("Pés", "Cole as lâminas 3 a 3, encaixes alinhados (pé de 9 mm). Depois de secos, encaixe o quadro com a "
         "PONTA CURTA para a FRENTE, centros a 55 e 305 mm da borda esquerda. O corpo de 9 mm desce até o fundo do "
         "encaixe (11 mm). Se ficar duro, lixe um pouco o encaixe; se quiser fixo, uma gota de cola."),
        ("Fotos", "Entram por cima, entre a frente e o fundo, e descem até o batente. Para tirar, puxe pelos "
         "rebaixos do fundo."),
    ], 5)
    y += 14
    corte_lateral(pg, pc, M + 26, y + 28, 0.85)
    xf = W - M - 360 * 0.24
    vista_frente(pg, pc, xf, y, 0.24)
    nota(pg, xf, y + 290 * 0.24, "pronto, visto de frente", TINTA, 7.5, 360 * 0.24, Qt.AlignHCenter)


def gerar(pdf_entrada, saida):
    pc = pecas(pdf_entrada)
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Porta-retratos Apollo e Emily — manual de montagem")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    pagina_pecas(pg, pc)
    pg.nova()
    pagina_corpo(pg, pc)
    pg.nova()
    pagina_acabamento(pg, pc)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
