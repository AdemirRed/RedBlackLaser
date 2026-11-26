"""Porta-retrato do cliente Douglas (PDF Carine V2, nome Carine). Uso: python douglas.py entrada.pdf saida.rbl mapa.pdf previa.png"""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPainterPath, QPainterPathStroker, QTransform
from scipy.cluster.hierarchy import DisjointSet
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt, gaussian_filter1d
from skimage.measure import approximate_polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maria_olivia as mo
import presepio as pr
from apollo_emily import caminho
from redblack import camadas as cm, objetos as ob, projeto as pj

NOMES = {"F01": "Frente esquerda", "F02": "Frente direita com o trio",
         "E01": "Espaçador esquerdo", "E02": "Espaçador direito",
         "T01": "Fundo esquerdo", "T02": "Fundo direito", "A01": "Apoio esquerdo",
         "A02": "Apoio direito", "N01": "Nome Carine", "J01": "Tala inferior",
         "J02": "Tala vertical"}


def ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def posicionar(p, x, y, ang=0):
    p = QTransform().rotate(ang).map(p)
    r = p.boundingRect()
    return p.translated(x-r.x(), y-r.y())


def nome(desenho, caixa):
    """O aplique "Carine" da chapa 01 do PDF (1:1, 196 × 55), levado à caixa dele no desenho montado (pág. 1):
    o pé das letras pousa ~7 mm na borda de cima de F02, 2 mm acima da janela da foto."""
    fora, furos = mo._fora_e_furos(posicionar(caminho(desenho), caixa.x(), caixa.y()))
    if abs(fora.boundingRect().width() - caixa.width()) > 0.5:
        raise ValueError("aplique do nome com outra largura que a do desenho montado")
    return fora, [h for h in furos if pr._area(h) >= 15]


