"""Objetos do documento e transformações de seleção (Etapa 3).

Tudo em coordenadas de documento (cena, mm, Y para baixo). Cada objeto guarda um caminho e
uma matriz; transformações são aplicadas como matrizes explícitas sobre a seleção inteira,
sempre em torno de um ponto (âncora do seletor de 9 pontos ou centro).
"""
import math
from dataclasses import dataclass, replace

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QStyle

from .camadas import IDS, PALETA, cor
from .texto import TextoParams, build_path, font_available
from .variaveis import renderizar

EPS = 1e-9


ESPESSURA = 2.5  # px na tela (Configurações → Visual); não muda o corte


# Área de clique: o miolo de peças fechadas + uma faixa de TOL_PX pixels em volta da linha (fácil de acertar
# com zoom longe); peças pequenas na tela, textos e imagens: a caixa toda. Quem decide entre mover e fazer a
# caixa de seleção (peça com outras dentro) é a área de desenho. ESCALA_TELA (px por mm) segue o zoom.
TOL_PX = 6.0
PEQUENO_PX = 24.0
COMPLEXO = 1500  # pontos: acima disso a área de clique é a caixa (sem união booleana, que é lenta)
MARGEM_MAX_MM = 6.0
ESCALA_TELA = 2.0


def _fechado(path) -> bool:
    """Algum contorno fechado (último ponto = primeiro)?"""
    ini = None
    for i in range(path.elementCount()):
        e = path.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            ini = (e.x, e.y)
        elif ini is not None and abs(e.x - ini[0]) < 1e-9 and abs(e.y - ini[1]) < 1e-9 and i > 0 and (
                i + 1 == path.elementCount() or path.elementAt(i + 1).type == QPainterPath.MoveToElement):
            return True
    return False


SELECAO_COR = QColor("#ff2bd6")  # realce das peças selecionadas (bem visível nos três fundos)


def _caneta_selecao():
    pen = QPen(SELECAO_COR, ESPESSURA + 1.0, Qt.DashLine)
    pen.setCosmetic(True)
    return pen


def _escala_item(item) -> float:
    return max(1e-9, math.sqrt(abs(item.sceneTransform().determinant())))


PREENCHIDAS = set()  # camadas no modo Preenchimento: a tela mostra a área que será gravada (cor translúcida)


def definir_preenchidas(ids) -> None:
    PREENCHIDAS.clear()
    PREENCHIDAS.update(ids)


def _tinta(cor) -> QColor:
    c = QColor(cor)
    c.setAlpha(85)
    return c


def definir_espessura(px: float) -> None:
    global ESPESSURA
    ESPESSURA = max(0.5, min(8.0, float(px)))


class Shape(QGraphicsPathItem):
    bloqueado = False  # Organizar → Bloquear: não se move, não muda de tamanho nem gira
    ancora = None  # objeto "pai": quando ele se move/gira/escala, este acompanha (ver MainWindow._seguir_ancoras)
    grupo_aberto = None  # (id, nome) do grupo aberto para edição de que este objeto faz parte (MainWindow.abrir_grupo)

    def __init__(self, path: QPainterPath, name: str, layer: str, color: str):
        super().__init__(path)
        self.name, self.layer, self.color = name, layer, color
        pen = QPen(QColor(color), ESPESSURA)
        pen.setCosmetic(True)  # espessura em pixels, independente do zoom
        self.setPen(pen)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected  # a caixa de seleção é desenhada pelo overlay
        if self.path().elementCount() > COMPLEXO:  # traçado de foto: sem antialiasing desenha ~12x mais rápido
            painter.setRenderHint(QPainter.Antialiasing, False)
        if self.layer in PREENCHIDAS:
            painter.fillPath(self.path(), _tinta(self.color))
        super().paint(painter, option, widget)
        if self.isSelected():  # cada peça selecionada fica tracejada em destaque
            painter.setPen(_caneta_selecao())
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.path())

    _versao = 0
    _clique = None  # (chave, caminho) da área de clique em cache

    def setPath(self, path):
        self._versao += 1
        super().setPath(path)

    def boundingRect(self):
        m = MARGEM_MAX_MM / _escala_item(self)  # folga fixa: o índice da cena não precisa mudar com o zoom
        return self.path().boundingRect().adjusted(-m, -m, m, m)

    def _tolerancia(self):
        return min(TOL_PX / ESCALA_TELA, MARGEM_MAX_MM) / _escala_item(self)  # em unidades do objeto

    def contorno_clique(self):
        """Faixa em volta da linha (TOL_PX pixels), em coordenadas do objeto."""
        tol = self._tolerancia()
        chave = (round(tol, 9), self._versao)
        if getattr(self, "_faixa", None) is None or self._faixa[0] != chave:
            st = QPainterPathStroker()
            st.setWidth(2 * tol)
            st.setCapStyle(Qt.RoundCap)
            st.setJoinStyle(Qt.RoundJoin)
            self._faixa = (chave, st.createStroke(self.path()))
        return self._faixa[1]

    def shape(self):
        es, tol = _escala_item(self), self._tolerancia()
        r = self.path().boundingRect()
        # Muito complexo (ex.: traçado de foto): a união miolo + faixa leva minutos e travava a tela; clica na caixa.
        pequeno = (min(r.width(), r.height()) * es * ESCALA_TELA < PEQUENO_PX or self._clique_por_dentro()
                   or self.path().elementCount() > COMPLEXO)
        chave = (round(tol, 9), pequeno, self._versao)
        if self._clique is None or self._clique[0] != chave:
            if pequeno:
                area = QPainterPath()
                area.addRect(r.adjusted(-tol, -tol, tol, tol))
            elif _fechado(self.path()):
                area = self.path().united(self.contorno_clique())  # miolo + faixa da linha
            else:
                area = self.contorno_clique()  # linha aberta: só a faixa
            self._clique = (chave, area)
        return self._clique[1]

    def _clique_por_dentro(self):
        """Textos e imagens: clique em qualquer ponto da caixa."""
        return False

    extra = None  # ImagemOriginal (imagem) | TextoParams (texto) | None (vetor)

    def snapshot(self):
        """(caminho, matriz, nome, camada, cor, extra) — estado completo e imutável do objeto."""
        return (QPainterPath(self.path()), self.sceneTransform(), self.name, self.layer, self.color, self.extra)


