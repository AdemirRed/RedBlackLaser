"""A arte do projeto vira uma imagem (textura) em escala real para aplicar no copo: o que vai ser gravado fica
escuro, o resto transparente."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QTransform

from ... import percurso as pc
from ...importar_imagem import ImagemOriginal

PX_MM = 8.0          # resolução da textura
MAX_LADO = 4096      # px
REFERENCIA = "C29"   # camada de referência (área/guias): não entra na arte


def _folhas(janela, so_selecionados):
    camadas = {c.id: c for c in janela.layers}
    itens = janela._sel() if so_selecionados else janela.canvas.view.shapes()
    out = []
    for it in itens:
        if not it.isVisible():
            continue
        for path, tf, layer, extra in pc.folhas(it.snapshot()):
            c = camadas.get(layer)
            if layer == REFERENCIA or (c is not None and not c.saida):
                continue
            out.append((path, tf, c, extra))
    return out


def textura(janela, so_selecionados=False):
    """(QImage ARGB, largura_mm, altura_mm) ou None se não houver arte."""
    folhas = _folhas(janela, so_selecionados)
    caixa = QRectF()
    for path, tf, _, extra in folhas:
        caixa = caixa.united(tf.mapRect(path.boundingRect()))
    if not folhas or caixa.width() <= 0 or caixa.height() <= 0:
        return None
    esc = min(PX_MM, MAX_LADO / max(caixa.width(), caixa.height()))
    img = QImage(max(1, round(caixa.width() * esc)), max(1, round(caixa.height() * esc)),
                 QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    base = QTransform.fromTranslate(-caixa.left(), -caixa.top()) * QTransform.fromScale(esc, esc)
    tinta = QColor(20, 20, 20)
    for path, tf, c, extra in folhas:
        p.setTransform(tf * base)
        if isinstance(extra, ImagemOriginal):
            alfa = extra.qimage.convertToFormat(QImage.Format_Grayscale8)
            alfa.invertPixels()  # escuro grava (opaco), branco não grava (transparente)
            cinza = QImage(alfa.size(), QImage.Format_ARGB32_Premultiplied)
            cinza.fill(tinta)
            cinza.setAlphaChannel(alfa)
            p.drawImage(path.boundingRect(), cinza)
        elif c is not None and c.modo == "preenchimento":
            p.fillPath(path, tinta)
        else:
            pen = QPen(tinta, 0.35 * esc)  # linha: ~0,35 mm na peça
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    p.end()
    return img, caixa.width(), caixa.height()


NOME_AREA = "Volta completa 360°"


def area_360(janela):
    """Retângulo da área de gravação 360° na aba atual (cena, mm) ou None."""
    for s in janela.canvas.view.shapes():
        if s.layer == REFERENCIA and s.name.startswith(NOME_AREA):
            return s.sceneTransform().mapRect(s.path().boundingRect())
    return None


def textura_360(janela, area: QRectF, boca_esquerda=True):
    """Arte dentro da área 360° (X = ao longo da altura do copo, Y = em volta), já virada para o copo de pé:
    largura da imagem = volta inteira (circunferência), altura = altura da arte. None se a área estiver vazia."""
    folhas = [f for f in _folhas(janela, False) if f[1].mapRect(f[0].boundingRect()).intersects(area)]
    if not folhas:
        return None
    esc = min(PX_MM, MAX_LADO / max(area.width(), area.height()))
    w, h = max(1, round(area.height() * esc)), max(1, round(area.width() * esc))  # já girada
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    # Copo deitado no rotativo, visto de cima = como está na mesa. Em pé, olhando a gravação de frente: descer no
    # copo = +X (a boca é o lado esquerdo) e ir para a direita em volta = −Y. É uma ROTAÇÃO (não espelha): a arte
    # entra na área girada 90° para a esquerda, com o topo dela virado para a boca.
    if boca_esquerda:
        base = QTransform(0, 1, -1, 0, area.bottom(), -area.left())   # u = baixo − y, v = x − esquerda
    else:
        base = QTransform(0, -1, 1, 0, -area.top(), area.right())     # u = y − topo, v = direita − x
    base = base * QTransform.fromScale(esc, esc)
    tinta = QColor(20, 20, 20)
    p.setClipRect(QRectF(0, 0, w, h))
    for path, tf, c, extra in folhas:
        p.setTransform(tf * base)
        if isinstance(extra, ImagemOriginal):
            alfa = extra.qimage.convertToFormat(QImage.Format_Grayscale8)
            alfa.invertPixels()
            cinza = QImage(alfa.size(), QImage.Format_ARGB32_Premultiplied)
            cinza.fill(tinta)
            cinza.setAlphaChannel(alfa)
            p.drawImage(path.boundingRect(), cinza)
        elif c is not None and c.modo == "preenchimento":
            p.fillPath(path, tinta)
        else:
            pen = QPen(tinta, 0.35 * esc)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    p.end()
    return img, area.height(), area.width()
