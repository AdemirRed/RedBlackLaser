"""Placa PIX "Nail Designer Milli" (MDF 3 mm) a partir de Projeto_Tecnico_Placa_PIX_Milli_CORRIGIDO.pdf.

Peças (medidas do PDF): placa P1 110 × 160 (R8 em cima, R5 embaixo) com 2 rasgos abertos na base (centros X=18 e
X=92, 16 mm de fundo); 2 pés 45 × 32 com rasgo central de 16 mm em cima (encaixe em cruz: 16 + 16 = 32).
Encaixe JUSTO, sem cola: chapa de 3 mm que mede um pouco menos (~2,9) -> os DOIS rasgos com a mesma largura
RASGO (2,80; o PDF dizia 2,85). O kerf do laser abre ~0,1 mm: fica ~2,9, justo na chapa real.

Gravação (página 2 do PDF, escala 1:1): QR Pix 45 × 45 módulos de 1,15 mm (vetores do PDF, conferido lendo o QR
desenhado contra o texto do Pix), textos com as fontes embutidas no PDF (mesma posição/tamanho de cada letra),
contorno orgânico, coração e linhas (traço). Camadas na ordem do dono: C03 (preenchimento), C04 (traço), C01 (corte).

Executar:  python tools/projetos/placa_pix_milli.py [pdf] [saida.rbl]
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import importar_pdf as pdfimp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

PDF = r"F:\Downloads\Projeto_Tecnico_Placa_PIX_Milli_CORRIGIDO.pdf"
# Pix da cliente: dado pessoal, fica fora do git (tools/projetos/privado/, ver .gitignore)
_ARQ_PIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "privado", "placa_pix_milli.pix")
PIX = open(_ARQ_PIX, encoding="utf-8").read().strip() if os.path.exists(_ARQ_PIX) else None
PT = 25.4 / 72
RASGO = 2.80          # largura dos DOIS rasgos (macho e fêmea iguais), justo em MDF ~2,9 mm
FUNDO = 16.0          # fundo de cada rasgo (16 + 16 = 32 = altura do pé)
PLACA_W, PLACA_H, R_CIMA, R_BAIXO = 110.0, 160.0, 8.0, 5.0
RASGOS_X = (18.0, 92.0)
PE_W, PE_H, R_PE = 45.0, 32.0, 3.0
MARGEM, ENTRE = 2.0, 2.0


def crc16(s: str) -> str:
    c = 0xFFFF
    for ch in s.encode():
        c ^= ch << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return format(c, "04X")


# ------------------------------------------------------------------ corte (por medida)
def _canto(p, cx, cy, r, a0):
    p.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), a0, -90)


def placa_contorno():
    """Contorno fechado da placa com os 2 rasgos abertos na base (Y para baixo, origem no canto sup. esq.)."""
    w, h, rc, rb, f, s = PLACA_W, PLACA_H, R_CIMA, R_BAIXO, FUNDO, RASGO
    p = QPainterPath()
    p.moveTo(rc, 0)
    p.lineTo(w - rc, 0)
    _canto(p, w - rc, rc, rc, 90)             # sup. dir.
    p.lineTo(w, h - rb)
    _canto(p, w - rb, h - rb, rb, 0)          # inf. dir.
    for cx in sorted(RASGOS_X, reverse=True):  # base, da direita para a esquerda
        p.lineTo(cx + s / 2, h)
        p.lineTo(cx + s / 2, h - f)
        p.lineTo(cx - s / 2, h - f)
        p.lineTo(cx - s / 2, h)
    p.lineTo(rb, h)
    _canto(p, rb, h - rb, rb, 270)            # inf. esq.
    p.lineTo(0, rc)
    _canto(p, rc, rc, rc, 180)                # sup. esq.
    p.closeSubpath()
    return p


def pe_contorno():
    w, h, r, f, s = PE_W, PE_H, R_PE, FUNDO, RASGO
    p = QPainterPath()
    p.moveTo(r, 0)
    p.lineTo(w / 2 - s / 2, 0)
    p.lineTo(w / 2 - s / 2, f)
    p.lineTo(w / 2 + s / 2, f)
    p.lineTo(w / 2 + s / 2, 0)
    p.lineTo(w - r, 0)
    _canto(p, w - r, r, r, 90)
    p.lineTo(w, h - r)
    _canto(p, w - r, h - r, r, 0)
    p.lineTo(r, h)
    _canto(p, r, h - r, r, 270)
    p.lineTo(0, r)
    _canto(p, r, r, r, 180)
    p.closeSubpath()
    return p


# ------------------------------------------------------------------ gravação (do PDF)
def vetores_pdf(pdf):
    """Origem = canto sup. esq. da placa no PDF. Devolve (qr, traços)."""
    res = pdfimp.load(pdf, 1)
    placa = [p for _n, p in res.objetos if abs(p.boundingRect().width() - PLACA_W) < 0.3
             and abs(p.boundingRect().height() - PLACA_H) < 0.3]
    assert len(placa) == 1, "placa 110 x 160 não encontrada no PDF"
    o = placa[0].boundingRect().topLeft()
    caixa = QRectF(o.x(), o.y(), PLACA_W, PLACA_H)
    volta = QTransform.fromTranslate(-o.x(), -o.y())
    qr, tracos = QPainterPath(), QPainterPath()
    for _n, p in res.objetos:
        b = p.boundingRect()
        dentro = caixa.adjusted(0.5, 0.5, -0.5, -0.5)
        if not (dentro.contains(b.topLeft()) and dentro.contains(b.bottomRight())):
            continue  # (contains(QRectF) recusa as linhas retas, que têm altura zero)
        if abs(b.height() - 1.15) < 0.02 and b.width() >= 1.14:
            qr.addPath(volta.map(p))                       # faixas de módulos do QR
        elif b.width() > 2 or b.height() > 2:
            tracos.addPath(volta.map(p))                   # contorno orgânico, coração, linhas
    qr = qr.simplified()
    return qr, tracos, o


class _PenQt:
    """Caneta do fontTools que desenha num QPainterPath (unidades da fonte, Y para cima)."""

    def __init__(self):
        from fontTools.pens.basePen import BasePen

        caminho = QPainterPath()

        class Pen(BasePen):
            def _moveTo(self, pt):
                caminho.moveTo(*pt)

            def _lineTo(self, pt):
                caminho.lineTo(*pt)

            def _curveToOne(self, p1, p2, p3):
                caminho.cubicTo(QPointF(*p1), QPointF(*p2), QPointF(*p3))

            def _qCurveToOne(self, p1, p2):
                caminho.quadTo(QPointF(*p1), QPointF(*p2))

            def _closePath(self):
                caminho.closeSubpath()

        self.caminho = caminho
        self.Pen = Pen


def textos_pdf(pdf, o, _pasta=None):
    """Letras dos textos da placa = contornos dos glifos das fontes embutidas no PDF, na posição exata de cada um."""
    import io

    import pymupdf
    from fontTools.ttLib import TTFont
    fontes = {}
    path = QPainterPath()
    with pymupdf.open(pdf) as doc:
        pg = doc[1]
        for xref, *_r in pg.get_fonts():
            nome, _ext, _tp, buf = doc.extract_font(xref)
            if buf:
                fontes[nome.split("+")[-1]] = TTFont(io.BytesIO(buf))
        x0, y0 = o.x() / PT, o.y() / PT
        x1, y1 = x0 + PLACA_W / PT, y0 + PLACA_H / PT
        for sp in pg.get_texttrace():
            bx = sp["bbox"]
            if not (x0 < bx[0] and bx[2] < x1 and y0 < bx[1] and bx[3] < y1):
                continue  # só o que está dentro da placa (cotas e títulos ficam de fora)
            f = fontes[sp["font"].split("+")[-1]]
            gs = f.getGlyphSet()
            nomes = f.getGlyphOrder()
            upem = f["head"].unitsPerEm
            esc = sp["size"] / upem
            for uni, gid, origem, _bb in sp["chars"]:
                if gid is None or gid < 0 or gid >= len(nomes) or not chr(uni).strip():
                    continue
                pen = _PenQt()
                gs[nomes[gid]].draw(pen.Pen(gs))
                ox, oy = origem
                tf = (QTransform().scale(esc * PT, -esc * PT) *
                      QTransform.fromTranslate(ox * PT - o.x(), oy * PT - o.y()))
                path.addPath(tf.map(pen.caminho))
    return path


def conferir_qr(qr):
    """Rasteriza o QR desenhado e lê: tem que dar exatamente o texto do Pix."""
    import cv2
    from PySide6.QtGui import QColor, QImage, QPainter
    b = qr.boundingRect()
    k = 12
    im = QImage(int((b.width() + 12) * k), int((b.height() + 12) * k), QImage.Format_RGB32)
    im.fill(QColor("white"))
    p = QPainter(im)
    p.scale(k, k)
    p.translate(6 - b.left(), 6 - b.top())
    p.fillPath(qr, QColor("black"))
    p.end()
    arq = os.path.join(tempfile.mkdtemp(), "qr.png")
    im.save(arq)
    lido = cv2.QRCodeDetector().detectAndDecode(cv2.imread(arq))[0]
    assert lido == PIX, f"QR desenhado não bate com o Pix: {lido!r}"
    return b


def _grupo(itens, nome, dx, dy):
    t = QTransform.fromTranslate(dx, dy)
    g = ob.group([ob.Shape(t.map(p), f"{nome} — {d}", lid, cm.cor(lid)) for p, lid, d in itens])
    g.name = nome
    return g.snapshot()


def camadas():
    grav = dict(velocidade_mm_min=2000.0, potencia_max=35.0, potencia_min=0.0, passadas=1, air=True)
    return [cm.alterar(cm.Camada("C03", "Gravação: textos e QR (preenchimento)"), modo="preenchimento",
                       intervalo_mm=0.1, **grav),
            cm.alterar(cm.Camada("C04", "Gravação: contorno, coração e linhas (traço)"), modo="linha", **grav),
            cm.alterar(cm.Camada("C01", "Corte MDF 3 mm (por último)"), modo="linha", velocidade_mm_min=630.0,
                       potencia_max=85.0, potencia_min=0.0, passadas=2, air=True)]


NOTAS = f"""Placa PIX Nail Designer Milli (PDF Projeto_Tecnico_Placa_PIX_Milli_CORRIGIDO).
MDF 3 mm. Placa 110 x 160 + 2 pés 45 x 32, encaixe em cruz sem cola: os dois rasgos com {RASGO:.2f} mm (justo
em chapa ~2,9 mm), 16 mm de fundo cada. QR conferido: lê exatamente o Pix (CRC 5F07). Escaneie na peça pronta."""


def gerar(pdf=PDF, destino="Placa_PIX_Milli_MDF_3mm_RedBlack.rbl"):
    assert crc16(PIX[:-4]) == PIX[-4:], "CRC do Pix não confere"
    qr, tracos, o = vetores_pdf(pdf)
    bq = conferir_qr(qr)
    assert abs(bq.width() - 51.75) < 0.1 and abs(bq.height() - 51.75) < 0.1, bq  # 45 módulos × 1,15
    texto = textos_pdf(pdf, o, None)
    grav = QPainterPath()
    grav.addPath(texto)
    grav.addPath(qr)
    placa = [(grav, "C03", "textos e QR"), (tracos, "C04", "contorno, coração e linhas"),
             (placa_contorno(), "C01", "contorno com 2 rasgos")]
    x0 = MARGEM
    snaps = [_grupo(placa, "P1 Placa frontal", x0, MARGEM)]
    xp = x0 + PLACA_W + ENTRE
    snaps.append(_grupo([(pe_contorno(), "C01", "pé com rasgo")], "P2 Pé 1", xp, MARGEM))
    snaps.append(_grupo([(pe_contorno(), "C01", "pé com rasgo")], "P3 Pé 2", xp, MARGEM + PE_H + ENTRE))
    pj.save(destino, tuple(snaps), camadas(), notas=NOTAS, nomes_paginas=["Placa PIX Milli — MDF 3 mm"])
    return destino, qr, texto


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    a = sys.argv[1:]
    d, qr, texto = gerar(a[0] if a else PDF, a[1] if len(a) > 1 else "Placa_PIX_Milli_MDF_3mm_RedBlack.rbl")
    print(d, "| QR", round(qr.boundingRect().width(), 2), "mm | texto", texto.boundingRect())