class ImageShape(Shape):
    """Imagem raster: o caminho é o retângulo físico (mm); a imagem é desenhada dentro dele."""

    def __init__(self, imagem, w_mm: float, h_mm: float, name: str, layer="C00", color=PALETA[0]):
        path = QPainterPath()
        path.addRect(QRectF(0, 0, w_mm, h_mm))
        super().__init__(path, name, layer, color)
        self.extra = imagem

    @property
    def imagem(self):
        return self.extra

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(self.path().boundingRect(), self.imagem.qimage)

    def _clique_por_dentro(self):
        return True


class TextShape(Shape):
    """Texto editável. O contorno é gerado dos parâmetros; ao abrir um projeto usa-se o contorno
    salvo, de modo que a aparência não muda mesmo sem a fonte instalada."""

    def __init__(self, params: TextoParams, name: str, layer="C01", color=PALETA[1], path=None):
        super().__init__(path if path is not None else build_path(params), name, layer, color)
        self.extra = params

    def _clique_por_dentro(self):
        return True

    @property
    def params(self) -> TextoParams:
        return self.extra

    def shape(self):
        # Área clicável = retângulo do texto; só os traços das letras seria difícil de acertar.
        p = QPainterPath()
        p.addRect(self.path().boundingRect())
        return p

    @property
    def fonte_ausente(self) -> bool:
        return not font_available(self.extra.fonte)

    def set_params(self, params: TextoParams):
        self.setPath(build_path(params))
        self.extra = params


@dataclass(frozen=True)
class GroupData:
    children: tuple  # snapshots dos filhos, matrizes relativas ao grupo


class GroupShape(Shape):
    """Grupo: guarda os filhos como snapshots; o caminho é a união dos contornos (seleção/medidas)."""

    def __init__(self, data: GroupData, name: str, layer="—", color="#c9ccd2", path=None):
        if path is None:
            path = QPainterPath()
            for c in data.children:
                path.addPath(c[1].map(c[0]))
        super().__init__(path, name, layer, color)
        self.extra = data

    def shape(self):
        p = QPainterPath()
        p.addRect(self.path().boundingRect())  # clicar em qualquer ponto do grupo o seleciona
        return p

    def paint(self, painter, option, widget=None):
        _paint_children(painter, self.extra.children)
        if self.isSelected():
            painter.setPen(_caneta_selecao())
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.path())


def _paint_children(painter, children):
    for path, tf, _n, _l, color, extra in children:
        painter.save()
        painter.setTransform(tf, True)
        if isinstance(extra, GroupData):
            _paint_children(painter, extra.children)
        elif extra is not None and not isinstance(extra, TextoParams):  # imagem
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(path.boundingRect(), extra.qimage)
        else:
            if path.elementCount() > COMPLEXO:
                painter.setRenderHint(QPainter.Antialiasing, False)
            if _l in PREENCHIDAS:
                painter.fillPath(path, _tinta(color))
            pen = QPen(QColor(color), ESPESSURA)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        painter.restore()


