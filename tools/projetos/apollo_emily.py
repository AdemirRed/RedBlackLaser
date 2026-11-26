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
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPainterPathStroker, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

CHAPA_W, CHAPA_H = 370.0, 365.0   # no PDF (deitada)
MARGEM, ESPACO = 5.0, 4.0
PT = 25.4 / 72

# cor do PDF -> camada (ordem de saída = ordem desta lista)
CAMADAS = [("C05", "Corações gravados (1º)", "grav"),
           ("C06", "Guia das letras na faixa (linha fraca)", "guia"),
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
    with pymupdf.open(pdf) as doc:  # aberto e esquecido estoura o limite de ~509 arquivos do processo (testes)
        return [(n, caminho(d), _camada(d["color"])) for n in (1, 2) for d in doc[n].get_drawings()]


FAIXAS_PDF = {"Apollo": QPointF(185.0, 303.0), "Emily": QPointF(185.0, 348.0)}  # centro da faixa de cima / de baixo
RECUO_GUIA = 0.4  # mm para dentro do contorno da letra: a letra colada cobre a marca


def nomes_na_faixa(itens):
    """{nome: [path da letra já no centro da faixa onde vai colada]} no sistema do PDF."""
    letras = [p for n, p, lid in itens if n == 1 and lid == "C03" and p.boundingRect().width() < 50
              and 140 < p.boundingRect().top() < 175]
    assert len(letras) == 11, f"esperava 11 letras (Apollo + Emily), achei {len(letras)}"
    out = {}
    for nome, centro in FAIXAS_PDF.items():
        grupo = [p for p in letras if (p.boundingRect().center().x() < 185) == (nome == "Apollo")]
        caixa = QRectF()
        for p in grupo:
            caixa = caixa.united(p.boundingRect())
        d = centro - caixa.center()
        out[nome] = [QTransform.fromTranslate(d.x(), d.y()).map(p) for p in grupo]
    return out


def _externo(p):
    """Só os contornos de fora da letra (no gabarito vazado o miolo do "o" sai junto)."""
    subs = []  # subcaminhos COM as curvas (polígono deixaria o furo menor que a letra nas curvas)
    i = 0
    while i < p.elementCount():
        e = p.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            subs.append(QPainterPath(QPointF(e.x, e.y)))
        elif e.type == QPainterPath.LineToElement:
            subs[-1].lineTo(e.x, e.y)
        else:  # CurveTo + 2 CurveToData
            c2, fim = p.elementAt(i + 1), p.elementAt(i + 2)
            subs[-1].cubicTo(e.x, e.y, c2.x, c2.y, fim.x, fim.y)
            i += 2
        i += 1
    polis = [s.toFillPolygon() for s in subs]
    out = QPainterPath()
    for k, s in enumerate(subs):
        if not any(j != k and o.containsPoint(polis[k][0], Qt.OddEvenFill) for j, o in enumerate(polis)):
            s.closeSubpath()
            out.addPath(s)
    return out


LADO_GAB, PONTA_GAB, DENTE = 4.0, 12.0, 6.0  # mm: sobra ao lado das letras, nas pontas; dente (largura = fundo)


def gabaritos(itens):
    """Por nome, uma plaquinha com as letras vazadas e um dente igual no meio de cada ponta (como o desenho do
    usuário). Devolve [(path, camada, nome)] já girado para a mesa."""
    giro = QTransform(0, -1, 1, 0, 0, CHAPA_W)
    out, y = [], MARGEM
    for nome, grupo in nomes_na_faixa(itens).items():
        caixa = QRectF()
        for p in grupo:
            caixa = caixa.united(p.boundingRect())
        w, h = caixa.width() + 2 * PONTA_GAB, caixa.height() + 2 * LADO_GAB
        x0, meio = MARGEM, y + h / 2
        placa = QPainterPath(QPointF(x0, y))
        for px, py in ((x0 + w, y), (x0 + w, meio - DENTE / 2), (x0 + w - DENTE, meio - DENTE / 2),
                       (x0 + w - DENTE, meio + DENTE / 2), (x0 + w, meio + DENTE / 2), (x0 + w, y + h), (x0, y + h),
                       (x0, meio + DENTE / 2), (x0 + DENTE, meio + DENTE / 2), (x0 + DENTE, meio - DENTE / 2),
                       (x0, meio - DENTE / 2)):
            placa.lineTo(px, py)
        placa.closeSubpath()
        mover = QTransform.fromTranslate(x0 + PONTA_GAB - caixa.left(), y + LADO_GAB - caixa.top())
        out += [(giro.map(_externo(mover.map(p))), "C03", f"Gabarito {nome}: letra vazada") for p in grupo]
        out.append((giro.map(placa), "C01", f"Gabarito {nome} ({w:.0f} × {h:.0f})"))
        y += h + ESPACO
    return out


def guias(itens):
    """Contorno de cada nome gravado fraco NA FAIXA onde vai ser colado (centralizado), um pouco para dentro da
    letra — marca o lugar exato. [(2, path, "C06")] no sistema do PDF."""
    st = QPainterPathStroker()
    st.setWidth(2 * RECUO_GUIA)
    out = []
    for grupo in nomes_na_faixa(itens).values():
        for p in grupo:
            q = QPainterPath(p)
            q.setFillRule(Qt.OddEvenFill)
            out.append((2, q.subtracted(st.createStroke(q)).simplified(), "C06"))
    return out


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
                nome = {"C05": "Corações", "C06": f"Guia: cole {('Apollo', 'Emily')[k]} aqui"}.get(
                    lid, ("Faixa de cima (Apollo)", "Faixa de baixo (Emily, com alívios)")[k])
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
        if lid in ("C05", "C06"):
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
        if tipo == "guia":  # só marca o lugar: linha fina e fraca (M4), some debaixo da letra
            c = cm.alterar(c, modo="linha", velocidade_mm_min=3000.0, potencia_max=25.0, potencia_min=0.0, passadas=1)
        elif tipo == "grav":
            c = cm.alterar(c, modo="preenchimento", velocidade_mm_min=3000.0, potencia_max=15.0, potencia_min=0.0,
                           passadas=1, intervalo_mm=0.1)
        else:
            c = cm.alterar(c, **corte)
        out.append(c)
    return out


def gerar(pdf, saida):
    itens = ler(pdf)
    folhas = arrumar(itens + guias(itens))
    folhas[3] = gabaritos(itens)
    snaps = {n: [ob.Shape(p, nome, lid, cm.cor(lid)).snapshot() for p, lid, nome in folhas[n]] for n in (1, 2, 3)}
    # conferência: tudo dentro da mesa 365 × 370 com MARGEM da borda
    for n in (1, 2, 3):
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
             "Ordem: C05 grava os corações (3000 mm/min, 15 %) → C06 grava fraco (3000 mm/min, 25 %) o contorno de "
             "Apollo na faixa de cima e de Emily na de baixo, centralizados: cole cada letra em cima do desenho dela "
             "(a marca fica 0,4 mm para dentro e some debaixo da letra) → C02 teste de encaixe 8,9/9,1/9,3/9,5/9,7 "
             "(opcional: desligue a Saída se não quiser) → C03 pés, letras e espaçadores → C04 janelas → C01 frente, "
             "fundo e faixas. Cortes 650 mm/min, 85 %, 2 passadas.\n"
             "Chapa 3 (retalho): gabarito vazado de cada nome, com um dente no meio de cada ponta. Ponha em "
             "cima da marca gravada na faixa, passe cola nos furos e coloque as letras.\n"
             "Corte o teste primeiro, empilhe três retalhos e confira qual encaixe fica justo; se não for o 9,3, "
             "ajuste os encaixes dos 6 pés antes de cortar a chapa toda.")
    pj.save(saida, snaps[1], camadas(), notas=notas, paginas=[None, (tuple(snaps[2]), (), ()), (tuple(snaps[3]), (), ())],
            pagina_atual=0, nomes_paginas=["Chapa 1 — frente, pés, nomes", "Chapa 2 — fundo e faixas",
                                           "Chapa 3 — gabaritos das letras (retalho)"])
    return saida, ap


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
