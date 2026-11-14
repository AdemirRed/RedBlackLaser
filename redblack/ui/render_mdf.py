"""Prévia "peças cortadas" da aba aberta, em 2D (instantânea) e em 3D (Blender, com a espessura real).

2D: textura de MDF, bordas queimadas, furos vazados, sombra, gravações como queimado e linhas fracas como risco.
3D: cada peça vira um sólido com a espessura da chapa; o topo leva a textura (com gravações/riscos) e as laterais
o tom queimado do corte; peças apoiadas numa mesa, render Cycles na placa de vídeo (Blender instalado no PC).
Só prévia visual: não mexe no projeto nem gera G-code.

Camada em Linha é CORTE com potência ≥ 40 % (o nome com "grav", "marc", "risc", "cola" ou "refer" força
marcação); abaixo disso vira risco (ex.: marcas de cola fraquinhas)."""
import json
import os
import random
import re
import tempfile

from PySide6.QtCore import QProcess, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QVBoxLayout)

from .. import percurso as pc

POT_CORTE = 40.0
FECHADO_MM = 0.1  # contorno cujas pontas estão a até 0,1 mm conta como fechado (o laser corta igual)
ABERTURA_MAX_MM = 10.0  # aberturas maiores que 0,1 e até 10 mm: a prévia fecha, mas AVISA (no laser a peça prende)
NOMES_MARCACAO = ("grav", "marc", "risc", "cola", "refer")
MATERIAIS = {  # nome: (cor base, cor das fibras/pintas, cor da borda queimada)
    "MDF cru": ("#c8a274", "#a98257", "#2b1a0e"),
    "MDF branco": ("#ece8e1", "#d6d0c6", "#3a2a1c"),
    "MDF rosa": ("#e8638f", "#d8507e", "#4a2230"),
    "Compensado": ("#d9b07a", "#b98a4f", "#2e1c0d"),
    "Acrílico preto": ("#1c1c1f", "#2a2a2e", "#55555c"),
}


def e_corte(c) -> bool:
    nome = (c.nome or "").lower()
    return c.modo == "linha" and c.potencia_max >= POT_CORTE and not any(k in nome for k in NOMES_MARCACAO)


