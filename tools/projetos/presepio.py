"""Presépio (MDF 3 mm) a partir do PDF "Presepio_MDF_3mm_Projeto_Completo.pdf" (revisão 02), com as chapas reencaixadas.

O PDF traz as 17 peças em 3 páginas vetoriais 1:1 de 370 × 365 mm (vermelho = contorno, azul = vazados e rasgos,
preto traço = gravação de linha, preto cheio = gravação das figuras; códigos em texto). Aqui:
  - as peças ficam iguais ao projeto (encaixes de 3,00 mm, linguetas, tudo do PDF, sem escala);
  - o encaixe é refeito do zero (mesa 365 × 370, 2 mm da borda e 2 mm entre peças): as peças grandes primeiro e as
    pequenas também DENTRO dos vazados (vão da fachada, triângulos das laterais, cercas do fundo), que virariam sobra;
  - peça dentro de um vazado corta ANTES do vazado (camadas próprias): o miolo solto não arrasta a peça;
  - o código de cada peça é gravado nela (etiquetas.py) e os números do gabarito G01 viram gravação.

Executar:  python tools/projetos/presepio.py <entrada.pdf> <saida.rbl>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPainterPathStroker, QTransform  # noqa: E402
from scipy.signal import fftconvolve  # noqa: E402

from apollo_emily import PT, caminho  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

PAGINAS = (13, 14, 15)          # páginas 14–16 do PDF (0 = primeira): as chapas de corte 1:1
MESA_W, MESA_H = 365.0, 370.0   # área da mesa (X × Y)
MARGEM, VAO = 2.0, 2.0          # da borda da chapa e entre peças (mm), pedido do dono
GRAV_VEL, GRAV_POT = 2000.0, 35.0  # gravação das figuras, telhado e números: funda e bem visível
RES = 2.0                       # px por mm no encaixe por grade

NOMES = {"B01": "Base", "F01": "Fachada com estrela", "F02": "Fundo vazado", "L01": "Lateral esquerda",
         "L02": "Lateral direita", "T01": "Telhado esquerdo", "T02": "Telhado direito", "P01": "Maria",
         "P02": "Jesus e manjedoura", "P03": "José", "P04": "Melchior", "P05": "Baltazar", "P06": "Gaspar",
         "P07": "Ovelha", "P08": "Palmeira", "G01": "Gabarito de folgas", "G02": "Lingueta de teste"}

# camada: (nome, tipo). Ordem de saída = ordem desta lista.
CORTE_DENTRO_FURO, CONT_DENTRO, FURO, CONT = "C05", "C06", "C02", "C01"
GRAV_FIG, GRAV_LINHA, GRAV_NUM = "C03", "C04", "C07"
MARCA = "C08"  # contornos marcados de leve na chapa ANTES de pintar (abas "MARCA"): mostram onde pintar
CAMADAS = [(GRAV_FIG, "Gravação das figuras (preenchida, 1º)", "grav_fig"),
           (GRAV_LINHA, "Gravação de traço: telhado, estrela, folhas (2º)", "grav_linha"),
           (GRAV_NUM, "Números do gabarito G01 (gravação)", "grav_fig"),
           (CORTE_DENTRO_FURO, "Rasgos das peças que estão DENTRO de vazados (3º)", "corte"),
           (CONT_DENTRO, "Contorno das peças DENTRO de vazados (4º, antes do vazado)", "corte"),
           (FURO, "Vazados e rasgos (5º)", "corte"),
           (CONT, "Contornos externos (por último)", "corte"),
           (MARCA, "MARCA para pintar (só nas abas MARCA: 8000 mm/min, 80 %)", "marca")]


def _cor(c):
    return tuple(round(v, 1) for v in c) if c else None


def ler(pdf):
    """{código: {"partes": [(path mm, tipo)], "caixa": QRectF}} — tipo: cont, furo, linha, cheio, num."""
    doc = pymupdf.open(pdf)
    pecas = {}
    for n in PAGINAS:
        pg = doc[n]
        itens = []
        for d in pg.get_drawings():
            if d["type"] == "f":
                itens.append((caminho({**d, "closePath": True}), "cheio"))
            elif _cor(d.get("color")) == (1.0, 0.0, 0.0):
                itens.append((caminho(d), "cont"))
            elif _cor(d.get("color")) == (0.0, 0.0, 1.0):
                itens.append((caminho(d), "furo"))
            else:
                itens.append((caminho(d), "linha"))
        conts = [p for p, t in itens if t == "cont"]
        textos = [(s["text"].strip(), QRectF(*[v * PT for v in s["bbox"][:2]],
                                             (s["bbox"][2] - s["bbox"][0]) * PT, (s["bbox"][3] - s["bbox"][1]) * PT),
                   s["size"]) for b in pg.get_text("dict")["blocks"] for ln in b.get("lines", [])
                  for s in ln["spans"] if s["text"].strip()]

        def dono(r):
            c = r.center()
            cands = [p for p in conts if p.boundingRect().contains(c)]
            return min(cands, key=lambda p: p.boundingRect().width() * p.boundingRect().height()) if cands else None

        por_cont = {id(p): {"partes": [], "codigo": None} for p in conts}
        for p, t in itens:
            alvo = p if t == "cont" else dono(p.boundingRect())
            if alvo is None:
                raise ValueError(f"desenho fora de qualquer peça na página {n + 1}: {p.boundingRect()}")
            por_cont[id(alvo)]["partes"].append((p, t))
        for txt, r, tam in textos:
            alvo = dono(r)
            if alvo is None:
                continue
            if re.fullmatch(r"[A-Z]\d\d", txt):
                por_cont[id(alvo)]["codigo"] = txt
            else:  # números do gabarito de folgas: gravados
                por_cont[id(alvo)]["partes"].append((_texto(txt, r, tam * PT), "num"))
        for p in conts:
            info = por_cont[id(p)]
            if info["codigo"] is None:
                raise ValueError(f"peça sem código na página {n + 1}: {p.boundingRect()}")
            caixa = QRectF()
            for q, _ in info["partes"]:
                caixa = caixa.united(q.boundingRect())
            pecas[info["codigo"]] = {"partes": info["partes"], "caixa": caixa}
    doc.close()  # aberto e esquecido várias vezes estourava o limite de arquivos abertos (testes)
    return pecas


def _texto(txt, r, alt_mm):
    """Texto do PDF -> contorno (Arial) centrado na mesma caixa."""
    f = QFont("Arial")
    f.setPixelSize(100)
    p = QPainterPath()
    p.addText(0, 0, f, txt)
    esc = alt_mm * 0.72 / 100  # altura das maiúsculas ≈ 72 % do corpo
    p = QTransform.fromScale(esc, esc).map(p)
    b = p.boundingRect()
    return QTransform.fromTranslate(r.center().x() - b.center().x(), r.center().y() - b.center().y()).map(p)


def _recortar_linhas(partes, caixa):
    """Gravação de traço só dentro do contorno (o telhado do PDF passa 1 mm da borda: queimaria a peça vizinha)."""
    r = caixa.adjusted(0.6, 0.6, -0.6, -0.6)
    out = []
    for p, t in partes:
        if t != "linha" or r.contains(p.boundingRect()):
            out.append((p, t))
            continue
        novo = QPainterPath()
        for poly in p.toSubpathPolygons():
            pts = list(poly)
            for a, b in zip(pts, pts[1:]):
                seg = _clip(a, b, r)
                if seg:
                    if novo.elementCount() == 0 or (novo.currentPosition() - seg[0]).manhattanLength() > 1e-6:
                        novo.moveTo(seg[0])
                    novo.lineTo(seg[1])
        if not novo.isEmpty():
            out.append((novo, t))
    return out


def _clip(a, b, r):
    """Liang–Barsky: trecho a→b dentro do retângulo r, ou None."""
    t0, t1 = 0.0, 1.0
    dx, dy = b.x() - a.x(), b.y() - a.y()
    for p, q in ((-dx, a.x() - r.left()), (dx, r.right() - a.x()), (-dy, a.y() - r.top()), (dy, r.bottom() - a.y())):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return QPointF(a.x() + t0 * dx, a.y() + t0 * dy), QPointF(a.x() + t1 * dx, a.y() + t1 * dy)


def limpar(pecas):
    """Tira os rasgos azuis degenerados (tamanho zero ou menores que 1 mm, como o da boca do José, que furaria o
    rosto), recorta as linhas que passam do contorno e desenha o rosto do José (o PDF não tem)."""
    for v in pecas.values():
        cont = next(p for p, t in v["partes"] if t == "cont")
        partes = [(p, t) for p, t in v["partes"]
                  if not (t == "furo" and (min(p.boundingRect().width(), p.boundingRect().height()) < 0.1
                                           or max(p.boundingRect().width(), p.boundingRect().height()) < 1.0))]
        v["partes"] = _recortar_linhas(partes, cont.boundingRect())
        v["cont"] = cont
    if "P03" in pecas:
        pecas["P03"]["partes"].append((rosto_jose(), "cheio"))
    for k, v in pecas.items():  # figuras: corta SÓ por fora (pedido do dono depois de cortar a ovelha)
        if k.startswith("P"):
            nova = silhueta(v)
            v["partes"] = [(nova if t == "cont" else p, t) for p, t in v["partes"] if t != "furo"]
            v["cont"] = nova
    return pecas


FECHA_VAO = 2.5  # mm (raio): vãos de até ~5 mm entre partes da figura viram peça cheia
RODAPE = 5.5     # mm de baixo das figuras (rodapé + lingueta de 3 mm) que não mudam
REFAZER = ("P07",)  # peças com aba própria para cortar de novo num retalho


def silhueta(v, folga=0.6):
    """Contorno de corte = a borda de FORA da figura: o contorno do PDF unido ao desenho gravado (com `folga` mm em
    volta) e sem nenhum buraco. Na ovelha o contorno do PDF entrava pelos vãos da lã e o laser cortava a lã fora,
    sobrando só as linhas. O rodapé e a lingueta continuam exatos (são do contorno original)."""
    from scipy.ndimage import binary_dilation, binary_fill_holes
    from skimage.measure import approximate_polygon, find_contours
    res = 10.0  # px/mm (a união exata de caminhos levava ~50 s por figura)
    caixa = v["cont"].boundingRect().adjusted(-2 * folga, -2 * folga, 2 * folga, 2 * folga)
    gravado = _raster([p for p, t in v["partes"] if t == "cheio"], caixa, res=res)
    m = _raster([v["cont"]], caixa, res=res)[:gravado.shape[0], :gravado.shape[1]]
    m |= binary_dilation(gravado, _disco(int(round(folga * res))))
    # fecha vãos estreitos (lã da ovelha sem borda, entre o cajado e o corpo...): peça inteira, nada de "dedos"
    from scipy.ndimage import binary_closing
    m = binary_closing(np.pad(m, 30), _disco(int(round(FECHA_VAO * res))))[30:-30, 30:-30] | m
    m = binary_fill_holes(m)
    # rodapé + lingueta (5,5 mm de baixo) ficam EXATAMENTE como no projeto: canto arredondado não entra no rasgo
    corte = int((v["cont"].boundingRect().bottom() - RODAPE - caixa.top()) * res)
    m[max(corte, 0):, :] = False
    linha = max(find_contours(np.pad(m, 1).astype(float), 0.5), key=len)  # a borda de fora
    pts = [QPointF(caixa.left() + (x - 1) / res, caixa.top() + (y - 1) / res)
           for y, x in approximate_polygon(linha, 0.4)]
    fora = QPainterPath()
    fora.addPolygon(pts)
    fora.closeSubpath()
    # unido ao contorno original: rodapé e lingueta exatos; os vãos de dentro já foram preenchidos
    polys = fora.united(v["cont"]).simplified().toSubpathPolygons()
    out = QPainterPath()
    out.addPolygon(max(polys, key=lambda q: abs(_area_pts(list(q)))))
    out.closeSubpath()
    return out


def _traco(pontos, larg):
    p = QPainterPath(QPointF(*pontos[0]))
    for i in range(1, len(pontos) - 1, 2):  # curva suave passando pelos pontos (quadráticas pelos pares)
        p.quadTo(QPointF(*pontos[i]), QPointF(*pontos[i + 1]))
    if len(pontos) % 2 == 0:
        p.lineTo(QPointF(*pontos[-1]))
    st = QPainterPathStroker()
    st.setWidth(larg)
    st.setCapStyle(Qt.RoundCap)
    st.setJoinStyle(Qt.RoundJoin)
    return st.createStroke(p)


def rosto_jose():
    """Perfil (olhando para a esquerda), olho e sobrancelha do José, em mm do PDF (página 14): o desenho original
    deixa o rosto em branco entre o turbante e a barba."""
    out = QPainterPath()
    out.setFillRule(Qt.WindingFill)
    perfil = [(102.2, 254.5), (102.0, 255.4), (101.8, 256.3), (101.9, 256.8), (101.95, 257.0), (101.3, 258.0),
              (101.2, 258.5), (101.7, 258.75), (102.15, 258.8), (102.2, 259.3), (102.7, 259.5), (103.2, 259.7),
              (103.4, 259.9)]
    out.addPath(_traco(perfil, 0.45))
    out.addPath(_traco([(102.9, 256.25), (103.8, 255.8), (104.9, 256.1)], 0.45))  # sobrancelha
    olho = QPainterPath()
    olho.moveTo(103.2, 257.15)
    olho.quadTo(103.8, 256.7, 104.4, 257.1)
    olho.quadTo(103.8, 257.45, 103.2, 257.15)
    out.addPath(olho)
    out.addPath(_traco([(102.3, 257.6), (102.7, 258.3), (102.4, 258.6)], 0.3))  # asa do nariz
    return out


# ---------------------------------------------------------------- encaixe por grade (bitmap)
def _raster(paths, caixa, buracos=(), res=None):
    """Bitmap (RES px/mm) da área cheia dos `paths` menos os `buracos`, com a caixa no canto (0, 0)."""
    res = res or RES
    w, h = int(np.ceil(caixa.width() * res)) + 2, int(np.ceil(caixa.height() * res)) + 2
    img = QImage(w, h, QImage.Format_Grayscale8)
    img.fill(0)
    pt = QPainter(img)
    pt.scale(res, res)
    pt.translate(-caixa.left(), -caixa.top())
    pt.setPen(Qt.NoPen)
    for brush, ps in ((Qt.white, paths), (Qt.black, buracos)):
        pt.setBrush(brush)
        for p in ps:
            pt.drawPath(p)
    pt.end()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())[:, :w]
    return a > 0


def _disco(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


GIROS = (0, 90, 180, 270)
FURO_GRANDE = 150.0  # mm²: vazado onde cabe peça (os rasgos de 3 mm continuam "cheios" no encaixe)


def _girar(p, ang):
    return QTransform().rotate(ang).map(p)


def encaixar(pecas, n_chapas=4):
    """Coloca as peças (maiores primeiro) na 1ª chapa onde couberem, também dentro dos vazados das já postas.
    Devolve {código: (chapa, ângulo, dx, dy)}: peça girada `ângulo` em torno da origem e deslocada (dx, dy)."""
    from scipy.ndimage import binary_dilation
    gw, gh = int(MESA_W * RES), int(MESA_H * RES)
    ocupado = [np.zeros((gh, gw), bool) for _ in range(n_chapas)]
    usado = [None] * n_chapas  # caixa (y0, x0, y1, x1) em px do que já está na chapa
    folga = int(np.ceil(VAO * RES)) + 1  # +1 px: o bitmap arredonda
    disco = _disco(folga)
    ordem = sorted(pecas, key=lambda k: -pecas[k]["cont"].boundingRect().width()
                   * pecas[k]["cont"].boundingRect().height())
    pos = {}
    for k in ordem:
        v = pecas[k]
        melhor = None
        for ch in range(n_chapas):
            for ang in GIROS:
                c = _girar(v["cont"], ang)
                cx = c.boundingRect().adjusted(-folga / RES, -folga / RES, folga / RES, folga / RES)
                pe = binary_dilation(_raster([c], cx), disco)  # pegada com o vão em volta
                if pe.shape[0] > gh or pe.shape[1] > gw:
                    continue
                sobre = fftconvolve(ocupado[ch].astype(np.float32), pe[::-1, ::-1].astype(np.float32), mode="valid")
                livres = np.argwhere(sobre < 0.5)
                if not len(livres):
                    continue
                ys, xs = livres[:, 0], livres[:, 1]
                if usado[ch] is None:
                    cresce = np.zeros(len(ys))
                else:  # quanto a caixa ocupada da chapa cresce: dentro de um vazado = 0 (a sobra fica inteira)
                    y0, x0, y1, x1 = usado[ch]
                    cresce = ((np.maximum(y1, ys + pe.shape[0]) - np.minimum(y0, ys))
                              * (np.maximum(x1, xs + pe.shape[1]) - np.minimum(x0, xs)) - (y1 - y0) * (x1 - x0))
                i = np.lexsort((xs, ys + pe.shape[0], cresce))[0]  # menos crescimento, mais acima, à esquerda
                y, x = int(ys[i]), int(xs[i])
                nota = (ch, float(cresce[i]), y + pe.shape[0], x)
                if melhor is None or nota < melhor[0]:
                    melhor = (nota, ch, ang, x / RES - cx.left(), y / RES - cx.top())
            if melhor is not None:
                break
        if melhor is None:
            raise RuntimeError(f"{k} não coube em {n_chapas} chapas")
        nota, ch, ang, dx, dy = melhor
        pos[k] = (ch, ang, dx, dy)
        caixa = (QTransform().rotate(ang) * QTransform.fromTranslate(dx, dy)).map(v["cont"]).boundingRect()
        nova = (caixa.top() * RES, caixa.left() * RES, caixa.bottom() * RES, caixa.right() * RES)
        usado[ch] = nova if usado[ch] is None else (min(usado[ch][0], nova[0]), min(usado[ch][1], nova[1]),
                                                     max(usado[ch][2], nova[2]), max(usado[ch][3], nova[3]))
        tf = QTransform().rotate(ang) * QTransform.fromTranslate(dx, dy)
        buracos = [tf.map(p) for p, t in v["partes"] if t == "furo" and _area(p) > FURO_GRANDE]
        mat = _raster([tf.map(v["cont"])], QRectF(0, 0, MESA_W, MESA_H), buracos)[:gh, :gw]
        ocupado[ch][:mat.shape[0], :mat.shape[1]] |= mat
    return pos


def _area(p):
    return max((abs(sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(q, list(q)[1:] + list(q)[:1]))) / 2
                for q in p.toSubpathPolygons()), default=0.0)


# ---------------------------------------------------------------- montagem do projeto
TIPO_CAMADA = {"cheio": GRAV_FIG, "linha": GRAV_LINHA, "num": GRAV_NUM, "furo": FURO, "cont": CONT}
DESC = {"cheio": "gravação", "linha": "gravação de traço", "num": "números", "furo": "rasgo/vazado",
        "cont": "contorno"}


def folhas(pecas, pos):
    """[[(código, [(path na mesa, camada)])] por chapa]. Peça dentro de vazado de outra: camadas "DENTRO"."""
    n = max(ch for ch, *_ in pos.values()) + 1
    out = [[] for _ in range(n)]
    tfs = {k: QTransform().rotate(a) * QTransform.fromTranslate(dx, dy) for k, (_, a, dx, dy) in pos.items()}
    vazados = {k: [tfs[k].map(p) for p, t in pecas[k]["partes"] if t == "furo" and _area(p) > FURO_GRANDE]
               for k in pecas}
    for k in sorted(pecas):
        ch = pos[k][0]
        meio = tfs[k].map(pecas[k]["cont"]).boundingRect().center()
        dentro = any(h.contains(meio) for o in pecas if o != k and pos[o][0] == ch for h in vazados[o])
        partes = []
        for p, t in pecas[k]["partes"]:
            lid = TIPO_CAMADA[t]
            if dentro and t == "cont":
                lid = CONT_DENTRO
            elif dentro and t == "furo":
                lid = CORTE_DENTRO_FURO
            partes.append((tfs[k].map(p), lid, t))
        out[ch].append((k, partes, dentro))
    return out


def camadas():
    corte = mt.corte_mdf(3)  # 650 mm/min, 85 %, 2 passadas (nunca 100 %)
    out = []
    for lid, nome, tipo in CAMADAS:
        c = cm.Camada(lid, nome)
        if tipo == "grav_fig":  # mais lenta e forte que os 25 % a 3000 (o dono achou rasa e pouco visível, e vai por cima da tinta)
            c = cm.alterar(c, modo="preenchimento", velocidade_mm_min=GRAV_VEL, potencia_max=GRAV_POT, potencia_min=0.0,
                           passadas=1, intervalo_mm=0.1)
        elif tipo == "marca":  # risco rápido, não corta: só mostra o contorno para pintar no lugar certo
            c = cm.alterar(c, modo="linha", velocidade_mm_min=8000.0, potencia_max=80.0, potencia_min=0.0,
                           passadas=1, air=False)
        elif tipo == "grav_linha":
            c = cm.alterar(c, modo="linha", velocidade_mm_min=GRAV_VEL, potencia_max=GRAV_POT, potencia_min=0.0, passadas=1)
        else:
            c = cm.alterar(c, **corte)
        out.append(c)
    return out


def aproveitamento(chapa):
    mat = np.zeros((int(MESA_H * RES), int(MESA_W * RES)), bool)
    for _k, partes, _d in chapa:
        cont = [p for p, _l, t in partes if t == "cont"]
        bur = [p for p, _l, t in partes if t == "furo"]
        m = _raster(cont, QRectF(0, 0, MESA_W, MESA_H), bur)[:mat.shape[0], :mat.shape[1]]
        mat[:m.shape[0], :m.shape[1]] |= m
    return mat.mean()


def gerar(pdf, saida):
    pecas = limpar(ler(pdf))
    pos = encaixar(pecas)
    chapas = folhas(pecas, pos)
    snaps = []
    for chapa in chapas:
        grupos = []
        for k, partes, _dentro in chapa:
            itens = [ob.Shape(p, f"{k} — {DESC[t]}", lid, cm.cor(lid)) for p, lid, t in partes]
            g = ob.group(itens)
            g.name = f"{k} {NOMES[k]}"
            grupos.append(g.snapshot())
            caixa = QRectF()
            for p, _l, _t in partes:
                caixa = caixa.united(p.boundingRect())
            assert QRectF(MARGEM - 0.01, MARGEM - 0.01, MESA_W - 2 * MARGEM + 0.02,
                          MESA_H - 2 * MARGEM + 0.02).contains(caixa), (k, caixa)
        snaps.append(tuple(grupos))
    ap = [aproveitamento(c) for c in chapas]
    nomes = [f"Chapa {i + 1}" for i in range(len(chapas))]  # nome curto (limite da aba); peças nas notas
    dentro = sorted(k for c in chapas for k, _p, d in c if d)
    notas = ("Presépio MDF 3 mm (PDF revisão 02): 17 peças iguais ao projeto, reencaixadas em "
             f"{len(chapas)} chapas de 365 × 370 mm, {MARGEM:g} mm da borda e {VAO:g} mm entre peças.\n"
             + "".join(f"Chapa {i + 1}: " + ", ".join(f"{k} {NOMES[k]}" for k, *_ in sorted(c)) + ".\n"
                       for i, c in enumerate(chapas))
             + "Aproveitamento: " + ", ".join(f"chapa {i + 1} {a:.0%}" for i, a in enumerate(ap)) + ".\n"
             f"Peças dentro dos vazados de outras (sobra que vira peça): {', '.join(dentro) or 'nenhuma'}. "
             "Elas cortam ANTES do vazado (camadas C05 e C06): o miolo solto não arrasta a peça.\n"
             "C09 (códigos das peças) está com a Saída DESLIGADA: as peças saem sem marcação.\n"
             "Ordem: C03 figuras (preenchida 2000 mm/min, 35 %) → C04 telhado, estrela e "
             "folhas (traço 2000 mm/min, 35 %) → C07 números do gabarito → C05/C06 peças dentro de vazados → C02 "
             "vazados e rasgos → C01 contornos. Cortes 650 mm/min, 85 %, 2 passadas.\n"
             "Corte primeiro G01 + G02 (gabarito de folgas 2,80–3,20) e confira o encaixe antes das chapas. "
             "Montagem: siga o guia do PDF (as peças e os códigos são os mesmos).")
    # abas MARCA: os mesmos contornos, nas mesmas posições, para marcar antes de pintar (sem mover a origem)
    # + o limite de cada zona de outra cor (tronco, rosto, capa...), na mesma posição: onde trocar de tinta
    zonas = zonas_de_cor(pecas)
    tfs = {k: QTransform().rotate(a) * QTransform.fromTranslate(dx, dy) for k, (_c, a, dx, dy) in pos.items()}
    marcas = [tuple([ob.Shape(p, f"Marca {k}", MARCA, cm.cor(MARCA)).snapshot()
                     for k, partes, _d in c for p, _l, t in partes if t == "cont"]
                    + [ob.Shape(tfs[k].map(area), f"Marca {k} {nome} ({cor.lower()})", MARCA, cm.cor(MARCA)).snapshot()
                       for k, _p, _d in c for cor, nome, area in zonas.get(k, ())]) for c in chapas]
    nomes += [f"MARCA p/ pintar — chapa {i + 1}" for i in range(len(chapas))]
    notas += ("\nPINTAR ANTES: rode a aba \"MARCA p/ pintar — chapa N\" (contornos e limites entre as cores, 8000 mm/min, 80 %; veja o GUIA DE PINTURA), tire a "
              "chapa, pinte dentro das marcas, encoste a chapa de volta EXATAMENTE no mesmo lugar (no batente/esquadro "
              "da mesa, sem mexer na origem) e rode a aba \"Chapa N\" para gravar e cortar.")
    # peças para REFAZER sozinhas num retalho (a ovelha saiu quebrada com o corte por dentro do PDF), em pé, no canto
    sozinhas, marcas_sozinhas = [], []
    for k in REFAZER:
        c = pecas[k]["cont"].boundingRect()
        # canto de baixo à esquerda = origem da máquina: o retalho vai encostado no batente da origem
        tf = QTransform.fromTranslate(MARGEM - c.left(), MESA_H - MARGEM - c.height() - c.top())
        g = ob.group([ob.Shape(tf.map(p), f"{k} — {DESC[t]}", TIPO_CAMADA[t], cm.cor(TIPO_CAMADA[t]))
                      for p, t in pecas[k]["partes"]])
        g.name = f"{k} {NOMES[k]}"
        sozinhas.append((g.snapshot(),))
        marcas_sozinhas.append(tuple([ob.Shape(tf.map(pecas[k]["cont"]), f"Marca {k}", MARCA, cm.cor(MARCA)).snapshot()]
                                     + [ob.Shape(tf.map(a), f"Marca {k} {n}", MARCA, cm.cor(MARCA)).snapshot()
                                        for _c, n, a in zonas.get(k, ())]))
        nomes += [f"Refazer {NOMES[k].lower()} (retalho)", f"MARCA p/ pintar — {NOMES[k].lower()}"]
    extras = [x for par in zip(sozinhas, marcas_sozinhas) for x in par]
    pj.save(saida, snaps[0], camadas(), notas=notas,
            paginas=[None] + [(s, (), ()) for s in snaps[1:] + marcas + extras], pagina_atual=0, nomes_paginas=nomes)
    import etiquetas
    etiquetas.etiquetar(saida, saida)
    _letras_25(saida)
    return saida, ap, nomes, dentro, chapas


def _letras_25(caminho_rbl):
    """Códigos a 25 % (a 15 % não aparecem a 3000 mm/min), mas com a Saída DESLIGADA: o dono não quer as peças
    prontas marcadas (o código fica só no desenho, para conferir; ligue a Saída se quiser gravar)."""
    import json
    with open(caminho_rbl, encoding="utf-8") as f:
        d = json.load(f)
    for c in d["camadas"]:
        if c["id"] == "C09":
            c.update(potencia_max=25.0, saida=False, nome="Códigos das peças (SAÍDA DESLIGADA: não grava)")
    manter = [i for i, n in enumerate(d["nomes_paginas"]) if not n.startswith("SÓ LETRAS")]
    d["paginas"] = [d["paginas"][i] for i in manter]
    d["nomes_paginas"] = [d["nomes_paginas"][i] for i in manter]
    with open(caminho_rbl, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def _desenhar_chapa(pt, chapa, rotulos=True):
    from PySide6.QtGui import QColor, QPen
    cores = {GRAV_FIG: "#222222", GRAV_LINHA: "#666666", GRAV_NUM: "#222222", FURO: "#2f6bff", CONT: "#e0313b",
             CONT_DENTRO: "#ff8c00", CORTE_DENTRO_FURO: "#00a0a0"}
    pt.fillRect(QRectF(0, 0, MESA_W, MESA_H), QColor("#d9d9d9"))
    pt.fillRect(QRectF(MARGEM, MARGEM, MESA_W - 2 * MARGEM, MESA_H - 2 * MARGEM), QColor("#f3e3c3"))
    for k, partes, _d in chapa:
        for p, lid, t in partes:
            if t in ("cheio", "num"):
                pt.setPen(Qt.NoPen)
                pt.setBrush(QColor(cores[lid]))
            else:
                pt.setPen(QPen(QColor(cores[lid]), 0.4))
                pt.setBrush(Qt.NoBrush)
            pt.drawPath(p)
    if rotulos:
        f = QFont("Arial")
        f.setPixelSize(9)
        f.setBold(True)
        pt.setFont(f)
        for k, partes, _d in chapa:
            c = next(p for p, _l, t in partes if t == "cont").boundingRect().center()
            caixa = QRectF(c.x() - 13, c.y() - 6, 26, 12)
            pt.setPen(Qt.NoPen)
            pt.setBrush(QColor(255, 255, 255, 220))
            pt.drawRoundedRect(caixa, 2, 2)
            pt.setPen(QColor("#006400"))
            pt.drawText(caixa, Qt.AlignCenter, k)


def mapa_pdf(chapas, ap, pdf):
    """Uma página A4 por chapa: desenho com os códigos e a lista das peças (o guia de montagem é o do PDF)."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPdfWriter
    w = QPdfWriter(pdf)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    w.setResolution(300)
    pt = QPainter(w)
    pt.setRenderHint(QPainter.Antialiasing)
    mm = 300 / 25.4
    for i, chapa in enumerate(chapas):
        if i:
            w.newPage()
        pt.save()
        pt.scale(mm, mm)
        f = QFont("Arial")
        f.setPixelSize(7)
        f.setBold(True)
        pt.setFont(f)
        pt.setPen(QColor("#b3121b"))
        pt.drawText(QRectF(12, 8, 186, 10), Qt.AlignLeft | Qt.AlignVCenter,
                    f"PRESÉPIO MDF 3 mm — Chapa {i + 1} de {len(chapas)}")
        f.setPixelSize(4)
        f.setBold(False)
        pt.setFont(f)
        pt.setPen(QColor("#333333"))
        pt.drawText(QRectF(12, 18, 186, 6), Qt.AlignLeft | Qt.AlignVCenter,
                    f"Mesa 365 × 370 mm · 2 mm da borda e entre peças · aproveitamento {ap[i]:.0%}")
        esc = 186 / MESA_W
        pt.save()
        pt.translate(12, 27)
        pt.scale(esc, esc)
        _desenhar_chapa(pt, chapa)
        pt.restore()
        y = 27 + MESA_H * esc + 6
        f.setPixelSize(4.2)
        pt.setFont(f)
        for k, _p, dentro in sorted(chapa):
            pt.drawText(QRectF(14, y, 180, 5.5), Qt.AlignLeft | Qt.AlignVCenter,
                        f"{k}  {NOMES[k]}" + ("   — dentro de um vazado: corta antes dele (laranja)" if dentro else ""))
            y += 5.5
        y += 3
        for cor, txt in (("#e0313b", "vermelho: contorno (por último)"), ("#2f6bff", "azul: vazados e rasgos"),
                         ("#ff8c00", "laranja: peça dentro de vazado (corta antes)"),
                         ("#222222", "preto: gravação")):
            pt.setPen(QColor(cor))
            pt.drawText(QRectF(14, y, 180, 5), Qt.AlignLeft | Qt.AlignVCenter, "■ " + txt)
            y += 5
        pt.restore()
    pt.end()


