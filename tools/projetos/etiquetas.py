"""Grava o código de cada peça (L1, P1, G3...) dentro da própria peça, para saber onde vai na montagem.

Para cada peça (grupo de topo cujo nome começa com o código, ex.: "G3 Guia 52 × 5") procura, no sistema da própria
peça (gira junto se a peça foi girada na mesa), o lugar livre mais central onde o texto cabe: dentro do contorno,
a MARGEM da borda e longe de furos, rasgos e linhas gravadas. Tenta a altura maior primeiro (de 6 a 1,8 mm), em pé
ou deitado. As letras vão numa camada própria de gravação superficial (padrão 3000 mm/min, 15 %, preenchimento),
que sai ANTES dos cortes, e também numa aba "SÓ LETRAS" para gravar numa chapa já cortada, sem movê-la.

Executar:  python tools/projetos/etiquetas.py <entrada.rbl> <saida.rbl>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402

CAMADA = "C09"
MARGEM = 0.75                     # da borda da peça e de furos/rasgos/linhas (mm)
ALTURAS = (6.0, 5.0, 4.0, 3.5, 3.0, 2.5, 2.0, 1.8)
FONTE = "Arial"
CODIGO = re.compile(r"^([A-Z]{1,3}\d{0,2})\b")


def matriz(o):
    return QTransform(*o["matriz"])


def folhas(o, tf=QTransform()):
    """[(caminho no sistema da peça, camada)] — compõe as matrizes dos filhos até a raiz da peça."""
    if o["tipo"] == "grupo":
        return [f for c in o["filhos"] for f in folhas(c, matriz(c) * tf)]
    p = pj.list_to_path(o["caminho"], o.get("preenchimento") == "winding")
    return [(tf.map(p), o["camada"])]


def _engrossar(p, w):
    s = QPainterPathStroker()
    s.setWidth(w)
    return s.createStroke(p)


def area_livre(partes, cortes):
    """Contorno externo (o de maior caixa entre os cortes) menos a margem, os furos e as linhas."""
    fechados = [p for p, lid in partes if lid in cortes]
    cont = max(fechados, key=lambda p: p.boundingRect().width() * p.boundingRect().height())
    livre = cont.subtracted(_engrossar(cont, 2 * MARGEM))
    for p, lid in partes:
        if p is cont:
            continue
        livre = livre.subtracted(p.united(_engrossar(p, 2 * MARGEM)) if lid in cortes else _engrossar(p, 2 * MARGEM))
    return livre


def posicionar(livre, textos, passo=0.5):
    """(texto, altura, QTransform do texto) no ponto livre mais central; None se não couber nem a 1,8 mm."""
    r = livre.boundingRect()
    c = r.center()
    nx, ny = int(r.width() / passo) + 1, int(r.height() / passo) + 1
    pontos = sorted((QPointF(r.left() + i * passo, r.top() + j * passo) for i in range(nx) for j in range(ny)),
                    key=lambda p: (p - c).manhattanLength())
    pontos = [p for p in pontos if livre.contains(p)]
    # texto completo (ex.: "B2 FRENTE") até 3 mm; se não couber, só o código, até a menor altura
    tentativas = [(t, h) for t in textos[:-1] for h in ALTURAS if h >= 3.0] + [(textos[-1], h) for h in ALTURAS]
    for t, h in tentativas:
        caixa = tx.build_path(tx.TextoParams(t, FONTE, h, negrito=True, alinhamento="centro")).boundingRect()
        for ang in (0, 90):
            w, hh = (caixa.width(), caixa.height()) if ang == 0 else (caixa.height(), caixa.width())
            for p in pontos:
                if livre.contains(QRectF(p.x() - w / 2, p.y() - hh / 2, w, hh)):
                    tf = (QTransform.fromTranslate(-caixa.center().x(), -caixa.center().y())
                          * QTransform().rotate(ang) * QTransform.fromTranslate(p.x(), p.y()))
                    return t, h, tf
    return None


def etiquetar_pagina(objs, cortes, extras=None):
    """Objetos de texto (dicts do .rbl) com o código de cada peça; e os códigos que não couberam."""
    novos, sem_lugar = [], []
    for o in objs:
        m = CODIGO.match(o.get("nome", ""))
        if not m or o["tipo"] != "grupo":
            continue
        cod = m.group(1)
        textos = ([extras[cod]] if extras and cod in extras else []) + [cod]
        res = posicionar(area_livre(folhas(o), cortes), textos)
        if res is None:
            sem_lugar.append(cod)
            continue
        t, h, tf_local = res
        prm = tx.TextoParams(t, FONTE, h, negrito=True, alinhamento="centro")
        snap = (tx.build_path(prm), tf_local * matriz(o), f"Letra {cod}", CAMADA, cm.cor(CAMADA), prm)
        novos.append(pj._obj_to_dict(snap))
    return novos, sem_lugar


def camada_letras():
    c = cm.alterar(cm.Camada(CAMADA, "Letras das peças (gravação superficial, 1º)"), modo="preenchimento",
                   velocidade_mm_min=3000.0, potencia_max=15.0, potencia_min=0.0, passadas=1)
    import dataclasses
    return dataclasses.asdict(c)


def etiquetar(entrada, saida, extras=None):
    if not tx.font_available(FONTE):  # sem a fonte o Qt desenha quadradinhos no lugar das letras
        raise RuntimeError(f"Fonte {FONTE} não encontrada (rodando sem tela? defina QT_QPA_FONTDIR)")
    with open(entrada, encoding="utf-8") as f:
        d = json.load(f)
    cortes = {c["id"] for c in d["camadas"] if c["modo"] == "linha" and "Grava" not in c["nome"]}
    d["camadas"] = [camada_letras()] + [c for c in d["camadas"] if c["id"] != CAMADA]
    ps = d.get("paginas") or [None]
    nomes = d.get("nomes_paginas") or [f"Página {i + 1}" for i in range(len(ps))]
    relatorio, so_letras = {}, []
    for i, p in enumerate(ps):
        objs = d["objetos"] if p is None else p["objetos"]
        novos, sem = etiquetar_pagina(objs, cortes, extras)
        objs.extend(novos)
        relatorio[nomes[i]] = (len(novos), sem)
        if novos:
            so_letras.append(({"objetos": json.loads(json.dumps(novos))}, f"SÓ LETRAS de {nomes[i]} (não mover a chapa)"))
    d["paginas"] = ps + [p for p, _ in so_letras]
    d["nomes_paginas"] = nomes + [n for _, n in so_letras]
    d.setdefault("pagina_atual", 0)
    with open(saida, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return relatorio


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(etiquetar(sys.argv[1], sys.argv[2]))