def group(items) -> GroupShape:
    """Agrupa mantendo a posição exata: filhos guardam a matriz de cena atual; o grupo começa sem matriz."""
    children = tuple(it.snapshot() for it in items)
    return GroupShape(GroupData(children), f"Grupo ({len(children)})")


def ungroup(g: GroupShape) -> list:
    tf = g.sceneTransform()
    return [from_snapshot((c[0], c[1] * tf, *c[2:])) for c in g.extra.children]


# ---------- texto variável ----------
def renderizar_variaveis(snap, ctx):
    """Snapshot com textos variáveis redesenhados para o contexto (o modelo continua em TextoParams).

    `ctx`: dicionário, ou função peca -> dicionário (cada peça do gabarito tem sua linha).

    Devolve o MESMO objeto se nada mudou. Fonte não instalada: mantém o contorno salvo (não troca a
    aparência por uma fonte substituta).
    """
    path, tf, name, layer, color, extra = snap
    if isinstance(extra, GroupData):
        filhos = tuple(renderizar_variaveis(c, ctx) for c in extra.children)
        if all(a is b for a, b in zip(filhos, extra.children)):
            return snap
        gpath = QPainterPath()
        for c in filhos:
            gpath.addPath(c[1].map(c[0]))
        return (gpath, tf, name, layer, color, GroupData(filhos))
    if isinstance(extra, TextoParams) and extra.variavel and font_available(extra.fonte):
        texto, _ = renderizar(extra.texto, ctx(extra.peca) if callable(ctx) else ctx)
        novo = build_path(replace(extra, texto=texto if texto.strip() else "—", variavel=False))
        if novo != path:
            return (novo, tf, name, layer, color, extra)
    return snap


def pecas(snap) -> set:
    """Posições de gabarito (peca) dos textos variáveis do objeto, recursivo em grupos."""
    extra = snap[5]
    if isinstance(extra, GroupData):
        return set().union(*(pecas(c) for c in extra.children))
    return {extra.peca} if isinstance(extra, TextoParams) and extra.variavel else set()


def com_peca(snap, k: int):
    """Snapshot com os textos variáveis marcados como peça k do gabarito."""
    path, tf, name, layer, color, extra = snap
    if isinstance(extra, GroupData):
        return (path, tf, name, layer, color, GroupData(tuple(com_peca(c, k) for c in extra.children)))
    if isinstance(extra, TextoParams) and extra.variavel:
        return (path, tf, name, layer, color, replace(extra, peca=k))
    return snap


# ---------- camadas ----------
def with_layer(snap, layer_id: str):
    """Snapshot com a camada trocada; em grupos, todos os filhos (recursivo) mudam de camada."""
    path, tf, name, layer, color, extra = snap
    if isinstance(extra, GroupData):
        return (path, tf, name, layer, color, GroupData(tuple(with_layer(c, layer_id) for c in extra.children)))
    return (path, tf, name, layer_id, cor(layer_id), extra)


def leaf_layers(snap) -> set:
    """Camadas efetivamente usadas (grupos não têm camada própria)."""
    extra = snap[5]
    if isinstance(extra, GroupData):
        return set().union(*(leaf_layers(c) for c in extra.children))
    return {snap[3]}


def image_layers(snap) -> set:
    extra = snap[5]
    if isinstance(extra, GroupData):
        return set().union(*(image_layers(c) for c in extra.children))
    return {snap[3]} if extra is not None and not isinstance(extra, TextoParams) else set()


def normalize_layers(snap):
    """Projetos antigos usavam rótulos provisórios ("IMG", "—"): imagens -> C00, demais -> C01."""
    path, tf, name, layer, color, extra = snap
    if isinstance(extra, GroupData):
        return (path, tf, name, "—", color, GroupData(tuple(normalize_layers(c) for c in extra.children)))
    if layer in IDS:
        return snap
    return with_layer(snap, "C00" if extra is not None and not isinstance(extra, TextoParams) else "C01")


def from_snapshot(snap, name=None) -> Shape:
    path, tf, n, layer, color, extra = snap
    if extra is None:
        s = Shape(path, name or n, layer, color)
    elif isinstance(extra, GroupData):
        s = GroupShape(extra, name or n, layer, color, path=path)
    elif isinstance(extra, TextoParams):
        s = TextShape(extra, name or n, layer, color, path=path)
    else:
        r = path.boundingRect()
        s = ImageShape(extra, r.width(), r.height(), name or n, layer, color)
        s.setPath(path)  # mantém o retângulo exato salvo
    s.setTransform(tf)
    return s