def previa(chapas, png):
    """Imagem das chapas lado a lado (conferência)."""
    esc, sep = 2.5, 20
    img = QImage(int(len(chapas) * (MESA_W * esc + sep)), int(MESA_H * esc), QImage.Format_RGB32)
    img.fill(Qt.white)
    pt = QPainter(img)
    pt.setRenderHint(QPainter.Antialiasing)
    for i, chapa in enumerate(chapas):
        pt.save()
        pt.translate(i * (MESA_W * esc + sep), 0)
        pt.scale(esc, esc)
        _desenhar_chapa(pt, chapa)
        pt.restore()
    pt.end()
    img.save(png)


# ---------------------------------------------------------------- cores (pintura antes do laser)
TINTAS = {"Azul": "#2f6bd6", "Verde": "#3a9a3a", "Amarelo": "#f2c418", "Marrom": "#7a4a22", "Vermelho": "#d32f2f",
          "Rosa": "#f48fb1", "Sem tinta": "#f3e3c3"}
BASE_COR = {"B01": "Verde", "F01": "Marrom", "F02": "Marrom", "L01": "Marrom", "L02": "Marrom", "T01": "Vermelho",
            "T02": "Vermelho", "P01": "Azul", "P02": "Amarelo", "P03": "Marrom", "P04": "Vermelho", "P05": "Amarelo",
            "P06": "Azul", "P07": "Sem tinta", "P08": "Verde", "G01": "Sem tinta", "G02": "Sem tinta"}
