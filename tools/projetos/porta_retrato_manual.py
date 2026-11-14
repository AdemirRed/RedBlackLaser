"""Manual de montagem do porta-retrato Isabella e Nathan (PDF, A4): base laminada, encaixe dos quadros e apoios.

Executar:  python tools/projetos/porta_retrato_manual.py <saida.pdf>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QTransform  # noqa: E402

import porta_retrato_isabella_nathan as pr  # noqa: E402
from carroca_manual import AZUL, CINZA, TINTA, M, MADEIRA, VERDE, VERM, W, Pagina, nota, seta  # noqa: E402

PROF, LARG = 62.0, pr.BASE   # base 426 × 62
Y_RASGO = 13.0                # rasgos a 13 mm da borda da FRENTE
CAMADAS = [("CIMA — com rasgos (3 peças, saíram de dentro das janelas)", pr.CORTES_BASE, True),
           ("MEIO — com rasgos (2 peças)", (0.0, 205.0, LARG), True),
           ("BAIXO — lisa, é o fundo do encaixe (2 peças)", (0.0, 142.0, LARG), False)]
APOIOS = (62.0, 244.0)        # centro dos apoios, a partir da ponta esquerda da base
CAT = 36.0                    # catetos dos triângulos


def ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def rasgos_em(x0, x1):
    return [r for r in pr.RASGOS_BASE if x0 <= r and r + 26 <= x1]


def camada(pg, y, s, titulo, cortes, com_rasgos):
    """Uma camada da base em escala s, partes afastadas 2 mm (desenho), com as cotas de cada uma."""
    y += pg.texto(M, y, W - 2 * M, titulo, 9.5, True) + 1
    for a, b in zip(cortes, cortes[1:]):
        x = M + a * s + (cortes.index(a)) * 2
        tf = QTransform.fromScale(s, s) * QTransform.fromTranslate(x, y)
        pg.forma(ret(0, 0, b - a, PROF), tf, fundo=MADEIRA)
        if com_rasgos:
            for r in rasgos_em(a, b):
                pg.forma(ret(r - a, Y_RASGO, 26, pr.RASGO), tf, fundo="#ffffff")
                nota(pg, x + (r - a) * s - 4, y + (Y_RASGO + pr.RASGO) * s + 0.6,
                     f"{r - a:g}", AZUL, 6.5, (26 * s) + 8, Qt.AlignHCenter)
        pg.texto(x, y + PROF * s * 0.55, (b - a) * s, f"{b - a:g} mm", 10, True, alinhar=Qt.AlignHCenter)
    nota(pg, M, y - 4.6, "↑ FRENTE (lado do quadro: rasgos a 13 mm desta borda)", VERM, 6.5, W - 2 * M,
         Qt.AlignRight)
    return y + PROF * s + 5


def pagina_base(pg):
    s = (W - 2 * M - 4) / LARG
    y = M
    y += pg.texto(M, y, W - 2 * M, "Porta-retrato Isabella e Nathan — montagem", 18, True)
    y += pg.texto(M, y + 1, W - 2 * M, "MDF 3 mm. Monte tudo A SECO primeiro, confira com os quadros encaixados e só "
                  "depois cole. Medidas em mm, sempre a partir da ponta ESQUERDA olhando de frente.", 9,
                  cor="#444444") + 5
    y += pg.texto(M, y, W - 2 * M, "1. A base (426 × 62 × 9) = 3 camadas de 3 mm", 13, True) + 5
    for t, cortes, com in CAMADAS:
        y = camada(pg, y, s, t, cortes, com) + 3
    y += pg.texto(M, y, W - 2 * M,
                  "Números azuis: distância da ponta esquerda de cada peça até o rasgo. Os rasgos ficam a 13 mm da "
                  "borda da frente e a 40 mm da de trás. Se a peça estiver virada (rasgo perto da borda de trás ou "
                  "do lado errado), os rasgos de cima e do meio NÃO se alinham e a lingueta não entra.", 8.5,
                  cor=VERM) + 4
    y += pg.texto(M, y, W - 2 * M, "Base montada, vista de cima (emendas desencontradas)", 11, True) + 5
    tf = QTransform.fromScale(s, s) * QTransform.fromTranslate(M, y)
    pg.forma(ret(0, 0, LARG, PROF), tf, fundo=MADEIRA)
    for x in pr.CORTES_BASE[1:-1]:
        pg.forma(ret(x, 0, 0, PROF), tf, cor=VERDE, larg=0.5)
    pg.forma(ret(205, 0, 0, PROF), tf, cor=AZUL, larg=0.5, tracejado=True)
    pg.forma(ret(142, 0, 0, PROF), tf, cor=CINZA, larg=0.5, tracejado=True)
    for r in pr.RASGOS_BASE:
        pg.forma(ret(r, Y_RASGO, 26, pr.RASGO), tf, fundo="#ffffff")
        nota(pg, M + r * s - 3, y - 3.4, f"{r:g}", AZUL, 6.5, 26 * s + 6, Qt.AlignHCenter)
    pg.forma(ret(6, Y_RASGO, 414, pr.RASGO), tf, cor=VERM, larg=0.3, tracejado=True)  # quadros (414) centrados
    for c in APOIOS:
        pg.forma(ret(c - 3, Y_RASGO + pr.RASGO, 6, CAT), tf, cor=VERM, fundo="#f2b8b5")
        nota(pg, M + (c - 15) * s, y + (Y_RASGO + pr.RASGO + CAT) * s + 0.5, f"apoio, centro {c:g}", VERM, 6.5,
             30 * s, Qt.AlignHCenter)
    y += PROF * s + 6
    pg.texto(M, y, W - 2 * M,
             "Verde = emendas de cima (100 e 290) · azul tracejado = emenda do meio (205) · cinza tracejado = emenda "
             "de baixo (142) · vermelho tracejado = onde ficam os quadros (6 mm para dentro de cada ponta) · "
             "rosa = apoios.", 8, cor=CINZA)


def corte_lateral(pg, x0, y0, s):
    """Vista de lado (corte): base, bloco frente+guia+fundo no rasgo e o apoio atrás."""
    def em(u, v):  # u = profundidade (0 = frente), v = altura acima do chão
        return QPointF(x0 + u * s, y0 - v * s)

    def poli(pts, **kw):
        p = QPainterPath(em(*pts[0]))
        for q in pts[1:]:
            p.lineTo(em(*q))
        p.closeSubpath()
        pg.forma(p, QTransform(), **kw)

    for i, cor in enumerate(("#e8d3a8", MADEIRA, "#e8d3a8")):  # baixo, meio, cima
        z0 = i * 3
        if i == 0:
            poli([(0, 0), (PROF, 0), (PROF, 3), (0, 3)], fundo=cor)
        else:
            poli([(0, z0), (Y_RASGO, z0), (Y_RASGO, z0 + 3), (0, z0 + 3)], fundo=cor)
            poli([(Y_RASGO + 9, z0), (PROF, z0), (PROF, z0 + 3), (Y_RASGO + 9, z0 + 3)], fundo=cor)
    alto = 40
    for k, (nome, cor) in enumerate((("frente", "#c9a46a"), ("guia", "#d9bb85"), ("fundo", "#c9a46a"))):
        u = Y_RASGO + 3 * k
        poli([(u, 3), (u + 3, 3), (u + 3, alto), (u, alto)], fundo=cor)
        pg.texto(em(u, alto).x() - 2, em(u, alto).y() - 5, 3 * s + 4, str(k + 1), 8, True,
                 alinhar=Qt.AlignHCenter)
    poli([(Y_RASGO + 9, 9), (Y_RASGO + 9 + CAT, 9), (Y_RASGO + 9, 9 + CAT)], fundo="#f2b8b5", cor=VERM)
    nota(pg, em(0, alto + 9).x(), em(0, alto + 9).y(), "1 frente · 2 guia de baixo · 3 fundo", TINTA, 8, 80)
    nota(pg, em(PROF + 2, 6).x(), em(0, 6).y() - 2, "base 9 (3 × 3)", CINZA, 7, 30)
    nota(pg, em(PROF + 2, 22).x(), em(0, 22).y(), "apoio 36 × 36\n(2 triângulos\ncolados = 6 mm)", VERM, 7, 30)
    nota(pg, em(-16, 4).x() - 18, em(0, 4).y() - 2, "lingueta entra\n6 mm (até a\ncamada lisa)", AZUL, 7, 34,
         Qt.AlignRight)
    seta(pg, em(-2, 4).x(), em(0, 4).y(), em(Y_RASGO, 5).x(), em(0, 5).y(), AZUL)
    nota(pg, em(-2, -1).x(), em(0, -1).y() + 1, "← FRENTE", VERM, 7.5, 20)
    nota(pg, em(PROF - 12, -1).x(), em(0, -1).y() + 1, "TRÁS →", VERM, 7.5, 20)


def pagina_quadros(pg):
    y = M
    y += pg.texto(M, y, W - 2 * M, "2. Encaixe dos quadros e apoios", 13, True) + 3
    corte_lateral(pg, M + 48, y + 92, 1.6)
    y += 104
    passos = [
        ("Frente modular", "Em superfície plana, una a frente esquerda, a faixa ISABELLA e a frente NATHAN com A1, "
         "C1–C3 e D1/D2 (por trás). As 2 linguetas de cima da faixa entram no quadro em pé."),
        ("Bloco de 9 mm", "Atrás de cada frente cole a guia de baixo (A2 à esquerda, B2 à direita) e o fundo, com as "
         "linguetas de 26 × 6 das três peças UMA ATRÁS DA OUTRA. São essas três linguetas juntas (3 + 3 + 3 = 9) que "
         "entram em cada rasgo. Sem a guia de baixo o encaixe fica folgado."),
        ("Base a seco", "Monte as 3 camadas da página 1 (lisa embaixo, rasgos virados para a FRENTE) e encaixe os "
         "quadros. As 4 linguetas devem descer 6 mm e encostar na camada lisa."),
        ("Colar a base", "Desmonte, passe cola entre as camadas e monte de novo COM os quadros encaixados (ou com "
         "tiras de 9 mm nos rasgos) para os rasgos secarem alinhados. Prenda com grampos/peso."),
        ("Quadros na base", "Cola nas linguetas e encaixe. Confira o esquadro (90°) enquanto seca."),
        ("Apoios", "Cole os 4 triângulos aos pares, face com face (2 apoios de 6 mm). Cole cada apoio atrás de um "
         "quadro: um lado de 36 encostado no fundo, o outro deitado na base, centros a 62 e 244 mm da ponta "
         "esquerda da base. Os apoios NÃO entram em rasgo nenhum, são só colados."),
        ("Apliques", "Corações conforme a vista frontal do projeto; a coroa vai colada sobre o último A."),
    ]
    for i, (t, txt) in enumerate(passos, 1):
        pg.texto(M, y, 8, str(i), 13, True, VERM)
        pg.texto(M + 8, y, W - 2 * M - 8, t, 10.5, True)
        y += 5 + pg.texto(M + 8, y + 5, W - 2 * M - 8, txt, 9) + 2.5
    y += 3
    y += pg.texto(M, y, W - 2 * M, "Se a lingueta não entra (apertada)", 11, True, VERM) + 1
    pg.texto(M, y, W - 2 * M,
             "Os rasgos têm 9,00 exatos (3 + 3 + 3, sem folga). MDF de 3,1–3,2 mm ou camadas coladas desalinhadas "
             "deixam o bloco maior que o rasgo. Meça as três linguetas juntas com paquímetro; lixe as linguetas ou "
             "abra o rasgo com lima. Para recortar, gere as camadas de cima e do meio com o rasgo = medida + 0,2 mm "
             "(Organizar → Redimensionar slots).", 9)


def gerar(saida):
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Porta-retrato Isabella e Nathan — manual de montagem")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    pagina_base(pg)
    pg.nova()
    pagina_quadros(pg)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1]))
