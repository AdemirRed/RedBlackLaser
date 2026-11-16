"""Guia de pintura do presépio (PDF A4): uma cor lisa por peça, pintada na chapa ANTES de gravar e cortar.

As peças aparecem exatamente onde a aba "MARCA p/ pintar" risca os contornos (mesmo encaixe do presepio.py).
Cores que o dono tem: azul, verde, amarelo, marrom, vermelho, rosa. Preto = o laser (gravação e corte), depois.
Executar:  python tools/projetos/presepio_pintura.py <Presepio_MDF_3mm_Projeto_Completo.pdf> <saida.pdf>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QTransform  # noqa: E402

import presepio as pr  # noqa: E402
from carroca_manual import CINZA, M, MADEIRA, VERM, W, Pagina  # noqa: E402

LARG = W - 2 * M
TINTAS = {"Azul": "#2f6bd6", "Verde": "#3a9a3a", "Amarelo": "#f2c418", "Marrom": "#7a4a22", "Vermelho": "#d32f2f",
          "Rosa": "#f48fb1", "Sem tinta": MADEIRA}
COR = {"B01": "Verde", "F01": "Marrom", "F02": "Marrom", "L01": "Marrom", "L02": "Marrom", "T01": "Vermelho",
       "T02": "Vermelho", "P01": "Azul", "P02": "Amarelo", "P03": "Verde", "P04": "Vermelho", "P05": "Amarelo",
       "P06": "Rosa", "P07": "Sem tinta", "P08": "Verde", "G01": "Sem tinta", "G02": "Sem tinta"}
POR_QUE = {"B01": "grama", "F01": "madeira da casa", "F02": "madeira da casa", "L01": "madeira da casa",
           "L02": "madeira da casa", "T01": "telhas", "T02": "telhas", "P01": "manto de Maria",
           "P02": "palha da manjedoura", "P03": "túnica de José", "P04": "rei Melchior", "P05": "rei Baltazar",
           "P06": "rei Gaspar", "P07": "lã fica na cor da madeira", "P08": "folhas da palmeira",
           "G01": "peça de teste", "G02": "peça de teste"}
TOTAL = 4


def _texto_contraste(cor):
    c = QColor(TINTAS[cor])
    return "#ffffff" if c.lightness() < 140 else "#222222"


def chapa(pg, pecas_chapa, x, y, larg):
    esc = larg / pr.MESA_W
    tf = QTransform.fromScale(esc, esc) * QTransform.fromTranslate(x, y)
    pg.forma(QPainterPath(), tf)
    fundo = QPainterPath()
    fundo.addRect(QRectF(0, 0, pr.MESA_W, pr.MESA_H))
    pg.forma(fundo, tf, cor=CINZA, fundo="#f6efe2", larg=0.3)
    # maiores primeiro: a peça que fica dentro do vão de outra é pintada por cima
    ordem = sorted(pecas_chapa, key=lambda t: -next(p for p, _l, tp in t[1] if tp == "cont").boundingRect().width()
                   * next(p for p, _l, tp in t[1] if tp == "cont").boundingRect().height())
    for k, partes, _d in ordem:
        cont = next(p for p, _l, t in partes if t == "cont")
        pg.forma(cont, tf, cor="#111111", fundo=TINTAS[COR[k]], larg=0.25)
        for p, _l, t in partes:  # vãos grandes ficam sem tinta (caem fora)
            if t == "furo" and pr._area(p) > pr.FURO_GRANDE:
                pg.forma(p, tf, cor="#111111", fundo="#f6efe2", larg=0.2)
    usados = []
    for k, partes, _d in sorted(ordem, key=lambda t: _tamanho(t)):  # pequenas escolhem lugar primeiro
        r = _lugar_rotulo(k, partes, pecas_chapa, tf, usados, tf.mapRect(QRectF(0, 0, pr.MESA_W, pr.MESA_H)))
        usados.append(r)
        caixa = QPainterPath()
        caixa.addRoundedRect(r, 1.0, 1.0)
        pg.forma(caixa, QTransform(), cor="#111111", fundo="#ffffff", larg=0.15)
        pg.texto(r.x(), r.y() + 0.2, r.width(), pr.NOMES[k], 5.2, True, "#222222", Qt.AlignHCenter)
        pg.texto(r.x(), r.y() + 3.0, r.width(), COR[k].upper(), 5.6, True, TINTAS[COR[k]]
                 if COR[k] != "Sem tinta" else "#8a6d3b", Qt.AlignHCenter)
    return y + pr.MESA_H * esc


ROT_W, ROT_H = 25.0, 6.4  # mm na página


def _tamanho(t):
    r = next(p for p, _l, tp in t[1] if tp == "cont").boundingRect()
    return r.width() * r.height()


def _lugar_rotulo(k, partes, todas, tf, usados, dentro_de):
    """Retângulo do rótulo (mm da página): o ponto da peça mais longe das bordas (e dos vãos e das peças que estão
    dentro dela) onde o rótulo não bate em outro já posto."""
    import numpy as np
    from scipy.ndimage import distance_transform_edt
    cont = next(p for p, _l, t in partes if t == "cont")
    caixa = cont.boundingRect()
    buracos = [p for p, _l, t in partes if t == "furo"]
    buracos += [next(p for p, _l, t in pt if t == "cont") for o, pt, _d in todas
                if o != k and caixa.contains(next(p for p, _l, t in pt if t == "cont").boundingRect())]
    mat = pr._raster([cont], caixa, buracos)
    dist = distance_transform_edt(np.pad(mat, 1))[1:-1, 1:-1]  # borda da caixa conta como fora da peça
    for idx in np.argsort(dist, axis=None)[::-1][:4000:7]:
        yy, xx = np.unravel_index(idx, dist.shape)
        c = tf.map(QPointF(caixa.left() + xx / pr.RES, caixa.top() + yy / pr.RES))
        r = QRectF(c.x() - ROT_W / 2, c.y() - ROT_H / 2, ROT_W, ROT_H)
        if dentro_de.contains(r) and not any(r.intersects(u) for u in usados):
            return r
    c = tf.map(caixa.center())
    return QRectF(c.x() - ROT_W / 2, c.y() - ROT_H / 2, ROT_W, ROT_H)


def cabecalho(pg, n, titulo, sub=""):
    pg.p.fillRect(QRectF(0, 0, W * pg.k, 22 * pg.k), Qt.black)
    pg.texto(M, 5, LARG, "PRESÉPIO · MDF 3 mm · guia de pintura", 8, True, "#e0a0a0")
    pg.texto(M, 10.5, LARG, titulo, 15, True, "#ffffff")
    pg.texto(M, 288, LARG, f"página {n} de {TOTAL}", 7, False, CINZA, Qt.AlignRight)
    return 26 + (pg.texto(M, 26, LARG, sub, 9, False, CINZA) + 3 if sub else 2)


def pagina_regras(pg, chapas):
    y = cabecalho(pg, 1, "Pintura rápida antes do laser", "Uma cor lisa por peça. O preto (linhas do desenho, "
                  "rostos, telhas, contornos) quem faz é o laser DEPOIS, por cima da tinta.")
    pg.texto(M, y, LARG, "SUAS CORES", 10, True, VERM)
    y += 6
    larg = LARG / 7
    for i, (nome, hexa) in enumerate(TINTAS.items()):
        q = QPainterPath()
        q.addRoundedRect(QRectF(M + i * larg + 2, y, larg - 4, 14), 2, 2)
        pg.forma(q, QTransform(), cor="#222222", fundo=hexa, larg=0.25)
        pg.texto(M + i * larg, y + 15.5, larg, nome, 7.5, True, "#222222", Qt.AlignHCenter)
    y += 26
    pg.texto(M, y, LARG, "QUAL COR EM CADA PEÇA", 10, True, VERM)
    y += 6
    meia = LARG / 2
    for i, k in enumerate(sorted(COR)):
        cx, cy = M + (i % 2) * meia, y + (i // 2) * 7
        q = QPainterPath()
        q.addRoundedRect(QRectF(cx, cy + 0.6, 9, 5), 1, 1)
        pg.forma(q, QTransform(), cor="#222222", fundo=TINTAS[COR[k]], larg=0.2)
        pg.texto(cx + 11, cy + 0.8, meia - 12, f"{pr.NOMES[k]}: {COR[k].lower()} ({POR_QUE[k]})", 8)
    y += (len(COR) + 1) // 2 * 7 + 6
    pg.texto(M, y, LARG, "PASSO A PASSO (em cada chapa)", 10, True, VERM)
    y += 6
    for i, s in enumerate((
            "Encoste a chapa no canto da mesa (batente) e rode a aba \"MARCA p/ pintar — chapa N\": o laser risca "
            "o contorno de cada peça em menos de 1 minuto.",
            "Tire a chapa e pinte DENTRO de cada risco com a cor da página dessa chapa. Rolinho de espuma ou pincel "
            "largo, 1 demão fina. Pode passar no máximo 1 mm do risco (as peças estão a 2 mm uma da outra).",
            "Não pinte o vão grande da fachada nem os triângulos e janelas das laterais e do fundo: eles caem fora "
            "(dentro deles há peças de outra cor, pinte só a peça).",
            "Deixe secar bem (toque seco não basta: espere 1 hora). Tinta mole gruda e mancha na gravação.",
            "Encoste a chapa de volta EXATAMENTE no mesmo canto, sem mexer na origem, e rode a aba \"Chapa N\": o "
            "laser grava o desenho em preto por cima da tinta e corta.")):
        y += pg.texto(M, y, LARG, f"{i + 1}.  {s}", 8.5) + 2
    y += 3
    q = QPainterPath()
    alt = 26
    q.addRect(QRectF(M, y, LARG, alt))
    pg.forma(q, QTransform(), cor=VERM, fundo="#fdf0f0", larg=0.4)
    pg.texto(M + 4, y + 3, LARG - 8, "Atenção", 10, True, VERM)
    pg.texto(M + 4, y + 9, LARG - 8, "• Tinta grossa engrossa o MDF e os encaixes ficam apertados: só 1 demão fina.\n"
             "• Faça antes um teste num retalho: pinte, deixe secar e grave a 25 %. Se a gravação sumir na tinta, "
             "suba a potência da gravação aos poucos.\n"
             "• As bordas cortadas ficam na cor da madeira (o laser corta depois da tinta).", 8)


def pagina_chapa(pg, n, i, chapa_pecas):
    y = cabecalho(pg, n, f"Chapa {i + 1}: onde pintar", "Como a chapa fica na mesa, igual à marcação do laser. "
                  "Pinte cada peça da cor escrita nela.")
    y = chapa(pg, chapa_pecas, M, y + 2, LARG) + 6
    cores = {}
    for k, _p, _d in chapa_pecas:
        cores.setdefault(COR[k], []).append(pr.NOMES[k])
    for cor, nomes in cores.items():
        q = QPainterPath()
        q.addRoundedRect(QRectF(M, y + 0.6, 9, 5), 1, 1)
        pg.forma(q, QTransform(), cor="#222222", fundo=TINTAS[cor], larg=0.2)
        y += pg.texto(M + 11, y + 0.8, LARG - 11, f"{cor}: " + ", ".join(nomes), 8.5) + 2.5


def gerar(pdf_entrada, saida):
    pecas = pr.limpar(pr.ler(pdf_entrada))
    chapas = pr.folhas(pecas, pr.encaixar(pecas))  # o mesmo encaixe do projeto (determinístico)
    assert len(chapas) + 1 == TOTAL
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Presépio — guia de pintura")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    pagina_regras(pg, chapas)
    for i, c in enumerate(chapas):
        pg.nova()
        pagina_chapa(pg, i + 2, i, c)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
