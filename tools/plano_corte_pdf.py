"""Plano de corte em PDF para imprimir, a partir de um projeto .rbl.

Uma página por aba (chapa): desenho em escala com as peças numeradas, ordem das camadas com velocidade/potência/
passadas e tempo estimado; e uma página final com a lista de peças e as notas do projeto.

Executar:  python tools/plano_corte_pdf.py projeto.rbl [saida.pdf]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QMarginsF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen,  # noqa: E402
                           QTransform)

from redblack import __version__  # noqa: E402
from redblack import projeto as pj  # noqa: E402

MODOS = {"linha": "Corte/risco em linha", "preenchimento": "Gravação (preenchimento)", "imagem": "Imagem"}


def _achatar(objs, pai=QTransform()):
    """[(caminho em mm na mesa, camada, cor)] de uma lista de objetos (grupos abertos recursivamente)."""
    out = []
    for o in objs:
        m = o["matriz"]
        tf = QTransform(*m) * pai
        if o["tipo"] == "grupo":
            out += _achatar(o.get("filhos", []), tf)
        elif o["tipo"] in ("vetor", "texto"):
            out.append((tf.map(pj.list_to_path(o["caminho"], o.get("preenchimento") == "winding")), o["camada"],
                        o["cor"]))
    return out


def ler(arquivo):
    with open(arquivo, encoding="utf-8") as f:
        d = json.load(f)
    paginas = [d["objetos"] if p is None else p["objetos"] for p in d.get("paginas") or [None]]
    nomes = d.get("nomes_paginas") or [f"Página {k}" for k in range(1, len(paginas) + 1)]
    folhas = []
    for nome, objs in zip(nomes, paginas):
        pecas = []
        for o in objs:
            partes = _achatar([o])
            caixa = QRectF()
            for c, _, _ in partes:
                caixa = caixa.united(c.boundingRect())
            pecas.append({"nome": o["nome"], "partes": partes, "caixa": caixa})
        folhas.append((nome, pecas))
    return d, folhas


def _tempo(seg):
    m, s = divmod(int(round(seg)), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def _n(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


def gerar(arquivo, destino):
    d, folhas = ler(arquivo)
    camadas = [c for c in d.get("camadas", []) if c.get("saida", True)]
    titulo = os.path.splitext(os.path.basename(arquivo))[0]
    pdf = QPdfWriter(destino)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(10, 10, 10, 10),
                                  QPageLayout.Millimeter))
    pdf.setResolution(300)
    pdf.setTitle(f"Plano de corte — {titulo}")
    pdf.setCreator(f"RedBlack Laser {__version__}")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    px = pdf.resolution() / 25.4  # px por mm
    p.scale(px, px)  # daqui em diante tudo em mm
    W, H = 277.0, 190.0  # área útil do A4 deitado
    total_geral = 0.0

    def texto(x, y, s, tam=9, negrito=False, cor="#222", larg=None, alin=Qt.AlignLeft):
        f = QFont("Segoe UI")
        f.setPointSizeF(tam / px)  # o pintor já está escalado para mm
        f.setBold(negrito)
        p.setFont(f)
        p.setPen(QColor(cor))
        r = QRectF(x, y, larg or 200, tam * 0.6)
        p.drawText(r, alin | Qt.AlignVCenter | Qt.TextDontClip, s)

    for k, (nome, pecas) in enumerate(folhas):
        if k:
            pdf.newPage()
        caixa = QRectF()
        for pc in pecas:
            caixa = caixa.united(pc["caixa"])
        texto(0, 0, f"PLANO DE CORTE — {titulo}", 14, True)
        texto(0, 7, f"Aba {k + 1}/{len(folhas)}: {nome}   ·   área usada {_n(caixa.width(), 0)} × "
                    f"{_n(caixa.height(), 0)} mm (a partir do canto da mesa)", 9.5, cor="#555")
        # desenho em escala, à esquerda
        area = QRectF(0, 14, 180, H - 14)
        esc = min(area.width() / max(caixa.right(), 1), area.height() / max(caixa.bottom(), 1))
        p.save()
        p.translate(area.topLeft())
        p.scale(esc, esc)
        p.setPen(QPen(QColor("#bbb"), 0.3 / esc, Qt.DashLine))
        p.drawRect(QRectF(0, 0, caixa.right(), caixa.bottom()))
        for pc in pecas:
            for c, _, cor in pc["partes"]:
                p.setPen(QPen(QColor(cor), 0.35 / esc))
                p.drawPath(c)
        p.restore()
        for pc in pecas:  # rótulos (código da peça) no centro da caixa
            cod = pc["nome"].split()[0]
            ctr = pc["caixa"].center()
            x, y = area.left() + ctr.x() * esc, area.top() + ctr.y() * esc
            texto(x - 10, y - 1.2, cod, 5.5, True, "#000", 20, Qt.AlignHCenter)
        # ordem das camadas e tempo
        x0, y = 188, 16
        texto(x0, y, "ORDEM DE EXECUÇÃO", 10, True)
        y += 7
        total = 0.0
        for ordem, c in enumerate(camadas, 1):
            comp = sum(cam.length() for pc in pecas for cam, lid, _ in pc["partes"] if lid == c["id"])
            if not comp:
                continue
            seg = comp * c["passadas"] / c["velocidade_mm_min"] * 60
            total += seg
            p.fillRect(QRectF(x0, y - 0.3, 4, 4), QColor(next((cor for pc in pecas for _, lid, cor in pc["partes"]
                                                               if lid == c["id"]), "#888")))
            texto(x0 + 6, y, f"{ordem}. {c['id']} — {c['nome']}", 8.5, True, larg=85)
            texto(x0 + 6, y + 4.5, f"{MODOS.get(c['modo'], c['modo'])} · {_n(c['velocidade_mm_min'], 0)} mm/min · "
                                   f"{_n(c['potencia_max'], 0)} % · {c['passadas']} passada(s)", 7.5, cor="#444", larg=85)
            texto(x0 + 6, y + 8.5, f"{_n(comp / 1000, 2)} m de linha · ≈ {_tempo(seg)}", 7.5, cor="#444", larg=85)
            y += 15
        total_geral += total
        texto(x0, y, f"Tempo estimado da aba: ≈ {_tempo(total)}", 9, True)
        texto(x0, y + 4.5, "(só o tempo cortando; deslocamentos e aceleração somam mais)", 7, cor="#777", larg=85)
        y += 13
        texto(x0, y, "ANTES DE APERTAR INICIAR", 10, True)
        for linha in ("1. Chapa plana, presa e no lugar certo da mesa.", "2. Foco ajustado para a espessura da chapa.",
                      "3. Enquadrar (contorno) antes de cortar.", "4. Assistência de ar ligada no corte.",
                      "5. Nunca deixar a máquina sozinha cortando.",
                      "Valores de velocidade/potência: ponto de partida", "NÃO validado — teste antes."):
            y += 5
            texto(x0, y, linha, 7.8, cor="#333", larg=88)
        texto(0, H + 3, f"Gerado pelo RedBlack Laser {__version__} · {os.path.basename(arquivo)}", 7, cor="#999")

    # lista de peças + notas
    pdf.newPage()
    texto(0, 0, f"LISTA DE PEÇAS — {titulo}", 14, True)
    y = 10
    for x, s in ((0, "Peça"), (95, "Larg. × alt. (mm)"), (135, "Aba")):
        texto(x, y, s, 8.5, True)
    linhas = [(pc["nome"], pc["caixa"], nome) for nome, pecas in folhas for pc in pecas]
    for nome_pc, cx, aba in linhas:
        y += 4.4
        if y > H:
            break
        texto(0, y, nome_pc, 7.8, larg=93)
        texto(95, y, f"{_n(cx.width())} × {_n(cx.height())}", 7.8)
        texto(135, y, aba.split()[0], 7.8)
    texto(0, H + 3, f"{len(linhas)} itens · tempo total estimado ≈ {_tempo(total_geral)} (só corte)", 8, True)
    xn, y = 155, 10
    texto(xn, y, "NOTAS DO PROJETO", 8.5, True)
    f = QFont("Segoe UI")
    f.setPointSizeF(6.8 / px)
    p.setFont(f)
    p.setPen(QColor("#333"))
    p.drawText(QRectF(xn, y + 4, W - xn, H - y), Qt.TextWordWrap, d.get("notas", ""))
    p.end()
    return destino


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])
    arq = sys.argv[1]
    print(gerar(arq, sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(arq)[0] + "_plano_de_corte.pdf"))