def _encadear(linhas, tol=0.05):
    """Emenda os pedacinhos que se tocam (ponta com ponta) em traços contínuos. O PDF vem picado (5381 pedaços, metade
    < 0,6 mm): cada pedaço é um liga/desliga do laser, com pontinho na emenda e traço desigual. Onde 3+ pedaços se
    encontram, segue pelo que continua mais reto."""
    pontas = np.concatenate([[l[0], l[-1]] for l in linhas])
    nos = DisjointSet(range(len(pontas)))
    for a, b in cKDTree(pontas).query_pairs(tol):
        nos.merge(a, b)
    no = [nos[i] for i in range(len(pontas))]
    junto = {}
    for i in range(len(pontas)):
        junto.setdefault(no[i], []).append(i)  # ponta i = pedaço i // 2, início (par) ou fim (ímpar)

    def direcao(i):  # direção saindo do nó pela ponta i
        l = linhas[i // 2] if i % 2 == 0 else linhas[i // 2][::-1]
        v = l[min(len(l) - 1, 3)] - l[0]
        return v / (np.linalg.norm(v) or 1)

    usado = np.zeros(len(linhas), bool)

    def seguir(i):  # sai pela ponta i (do pedaço já usado) e anda enquanto houver continuação
        trecho = []
        while True:
            livres = [j for j in junto[no[i]] if j != i and not usado[j // 2]]
            if not livres:
                return trecho
            d = direcao(i)
            j = min(livres, key=lambda j: float(np.dot(d, direcao(j))))  # mais oposto à chegada = mais reto
            if np.dot(d, direcao(j)) > 0.3:  # dobra fechada demais (> ~107°): é outro traço
                return trecho
            usado[j // 2] = True
            l = linhas[j // 2] if j % 2 == 0 else linhas[j // 2][::-1]
            trecho.append(l[1:])
            i = j ^ 1  # sai pela outra ponta do pedaço
    saida = []
    for k in np.argsort([-len(l) for l in linhas]):
        if usado[k]:
            continue
        usado[k] = True
        frente = seguir(2 * k + 1)
        tras = seguir(2 * k)
        # os de trás foram andados a partir do início do pedaço: invertidos, vêm antes dele
        saida.append(np.concatenate(([np.concatenate(tras)[::-1]] if tras else []) + [linhas[k]] + frente))
    return saida


def _sem_po(linhas, minimo=0.6, perto=0.3):
    """Tira o pó do traçado: traço com menos de `minimo` mm que não encosta (a `perto` mm) em nenhum outro vira um
    pontinho queimado solto. Os tracinhos que fazem parte de um desenho (sobrancelha, dentes) encostam e ficam."""
    comp = [np.linalg.norm(np.diff(l, axis=0), axis=1).sum() for l in linhas]
    pontos = np.concatenate(linhas)
    dono = np.repeat(np.arange(len(linhas)), [len(l) for l in linhas])
    arvore = cKDTree(pontos)
    fica = []
    for i, l in enumerate(linhas):
        if comp[i] >= minimo or any(dono[j] != i for v in arvore.query_ball_point(l, perto) for j in v):
            fica.append(l)
    return fica


def _alisar(pts, sigma=0.25, passo=0.05):
    """Tira o degrau/tremido da vetorização (σ 0,25 mm: o cabelo fica liso e olhos, dentes e óculos continuam
    nítidos — conferido ampliado), mantendo as pontas no lugar."""
    dist = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    if dist[-1] < 4 * sigma:
        return pts
    t = np.linspace(0, dist[-1], max(2, int(dist[-1] / passo) + 1))
    fechado = np.linalg.norm(pts[0] - pts[-1]) < 0.05
    res = np.column_stack([gaussian_filter1d(np.interp(t, dist, e), sigma / passo, mode="wrap" if fechado else "nearest")
                           for e in pts.T])
    if not fechado:
        res[[0, -1]] = pts[[0, -1]]
    return res


def retrato(desenhos, cont):
    # O PDF divide mechas, óculos e rugas em segmentos que partilham extremidades: emendar e alisar antes de tudo.
    # Avaliar o tamanho do componente, nunca a área de um traço aberto isoladamente.
    linhas = [np.array([(a.x(), a.y()) for a in caminho(d).toSubpathPolygons()[0]])
              for d in desenhos]
    linhas = [_alisar(l) for l in _sem_po(_encadear(linhas))]
    grupos = DisjointSet(range(len(linhas)))
    # Alguns fios terminam no meio de outro traço; preservar vizinhos a 0,25 mm.
    pontos = np.concatenate(linhas)
    donos = np.repeat(np.arange(len(linhas)), [len(l) for l in linhas])
    arvore = cKDTree(pontos)
    for i, pts in enumerate(linhas):
        for vizinhos in arvore.query_ball_point(pts[[0, -1]], 0.25):
            for outro in np.unique(donos[vizinhos]):
                grupos.merge(i, int(outro))
    caixa = cont.boundingRect().adjusted(-3, -3, 3, 3)
    res = 6
    distancia = distance_transform_edt(pr._raster([cont], caixa, res=res)) / res
    origem = np.array([caixa.x(), caixa.y()])
    trechos = []
    for indices in grupos.subsets():
        pontos = np.concatenate([linhas[i] for i in indices])
        w, h = np.ptp(pontos, axis=0)
        if w*h < 0.8 and max(w, h) < 2:
            continue
        for i in sorted(indices):
            pts = linhas[i]
            # Verificar também o meio de segmentos longos antes de gravar perto do corte.
            seg = np.diff(pts, axis=0)
            dist = np.r_[0, np.cumsum(np.linalg.norm(seg, axis=1))]
            t = np.union1d(dist, np.arange(0, dist[-1], 0.4))
            amostra = np.column_stack([np.interp(t, dist, eixo) for eixo in pts.T])
            x, y = ((amostra-origem)*res).astype(int).T
            ok = distancia[y, x] >= 1.85
            for trecho in np.split(amostra[ok], np.flatnonzero(np.diff(np.flatnonzero(ok)) > 1)+1):
                if len(trecho) < 2:
                    continue
                trechos.append(approximate_polygon(trecho, 0.015))
    saida = QPainterPath()
    for trecho in _ordenar(trechos):
        saida.moveTo(*trecho[0])
        for ponto in trecho[1:]:
            saida.lineTo(*ponto)
    return saida


def _ordenar(trechos):
    """Ordem de gravação: o próximo traço é o que tem uma ponta mais perto de onde o laser parou (entrando por ela).
    O RedBlack grava os subcaminhos de um objeto na ordem do arquivo; sem isto o cabeçote cruzava o retrato
    entre um traço e outro (trio: 11 min, dos quais ~7 só de deslocamento)."""
    inicio = np.array([t[0] for t in trechos])
    fim = np.array([t[-1] for t in trechos])
    livre = np.ones(len(trechos), bool)
    pos = inicio[np.argmin(inicio[:, 1] * 1e3 + inicio[:, 0])]  # começa no traço mais de cima
    out = []
    for _ in range(len(trechos)):
        di = np.where(livre, np.hypot(*(inicio - pos).T), np.inf)
        df = np.where(livre, np.hypot(*(fim - pos).T), np.inf)
        i, j = int(np.argmin(di)), int(np.argmin(df))
        t = trechos[i] if di[i] <= df[j] else trechos[j][::-1]
        livre[i if di[i] <= df[j] else j] = False
        out.append(t)
        pos = t[-1]
    return out


def ler(pdf):
    with pymupdf.open(pdf) as doc:
        vista = doc[0].get_drawings()
        esq, dir_, fundos, esp = [doc[i].get_drawings() for i in range(5, 9)]
    # Coordenadas de montagem relativas ao canto superior esquerdo de F01.
    modelos = {"F01": (esq[1], 0, 0, 0), "F02": (dir_[0], 165.7, 60, 0),
               "T01": (fundos[0], 0, 0, 0), "T02": (fundos[1], 168, 60, -90),
               "E01": (esp[0], 0, 5, 0), "E02": (esp[1], 168, 65, 180),
               "J01": (esp[2], 145.5, 216, 0), "A01": (esq[3], 0, 0, 0),
               "A02": (esq[4], 0, 0, 0)}
    pecas = {}

    def peca(k, cont, furos=()):
        pecas[k] = {"cont": cont, "partes": [(cont, "cont")] + [(h, "furo") for h in furos]}

    for k, (d, x, y, ang) in modelos.items():
        cont, furos = mo._fora_e_furos(posicionar(caminho(d), x, y, ang))
        if k == "F02":
            # Alisar apenas o perfil orgânico, conservando dentes, janelas e borda ondulada.
            pts = np.array([(a.x(), a.y()) for a in cont.toSubpathPolygons()[0]])
            perfil = np.flatnonzero(pts[:, 0] > 394.1)
            assert np.all(np.diff(perfil) == 1), "Perfil do trio inesperado"
            i, j = perfil[0]-1, perfil[-1]+1
            segmento = pts[i:j+1]
            dist = np.r_[0, np.cumsum(np.linalg.norm(np.diff(segmento, axis=0), axis=1))]
            t = np.linspace(0, dist[-1], round(dist[-1]/0.1)+1)
            liso = np.column_stack([gaussian_filter1d(np.interp(t, dist, eixo), 3, mode="nearest")
                                    for eixo in segmento.T])
            liso[[0, -1]] = segmento[[0, -1]]
            cont = QPainterPath()
            cont.addPolygon([QPointF(*pt) for pt in np.vstack((pts[:i], approximate_polygon(liso, 0.025), pts[j+1:]))])
            cont.closeSubpath()
            coracoes = [mo._coracao(h.boundingRect()) for h in furos if pr._area(h) < 100]
        if k in ("F02", "E02", "T02"):
            furos = [h for h in furos if pr._area(h) > 100] + coracoes
        peca(k, cont, furos)
    peca("J02", ret(160, 75, 16, 115))
    # A escala da vista é calculada pela largura física de F01 na prancha de corte.
    ref = caminho(vista[1]).boundingRect()
    escala = pecas["F01"]["cont"].boundingRect().width()/ref.width()
    tf = QTransform.fromTranslate(-ref.x(), -ref.y()) * QTransform.fromScale(escala, escala)
    peca("N01", *nome(esq[0], tf.map(caminho(vista[4])).boundingRect()))
    assento = mo._rebaixo_limpo([pecas["N01"]["cont"]])
    for k in ("F01", "F02"):
        v = pecas[k]
        util = mo._area_util(v["cont"], [p for p, t in v["partes"] if t == "furo"])
        parte = assento.intersected(util)
        if not parte.isEmpty():
            v["partes"].append((parte, "rebaixo"))
    for d in vista[5:8]:
        linha = tf.map(caminho(d))
        k = "F01" if linha.boundingRect().center().x() < 168 else "F02"
        pecas[k]["partes"].append((linha, "linha"))
    cont_pdf = pecas["F02"]["cont"].translated(-160.7, -55)
    trio = retrato(dir_[1:], cont_pdf).translated(160.7, 55)
    pecas["F02"]["partes"].append((trio, "linha"))
    return pecas


NOTAS = """Douglas | MDF 3 mm | Frente 500 × 233 mm. Mesa 365 × 370 mm, margem e separação mínimas 2 mm.
C10: assento do nome +0,10 mm por lado, preenchimento 1500 mm/min, 60%, 1 passada, linhas a cada 0,15 mm.
C04: o trio tem traços abertos. Seguir cada linha preserva cabelo, óculos e sorrisos. Trio e ondas: 2000 mm/min, 35%, 1 passada. Testar contraste em retalho do mesmo MDF.
C05/C06: miolos e contornos dentro das janelas. C02: janelas e vazados. C01: contornos por último. Todos os cortes: 630 mm/min, 85%, 2 passadas.
Montagem (medidas a partir do canto superior esquerdo da frente, olhando pela frente):
1. Unir F01 e F02 na emenda em V em x168, sem folga adicionada. Colar e prensar em superfície plana.
2. Colar E01/E02 atrás das respectivas frentes com os U abertos para cima. Alinhar as bases onduladas e os dois corações com T01/T02 antes de colar os fundos. Manter cola fora dos canais.
3. Colar J01 horizontal (45 × 9) e J02 vertical (16 × 115) NA FACE EXTERNA DOS FUNDOS já colados. Centrar ambas na junta. J01 começa 216 mm abaixo do topo de F01 e J02 a 75 mm. As talas ligam os dois fundos à estrutura sem entrar nos canais. Colagem plana no verso, sem rebaixo.
4. Colar A01 em T01 e A02 em T02 afastados das talas e entradas. Regular a inclinação com os dois pés na mesa antes da cura.
5. Colar N01 Carine no assento superior de F02. Os pontos mais baixos avançam 7 mm na borda. Inserir pelo topo fotos 150 × 210 e 210 × 150 mm."""


def previa(pecas, chapas, png):
    # A vista montada usa os mesmos vetores e coordenadas do arquivo de corte.
    img = QImage(2850, 2340, QImage.Format_RGB32)
    img.fill(QColor("#252322"))
    pt = QPainter(img)
    pt.setRenderHint(QPainter.Antialiasing)
    f = QFont("Arial")
    f.setPixelSize(48)
    pt.setFont(f)
    pt.setPen(QColor("#f7e9d3"))
    pt.drawText(72, 75, "Douglas   /   MDF 3 mm")
    pt.save()
    pt.translate(165, 110)
    pt.scale(5, 5)
    for k in ("F01", "F02", "N01"):
        partes = pecas[k]["partes"]
        solido = mo._area_util(pecas[k]["cont"], [h for h,t in partes if t == "furo"])
        pt.setPen(QPen(QColor("#805734"), 0.24))
        pt.setBrush(QColor("#c68b56" if k == "N01" else "#e2ba85"))
        pt.drawPath(solido)
        pt.setPen(QPen(QColor("#513423"), 0.18))
        pt.setBrush(Qt.NoBrush)
        for h, t in partes:
            if t == "linha":
                pt.drawPath(h)
    pt.restore()
    for i, chapa in enumerate(chapas):
        pt.save()
        pt.translate(24 + 948*i, 1380)
        pt.setPen(QColor("#f7e9d3"))
        pt.drawText(0, -20, f"Chapa {i+1}")
        pt.scale(2.45, 2.45)
        pr._desenhar_chapa(pt, chapa)
        pt.restore()
    pt.end()
    if not img.save(str(png)):
        raise OSError(f"Falha ao salvar {png}")


def gerar(pdf, saida, mapa, png):
    pecas = ler(pdf)
    with patch.dict(pr.TIPO_CAMADA, rebaixo="C10"):
        chapas = pr.folhas(pecas, pr.encaixar(pecas))
    snaps = []
    for chapa in chapas:
        grupos = []
        for k, partes, _ in chapa:
            g = ob.group([ob.Shape(p, f"{k} {t}", lid, cm.cor(lid)) for p, lid, t in partes])
            g.name = f"{k} {NOMES[k]}"
            grupos.append(g.snapshot())
        snaps.append(tuple(grupos))
    rebaixo, _, *cortes = mo.camadas()
    rebaixo = mo.rebaixo_rapido(rebaixo)
    linha = cm.alterar(cm.Camada("C04", "Trio e ondas"), modo="linha", velocidade_mm_min=2000,
                       potencia_min=0, potencia_max=35, passadas=1)
    pj.save(str(saida), snaps[0], [rebaixo, linha, *cortes], notas=NOTAS,
            paginas=[None] + [(s, (), ()) for s in snaps[1:]], pagina_atual=0,
            nomes_paginas=[f"Chapa {i+1}" for i in range(len(chapas))])
    # Os centros das caixas dos apoios triangulares quase coincidem na janela.
    # Rotular cada apoio dentro do próprio triângulo, tanto no mapa como na prévia.
    desenhar = pr._desenhar_chapa

    def rotular(pt, chapa):
        desenhar(pt, chapa, rotulos=False)
        f = QFont("Arial")
        f.setPixelSize(7)
        f.setBold(True)
        pt.setFont(f)
        for k, partes, _ in chapa:
            cont = next(p for p, _, t in partes if t == "cont")
            r = cont.boundingRect()
            centro = r.center()
            if k in ("A01", "A02"):
                q = list(cont.toSubpathPolygons()[0])[:3]
                centro = (q[0] + q[1] + q[2])/3
            if k == "N01":
                centro = QPointF(r.left()+12, r.top()+4)
            caixa = QRectF(centro.x()-9, centro.y()-4, 18, 8)
            pt.fillRect(caixa, QColor("#fff0d7"))
            pt.setPen(QColor("#23543a"))
            pt.drawText(caixa, Qt.AlignCenter, k)

    with patch.object(pr, "_desenhar_chapa", rotular):
        previa(pecas, chapas, png)
    with TemporaryDirectory() as tmp, patch.dict(pr.NOMES, NOMES), patch.object(pr, "_desenhar_chapa", rotular):
        base = str(Path(tmp)/"mapa.pdf")
        pr.mapa_pdf(chapas, [pr.aproveitamento(c) for c in chapas], base)
        with pymupdf.open(base) as doc:
            for i, pg in enumerate(doc):
                titulo = pg.search_for("PRESÉPIO")[0]
                pg.add_redact_annot(pymupdf.Rect(20, titulo.y0-1, pg.rect.width-20, titulo.y1+1))
                pg.apply_redactions()
                pg.insert_text((34, titulo.y1-3), f"Douglas | MDF 3 mm | Chapa {i+1} de {len(chapas)}",
                               fontsize=16, fontname="hebo")
            doc.save(str(mapa), garbage=4, deflate=True)
    return [[k for k, *_ in c] for c in chapas]


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", r"C:\Windows"))/"Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(*sys.argv[1:]))