# Zonas de outra cor, em coordenadas 0–10 da caixa da peça em pé (como no PDF; x para a direita, y para baixo).
# A 1ª zona da lista vence. "só": pinta só áreas fechadas pelas linhas do desenho (a estrela da fachada).
# Regra do dono: pele SEM TINTA (fica clara, cor da madeira) e o manto/capa de cada figura numa cor só.
PELE = "Sem tinta"
ZONAS = {
    "P08": [("Amarelo", "cocos", [(3.0, 3.8), (4.6, 3.8), (4.5, 5.7), (3.0, 5.7)]),
            ("Amarelo", "cocos", [(5.4, 3.8), (7.0, 3.8), (7.0, 5.7), (5.5, 5.7)]),
            ("Amarelo", "cocos", [(4.6, 3.8), (5.4, 3.8), (5.4, 4.9), (4.6, 4.9)]),
            ("Marrom", "tronco", [(4.0, 4.9), (6.0, 4.9), (6.3, 6.3), (7.6, 9.99), (2.4, 9.99), (3.7, 6.3)])],
    "P01": [(PELE, "rosto", [(6.0, 1.4), (7.9, 1.1), (8.1, 3.0), (6.9, 3.3), (6.2, 2.6)]),
            (PELE, "mãos", [(6.7, 3.0), (8.2, 2.9), (8.0, 4.9), (6.7, 4.9)]),
            ("Sem tinta", "vestido", [(3.8, 3.0), (6.4, 3.0), (6.7, 4.9), (6.0, 7.0), (3.5, 7.0), (3.4, 4.6)])],
    "P02": [(PELE, "cabeça", [(3.4, 1.1), (5.3, 1.1), (5.5, 2.4), (5.0, 3.2), (3.5, 3.2), (3.2, 2.2)]),
            (PELE, "braço", [(6.5, 2.3), (7.9, 2.3), (7.9, 3.4), (6.5, 3.4)]),
            (PELE, "braço", [(1.7, 2.7), (3.6, 2.7), (3.6, 3.7), (1.7, 3.7)]),
            ("Sem tinta", "pano", [(2.8, 3.3), (6.6, 3.3), (7.4, 4.8), (6.4, 7.4), (4.6, 7.4), (3.0, 4.7)]),
            ("Marrom", "manjedoura", [(1.4, 6.0), (8.6, 6.0), (8.8, 9.3), (1.2, 9.3)])],
    "P03": [("Amarelo", "turbante", [(3.0, 0.0), (6.4, 0.0), (6.4, 1.0), (3.0, 1.0)]),
            (PELE, "rosto", [(2.9, 0.9), (4.2, 0.9), (4.2, 1.9), (2.9, 1.9)])],
    "P04": [("Amarelo", "coroa", [(3.4, 0.0), (6.2, 0.0), (6.2, 2.1), (3.4, 1.2)]),
            ("Amarelo", "baú", [(0.1, 3.0), (2.8, 3.0), (2.8, 5.3), (0.1, 5.3)]),
            (PELE, "rosto", [(2.9, 1.3), (4.0, 1.1), (4.6, 2.6), (3.9, 3.9), (3.0, 3.2)])],
    "P05": [("Vermelho", "turbante", [(3.5, 0.0), (6.2, 0.0), (6.2, 1.3), (3.5, 1.0)]),
            (PELE, "rosto", [(2.9, 0.8), (4.5, 0.8), (4.5, 2.0), (2.9, 2.0)]),
            (PELE, "mãos", [(0.9, 3.5), (2.5, 3.5), (2.5, 4.1), (0.9, 4.1)])],
    "P06": [("Amarelo", "coroa", [(3.8, 0.0), (6.6, 0.0), (6.6, 1.5), (3.8, 1.0)]),
            ("Amarelo", "vaso", [(0.0, 1.7), (3.0, 1.7), (3.0, 3.8), (0.0, 3.8)]),
            (PELE, "rosto", [(3.4, 0.8), (5.0, 0.9), (5.1, 2.1), (3.6, 2.1)]),
            (PELE, "mãos", [(0.9, 3.8), (2.6, 3.8), (2.6, 4.4), (0.9, 4.4)])],
    "F01": [("Amarelo", "estrela", [(4.0, 0.0), (6.0, 0.0), (6.0, 2.8), (4.0, 2.8)], "só")],
}
RES_COR = 8.0  # px/mm no cálculo das zonas