def espessura_do_nome(caminho, padrao=3.0) -> float:
    """"mini-pia-3mm.rbl" -> 3.0; "teste 6,5 mm" -> 6.5; sem número -> padrão."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*mm", os.path.basename(caminho or ""), re.I)
    return float(m.group(1).replace(",", ".")) if m else padrao


def textura(cor, pinta, lado=256, semente=7) -> QImage:
    """Textura de MDF: base lisa com pintas finas de fibra prensada (repetível, sem arquivo de imagem)."""
    img = QImage(lado, lado, QImage.Format_RGB32)
    img.fill(QColor(cor))
    rnd = random.Random(semente)
    p = QPainter(img)
    base, fib = QColor(cor), QColor(pinta)
    for _ in range(lado * lado // 6):
        c = QColor(fib if rnd.random() < 0.5 else base.lighter(106 + rnd.randint(0, 8)))
        c.setAlpha(rnd.randint(25, 90))
        p.setPen(c)
        x, y = rnd.randrange(lado), rnd.randrange(lado)
        p.drawLine(x, y, x + rnd.randint(0, 2), y + rnd.randint(-1, 1))
    p.end()
    return img


def pecas_da_aba(janela):
    """([contornos fechados de corte (QPolygonF)], riscos, gravações) em mm de cena, das camadas com Saída."""
    camadas = {c.id: c for c in janela.layers}
    cortes, riscos, gravs, abertos = [], QPainterPath(), [], []
    for s in janela.canvas.view.shapes():
        for path, tf, layer, extra in pc.folhas(s.snapshot()):
            c = camadas.get(layer) or camadas.get(layer.split(".")[0])
            if c is None or not c.saida:
                continue
            p = tf.map(path)
            if c.modo == "imagem":
                gravs.append((p, getattr(extra, "qimage", None), tf, path.boundingRect()))
            elif c.modo == "preenchimento":
                gravs.append((p, None, None, None))
            elif e_corte(c):
                for sub in p.toSubpathPolygons():
                    fim = sub.last() - sub.first() if sub.size() else None
                    if sub.size() >= 3 and abs(fim.x()) + abs(fim.y()) <= FECHADO_MM:
                        if sub.first() != sub.last():  # pontas encostadas sem "fechar caminho": fecha aqui
                            sub.append(sub.first())
                        cortes.append(sub)
                    elif sub.size() >= 2:
                        abertos.append(sub)  # pedaço de contorno: pode fechar junto com outros
            else:
                riscos.addPath(p)
    fechados, sobras = encadear(abertos)
    quase, sobras = encadear(sobras, ABERTURA_MAX_MM)  # contorno com abertura pequena: mostra, mas avisa
    aberturas = []
    for cad in quase:
        aberturas += getattr(cad, "aberturas", [])
    cortes += fechados + quase
    for sub in sobras:
        riscos.addPolygon(sub)  # corte aberto de verdade: só o traço
    pecas_da_aba.aberturas = aberturas  # [(mm, x, y)] da última leitura, para o aviso da janela
    return cortes, riscos, gravs


def _dist(a, b):
    return ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5


def encadear(pedacos, tol=FECHADO_MM):
    """Junta pedaços abertos cujas pontas se encostam (ex.: contorno feito de várias linhas, ou "Juntar" que deixou
    trechos separados) em contornos fechados. Devolve (fechados, que sobraram abertos)."""
    from PySide6.QtGui import QPolygonF
    livres = [QPolygonF(p) for p in pedacos]
    fechados, abertos = [], []

    def _perto(a, b):
        return _dist(a, b) <= tol

    while livres:
        cad = livres.pop(0)
        vaos = []
        mudou = True
        while mudou and not (cad.size() >= 3 and _perto(cad.first(), cad.last())):
            mudou = False
            for k, q in enumerate(livres):
                for a, b, junta in ((cad.last(), q.first(), lambda: QPolygonF(list(cad) + list(q))),
                                    (cad.last(), q.last(), lambda: QPolygonF(list(cad) + list(reversed(list(q))))),
                                    (cad.first(), q.last(), lambda: QPolygonF(list(q) + list(cad))),
                                    (cad.first(), q.first(), lambda: QPolygonF(list(reversed(list(q))) + list(cad)))):
                    if _perto(a, b):
                        if _dist(a, b) > FECHADO_MM:
                            vaos.append((_dist(a, b), (a.x() + b.x()) / 2, (a.y() + b.y()) / 2))
                        cad = junta()
                        break
                else:
                    continue
                livres.pop(k)
                mudou = True
                break
        if cad.size() >= 3 and _perto(cad.first(), cad.last()):
            if _dist(cad.first(), cad.last()) > FECHADO_MM:
                vaos.append((_dist(cad.first(), cad.last()), (cad.first().x() + cad.last().x()) / 2,
                             (cad.first().y() + cad.last().y()) / 2))
            if cad.first() != cad.last():
                cad.append(cad.first())
            cad.aberturas = vaos
            fechados.append(cad)
        else:
            abertos.append(cad)
    return fechados, abertos


def _area(poly):
    return abs(sum(poly[i].x() * poly[i + 1].y() - poly[i + 1].x() * poly[i].y() for i in range(poly.size() - 1))) / 2


def estrutura(contornos, externo="auto"):
    """Quem está dentro de quem. Devolve ([(contorno da peça, [furos diretos])], chapa ou None, furos da chapa).
    Um contorno em volta de tudo é a CHAPA quando `externo` = "chapa", ou em "auto" quando há peça com furo dentro
    dele ou as de dentro ocupam mais de 35 % dele (uma peça só com furos pequenos continua peça)."""
    n = len(contornos)
    areas = [_area(c) for c in contornos]
    caminhos = []
    for c in contornos:
        cam = QPainterPath()
        cam.addPolygon(c)
        caminhos.append(cam)
    pai = [None] * n  # menor contorno que contém o i
    for i in range(n):
        r = contornos[i].boundingRect()
        teste = r.center() if caminhos[i].contains(r.center()) else contornos[i][0]
        for j in range(n):
            if (i != j and areas[j] > areas[i] and caminhos[j].boundingRect().contains(r)
                    and caminhos[j].contains(teste) and (pai[i] is None or areas[j] < areas[pai[i]])):
                pai[i] = j
    prof = []
    for i in range(n):
        d, k = 0, pai[i]
        while k is not None:
            d, k = d + 1, pai[k]
        prof.append(d)
    raizes = [i for i in range(n) if prof[i] == 0]
    chapa = None
    if len(raizes) == 1 and externo != "peca":
        r = raizes[0]
        filhos = [i for i in range(n) if pai[i] == r]
        bb = contornos[r].boundingRect()
        retangular = areas[r] >= 0.9 * bb.width() * bb.height()  # sobra de chapa é (quase) um retângulo
        if filhos and (externo == "chapa" or (retangular and (any(prof[i] >= 2 for i in range(n))
                                                              or sum(areas[i] for i in filhos) > 0.35 * areas[r]))):
            chapa = r
    pecas = []
    for i in range(n):
        d = prof[i] - (1 if chapa is not None else 0)
        if i != chapa and d % 2 == 0:  # profundidade ímpar = furo
            pecas.append((contornos[i], [contornos[k] for k in range(n) if pai[k] == i]))
    furos_chapa = [contornos[k] for k in range(n) if chapa is not None and pai[k] == chapa]
    return pecas, (contornos[chapa] if chapa is not None else None), furos_chapa


def _caminho(contorno, furos):
    cam = QPainterPath()
    cam.setFillRule(Qt.OddEvenFill)
    cam.addPolygon(contorno)
    for f in furos:
        cam.addPolygon(f)
    return cam


def montar_pecas(contornos, externo="auto"):
    """Contornos fechados -> (peças como QPainterPath com furos vazados, sobra da chapa ou None)."""
    pecas, chapa, furos = estrutura(contornos, externo)
    return [_caminho(c, f) for c, f in pecas], (_caminho(chapa, furos) if chapa is not None else None)


def _pintar_gravacoes(p, gravs, riscos):
    for g, qimg, tf, r in gravs:  # gravação: queimado (imagem: tons da foto multiplicando a madeira)
        if qimg is not None and not qimg.isNull():
            p.save()
            p.setTransform(tf * p.transform())
            p.setOpacity(0.85)
            p.setCompositionMode(QPainter.CompositionMode_Multiply)
            p.drawImage(r, qimg.convertToFormat(QImage.Format_Grayscale8))
            p.restore()
        else:
            p.fillPath(g, QColor(60, 34, 16, 200))
    p.setPen(QPen(QColor(70, 40, 18, 210), 0.25))
    p.setBrush(Qt.NoBrush)
    p.drawPath(riscos)


def renderizar(janela, material="MDF cru", px_por_mm=4.0, max_px=3600, externo="auto", mostrar_sobra=False) -> QImage:
    contornos, riscos, gravs = pecas_da_aba(janela)
    pecas, sobra = montar_pecas(contornos, externo)
    cortes = QPainterPath()
    cortes.setFillRule(Qt.OddEvenFill)  # cada contorno aparece uma vez: peça, furo, peça dentro do furo…
    for pz in pecas:
        cortes.addPath(pz)
    caixa = cortes.boundingRect() | riscos.boundingRect()
    if mostrar_sobra and sobra is not None:
        caixa |= sobra.boundingRect()
    for g, *_ in gravs:
        caixa |= g.boundingRect()
    if caixa.isEmpty():
        return QImage()
    caixa = caixa.adjusted(-8, -8, 8, 8)
    esc = min(px_por_mm, max_px / max(caixa.width(), caixa.height()))
    img = QImage(int(caixa.width() * esc), int(caixa.height() * esc), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#7d8188"))  # mesa clara: linhas e peças escuras continuam visíveis
    cor, pinta, queimado = MATERIAIS.get(material, MATERIAIS["MDF cru"])
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(esc, esc)
    p.translate(-caixa.left(), -caixa.top())
    tex = QBrush(textura(cor, pinta))
    tex.setTransform(QTransform.fromScale(1 / esc, 1 / esc))  # pintas do tamanho certo em qualquer escala
    if mostrar_sobra and sobra is not None:  # sobra da chapa, apagada, por baixo das peças
        p.fillPath(sobra, tex)
        p.fillPath(sobra, QColor(30, 32, 36, 150))
        p.setPen(QPen(QColor(queimado), 0.45))
        p.drawPath(sobra)
    for k, a in ((2.2, 22), (1.6, 30), (1.0, 40)):  # sombra: peças "apoiadas" na mesa
        for pz in pecas:
            p.fillPath(pz.translated(k, k), QColor(0, 0, 0, a))
    for pz in pecas:
        p.fillPath(pz, tex)
    p.save()
    if not cortes.isEmpty():
        p.setClipPath(cortes)
    _pintar_gravacoes(p, gravs, riscos)
    p.restore()
    p.setBrush(Qt.NoBrush)  # bordas do corte: queimado escuro por fora, madeira tostada por dentro
    p.setPen(QPen(QColor(queimado), 0.45, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(cortes)
    tost = QColor(queimado)
    tost.setAlpha(90)
    p.save()
    if not cortes.isEmpty():
        p.setClipPath(cortes)
    p.setPen(QPen(tost, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(cortes)
    p.restore()
    p.end()
    return img


# ---------------------------------------------------------------- 3D (Blender)
def _camada_3d(pasta, nome, janela, material, espessura, externo, z0):
    """Dados de uma camada (aba aberta) para o Blender: anéis das peças, textura do topo, cor da borda, altura."""
    contornos, riscos, gravs = pecas_da_aba(janela)
    pecas, _chapa, _f = estrutura(contornos, externo)
    if not pecas:
        return None
    caixa = QRectF()
    for c, _ in pecas:
        caixa |= c.boundingRect()
    caixa = caixa.adjusted(-1, -1, 1, 1)
    esc = min(6.0, 6000 / max(caixa.width(), caixa.height()))  # textura do topo: até 6 px/mm
    topo = QImage(max(1, int(caixa.width() * esc)), max(1, int(caixa.height() * esc)), QImage.Format_RGB32)
    cor, pinta, queimado = MATERIAIS.get(material, MATERIAIS["MDF cru"])
    p = QPainter(topo)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(esc, esc)
    p.translate(-caixa.left(), -caixa.top())
    tex = QBrush(textura(cor, pinta))
    tex.setTransform(QTransform.fromScale(1 / esc, 1 / esc))
    p.fillRect(caixa, tex)
    _pintar_gravacoes(p, gravs, riscos)
    tost = QColor(queimado)  # beirada tostada no topo, junto do corte
    tost.setAlpha(110)
    p.setPen(QPen(tost, 0.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for c, furos in pecas:
        p.drawPath(_caminho(c, furos))
    p.end()
    os.makedirs(pasta, exist_ok=True)
    arq_tex = os.path.join(pasta, f"topo_{nome}.png")
    topo.save(arq_tex)

    def anel(poly):
        pts = [(round(q.x(), 4), round(q.y(), 4)) for q in poly]
        return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    qb = QColor(queimado)
    # simplified(): desfaz cruzamentos (ex.: abertura fechada pela prévia) em anéis limpos que o Blender preenche
    aneis = [[anel(sp) for sp in _caminho(c, furos).simplified().toSubpathPolygons() if sp.size() >= 4]
             for c, furos in pecas]
    return {"pecas": [a for a in aneis if a], "caixa": [caixa.left(), caixa.top(), caixa.right(), caixa.bottom()],
            "espessura": espessura, "z0": z0, "textura": arq_tex,
            "borda": [qb.redF() ** 2.2, qb.greenF() ** 2.2, qb.blueF() ** 2.2],
            "acrilico": material.startswith("Acrílico")}


def material_da_aba(nome, padrao):
    n = nome.lower()
    return ("MDF rosa" if "rosa" in n else "MDF branco" if "branc" in n else
            "Acrílico preto" if "acríl" in n or "acril" in n else padrao)


def preparar_3d(pasta, janela, material="MDF cru", espessura=3.0, externo="auto", resolucao=1600, amostras=128,
                empilhar=False):
    """Grava texturas + dados + script em `pasta`. Devolve (script, dados, saída) ou None sem peças.
    `empilhar`: todas as abas, uma em cima da outra (a 1ª aba fica por cima; material pelo nome da aba: "rosa",
    "branca"…; senão o escolhido)."""
    camadas = []
    if empilhar and len(getattr(janela, "paginas", [])) > 1:
        atual = janela.pagina_atual
        n = len(janela.paginas)
        for k in range(n):  # de baixo (última aba) para cima (1ª aba)
            i = n - 1 - k
            janela.ir_para_pagina(i)
            c = _camada_3d(pasta, str(i), janela, material_da_aba(janela.nomes_paginas[i], material), espessura,
                           externo, len(camadas) * espessura)
            if c:
                camadas.append(c)
        janela.ir_para_pagina(atual)
    else:
        c = _camada_3d(pasta, "0", janela, material, espessura, externo, 0.0)
        if c:
            camadas.append(c)
    if not camadas:
        return None
    dados = {"camadas": camadas, "resolucao": resolucao, "amostras": amostras,
             "saida": os.path.join(pasta, "pecas_3d.png")}
    arq_dados = os.path.join(pasta, "cena.json")
    with open(arq_dados, "w", encoding="utf-8") as f:
        json.dump(dados, f)
    script = os.path.join(pasta, "cena_pecas.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(SCRIPT_3D)
    return script, arq_dados, dados["saida"]


SCRIPT_3D = r'''
import json, math, sys
import bpy
from mathutils import Vector

d = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
MM = 0.001
cena = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
x0 = min(c["caixa"][0] for c in d["camadas"]); y0 = min(c["caixa"][1] for c in d["camadas"])
x1 = max(c["caixa"][2] for c in d["camadas"]); y1 = max(c["caixa"][3] for c in d["camadas"])
L, A = (x1 - x0) * MM, (y1 - y0) * MM
centro = Vector(((x0 + x1) / 2 * MM, -(y0 + y1) / 2 * MM, 0))

for nc, cam in enumerate(d["camadas"]):
    E = cam["espessura"] * MM
    cx0, cy0, cx1, cy1 = cam["caixa"]
    topo = bpy.data.materials.new(f"Topo{nc}"); topo.use_nodes = True
    nt = topo.node_tree; bs = nt.nodes["Principled BSDF"]
    im = nt.nodes.new("ShaderNodeTexImage"); im.image = bpy.data.images.load(cam["textura"])
    nt.links.new(im.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.25 if cam["acrilico"] else 0.78
    borda = bpy.data.materials.new(f"Borda{nc}"); borda.use_nodes = True
    bb = borda.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = (*cam["borda"], 1); bb.inputs["Roughness"].default_value = 0.9
    for n, aneis in enumerate(cam["pecas"]):
        cu = bpy.data.curves.new(f"Peca{nc}_{n}", "CURVE"); cu.dimensions = "2D"; cu.fill_mode = "BOTH"
        cu.extrude = E / 2
        for anel in aneis:
            sp = cu.splines.new("POLY"); sp.points.add(len(anel) - 1); sp.use_cyclic_u = True
            for i, (x, y) in enumerate(anel):
                sp.points[i].co = (x * MM, -y * MM, 0, 1)
        ob = bpy.data.objects.new(f"Peca{nc}_{n}", cu); cena.collection.objects.link(ob)
        grafo = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(grafo))
        bpy.data.objects.remove(ob, do_unlink=True)
        me.materials.append(topo); me.materials.append(borda)
        uv = me.uv_layers.new()
        for pol in me.polygons:
            pol.material_index = 0 if abs(pol.normal.z) > 0.9 else 1
            pol.use_smooth = False
        for lp in me.loops:
            v = me.vertices[lp.vertex_index].co
            uv.data[lp.index].uv = ((v.x / MM - cx0) / (cx1 - cx0), 1 - ((-v.y / MM) - cy0) / (cy1 - cy0))
        po = bpy.data.objects.new(f"Peca{nc}_{n}", me)
        po.location.z = cam["z0"] * MM + E / 2 + 0.00005 * (nc + 1)  # sem encostar (listras)
        cena.collection.objects.link(po)

bpy.ops.mesh.primitive_plane_add(size=1, location=(centro.x, centro.y, 0))
mesa = bpy.context.active_object; mesa.scale = (L * 4 + 0.3, A * 4 + 0.3, 1)
mm = bpy.data.materials.new("Mesa"); mm.use_nodes = True
mb = mm.node_tree.nodes["Principled BSDF"]
mb.inputs["Base Color"].default_value = (0.09, 0.095, 0.105, 1); mb.inputs["Roughness"].default_value = 0.55
mesa.data.materials.append(mm)

w = bpy.data.worlds.new("Mundo"); cena.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.78, 0.82, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.08
alvo = bpy.data.objects.new("Alvo", None); alvo.location = centro; cena.collection.objects.link(alvo)
tam = max(L, A)
def luz(nome, desloc, e, t):
    l = bpy.data.lights.new(nome, "AREA"); l.energy = e * (tam / 0.3) ** 2; l.size = t * tam
    o = bpy.data.objects.new(nome, l); o.location = centro + Vector(desloc) * tam; cena.collection.objects.link(o)
    c = o.constraints.new("TRACK_TO"); c.target = alvo
luz("Principal", (-0.6, -0.8, 1.3), 3.6, 0.8)
luz("Preenchimento", (0.9, -0.4, 0.8), 0.9, 0.6)
luz("Recorte", (0.3, 1.0, 0.7), 2.4, 0.5)
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d); cena.collection.objects.link(cam)
cam.location = centro + Vector((0.12, -1.25, 1.05)) * tam * 1.25  # ~40° de cima: vê o topo e a espessura
c = cam.constraints.new("TRACK_TO"); c.target = alvo
cena.camera = cam

cena.render.engine = "CYCLES"
cena.cycles.samples = d["amostras"]
cena.cycles.use_denoising = True
cena.render.resolution_x = d["resolucao"]
cena.render.resolution_y = int(d["resolucao"] * 0.7)
cena.render.filepath = d["saida"]
cena.render.image_settings.file_format = "PNG"
vts = [v.identifier for v in cena.view_settings.bl_rna.properties["view_transform"].enum_items]
cena.view_settings.view_transform = "AgX" if "AgX" in vts else "Filmic"
try:
    pref = bpy.context.preferences.addons["cycles"].preferences
    for tipo in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            pref.compute_device_type = tipo
            pref.get_devices()
            if any(x.type == tipo for x in pref.devices):
                for x in pref.devices:
                    x.use = True
                cena.cycles.device = "GPU"
                print("PLACA DE VIDEO:", tipo)
                break
        except TypeError:
            continue
except Exception as e:
    print("SEM GPU:", e)
bpy.ops.render.render(write_still=True)
print("RENDER OK", d["saida"])
'''


class DialogoRenderMdf(QDialog):
    def __init__(self, janela):
        super().__init__(janela)
        self.jp = janela
        self.setWindowTitle("Peças cortadas — prévia em MDF")
        self.resize(1000, 760)
        v = QVBoxLayout(self)
        topo = QHBoxLayout()
        topo.addWidget(QLabel("Material:"))
        self.material = QComboBox()
        self.material.addItems(list(MATERIAIS))
        self.material.currentTextChanged.connect(self.atualizar)
        topo.addWidget(self.material)
        topo.addWidget(QLabel("Contorno de fora:"))
        self.externo = QComboBox()
        for txt, dado in (("Automático", "auto"), ("É a chapa (sobra)", "chapa"), ("É uma peça", "peca")):
            self.externo.addItem(txt, dado)
        self.externo.currentIndexChanged.connect(self.atualizar)
        topo.addWidget(self.externo)
        self.sobra = QCheckBox("Sobra da chapa")
        self.sobra.toggled.connect(self.atualizar)
        topo.addWidget(self.sobra)
        topo.addStretch(1)
        v.addLayout(topo)
        tres = QHBoxLayout()
        tres.addWidget(QLabel("Espessura:"))
        self.espessura = QDoubleSpinBox()
        self.espessura.setRange(0.5, 50)
        self.espessura.setDecimals(1)
        self.espessura.setSuffix(" mm")
        self.espessura.setValue(espessura_do_nome(getattr(janela, "file_path", "")))
        tres.addWidget(self.espessura)
        self.empilhar = QCheckBox("Montar todas as abas (empilhadas)")
        self.empilhar.setToolTip("3D com as abas uma sobre a outra: a 1ª aba por cima. Cor pelo nome da aba "
                                 "(\"rosa\", \"branca\"…); as outras usam o material escolhido")
        self.empilhar.setChecked(len(getattr(janela, "paginas", [])) > 1)
        tres.addWidget(self.empilhar)
        self.b_3d = QPushButton("Renderizar em 3D (Blender)")
        self.b_3d.clicked.connect(lambda: self.renderizar_3d())
        tres.addWidget(self.b_3d)
        self.b_2d = QPushButton("Voltar à vista de cima")
        self.b_2d.clicked.connect(self.atualizar)
        tres.addWidget(self.b_2d)
        self.status = QLabel("")
        tres.addWidget(self.status, 1)
        salvar = QPushButton("Salvar PNG…")
        salvar.clicked.connect(self.salvar)
        tres.addWidget(salvar)
        v.addLayout(tres)
        zoom = QHBoxLayout()  # zoom da imagem (também Ctrl + rodinha) e tela cheia (F11)
        for txt, dica, fn in (("Ajustar à janela", "Imagem inteira na janela (tira o zoom)", self.ajustar),
                              ("−", "Afastar", lambda: self.zoom_por(1 / 1.25)),
                              ("+", "Aproximar", lambda: self.zoom_por(1.25)),
                              ("100 %", "Tamanho real da imagem", lambda: self.definir_zoom(1.0))):
            b = QPushButton(txt)
            b.setToolTip(dica)
            b.clicked.connect(fn)
            zoom.addWidget(b)
        self.lbl_zoom = QLabel()
        zoom.addWidget(self.lbl_zoom)
        zoom.addStretch(1)
        self.b_cheia = QPushButton("Tela cheia (F11)")
        self.b_cheia.clicked.connect(self.alternar_tela_cheia)
        zoom.addWidget(self.b_cheia)
        v.addLayout(zoom)
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F11"), self, self.alternar_tela_cheia)
        QShortcut(QKeySequence("Ctrl+0"), self, self.ajustar)
        QShortcut(QKeySequence("Ctrl++"), self, lambda: self.zoom_por(1.25))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self.zoom_por(1 / 1.25))
        self.vista = QLabel()
        self.vista.setAlignment(Qt.AlignCenter)
        rol = self.rolagem = QScrollArea()
        rol.setWidgetResizable(True)
        rol.setWidget(self.vista)
        rol.viewport().installEventFilter(self)  # Ctrl + rodinha = zoom
        v.addWidget(rol, 1)
        self.pm, self.zoom, self.ajustado = QPixmap(), 1.0, True
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet("background:#5a3a10;color:#ffe2a8;padding:6px;border-radius:3px")
        self.aviso.hide()
        v.addWidget(self.aviso)
        v.addWidget(QLabel("Corte = camada em Linha com potência ≥ 40 % (nome com \"grav\"/\"marca\"/\"cola\" vira "
                           "risco). Preenchimento e Imagem aparecem como gravação queimada. Prévia aproximada."))
        self.img, self.saida_3d = QImage(), None
        self.atualizar()

    def _mostrar(self, pm):
        self.pm = pm
        self.ajustar()

    def ajustar(self):
        """Zoom que cabe a imagem inteira na área visível."""
        if self.pm.isNull():
            return
        area = self.rolagem.viewport().size()
        self.definir_zoom(min(1.0 * max(area.width() - 4, 50) / self.pm.width(),
                              1.0 * max(area.height() - 4, 50) / self.pm.height()), ajustado=True)

    def zoom_por(self, f):
        self.definir_zoom(self.zoom * f)

    def definir_zoom(self, z, ajustado=False):
        if self.pm.isNull():
            return
        self.zoom, self.ajustado = max(0.05, min(z, 8.0)), ajustado
        self.vista.setPixmap(self.pm.scaled(max(1, int(self.pm.width() * self.zoom)),
                                            max(1, int(self.pm.height() * self.zoom)),
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.lbl_zoom.setText(f"{self.zoom * 100:.0f} %")

    def alternar_tela_cheia(self):
        if self.isFullScreen():
            self.showNormal()
            self.b_cheia.setText("Tela cheia (F11)")
        else:
            self.showFullScreen()
            self.b_cheia.setText("Sair da tela cheia (F11 / Esc)")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.isFullScreen():
            self.alternar_tela_cheia()  # Esc sai da tela cheia (não fecha a janela)
            return
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "ajustado", False):
            self.ajustar()  # janela mudou de tamanho (ou tela cheia): continua mostrando tudo

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Wheel and ev.modifiers() & Qt.ControlModifier:
            self.zoom_por(1.25 if ev.angleDelta().y() > 0 else 1 / 1.25)
            return True
        return super().eventFilter(obj, ev)

    def _avisar_aberturas(self):
        from .. import gcode as gc
        ab = getattr(pecas_da_aba, "aberturas", [])
        if not ab:
            self.aviso.hide()
            return
        W, H = gc.area(gc.PERFIL)
        onde = "; ".join(f"{d:.1f} mm perto de X {gc.doc_para_maquina(x, y, W, H)[0]:.0f}, "
                         f"Y {gc.doc_para_maquina(x, y, W, H)[1]:.0f}" for d, x, y in ab).replace(".", ",")
        self.aviso.setText(f"⚠ Contorno de corte com {len(ab)} abertura(s): {onde}. Na prévia aparece fechado, mas "
                           "no laser a peça fica PRESA nesses pontos. Feche no desenho (Editar nós: arraste a ponta "
                           "até a outra; depois Juntar pontas, Alt+J).")
        self.aviso.show()

    def atualizar(self, *_):
        self.saida_3d = None
        self.img = renderizar(self.jp, self.material.currentText(), externo=self.externo.currentData(),
                              mostrar_sobra=self.sobra.isChecked())
        self._avisar_aberturas()
        if self.img.isNull():
            self.vista.setText("Nada para mostrar: nenhuma camada com Saída ligada nesta aba.")
            return
        self._mostrar(QPixmap.fromImage(self.img))

    def renderizar_3d(self, esperar=False, resolucao=1600, amostras=128):
        from ..plugins.cilindros import render as rd
        blender = rd.localizar_blender(self.jp.settings.value("cilindros/blender", ""))
        if not blender:
            QMessageBox.information(self, "Render 3D", "Blender não encontrado. Instale o Blender (gratuito, "
                                    "blender.org); o RedBlack acha sozinho nas pastas de sempre.")
            return None
        prep = preparar_3d(tempfile.mkdtemp(prefix="redblack_pecas_"), self.jp, self.material.currentText(),
                           self.espessura.value(), self.externo.currentData(), resolucao, amostras,
                           self.empilhar.isChecked())
        if prep is None:
            self.status.setText("Nenhuma peça de corte nesta aba.")
            return None
        script, dados, saida = prep
        self.processo = QProcess(self)
        self.processo.setProgram(blender)
        self.processo.setArguments(rd.argumentos(script, dados))
        self.processo.finished.connect(lambda *_: self._pronto(saida))
        self.b_3d.setEnabled(False)
        self.status.setText("Renderizando em 3D na placa de vídeo… (alguns segundos)")
        self.processo.start()
        if esperar:
            self.processo.waitForFinished(600_000)
        return saida

    def _pronto(self, saida):
        self.b_3d.setEnabled(True)
        log = bytes(self.processo.readAllStandardOutput()).decode("utf-8", "replace")
        self.ultimo_log = log
        if not os.path.isfile(saida):
            self.status.setText("O render 3D falhou (veja se o Blender abre normalmente).")
            return
        gpu = next((ln.split(":", 1)[1].strip() for ln in log.splitlines() if ln.startswith("PLACA DE VIDEO")), None)
        self.status.setText(f"3D pronto ({'placa de vídeo ' + gpu if gpu else 'processador'}).")
        self.saida_3d = saida
        self._mostrar(QPixmap(saida))

    def salvar(self):
        nome = "pecas_3d.png" if self.saida_3d else "pecas_mdf.png"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar prévia", nome, "PNG (*.png)")
        if not path:
            return
        path = path if path.lower().endswith(".png") else path + ".png"
        if self.saida_3d:
            QPixmap(self.saida_3d).save(path, "PNG")
        else:  # vista de cima em resolução maior que a da tela (8 px/mm, até 8000 px)
            renderizar(self.jp, self.material.currentText(), 8.0, 8000, self.externo.currentData(),
                       self.sobra.isChecked()).save(path)