def to_curves(item: "TextShape") -> Shape:
    """Texto -> vetor comum com o mesmo contorno e matriz (propriedades de texto descartadas)."""
    s = Shape(QPainterPath(item.path()), item.name, item.layer, item.color)
    s.setTransform(item.sceneTransform())
    return s


# ---------- medidas ----------
def angulo(item) -> float:
    """Giro atual do objeto em graus (positivo = horário na tela), de -180 a 180."""
    tf = item.sceneTransform()
    return math.degrees(math.atan2(tf.m12(), tf.m11()))


def escala_uniforme(item):
    """Escala do objeto se for igual nos dois eixos (com ou sem giro); None se esticado."""
    tf = item.sceneTransform()
    sx, sy = math.hypot(tf.m11(), tf.m12()), math.hypot(tf.m21(), tf.m22())
    return sx if abs(sx - sy) <= 1e-9 * max(sx, sy, 1.0) else None

def geom_rect(item) -> QRectF:
    """Retângulo exato da geometria (sem espessura de traço) em coordenadas de cena."""
    return item.sceneTransform().map(item.path()).boundingRect()


def bounds(items) -> QRectF:
    r = QRectF()
    for it in items:
        r = r.united(geom_rect(it)) if not r.isNull() else geom_rect(it)
    return r


def anchor_point(r: QRectF, idx: int) -> QPointF:
    """Ponto do seletor de 9 pontos: idx 0..8, linha a linha a partir do topo esquerdo da tela."""
    col, row = idx % 3, idx // 3
    return QPointF(r.left() + col * r.width() / 2, r.top() + row * r.height() / 2)


# ---------- transformações ----------
def _about(p: QPointF, tf: QTransform) -> QTransform:
    return QTransform.fromTranslate(-p.x(), -p.y()) * tf * QTransform.fromTranslate(p.x(), p.y())


def apply(items, m: QTransform):
    """Aplica m (em coordenadas de cena) depois da transformação atual de cada objeto."""
    for it in items:
        total = it.sceneTransform() * m
        it.setPos(0, 0)
        it.setTransform(total)


def restore(originals):
    for it, tf in originals:
        it.setPos(0, 0)
        it.setTransform(tf)


def move_by(items, dx, dy):
    apply(items, QTransform.fromTranslate(dx, dy))


def scale(items, sx, sy, p: QPointF):
    apply(items, _about(p, QTransform.fromScale(sx, sy)))


def rotate(items, deg, p: QPointF):
    """deg positivo = horário na tela (mesma convenção da referência)."""
    apply(items, _about(p, QTransform().rotate(deg)))


def set_anchor_pos(items, x, y, idx):
    p = anchor_point(bounds(items), idx)
    move_by(items, x - p.x(), y - p.y())


def set_size(items, w, h, idx):
    """Redimensiona a caixa da seleção para w × h mantendo fixo o ponto idx.

    Eixo com tamanho zero (ex.: linha horizontal) não é escalável e fica como está.
    """
    r = bounds(items)
    sx = w / r.width() if r.width() > EPS else 1.0
    sy = h / r.height() if r.height() > EPS else 1.0
    scale(items, sx, sy, anchor_point(r, idx))


def mirror(items, horizontal: bool):
    r = bounds(items)
    scale(items, -1 if horizontal else 1, 1 if horizontal else -1, r.center())


ALIGN = ("left", "hcenter", "right", "top", "vcenter", "bottom")


def align(items, mode: str):
    """Alinha cada objeto à caixa da seleção inteira."""
    ref = bounds(items)
    for it in items:
        r = geom_rect(it)
        dx = {"left": ref.left() - r.left(), "right": ref.right() - r.right(),
              "hcenter": ref.center().x() - r.center().x()}.get(mode, 0.0)
        dy = {"top": ref.top() - r.top(), "bottom": ref.bottom() - r.bottom(),
              "vcenter": ref.center().y() - r.center().y()}.get(mode, 0.0)
        move_by([it], dx, dy)


def distribute(items, horizontal: bool):
    """Centros igualmente espaçados entre o primeiro e o último (exige 3+ objetos)."""
    if len(items) < 3:
        return
    key = (lambda it: geom_rect(it).center().x()) if horizontal else (lambda it: geom_rect(it).center().y())
    order = sorted(items, key=key)
    a, b = key(order[0]), key(order[-1])
    step = (b - a) / (len(order) - 1)
    for i, it in enumerate(order[1:-1], 1):
        d = a + i * step - key(it)
        move_by([it], d if horizontal else 0, 0 if horizontal else d)
