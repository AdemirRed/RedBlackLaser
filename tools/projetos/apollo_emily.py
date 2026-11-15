"""Porta-retratos Apollo e Emily (MDF 3 mm, 2 chapas de 370 × 365 mm) a partir do PDF de corte.

O PDF já traz o encaixe das peças em duas chapas, mas com espaçadores e faixas a 1–2 mm da borda (queima a borda
da chapa) e a chapa deitada (370 de largura) numa mesa de 365 × 370. Aqui:
  - as peças vão para MARGEM mm da borda e ficam a ESPACO mm umas das outras (sobra embaixo da frente/fundo);
  - a chapa gira 90° (sem espelhar) para caber na mesa;
  - camadas pela cor do PDF, na ordem certa: corações gravados → teste de encaixe → pés, letras e espaçadores →
    janelas → contornos grandes (frente, fundo, faixas). Furos/miolos antes do contorno saem sozinhos (percurso).

Executar:  python tools/projetos/apollo_emily.py <entrada.pdf> <saida.rbl>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter, QPainterPath, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

CHAPA_W, CHAPA_H = 370.0, 365.0   # no PDF (deitada)
MARGEM, ESPACO = 5.0, 4.0
PT = 25.4 / 72

# cor do PDF -> camada (ordem de saída = ordem desta lista)
CAMADAS = [("C05", "Corações gravados (1º)", "grav"),
           ("C02", "Teste de encaixe 8,9–9,7 (opcional, 2º)", "corte"),
           ("C03", "Pés, letras e espaçadores (3º)", "corte"),
           ("C04", "Janelas da frente (4º)", "corte"),
           ("C01", "Frente, fundo e faixas (por último)", "corte")]
COR = {(0, 0, 0): "C05", (0.6, 0, 0.6): "C02", (0, 0.5, 0): "C03", (0, 0, 1): "C04", (1, 0, 0): "C01"}


def _camada(cor):
    c = tuple(round(v, 1) for v in cor)
    return COR[c]


def caminho(d):
    """Desenho do pymupdf -> QPainterPath em mm (curvas mantidas)."""
    p, atual = QPainterPath(), None

    def q(pt):
        return QPointF(pt.x * PT, pt.y * PT)

    for it in d["items"]:
        if it[0] == "re":
            r = it[1]
            p.addRect(QRectF(r.x0 * PT, r.y0 * PT, r.width * PT, r.height * PT))
            atual = None
            continue
        if it[0] == "qu":
            p.addPolygon([q(it[1].ul), q(it[1].ur), q(it[1].lr), q(it[1].ll), q(it[1].ul)])
            atual = None
            continue
        a = q(it[1])
        if atual is None or (a - atual).manhattanLength() > 1e-3:
            if atual is not None and d.get("closePath"):
                p.closeSubpath()
            p.moveTo(a)
        if it[0] == "l":
            p.lineTo(q(it[2]))
            atual = q(it[2])
        elif it[0] == "c":
            p.cubicTo(q(it[2]), q(it[3]), q(it[4]))
            atual = q(it[4])
        else:
            raise ValueError(f"item de desenho não tratado: {it[0]}")
    if d.get("closePath"):
        p.closeSubpath()
    return p


def ler(pdf):
    """[(página 1|2, path mm, camada)] das duas chapas."""
    doc = pymupdf.open(pdf)
    return [(n, caminho(d), _camada(d["color"])) for n in (1, 2) for d in doc[n].get_drawings()]


def arrumar(itens):
    """Afasta da borda e entre si (no sistema do PDF) e devolve {página: [(path, camada, nome)]} já girado."""
    giro = QTransform(0, -1, 1, 0, 0, CHAPA_W)  # (x, y) -> (y, 370 − x): 90° sem espelhar; mesa 365 × 370
    out = {1: [], 2: []}
    for n, p, lid in itens:
        r = p.boundingRect()
        if r.height() > 200 or r.top() < 285:          # frente/fundo e tudo dentro das janelas
            dy, nome = MARGEM - 10.0, {"C01": "Frente" if n == 1 else "Fundo", "C04": "Janela"}.get(lid, "")
        else:                                           # faixa de sobra embaixo: re-empilha
            base = MARGEM + 270.0 + ESPACO
            if n == 1:  # espaçadores 14, 12, 14 e batente 14 (na ordem do PDF)
                linha = sorted({round(t.boundingRect().top()) for m, t, lid2 in itens if m == 1 and lid2 == "C03"
                                and t.boundingRect().top() >= 285}).index(round(r.top()))
                alturas = [14.0, 12.0, 14.0, 14.0]
                dy = base + sum(alturas[:linha]) + ESPACO * linha - r.top()
                nome = "Batente 320 × 14" if r.width() > 300 else f"Espaçador {r.width():.0f} × {r.height():.0f}"
            else:       # faixas 30 de altura (e os corações de cada uma)
                k = 0 if r.top() < 325 else 1
                topo_pdf = (288.0, 333.0)[k]
                dy = base + k * (30.0 + ESPACO) - topo_pdf
                nome = "Corações" if lid == "C05" else ("Faixa de cima (Apollo)", "Faixa de baixo (pés)")[k]
        if not nome:
            nome = {"C02": "Teste de encaixe", "C03": "Pé" if r.width() > 50 else "Letra"}.get(lid, lid)
        out[n].append((giro.map(QTransform.fromTranslate(0, dy).map(p)), lid, nome))
    return out


def aproveitamento(pecas):
    """Área das peças (contorno de corte, furos descontados) / área da chapa — por rasterização a 4 px/mm."""
    esc = 4
    img = QImage(int(CHAPA_H * esc), int(CHAPA_W * esc), QImage.Format_Grayscale8)
    img.fill(0)
    pt = QPainter(img)
    pt.scale(esc, esc)
    pt.setPen(Qt.NoPen)
    for p, lid, _ in sorted(pecas, key=lambda t: -t[0].boundingRect().width() * t[0].boundingRect().height()):
        if lid == "C05":
            continue
        q = QPainterPath(p)
        q.setFillRule(Qt.OddEvenFill)
        # recorte: furo (janela) apaga; peça dentro do furo pinta de novo — ordem do maior para o menor
        pt.setBrush(Qt.black if lid == "C04" else Qt.white)
        pt.drawPath(q)
    pt.end()
    cheio = sum(img.constBits()[i] > 127 for i in range(0, img.sizeInBytes(), 1))
    return cheio / (img.width() * img.height())


def camadas():
    corte = mt.corte_mdf(3)
    out = []
    for lid, nome, tipo in CAMADAS:
        c = cm.Camada(lid, nome)
        if tipo == "grav":
            c = cm.alterar(c, modo="preenchimento", velocidade_mm_min=3000.0, potencia_max=15.0, potencia_min=0.0,
                           passadas=1, intervalo_mm=0.1)
        else:
            c = cm.alterar(c, **corte)
        out.append(c)
    return out


def gerar(pdf, saida):
    folhas = arrumar(ler(pdf))
    snaps = {n: [ob.Shape(p, nome, lid, cm.cor(lid)).snapshot() for p, lid, nome in folhas[n]] for n in (1, 2)}
    # conferência: tudo dentro da mesa 365 × 370 com MARGEM da borda
    for n in (1, 2):
        caixa = QRectF()
        for p, _, _ in folhas[n]:
            caixa = caixa.united(p.boundingRect())
        assert caixa.left() >= MARGEM - 0.01 and caixa.top() >= MARGEM - 0.01, caixa
        assert caixa.right() <= CHAPA_H - MARGEM + 0.01 and caixa.bottom() <= CHAPA_W - MARGEM + 0.01, caixa
    ap = {n: aproveitamento(folhas[n]) for n in (1, 2)}
    notas = (f"Porta-retratos Apollo e Emily — MDF 3 mm, 2 chapas de 365 × 370 mm (a chapa de 370 × 365 do PDF, "
             f"girada 90° para caber na mesa).\n"
             f"Peças a {MARGEM:g} mm da borda da chapa (não queima a borda) e {ESPACO:g} mm entre si.\n"
             f"Aproveitamento: chapa 1 {ap[1]:.0%}, chapa 2 {ap[2]:.0%}.\n"
             "Ordem: C05 grava os corações (3000 mm/min, 15 %) → C02 teste de encaixe 8,9/9,1/9,3/9,5/9,7 "
             "(opcional: desligue a Saída se não quiser) → C03 pés, letras e espaçadores → C04 janelas → C01 frente, "
             "fundo e faixas. Cortes 650 mm/min, 85 %, 2 passadas.\n"
             "Corte o teste primeiro, empilhe três retalhos e confira qual encaixe fica justo; se não for o 9,3, "
             "ajuste os encaixes dos 6 pés antes de cortar a chapa toda.")
    pj.save(saida, snaps[1], camadas(), notas=notas, paginas=[None, (tuple(snaps[2]), (), ())], pagina_atual=0,
            nomes_paginas=["Chapa 1 — frente, pés, nomes", "Chapa 2 — fundo e faixas"])
    return saida, ap


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