def zonas_de_cor(pecas):
    """{código: [(cor, nome, área QPainterPath em mm do PDF)]}: áreas de outra cor, encostadas nas linhas do desenho
    (a emenda entre duas cores fica debaixo da linha que o laser grava depois)."""
    from scipy.ndimage import distance_transform_edt, label
    from skimage.measure import approximate_polygon, find_contours
    out = {}
    for k, zonas in ZONAS.items():
        v = pecas[k]
        caixa = v["cont"].boundingRect()
        mat = _raster([v["cont"]], caixa, [p for p, t in v["partes"] if t == "furo"], res=RES_COR)
        st = QPainterPathStroker()
        st.setWidth(0.35)
        linhas = ([p for p, t in v["partes"] if t == "cheio"]
                  + [st.createStroke(p) for p, t in v["partes"] if t == "linha"])
        preto = _raster(linhas, caixa, res=RES_COR)[:mat.shape[0], :mat.shape[1]]
        zona_pix = np.full(mat.shape, -1, np.int16)
        for i in range(len(zonas) - 1, -1, -1):  # a 1ª da lista vence
            q = QPainterPath()
            q.addPolygon([QPointF(caixa.left() + x / 10 * caixa.width(), caixa.top() + y / 10 * caixa.height())
                          for x, y in zonas[i][2]])
            q.closeSubpath()
            zona_pix[_raster([q], caixa, res=RES_COR)[:mat.shape[0], :mat.shape[1]]] = i
        branco = mat & ~preto
        rot, n = label(branco)
        areas = np.bincount(rot.ravel(), minlength=n + 1)
        cor = np.full(mat.shape, -1, np.int16)  # -1 = cor da peça
        for i, z in enumerate(zonas):
            so = len(z) > 3 and z[3] == "só"
            dentro = np.bincount(rot[zona_pix == i].ravel(), minlength=n + 1)
            area_zona = max(1, int((zona_pix == i).sum()))
            for c in np.nonzero(dentro)[0]:
                if c == 0:
                    continue
                if dentro[c] >= 0.5 * areas[c]:
                    cor[(rot == c) & (cor == -1)] = i
                elif not so and (dentro[c] >= 0.35 * areas[c] or areas[c] > 4 * area_zona):  # vaza: corta pela zona
                    cor[(rot == c) & (zona_pix == i) & (cor == -1)] = i
        _, (iy, ix) = distance_transform_edt(~branco, return_indices=True)  # linha preta: cor do branco mais perto
        cor = np.where(branco, cor, cor[iy, ix])
        cor[~mat] = -2
        lista = []
        for i, z in enumerate(zonas):
            m = np.pad(cor == i, 1)
            if m.sum() < 4 * RES_COR * RES_COR:  # menos de 4 mm²
                continue
            area = QPainterPath()
            area.setFillRule(Qt.OddEvenFill)
            for linha in find_contours(m.astype(float), 0.5):
                pts = approximate_polygon(linha, 0.6)
                pol = [QPointF(caixa.left() + (x - 1) / RES_COR, caixa.top() + (y - 1) / RES_COR) for y, x in pts]
                if len(pol) >= 4 and abs(_area_pts(pol)) >= 1.0:
                    area.addPolygon(pol)
                    area.closeSubpath()
            if not area.isEmpty():
                lista.append((z[0], z[1], area))
        out[k] = lista
    return out


def _area_pts(pts):
    return sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(pts, pts[1:] + pts[:1])) / 2


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    saida, ap, nomes, dentro, chapas = gerar(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 3:
        previa(chapas, sys.argv[3])
    if len(sys.argv) > 4:
        mapa_pdf(chapas, ap, sys.argv[4])
    print(saida, [f"{a:.0%}" for a in ap], nomes, "dentro:", dentro)
