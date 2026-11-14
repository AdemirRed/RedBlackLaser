"""Área de desenho — Etapa 2: zoom, deslocamento, grade adaptativa, réguas e medição em mm.

Cena em mm (coordenadas de documento, Y para baixo). Réguas e status usam coordenadas de
exibição (origem inferior esquerda) via redblack.geometria.
"""
import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QGridLayout, QLineEdit, QWidget
from shiboken6 import isValid

from .. import encaixe as enc
from .. import formas as fm
from .. import geometria as g
from .. import objetos as ob
from ..camadas import cor

RULER = 24
MARGIN = 8.0  # mm em volta da mesa no "Ajustar à área"
ZOOM_STEP = 1.25
HANDLE_PX = 8      # tamanho da alça na tela
ROT_OFFSET_PX = 24  # distância da alça de rotação acima da caixa
ROT_SNAP = 15.0     # graus, com Shift

# Alças de redimensionamento: (nome, coluna, linha) no seletor 3×3; "rot" = rotação.
HANDLES = (("nw", 0, 0), ("n", 1, 0), ("ne", 2, 0), ("e", 2, 1),
           ("se", 2, 2), ("s", 1, 2), ("sw", 0, 2), ("w", 0, 1))


def _shift_as_ctrl(e: QMouseEvent) -> QMouseEvent:
    """Shift+clique adiciona/remove da seleção, como na referência; o Qt usa Ctrl para isso.

    Precisa valer no pressionar e no soltar: o Qt alterna a seleção ao soltar.
    """
    if not e.modifiers() & Qt.ShiftModifier:
        return e
    mods = (e.modifiers() & ~Qt.ShiftModifier) | Qt.ControlModifier
    return QMouseEvent(e.type(), e.position(), e.globalPosition(), e.button(), e.buttons(), mods)


SNAP_PX = 12  # raio de encaixe na tela
# Fundo da área de desenho (Configurações → Visual): fora da mesa, mesa, grade menor e maior.
COR_PREVIA_CLARA = "#0b3fb3"  # prévia de desenho (linha/forma em andamento) na mesa clara
TEMAS = {"cinza": ("Cinza neutro (claro, sem ser branco)", "#3a3d42", "#c4c6ca", "#b6b9bd", "#9a9da3"),
         "grafite": ("Grafite (cinza médio escuro)", "#202226", "#4b4e55", "#555960", "#6c7078"),
         "escuro": ("Escuro (antigo)", "#15171a", "#2a2d33", "#33373e", "#4a4f5a")}
CONTORNO = QColor(20, 22, 26, 200)  # contorno escuro das marcas amarelas: visíveis em qualquer fundo


class SnapIndicator(QGraphicsItem):
    """Marca o ponto de encaixe sob o cursor: quadrado = canto/ponto, círculo = centro,
    losango = mesa, anel grande = início da linha (clicar fecha o contorno)."""

    ROTULOS = {"canto": "canto", "centro": "centro", "mesa": "mesa", "início": "fechar", "ponto": "ponto",
               "grade": "grade", "linha": "na linha"}

    def __init__(self):
        super().__init__()
        self.alvo = None
        self.setZValue(120)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setVisible(False)

    def set_alvo(self, alvo):
        if alvo == self.alvo:
            return
        self.prepareGeometryChange()
        self.alvo = alvo
        self.setVisible(alvo is not None)

    def boundingRect(self):
        if self.alvo is None:
            return QRectF()
        return QRectF(self.alvo.x - 60, self.alvo.y - 60, 120, 120)  # folga para o rótulo em qualquer zoom razoável

    def paint(self, p, option, widget=None):
        a = self.alvo
        if a is None:
            return
        tela = p.worldTransform().map(QPointF(a.x, a.y))
        p.save()
        p.resetTransform()  # desenha em pixels de tela
        for tinta, larg in ((CONTORNO, 4.5), (QColor("#ffcc33"), 2)):  # contorno escuro e depois o amarelo
            self._marca(p, a, tela, tinta, larg)
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        _rotulo(p, tela + QPointF(6 + 30, -6 - 8), self.ROTULOS.get(a.tipo, a.tipo))
        p.restore()

    @staticmethod
    def _marca(p, a, tela, cor, larg):
        p.setPen(QPen(cor, larg))
        p.setBrush(Qt.NoBrush)
        r = 6
        if a.tipo == "centro":
            p.drawEllipse(tela, r, r)
        elif a.tipo == "mesa":
            p.drawPolygon([tela + QPointF(0, -r - 2), tela + QPointF(r + 2, 0), tela + QPointF(0, r + 2), tela + QPointF(-r - 2, 0)])
        elif a.tipo == "início":
            p.setPen(QPen(QColor("#2bd46a") if cor != CONTORNO else cor, larg))
            p.drawEllipse(tela, r + 4, r + 4)
        elif a.tipo == "linha":  # X: um ponto qualquer sobre o contorno
            p.drawLine(tela + QPointF(-r, -r), tela + QPointF(r, r))
            p.drawLine(tela + QPointF(-r, r), tela + QPointF(r, -r))
        else:
            p.drawRect(QRectF(tela.x() - r, tela.y() - r, 2 * r, 2 * r))


def _mm(v: float) -> str:
    return f"{v:.2f} mm".replace(".", ",")


def lugar_numero_dist(pa: QPointF, pb: QPointF) -> QPointF:
    """Onde fica o número de uma linha de distância (pixels): ao lado da vertical, acima da horizontal — longe dos
    números de largura (embaixo da seleção) e altura (à direita)."""
    meio = (pa + pb) / 2
    return meio + (QPointF(40, 0) if abs(pb.x() - pa.x()) < abs(pb.y() - pa.y()) else QPointF(0, -12))


def _rotulo(p: QPainter, centro: QPointF, texto: str, cor=None):
    """Texto em pixels de tela com fundo escuro, centrado em `centro` (sistema atual do pintor)."""
    m = p.fontMetrics()
    w, h = m.horizontalAdvance(texto) + 8, m.height() + 2
    caixa = QRectF(centro.x() - w / 2, centro.y() - h / 2, w, h)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(21, 23, 26, 215))
    p.drawRoundedRect(caixa, 3, 3)
    p.setPen(cor or QColor("#ffcc33"))
    p.drawText(caixa, Qt.AlignCenter, texto)


EDITOR_CSS = ("QLineEdit{background:#15171a;color:#ffcc33;border:1px solid #ffcc33;border-radius:3px;"
              "padding:1px 4px}")
ROTULO_DIST = 14  # px entre a caixa e o centro do rótulo de largura/altura


def centros_rotulos(rr: QRectF) -> dict:
    """Centro (em pixels) dos rótulos de largura ("w", abaixo) e altura ("h", à direita) de uma caixa na tela."""
    return {"w": QPointF(rr.center().x(), rr.bottom() + ROTULO_DIST),
            "h": QPointF(rr.right() + ROTULO_DIST, rr.center().y())}


class MedidasOverlay(QGraphicsItem):
    """Valores das medidas na tela: comprimento em cima da linha medida (ou do segmento em desenho),
    largura abaixo e altura à direita da caixa da seleção ou da forma em desenho.

    Só exibe; não muda nada. `ativo` = opção "Mostrar medidas".
    """

    def __init__(self):
        super().__init__()
        self.ativo = True
        self.itens = {}  # nome -> QLineF (comprimento) ou QRectF (largura × altura)
        self.setZValue(110)
        self.setAcceptedMouseButtons(Qt.NoButton)

    def set(self, nome, valor):
        if valor is None or (isinstance(valor, QRectF) and valor.isNull()):
            if self.itens.pop(nome, None) is not None:
                self.update()
        elif self.itens.get(nome) != valor:
            self.itens[nome] = valor
            self.update()

    def set_ativo(self, on: bool):
        self.ativo = on
        self.update()

    def _visiveis(self):
        """A régua (Medir) sempre mostra a medida; o resto depende de "Mostrar medidas"."""
        return {k: v for k, v in self.itens.items() if self.ativo or k == "medida"}

    def textos(self):
        """Textos exibidos agora (para os testes)."""
        out = []
        for k, v in self._visiveis().items():
            if k == "dist":
                out += [_mm(d) for d, _, _ in v.values()]
            else:
                out += [_mm(v.length())] if isinstance(v, QLineF) else [_mm(v.width()), _mm(v.height())]
        return out

    def boundingRect(self):
        return self.scene().sceneRect() if self.scene() else QRectF()

    def paint(self, p, option, widget=None):
        itens = self._visiveis()
        if not itens:
            return
        tf = p.worldTransform()
        p.save()
        p.resetTransform()  # rótulos em pixels de tela, legíveis em qualquer zoom
        if "dist" in itens:  # linhas de distância da seleção até o que está em volta (clique no número)
            linha = QPen(QColor("#d63fd6"), 1.5, Qt.DashLine)
            for d, a, b in itens["dist"].values():
                pa, pb = tf.map(QPointF(*a)), tf.map(QPointF(*b))
                if QLineF(pa, pb).length() < 2:
                    continue
                p.setPen(QPen(CONTORNO, 3.5))
                p.drawLine(pa, pb)
                p.setPen(linha)
                p.drawLine(pa, pb)
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                _rotulo(p, lugar_numero_dist(pa, pb), _mm(d), QColor("#f08af0"))
        for nome, v in itens.items():
            if nome == "dist":
                continue
            regua = nome == "medida"
            p.setFont(QFont("Segoe UI", 10 if regua else 8, QFont.Bold if regua else QFont.Normal))
            if isinstance(v, QLineF):
                a, b = tf.map(v.p1()), tf.map(v.p2())
                if QLineF(a, b).length() < 1:
                    continue
                ang = math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))
                if ang > 90:  # texto nunca de cabeça para baixo
                    ang -= 180
                elif ang <= -90:
                    ang += 180
                if regua:  # tracinhos nas pontas, como numa trena
                    n = QLineF(a, b).normalVector().unitVector()
                    d = QPointF(n.dx(), n.dy()) * 7
                    tr = QPen(QColor("#ffcc33"), 2)
                    p.setPen(tr)
                    p.drawLine(a - d, a + d)
                    p.drawLine(b - d, b + d)
                p.save()
                p.translate((a + b) / 2)
                p.rotate(ang)
                _rotulo(p, QPointF(0, -14 if regua else -11), _mm(v.length()))  # em cima da linha
                p.restore()
            else:
                rr = tf.mapRect(v)
                c = centros_rotulos(rr)
                _rotulo(p, c["w"], _mm(v.width()))
                p.save()
                p.translate(c["h"])
                p.rotate(-90)
                _rotulo(p, QPointF(0, 0), _mm(v.height()))
                p.restore()
        p.restore()


class GabaritoOverlay(QGraphicsItem):
    """Células do gabarito (guia na tela, não vai para o laser), numeradas na ordem das peças."""

    def __init__(self):
        super().__init__()
        self.gabarito = None
        self._rect = QRectF()
        self.setZValue(-1)  # abaixo dos objetos
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setVisible(False)

    def set_gabarito(self, gb):
        self.prepareGeometryChange()
        self.gabarito = gb
        if gb is not None:
            x0, y0, x1, y1 = gb.limites()
            self._rect = QRectF(x0, y0, x1 - x0, y1 - y0).adjusted(-20, -20, 20, 20)
        self.setVisible(gb is not None)

    def boundingRect(self):
        return self._rect if self.gabarito else QRectF()

    def paint(self, p, option, widget=None):
        if self.gabarito is None:
            return
        pen = QPen(QColor("#33c3d6"), 1, Qt.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(QColor(51, 195, 214, 18))
        cel = self.gabarito.celulas()
        for x, y, w, h in cel:
            p.drawRect(QRectF(x, y, w, h))
        tf = p.worldTransform()
        p.save()
        p.resetTransform()
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#33c3d6"))
        for k, (x, y, _, _) in enumerate(cel, 1):
            p.drawText(tf.map(QPointF(x, y)) + QPointF(3, 12), str(k))
        p.restore()


class PercursoOverlay(QGraphicsItem):
    """Prévia do percurso: cortes na cor da camada, deslocamentos sem laser tracejados em cinza.

    A parte já executada (até o instante da simulação) fica forte; o restante, esmaecido.
    A cabeça do laser é um círculo cheio quando emite e vazado quando se desloca.
    """

    def __init__(self):
        super().__init__()
        self.percurso, self.cron, self.t = None, [], 0.0
        self.mostrar_vazios = True
        self._rect = QRectF()
        self._cortes_all, self._vazios_all = {}, QPainterPath()
        self._cortes_done, self._vazios_done = {}, QPainterPath()
        self._head, self._emitindo = None, False
        self.setZValue(50)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setVisible(False)

    @staticmethod
    def _add(path, pts):
        path.moveTo(*pts[0])
        for p in pts[1:]:
            path.lineTo(*p)

    def set_percurso(self, p):
        self.prepareGeometryChange()
        self.percurso = p
        self.cron = p.cronograma() if p else []
        self._cortes_all, self._vazios_all = {}, QPainterPath()
        b = p.limites() if p else None
        if b is None:
            self._rect = QRectF()
            self._head = None
        else:
            m = 15.0
            self._rect = QRectF(min(b[0], 0) - m, min(b[1], 0) - m, max(b[2], g.BED_W) - min(b[0], 0) + 2 * m,
                                max(b[3], g.BED_H) - min(b[1], 0) + 2 * m)
            for t in p.trechos:
                self._add(self._vazios_all if t.tipo != "corte" else self._cortes_all.setdefault(t.camada, QPainterPath()),
                          t.pontos)
        self.set_tempo(0.0)
        self.setVisible(p is not None and b is not None)

    def set_tempo(self, t: float):
        """Instante da simulação em segundos."""
        self.t = t
        self._cortes_done, self._vazios_done = {}, QPainterPath()
        p = self.percurso
        if p and p.trechos:
            n, parcial, self._head, self._emitindo = p.estado_em(t, self.cron)
            for tr in p.trechos[:n]:
                self._add(self._vazios_done if tr.tipo != "corte" else self._cortes_done.setdefault(tr.camada, QPainterPath()),
                          tr.pontos)
            if len(parcial) >= 2 and n < len(p.trechos):
                tr = p.trechos[n]
                self._add(self._vazios_done if tr.tipo != "corte" else self._cortes_done.setdefault(tr.camada, QPainterPath()),
                          parcial)
        self.update()

    def set_mostrar_vazios(self, on: bool):
        self.mostrar_vazios = on
        self.update()

    def boundingRect(self):
        return self._rect

    def paint(self, p, option, widget=None):
        if self.percurso is None:
            return
        s = p.worldTransform().m11() or 1.0

        def pen(color, alpha, width, dash=False):
            c = QColor(color)
            c.setAlpha(alpha)
            q = QPen(c, width)
            q.setCosmetic(True)
            if dash:
                q.setStyle(Qt.DashLine)
            return q

        p.setBrush(Qt.NoBrush)
        if self.mostrar_vazios:
            p.setPen(pen("#9aa0aa", 70, 1, True))
            p.drawPath(self._vazios_all)
            p.setPen(pen("#c9ccd2", 230, 1, True))
            p.drawPath(self._vazios_done)
        for lid, path in self._cortes_all.items():
            p.setPen(pen(cor(lid), 80, 1))
            p.drawPath(path)
        for lid, path in self._cortes_done.items():
            p.setPen(pen(cor(lid), 255, 2))
            p.drawPath(path)
        if self._head is not None:
            r = 6 / s
            p.setPen(pen("#ffffff", 255, 1.5))
            p.setBrush(QColor("#ff3b30") if self._emitindo else Qt.NoBrush)
            p.drawEllipse(QPointF(*self._head), r, r)


class NodeOverlay(QGraphicsItem):
    """Nós do caminho selecionado (modo Editar nós)."""

    def __init__(self):
        super().__init__()
        self.item, self.scale, self._pts, self._alcas = None, 1.0, [], []
        self.setZValue(101)
        self.setAcceptedMouseButtons(Qt.NoButton)

    def set_state(self, item, scale):
        def em_cena(i):
            e = item.path().elementAt(i)
            return item.sceneTransform().map(QPointF(e.x, e.y))
        pts = [] if item is None else [(i, em_cena(i)) for i in fm.nodes(item.path())]
        alcas = [] if item is None else [(i, em_cena(i), em_cena(no)) for i, no in fm.controles(item.path())]
        if item is self.item and scale == self.scale and pts == self._pts and alcas == self._alcas:
            return
        self.prepareGeometryChange()
        self.item, self.scale, self._pts, self._alcas = item, scale, pts, alcas
        self.setVisible(bool(pts))

    def node_points(self):
        return self._pts

    def handle_points(self):
        """[(índice do controle, ponto da alça, ponto do nó)] em coordenadas de cena."""
        return self._alcas

    def boundingRect(self):
        if not self._pts:
            return QRectF()
        todos = [p for _, p in self._pts] + [a for _, a, _ in self._alcas]
        xs, ys = [p.x() for p in todos], [p.y() for p in todos]
        m = HANDLE_PX / self.scale
        return QRectF(min(xs) - m, min(ys) - m, max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m)

    def paint(self, p, option, widget=None):
        pen = QPen(QColor("#ffffff"), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        h = (HANDLE_PX - 1) / self.scale
        if self._alcas:  # alças das curvas: linha até o nó e bolinha (arraste para mudar a curva)
            linha = QPen(QColor("#9aa3b2"), 1, Qt.DashLine)
            linha.setCosmetic(True)
            p.setPen(linha)
            for _, a, no in self._alcas:
                p.drawLine(no, a)
            p.setPen(pen)
            p.setBrush(QColor("#ffcc33"))
            for _, a, _ in self._alcas:
                p.drawEllipse(a, h / 2, h / 2)
        p.setBrush(QColor("#2f6bff"))
        for _, pt in self._pts:
            p.drawRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h))


class SelectionOverlay(QGraphicsItem):
    """Caixa da seleção com alças; tamanhos em pixels de tela, convertidos pela escala atual."""

    def __init__(self):
        super().__init__()
        self.rect = QRectF()
        self.scale = 1.0
        self.setZValue(100)
        self.setAcceptedMouseButtons(Qt.NoButton)

    def set_state(self, rect: QRectF, scale: float):
        if rect == self.rect and scale == self.scale:
            return
        self.prepareGeometryChange()
        self.rect, self.scale = rect, scale
        self.setVisible(not rect.isNull())

    def handle_points(self):
        r = self.rect
        pts = [(n, QPointF(r.left() + c * r.width() / 2, r.top() + w * r.height() / 2)) for n, c, w in HANDLES]
        pts.append(("rot", QPointF(r.center().x(), r.top() - ROT_OFFSET_PX / self.scale)))
        return pts

    def boundingRect(self):
        m = (ROT_OFFSET_PX + HANDLE_PX) / self.scale
        return self.rect.adjusted(-m, -m, m, m)

    def paint(self, p, option, widget=None):
        if self.rect.isNull():
            return
        dash = QPen(QColor("#e0313b"), 1, Qt.DashLine)
        dash.setCosmetic(True)
        p.setPen(dash)
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.rect)
        solid = QPen(QColor("#ffffff"), 1)
        solid.setCosmetic(True)
        p.setPen(solid)
        p.setBrush(QColor("#e0313b"))
        h = HANDLE_PX / self.scale
        for name, pt in self.handle_points():
            if name == "rot":
                p.drawLine(QPointF(pt.x(), self.rect.top()), pt)
                p.drawEllipse(pt, h / 2, h / 2)
            else:
                p.drawRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h))


class BedView(QGraphicsView):
    cursorMoved = Signal(object)   # (x, y) em coordenadas de exibição, ou None
    viewChanged = Signal()         # escala ou deslocamento mudou
    measured = Signal(str)         # texto da medição atual
    toolExit = Signal()            # Esc encerrou a ferramenta
    selectionGeometryChanged = Signal()  # seleção ou sua caixa mudou
    editBegin = Signal()           # antes de uma edição interativa (para o histórico)
    editEnd = Signal(str)          # depois dela, com o nome da operação
    textRequested = Signal(object)     # ferramenta Texto: clique em (QPointF de cena)
    editTextRequested = Signal(object)  # duplo clique num TextShape
    duploCliqueVazio = Signal(object)   # duplo clique na mesa sem objeto (QPointF de cena, mm)
    soltouArquivos = Signal(object, object)  # (QMimeData, QPointF de cena): arrastar e soltar na mesa
    shapeCreated = Signal(object, str)  # (QPainterPath em mm de cena, tipo) das ferramentas de desenho
    noOperacao = Signal(str, object)     # Editar nós: tecla (D I M L C S B) e ponto do cursor (QPointF de cena)
    aparoPedido = Signal(object)         # ferramenta Aparar: clique em (QPointF de cena)
    aparoSobre = Signal(object)          # ferramenta Aparar: mouse sobre (QPointF de cena) para realçar o trecho
    bolearPedido = Signal(object, bool)  # ferramenta Bolear: clique (QPointF de cena, Shift = pontas redondas)
    bolearSobre = Signal(object, bool)   # ferramenta Bolear: mouse sobre (prévia do arredondamento)
    medidaDigitada = Signal(str, float)  # ("w" | "h", mm) digitado no rótulo da seleção
    arrastando = Signal()                # objetos sendo arrastados/transformados (âncoras acompanham)
    pontoColetado = Signal(int, object)  # coleta de pontos (dois pontos): (quantos já, QPointF de cena)
    grupoAbrir = Signal(object)          # duplo clique num grupo: abrir para editar as peças

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)  # zoom ancorado manualmente
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # grade no fundo
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Área de desenho")
        self.fit_mode = True
        self.measure_mode = False
        self.text_mode = False
        self._pan_last = None
        self._space = False
        self.modo_mao = False  # ferramenta Mover a vista: botão esquerdo arrasta a vista
        self.coleta = None  # lista de pontos clicados (com encaixe) enquanto um comando pede pontos; Esc cancela
        self._measure_start = None
        sombra = QPen(CONTORNO, 4.5)
        sombra.setCosmetic(True)
        self._measure_sombra = scene.addLine(QLineF(), sombra)  # contorno escuro: visível no fundo claro
        self._measure_sombra.setZValue(9)
        self._measure_sombra.hide()
        regua = QPen(QColor("#ffcc33"), 2, Qt.DashLine)
        regua.setCosmetic(True)
        self._measure_line = scene.addLine(QLineF(), regua)
        self._measure_line.setZValue(10)
        self.tema = TEMAS["cinza"]
        self._measure_line.hide()
        self.horizontalScrollBar().valueChanged.connect(self.viewChanged)
        self.verticalScrollBar().valueChanged.connect(self.viewChanged)
        # Seleção
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)  # caixa: pega o que ela toca (linhas e peças)
        self.viewChanged.connect(self._escala_para_objetos)
        self.overlay = SelectionOverlay()
        scene.addItem(self.overlay)
        self._drag = None
        self._move_pending = False
        self._sel_rect = QRectF()
        self.dist = {}  # distâncias da seleção até o que está em volta (encaixe.distancias_lados)
        self._sel_ids = ()
        # Desenho e nós
        self.draw_tool = None  # "rect" | "ellipse" | "polygon" | "line"
        self.polygon_sides = 6
        self.raio_canto = 0.0  # mm, para novos retângulos
        self.star_razao = 0.5  # raio interno / externo das estrelas
        self.star_pontas = 5   # pontas da ferramenta Estrela (separado dos lados do Polígono)
        self.forma_pronta = "Estrela de 5 pontas"  # ferramenta "forma pronta" (menu suspenso das formas)
        self.node_mode = False
        self._shape_start = None
        self._line_pts = []
        self._line_alcas, self._line_arraste = {}, None  # alças (curvas) da linha em desenho; arraste em curso
        preview_pen = QPen(QColor(COR_PREVIA_CLARA), 2.0, Qt.DashLine)  # cor acompanha o tema (set_tema)
        preview_pen.setCosmetic(True)
        self._preview = scene.addPath(QPainterPath(), preview_pen)
        self._preview.setZValue(20)
        realce = QPen(QColor("#ff3b30"), 3)
        realce.setCosmetic(True)
        self._realce = scene.addPath(QPainterPath(), realce)
        self._realce.setZValue(21)
        self.node_overlay = NodeOverlay()
        scene.addItem(self.node_overlay)
        self.percurso_overlay = PercursoOverlay()
        scene.addItem(self.percurso_overlay)
        self.encaixe_ativo = True
        guia = QPen(QColor("#ff2bd6"), 1, Qt.DashLine)
        guia.setCosmetic(True)
        self._guias = scene.addPath(QPainterPath(), guia)  # guias inteligentes ao arrastar objetos
        self._guias.setZValue(130)
        self._guias_alvos = None  # caixas dos outros objetos + mesa, calculadas uma vez por arraste
        self.snap_ind = SnapIndicator()
        scene.addItem(self.snap_ind)
        self.medidas = MedidasOverlay()
        scene.addItem(self.medidas)
        anc = QPen(QColor("#33c3d6"), 1, Qt.DashLine)
        anc.setCosmetic(True)
        self._ancoras = scene.addPath(QPainterPath(), anc)
        self._ancoras.setZValue(104)
        self.gabarito_overlay = GabaritoOverlay()
        scene.addItem(self.gabarito_overlay)
        self._node_drag = None
        self.snap_px = SNAP_PX
        self.encaixe_grade = False
        self.zoom_invertido = False
        self.passo_seta, self.passo_seta_shift = 1.0, 10.0  # mm (Configurações)
        self.permitir = {"mover": True, "tamanho": True, "girar": True, "cisalhar": False}  # barra de status
        self._sem_arrasto = False
        self.ordem_sel = []  # seleção na ordem em que foi feita (o 1º é a âncora ao prender)
        self.editor_medida = QLineEdit(self.viewport())
        self.editor_medida.setAccessibleName("Digitar medida")
        self.editor_medida.setAlignment(Qt.AlignCenter)
        self.editor_medida.setStyleSheet(EDITOR_CSS)
        self.editor_medida.hide()
        self.editor_medida.returnPressed.connect(self._aplicar_medida)
        self.editor_medida.installEventFilter(self)
        self._medida_qual = None
        scene.selectionChanged.connect(self.refresh_selection)
        scene.changed.connect(self.refresh_selection)
        self.viewChanged.connect(self.refresh_selection)

    # ---------- seleção ----------
    def shapes(self):
        s = self.scene()  # None quando sinais atrasados chegam durante o encerramento
        return [it for it in s.items(Qt.AscendingOrder) if isinstance(it, ob.Shape)] if s else []

    def selected(self):
        return [it for it in self.shapes() if it.isSelected()]

    def refresh_selection(self, *_):
        if not isValid(self.overlay):  # cena sendo destruída ao fechar a janela
            return
        sel = self.selected()
        self.ordem_sel = [x for x in self.ordem_sel if x in sel] + [x for x in sel if x not in self.ordem_sel]
        rect = ob.bounds(sel) if sel else QRectF()
        # Edição de nós: só num único caminho comum (texto/imagem/grupo não têm nós editáveis).
        target = sel[0] if self.node_mode and len(sel) == 1 and type(sel[0]) is ob.Shape else None
        self.node_overlay.set_state(target, self.scale_px_mm)
        self.overlay.set_state(QRectF() if self.node_mode else rect, self.scale_px_mm)
        self.medidas.set("sel", None if self.node_mode else rect)
        ids = tuple(id(it) for it in sel)
        if rect != self._sel_rect or ids != self._sel_ids:
            self._sel_rect, self._sel_ids = rect, ids
            self.dist = {}
            if sel and not self.node_mode and self.medidas.ativo:
                outros = [s.snapshot() for s in self.shapes() if s.isVisible() and not s.isSelected()]
                self.dist = enc.distancias_lados(rect.getCoords(), outros, g.BED_W, g.BED_H)
            self.medidas.set("dist", {f"d_{k}": v for k, v in self.dist.items()} or None)
            self.selectionGeometryChanged.emit()

    def handle_at(self, view_pos):
        if not self.overlay.isVisible() or any(s.bloqueado for s in self.selected()):
            return None
        for name, pt in self.overlay.handle_points():
            meio = name in ("n", "s", "e", "w")
            chave = "girar" if name == "rot" else "cisalhar" if meio and self.permitir["cisalhar"] else "tamanho"
            if not self.permitir[chave]:
                continue
            d = QPointF(self.mapFromScene(pt)) - QPointF(view_pos)
            if abs(d.x()) <= HANDLE_PX and abs(d.y()) <= HANDLE_PX:
                return name
        return None

    def _drag_update(self, scene_pos: QPointF, free: bool):
        d = self._drag
        ob.restore(d["originals"])
        items = [it for it, _ in d["originals"]]
        r, start = d["rect"], d["start"]
        if d["kind"] == "rot":
            c = r.center()
            a = math.degrees(math.atan2(scene_pos.y() - c.y(), scene_pos.x() - c.x())
                             - math.atan2(start.y() - c.y(), start.x() - c.x()))
            if free:  # Shift: passos de 15°
                a = round(a / ROT_SNAP) * ROT_SNAP
            ob.rotate(items, a, c)
            self.measured.emit(f"Girar: {a:+.1f}°".replace(".", ","))
            return
        if d["kind"] in ("n", "s", "e", "w") and self.permitir["cisalhar"]:  # tira do esquadro
            col, row = next((c, w) for n, c, w in HANDLES if n == d["kind"])
            anchor = ob.anchor_point(r, (2 - row) * 3 + (2 - col))  # meio do lado oposto
            tf = QTransform()
            if d["kind"] in ("n", "s"):
                k = (scene_pos.x() - start.x()) / (start.y() - anchor.y())
                tf = QTransform(1, 0, k, 1, 0, 0)  # x' = x + k·y
                txt = f"Cisalhar X: {math.degrees(math.atan(k)):+.1f}°"
            else:
                k = (scene_pos.y() - start.y()) / (start.x() - anchor.x())
                tf = QTransform(1, k, 0, 1, 0, 0)  # y' = y + k·x
                txt = f"Cisalhar Y: {math.degrees(math.atan(k)):+.1f}°"
            ob.apply(items, ob._about(anchor, tf))
            self.measured.emit(txt.replace(".", ","))
            return
        col, row = next((c, w) for n, c, w in HANDLES if n == d["kind"])
        anchor = ob.anchor_point(r, (2 - row) * 3 + (2 - col))  # ponto oposto
        sx = (scene_pos.x() - anchor.x()) / (start.x() - anchor.x()) if col != 1 else 1.0
        sy = (scene_pos.y() - anchor.y()) / (start.y() - anchor.y()) if row != 1 else 1.0
        if col != 1 and row != 1 and not free:  # canto: proporção mantida; Shift libera
            sx = sy = sx if abs(sx) >= abs(sy) else sy
        sx, sy = max(sx, 1e-3), max(sy, 1e-3)  # espelhar é pelo menu, não arrastando
        ob.scale(items, sx, sy, anchor)
        b = ob.bounds(items)
        self.measured.emit(f"Tamanho: {b.width():.2f} × {b.height():.2f} mm".replace(".", ","))

    def set_ancoras(self, pares):
        """[(centro da âncora, centro do preso)] em mm: linhas tracejadas com um ponto na âncora."""
        if not isValid(self._ancoras):  # cena sendo destruída ao fechar a janela
            return
        p = QPainterPath()
        r = 3 / self.scale_px_mm
        for a, f in pares:
            p.moveTo(a)
            p.lineTo(f)
            p.addEllipse(a, r, r)
        self._ancoras.setPath(p)

    # ---------- medida digitada no rótulo ----------
    def rotulo_em(self, view_pos):
        """"w"/"h" se view_pos está sobre o rótulo de largura/altura da seleção (rótulos visíveis)."""
        if not self.medidas.ativo or self._sel_rect.isNull() or self.node_mode:
            return None
        c = centros_rotulos(QRectF(self.mapFromScene(self._sel_rect).boundingRect()))
        for k, pt in c.items():
            meia_l, meia_a = (45, 10) if k == "w" else (10, 45)  # altura: rótulo em pé
            if abs(view_pos.x() - pt.x()) <= meia_l and abs(view_pos.y() - pt.y()) <= meia_a:
                return k
        for k, pt in self._centros_dist().items():
            if abs(view_pos.x() - pt.x()) <= 40 and abs(view_pos.y() - pt.y()) <= 11:
                return k
        return None

    def _centros_dist(self):
        """Centro (pixels da vista) do número de cada linha de distância visível."""
        out = {}
        for lado, (_, a, b) in (getattr(self, "dist", None) or {}).items():
            pa, pb = QPointF(self.mapFromScene(QPointF(*a))), QPointF(self.mapFromScene(QPointF(*b)))
            if QLineF(pa, pb).length() >= 2:
                out[f"d_{lado}"] = lugar_numero_dist(pa, pb)
        return out

    def editar_medida(self, qual, texto=None):
        """Abre a caixa de digitação sobre o rótulo; Enter aplica, Tab troca largura/altura, Esc cancela."""
        if self._sel_rect.isNull():
            return
        self._medida_qual = qual
        if qual.startswith("d_"):
            valor = self.dist[qual[2:]][0]
            c = self._centros_dist()[qual]
        else:
            valor = self._sel_rect.width() if qual == "w" else self._sel_rect.height()
            c = centros_rotulos(QRectF(self.mapFromScene(self._sel_rect).boundingRect()))[qual]
        e = self.editor_medida
        e.setStyleSheet(EDITOR_CSS)
        e.setText(texto if texto is not None else f"{valor:.2f}".replace(".", ","))
        e.resize(90, 22)
        e.move(round(c.x() - 45), round(c.y() - 11))
        e.setToolTip("Largura em mm (Enter aplica, Tab vai para a altura, Esc cancela)" if qual == "w" else
                     "Altura em mm (Enter aplica, Tab vai para a largura, Esc cancela)" if qual == "h" else
                     "Distância até o que a linha toca, em mm (Enter move o objeto, Esc cancela)")
        e.show()
        e.setFocus()
        if texto is None:
            e.selectAll()
        else:
            e.deselect()
            e.setCursorPosition(len(texto))

    def _aplicar_medida(self, depois=None):
        try:
            v = float(self.editor_medida.text().strip().replace(",", ".").replace("mm", ""))
        except ValueError:
            v = 0.0
        minimo_ok = v >= 0 if (self._medida_qual or "").startswith("d_") else v > 0
        if not (minimo_ok and v <= 10000):
            self.editor_medida.setStyleSheet(self.editor_medida.styleSheet().replace("#ffcc33;border-radius",
                                                                                     "#e0313b;border-radius"))
            return
        qual = self._medida_qual
        self.editor_medida.hide()
        self.setFocus()
        self.medidaDigitada.emit(qual, v)
        if depois:
            self.editar_medida(depois)

    def eventFilter(self, obj, ev):
        if obj is not getattr(self, "editor_medida", None):  # o Qt usa o filtro antes do editor existir
            return super().eventFilter(obj, ev)
        if ev.type() == ev.Type.KeyPress:
            if ev.key() == Qt.Key_Escape:
                self.editor_medida.hide()
                self.setFocus()
                return True
            if ev.key() in (Qt.Key_Tab, Qt.Key_Backtab):
                q = self._medida_qual
                self._aplicar_medida(None if q.startswith("d_") else "h" if q == "w" else "w")
                return True
        if obj is self.editor_medida and ev.type() == ev.Type.FocusOut and self.editor_medida.isVisible():
            self.editor_medida.hide()  # clicou fora: cancela sem aplicar
        return super().eventFilter(obj, ev)

    # ---------- encaixe ----------
    def snap(self, scene_pt: QPointF, mods=Qt.NoModifier, extras=(), excluir=None) -> QPointF:
        """Ponto encaixado no canto/centro/ponto mais próximo (raio de SNAP_PX na tela).

        Alt segura = sem encaixe. `excluir`: posição a ignorar (o nó que está sendo arrastado).
        """
        if not self.encaixe_ativo or mods & Qt.AltModifier:
            self.snap_ind.set_alvo(None)
            return scene_pt
        snaps, alvos_obj = self._alvos_dos_objetos()
        alvos = list(extras) + enc.alvos_mesa(g.BED_W, g.BED_H) + alvos_obj
        if excluir is not None:
            alvos = [a for a in alvos if abs(a.x - excluir.x()) > 1e-9 or abs(a.y - excluir.y()) > 1e-9]
        raio = self.snap_px / self.scale_px_mm
        a = enc.mais_proximo(scene_pt.x(), scene_pt.y(), alvos, raio)
        if a is None and excluir is None:  # nenhum canto/centro perto: gruda em qualquer ponto do contorno
            a = enc.ponto_na_linha(snaps, scene_pt.x(), scene_pt.y(), raio)
        if a is None and self.encaixe_grade:  # grade menor visível, alinhada à origem inferior esquerda
            passo = g.steps_for(self.scale_px_mm)[0]
            x = round(scene_pt.x() / passo) * passo
            y = g.BED_H - round((g.BED_H - scene_pt.y()) / passo) * passo
            a = enc.Alvo(x, y, "grade")
        self.snap_ind.set_alvo(a)
        return QPointF(a.x, a.y) if a else scene_pt

    def _alvos_dos_objetos(self):
        """(snapshots, alvos de encaixe) dos objetos visíveis. Com ferramenta de desenho ativa os objetos não mudam a
        cada movimento do mouse: guarda em cache enquanto a lista/posição dos objetos for a mesma (era ~24 ms por
        movimento com 400 objetos)."""
        formas = [s for s in self.shapes() if s.isVisible()]
        chave = tuple((id(s), s.pos().x(), s.pos().y(), s.transform().m11(), s.transform().m12(),
                       s.transform().m21(), s.transform().m22(), s.path().elementCount()) for s in formas)
        cache = getattr(self, "_cache_alvos", None)
        if not self.draw_tool or cache is None or cache[0] != chave:
            snaps = [s.snapshot() for s in formas]
            cache = (chave, snaps, [a for sn in snaps for a in enc.alvos_de_snapshot(sn)])
            self._cache_alvos = cache if self.draw_tool else None
        return cache[1], cache[2]

    def _line_extras(self):
        pts = self._line_pts
        return [enc.Alvo(p.x(), p.y(), "início" if i == 0 and len(pts) >= 2 else "ponto") for i, p in enumerate(pts)]

    # ---------- ferramentas de desenho ----------
    def realcar(self, path):
        """Trecho em destaque (vermelho) — usado pela ferramenta Aparar."""
        self._realce.setPath(path if path is not None else QPainterPath())

    def set_draw_tool(self, kind):
        self.draw_tool = kind
        self._shape_start = None
        self._line_pts = []
        self._line_alcas, self._line_arraste = {}, None
        self._preview.setPath(QPainterPath())
        self._realce.setPath(QPainterPath())
        self.medidas.set("segmento", None)
        self.medidas.set("previa", None)
        self.snap_ind.set_alvo(None)
        self._guias.setPath(QPainterPath())
        self._update_cursor()

    def set_node_mode(self, on: bool):
        self.node_mode = on
        self._node_drag = None
        self.refresh_selection()

    def _shape_path(self, end: QPointF, mods) -> QPainterPath:
        a, kind = self._shape_start, self.draw_tool
        if kind == "star":
            r = g.distance((a.x(), a.y()), (end.x(), end.y()))
            return fm.star_path(a, r, max(3, self.star_pontas), self.star_razao) if r > 0 else QPainterPath()
        if kind == "polygon":
            r = g.distance((a.x(), a.y()), (end.x(), end.y()))
            return fm.polygon_path(a, r, self.polygon_sides) if r > 0 else QPainterPath()
        rect = fm.drag_rect(a, end, bool(mods & Qt.ShiftModifier), bool(mods & Qt.ControlModifier))
        if rect.width() <= 0 or rect.height() <= 0:
            return QPainterPath()
        if kind == "preset":
            from .. import formas_prontas
            return formas_prontas.forma_pronta(self.forma_pronta, rect)
        if kind == "rect":
            return fm.arredondar(fm.rect_path(rect), self.raio_canto)[0]  # raio 0 = cantos vivos
        return fm.ellipse_path(rect)

    def _show_shape_preview(self, path: QPainterPath):
        self._preview.setPath(path)
        b = path.boundingRect()
        self.medidas.set("previa", b)
        extra = ""
        if self.draw_tool in ("polygon", "star") and not path.isEmpty():
            c = self._shape_start
            e = path.elementAt(0)
            n = self.star_pontas if self.draw_tool == "star" else self.polygon_sides
            extra = f"   raio {g.distance((c.x(), c.y()), (e.x, e.y)):.2f} mm, {n} " + (
                "pontas" if self.draw_tool == "star" else "lados")
        self.measured.emit(f"Tamanho: {b.width():.2f} × {b.height():.2f} mm{extra}".replace(".", ","))

    def _line_point(self, scene_pt, mods):
        p = self.snap(scene_pt, mods, self._line_extras())
        if self.snap_ind.alvo is None and mods & Qt.ShiftModifier and self._line_pts:
            p = fm.snap_angle(self._line_pts[-1], scene_pt)  # Shift: múltiplos de 45° (sem encaixe)
        if self.snap_ind.alvo is None and self._line_pts and self.encaixe_ativo and not mods & Qt.AltModifier:
            return self._alinhar_linha(p, bool(mods & Qt.ShiftModifier))
        self._guias.setPath(QPainterPath())
        return p

    def _alinhar_linha(self, p, so_um_eixo=False):
        """Linhas de alinhamento ao desenhar: se o mouse está na mesma vertical/horizontal de um ponto já feito
        (mesmo longe), gruda nela e mostra a guia tracejada até esse ponto — fecha caixas no esquadro."""
        tol = self.snap_px / self.scale_px_mm
        refs = self._line_pts + [QPointF(a.x, a.y) for a in self._alvos_dos_objetos()[1] if a.tipo != "centro"]
        guias = QPainterPath()
        ax = min((r for r in refs if abs(r.x() - p.x()) <= tol), key=lambda r: abs(r.x() - p.x()), default=None)
        ay = min((r for r in refs if abs(r.y() - p.y()) <= tol), key=lambda r: abs(r.y() - p.y()), default=None)
        if so_um_eixo and ax is not None and ay is not None:  # Shift (45°) já fixou a direção: só um eixo
            ay = None
        if ax is not None:
            p = QPointF(ax.x(), p.y())
        if ay is not None:
            p = QPointF(p.x(), ay.y())
        for r in (ax, ay):
            if r is not None:
                guias.moveTo(r)
                guias.lineTo(p)
        self._guias.setPath(guias)
        return p

    def _line_preview(self, extra=None):
        pts = self._line_pts + ([extra] if extra is not None else [])
        path = fm.caminho_com_alcas(pts, self._line_alcas) if len(pts) >= 2 else QPainterPath()
        for i, a in self._line_alcas.items():  # alças visíveis enquanto desenha
            if i < len(self._line_pts):
                c = self._line_pts[i]
                path.moveTo(c - a)
                path.lineTo(c + a)
        self.medidas.set("segmento", QLineF(pts[-2], pts[-1]) if len(pts) >= 2 else None)
        if self._line_pts:  # marca o ponto inicial: clicar nele fecha o contorno
            r = 5 / self.scale_px_mm
            path.addEllipse(self._line_pts[0], r, r)
        self._preview.setPath(path)

    def _line_click(self, scene_pt, view_pos, mods):
        pts = self._line_pts
        pt = self._line_point(scene_pt, mods)
        if len(pts) >= 2:
            first = QPointF(self.mapFromScene(pts[0]))
            perto = math.hypot(first.x() - view_pos.x(), first.y() - view_pos.y()) <= fm.CLOSE_PX
            if pt == pts[0] or perto:
                self._finish_line(closed=True)
                return
        pts.append(pt)
        self._line_arraste = (len(pts) - 1, QPointF(view_pos))  # arrastar antes de soltar = curva
        self._line_preview()

    def _comprimento_digitado(self, mods=Qt.NoModifier):
        """Linha em andamento + número digitado: o próximo ponto fica exatamente a essa distância do último.
        Enter = no esquadro (horizontal ou vertical, para o lado do mouse); Shift+Enter = no ângulo livre do mouse.
        Devolve o ponto criado ou None."""
        txt, self._digitado = getattr(self, "_digitado", ""), ""
        try:
            d = float(txt.replace(",", "."))
        except ValueError:
            return None
        if not self._line_pts or d <= 0:
            return None
        a = self._line_pts[-1]
        alvo = getattr(self, "_mouse_linha", None) or a + QPointF(1, 0)
        v = alvo - a
        n = math.hypot(v.x(), v.y())
        if n < 1e-9:
            v, n = QPointF(1, 0), 1.0  # mouse em cima do ponto: segue para a direita
        elif not mods & Qt.ShiftModifier:  # esquadro: o eixo mais perto da direção do mouse
            v = QPointF(math.copysign(n, v.x()), 0) if abs(v.x()) >= abs(v.y()) else QPointF(0, math.copysign(n, v.y()))
        pt = a + v * (d / n)
        self._line_pts.append(pt)
        self._line_arraste = None
        self._line_preview(alvo)
        self.measured.emit(f"Segmento de {d:g} mm".replace(".", ","))
        return pt

    def _finish_line(self, closed=False):
        self._digitado = ""
        self._guias.setPath(QPainterPath())
        pts, self._line_pts = self._line_pts, []
        alcas, self._line_alcas, self._line_arraste = self._line_alcas, {}, None
        self._preview.setPath(QPainterPath())
        self.medidas.set("segmento", None)
        self.snap_ind.set_alvo(None)
        if len(pts) >= 2:
            self.shapeCreated.emit(fm.caminho_com_alcas(pts, alcas, closed), "line")

    def node_at(self, view_pos):
        """Índice do nó (ou da alça de curva) sob o cursor; nós têm prioridade."""
        for idx, pt in self.node_overlay.node_points():
            d = QPointF(self.mapFromScene(pt)) - QPointF(view_pos)
            if abs(d.x()) <= HANDLE_PX and abs(d.y()) <= HANDLE_PX:
                return idx
        for idx, pt, _ in self.node_overlay.handle_points():
            d = QPointF(self.mapFromScene(pt)) - QPointF(view_pos)
            if abs(d.x()) <= HANDLE_PX and abs(d.y()) <= HANDLE_PX:
                return idx
        return None

    def nudge(self, dx_mm, dy_display_mm):
        if any(s.bloqueado for s in self.selected()):
            return
        self.editBegin.emit()
        ob.move_by(self.selected(), dx_mm, -dy_display_mm)
        self.editEnd.emit("Mover com setas")

    # ---------- escala ----------
    @property
    def scale_px_mm(self) -> float:
        return self.transform().m11()

    def ajustar_a(self, r: QRectF):
        """Zoom para caber o retângulo (mm) com uma margem."""
        if r.isNull() or r.width() <= 0 and r.height() <= 0:
            return
        m = max(r.width(), r.height()) * 0.08 + 2
        self.fitInView(r.adjusted(-m, -m, m, m), Qt.KeepAspectRatio)
        s = g.clamp_scale(self.scale_px_mm)
        if s != self.scale_px_mm:
            c = r.center()
            self.setTransform(QTransform.fromScale(s, s))
            self.centerOn(c)
        self.fit_mode = False
        self.viewChanged.emit()

    def fit(self):
        self.fitInView(QRectF(-MARGIN, -MARGIN, g.BED_W + 2 * MARGIN, g.BED_H + 2 * MARGIN), Qt.KeepAspectRatio)
        self.fit_mode = True
        self.viewChanged.emit()

    def zoom_at(self, view_pos: QPointF, factor: float):
        """Zoom mantendo fixo o ponto da cena sob view_pos."""
        anchor = self.mapToScene(view_pos.toPoint())
        s = g.clamp_scale(self.scale_px_mm * factor)
        if s == self.scale_px_mm:
            return
        self.setTransform(QTransform.fromScale(s, s))
        self.fit_mode = False
        self.pan_by(self.mapFromScene(anchor) - view_pos.toPoint())
        self.viewChanged.emit()

    def zoom_center(self, factor: float):
        self.zoom_at(QPointF(self.viewport().rect().center()), factor)

    def pan_by(self, delta):
        """Desloca a vista em pixels (positivo = conteúdo vai para a esquerda/cima)."""
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() + round(delta.x()))
        v.setValue(v.value() + round(delta.y()))

    # ---------- eventos ----------
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewChanged.emit()  # réguas acompanham qualquer rolagem (barras, teclado), não só zoom/arraste

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit_mode:
            self.fit()
        self.viewChanged.emit()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120 * (-1 if self.zoom_invertido else 1)
        if steps:
            self.zoom_at(e.position(), ZOOM_STEP ** steps)
        e.accept()

    def event(self, e):
        # Editar nós: D/I/M/L/C/B são da edição, não dos atalhos globais (M = Medir etc.)
        if (e.type() == e.Type.ShortcutOverride and self.node_mode and e.text().upper() in ("D", "I", "M", "L", "C", "S", "B")
                and not e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Space and not e.isAutoRepeat():
            self._space = True
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif k in (Qt.Key_Plus, Qt.Key_Equal) and not e.modifiers() & Qt.ControlModifier:
            self.zoom_center(ZOOM_STEP)
        elif k == Qt.Key_Minus and not e.modifiers() & Qt.ControlModifier:
            self.zoom_center(1 / ZOOM_STEP)
        elif (self.draw_tool == "line" and self._line_pts and e.text() and e.text() in "0123456789.,"
              and not e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self._digitado = getattr(self, "_digitado", "") + e.text()  # medida exata do próximo segmento
            self.measured.emit(f"Comprimento: {self._digitado} mm — Enter = reto no esquadro, Shift+Enter = no "
                               "ângulo do mouse, Esc cancela")
        elif k == Qt.Key_Backspace and self.draw_tool == "line" and getattr(self, "_digitado", ""):
            self._digitado = self._digitado[:-1]
            self.measured.emit(f"Comprimento: {self._digitado} mm — Enter confirma, Esc cancela")
        elif k in (Qt.Key_Return, Qt.Key_Enter) and self.draw_tool == "line" and getattr(self, "_digitado", ""):
            self._comprimento_digitado(e.modifiers())
        elif k == Qt.Key_Escape and self.draw_tool == "line" and getattr(self, "_digitado", ""):
            self._digitado = ""
            self.measured.emit("Medida digitada cancelada")
        elif k in (Qt.Key_Return, Qt.Key_Enter) and self.draw_tool == "line" and self._line_pts:
            self._finish_line()
        elif k == Qt.Key_Escape and self.draw_tool == "line" and self._line_pts:
            self._line_pts = []  # cancela só a linha em andamento
            self._line_alcas, self._line_arraste = {}, None
            self._preview.setPath(QPainterPath())
            self.medidas.set("segmento", None)
        elif self.node_mode and e.text().upper() in ("D", "I", "M", "L", "C", "S", "B") and not e.modifiers() & (
                Qt.ControlModifier | Qt.AltModifier):
            pos = self.mapFromGlobal(self.cursor().pos())
            self.noOperacao.emit(e.text().upper(), self.mapToScene(pos))
        elif k == Qt.Key_Escape and self.coleta is not None:
            self.coleta = None
            self.snap_ind.set_alvo(None)
            self.pontoColetado.emit(0, None)  # 0 = cancelado
        elif k == Qt.Key_Escape and (self.measure_mode or self.text_mode or self.draw_tool or self.node_mode):
            self.toolExit.emit()
        elif k == Qt.Key_Escape and self.selected():
            self.scene().clearSelection()
        elif (e.text() and e.text() in "0123456789" and not e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)
              and self.selected() and not (self.measure_mode or self.text_mode or self.draw_tool or self.node_mode)):
            self.editar_medida("w", e.text())  # digitar um número com objeto selecionado = nova largura
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and self.selected():
            step = self.passo_seta_shift if e.modifiers() & Qt.ShiftModifier else self.passo_seta  # mm
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0.0)
            dy = {Qt.Key_Up: step, Qt.Key_Down: -step}.get(k, 0.0)
            self.nudge(dx, dy)
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = False
            self._pan_last = None
            self._update_cursor()
        else:
            super().keyReleaseEvent(e)

    def mousePressEvent(self, e):
        if self.coleta is not None and e.button() == Qt.LeftButton:
            p = self.snap(self.mapToScene(e.position().toPoint()), e.modifiers())
            self.coleta.append(p)
            self.pontoColetado.emit(len(self.coleta), p)
            return
        if (e.button() == Qt.LeftButton and not (self.measure_mode or self.text_mode or self.draw_tool)
                and not self.handle_at(e.position())  # alças (tamanho/girar) têm prioridade sobre os números
                and (q := self.rotulo_em(e.position()))):
            self.editar_medida(q)  # clicar no valor da largura/altura: digitar a medida ali mesmo
            return
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and (self._space or self.modo_mao)):
            self._pan_last = e.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
        elif e.button() == Qt.LeftButton and self.measure_mode:
            self._measure_start = self.snap(self.mapToScene(e.position().toPoint()), e.modifiers())
            self._set_measure(self._measure_start)
        elif e.button() == Qt.LeftButton and self.text_mode:
            self.textRequested.emit(self.snap(self.mapToScene(e.position().toPoint()), e.modifiers()))
        elif e.button() == Qt.LeftButton and self.draw_tool == "trim":
            self.aparoPedido.emit(self.mapToScene(e.position().toPoint()))
        elif e.button() == Qt.LeftButton and self.draw_tool == "bolear":
            self.bolearPedido.emit(self.mapToScene(e.position().toPoint()), bool(e.modifiers() & Qt.ShiftModifier))
        elif e.button() == Qt.LeftButton and self.draw_tool in ("rect", "ellipse", "polygon", "star", "preset"):
            self._shape_start = self.snap(self.mapToScene(e.position().toPoint()), e.modifiers())
        elif e.button() == Qt.LeftButton and self.draw_tool == "line":
            self._line_click(self.mapToScene(e.position().toPoint()), e.position(), e.modifiers())
        elif e.button() == Qt.LeftButton and self.node_mode and (n := self.node_at(e.position())) is not None:
            item = self.node_overlay.item
            self.editBegin.emit()
            nos_ = dict(self.node_overlay.node_points())
            alca = n not in nos_
            no = nos_[n] if not alca else next(a for i, a, _ in self.node_overlay.handle_points() if i == n)
            self._node_drag = {"item": item, "idx": n, "orig": QPainterPath(item.path()), "start": no, "alca": alca}
        elif e.button() == Qt.LeftButton and (h := self.handle_at(e.position())):
            sel = self.selected()
            self.editBegin.emit()
            self._drag = {"kind": h, "start": self.mapToScene(e.position().toPoint()),
                          "rect": ob.bounds(sel), "originals": [(it, it.sceneTransform()) for it in sel]}
        else:
            if e.button() == Qt.LeftButton:
                # Pode virar um arraste de objetos (Qt); o histórico ignora se nada mudar.
                self._move_pending = True
                self.editBegin.emit()
            sob, acima = self._mais_de_dentro(e.position().toPoint())
            somar = bool(e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier))
            self._sel_inicial = set(self.selected()) if somar else set()
            self._clique_recipiente = None
            if (e.button() == Qt.LeftButton and sob is not None and not sob.isSelected() and not somar
                    and not self._na_linha(sob, self.mapToScene(e.position().toPoint()))
                    and self._tem_pecas_dentro(sob)):
                # Miolo vazio de uma peça com outras dentro (base com furos): arrastar faz a caixa de seleção;
                # um clique sem arrastar seleciona a peça (ver mouseReleaseEvent).
                acima = [i for i in self.items(e.position().toPoint()) if isinstance(i, ob.Shape)]
                self._clique_recipiente = (sob, e.position())
                sob = None
            if e.button() == Qt.LeftButton:
                self._sem_arrasto = sob is not None and (not self.permitir["mover"] or sob.bloqueado
                                                         or (sob.isSelected() and any(s.bloqueado for s in self.selected())))
            for it in acima:  # os de cima deixam o clique passar para o objeto mais de dentro
                it.setAcceptedMouseButtons(Qt.NoButton)
            try:
                super().mousePressEvent(_shift_as_ctrl(e))
            finally:
                for it in acima:
                    it.setAcceptedMouseButtons(Qt.AllButtons)

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._pan_last is not None:
            self.pan_by(self._pan_last - pos)
            self._pan_last = pos
        elif self._measure_start is not None:
            self._set_measure(self.snap(self.mapToScene(pos.toPoint()), e.modifiers()))
        elif self._drag is not None:
            self._drag_update(self.mapToScene(pos.toPoint()), bool(e.modifiers() & Qt.ShiftModifier))
            self.arrastando.emit()
            p = self.mapToScene(pos.toPoint())
            self.cursorMoved.emit(g.to_display(p.x(), p.y()))
            return
        elif self._shape_start is not None:
            end = self.snap(self.mapToScene(pos.toPoint()), e.modifiers())
            self._show_shape_preview(self._shape_path(end, e.modifiers()))
        elif self._node_drag is not None:
            d = self._node_drag
            alvo = self.snap(self.mapToScene(pos.toPoint()), e.modifiers(), excluir=d["start"])
            inv, _ = d["item"].sceneTransform().inverted()
            now, start = inv.map(alvo), inv.map(d["start"])
            mover = fm.move_controle if d.get("alca") else fm.move_node
            d["item"].setPath(mover(d["orig"], d["idx"], now.x() - start.x(), now.y() - start.y()))
        elif self.draw_tool == "trim":
            self.aparoSobre.emit(self.mapToScene(pos.toPoint()))
        elif self.draw_tool == "bolear":
            self.bolearSobre.emit(self.mapToScene(pos.toPoint()), bool(e.modifiers() & Qt.ShiftModifier))
        elif self.draw_tool == "line" and self._line_arraste is not None and e.buttons() & Qt.LeftButton:
            i, ini = self._line_arraste
            if (pos - ini).manhattanLength() > 4:  # arrastou: o ponto ganha alça (curva)
                self._line_alcas[i] = self.mapToScene(pos.toPoint()) - self._line_pts[i]
                self._line_preview()
        elif self.draw_tool == "line":
            cur = self._line_point(self.mapToScene(pos.toPoint()), e.modifiers())
            self._mouse_linha = cur  # direção para a medida digitada
            self._line_preview(cur if self._line_pts else None)
        elif (self.measure_mode or self.text_mode or self.draw_tool or self.coleta is not None) and not (
                self._space or self.modo_mao):
            self.snap(self.mapToScene(pos.toPoint()), e.modifiers())  # mostra o encaixe antes do clique
        elif self.overlay.isVisible() and not self.measure_mode and not (self._space or self.modo_mao):
            h = self.handle_at(pos)
            cursors = {"n": Qt.SizeVerCursor, "s": Qt.SizeVerCursor, "e": Qt.SizeHorCursor, "w": Qt.SizeHorCursor,
                       "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor,
                       "sw": Qt.SizeBDiagCursor, "rot": Qt.CrossCursor}
            if h:
                self.viewport().setCursor(cursors[h])
            else:
                self._update_cursor()
        p = self.mapToScene(pos.toPoint())
        self.cursorMoved.emit(g.to_display(p.x(), p.y()))
        if self._sem_arrasto and e.buttons() & Qt.LeftButton:
            return  # Mover desligado ou objeto bloqueado: clique seleciona, mas não arrasta
        super().mouseMoveEvent(e)
        if e.buttons() & Qt.LeftButton and not self.rubberBandRect().isNull():
            self._caixa_selecao()
        if self._move_pending and e.buttons() & Qt.LeftButton:
            if isinstance(self.scene().mouseGrabberItem(), ob.Shape):  # arrastando objetos (não a caixa de seleção)
                self._alinhar_arraste(e.modifiers())
            self.arrastando.emit()  # o Qt já moveu os selecionados

    def mouseReleaseEvent(self, e):
        if self._pan_last is not None and e.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._pan_last = None
            self._update_cursor()
        elif e.button() == Qt.LeftButton and self._measure_start is not None:
            self._measure_start = None
        elif e.button() == Qt.LeftButton and self._drag is not None:
            kind = self._drag["kind"]
            self._drag = None
            self.refresh_selection()
            self.editEnd.emit("Girar" if kind == "rot" else "Redimensionar")
        elif e.button() == Qt.LeftButton and self._shape_start is not None:
            path = self._shape_path(self.snap(self.mapToScene(e.position().toPoint()), e.modifiers()), e.modifiers())
            self._shape_start = None
            self._preview.setPath(QPainterPath())
            self.medidas.set("previa", None)
            self.snap_ind.set_alvo(None)
            if not path.isEmpty():
                self.shapeCreated.emit(path, self.draw_tool)
        elif e.button() == Qt.LeftButton and self._node_drag is not None:
            self._node_drag = None
            self.snap_ind.set_alvo(None)
            self.refresh_selection()
            self.editEnd.emit("Editar nós")
        elif e.button() == Qt.LeftButton and self.draw_tool in ("line", "trim", "bolear"):
            self._line_arraste = None  # linhas: pontos no pressionar (arrastar = alça); aparar: no pressionar
        else:
            super().mouseReleaseEvent(_shift_as_ctrl(e))
            if e.button() == Qt.LeftButton and getattr(self, "_clique_recipiente", None):
                sob, ini = self._clique_recipiente
                self._clique_recipiente = None
                if (e.position() - ini).manhattanLength() < 4 and isValid(sob) and sob.scene() is self.scene():
                    self.scene().clearSelection()  # clique sem arrastar no miolo: seleciona a peça
                    sob.setSelected(True)
            if e.button() == Qt.LeftButton:
                self._sem_arrasto = False
            if e.button() == Qt.LeftButton and self._move_pending:
                self._move_pending = False
                self._guias.setPath(QPainterPath())
                self._guias_alvos = None
                self.editEnd.emit("Mover")

    # ---------- arrastar e soltar arquivos/imagens/SVG de fora ----------
    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage() or md.hasText():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage() or e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage() or md.hasText():
            e.acceptProposedAction()
            self.soltouArquivos.emit(md, self.mapToScene(e.position().toPoint()))
        else:
            super().dropEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton and self.draw_tool == "line":
            # O 2º clique do duplo clique já adicionou um ponto repetido no pressionar: descarta.
            pts = self._line_pts
            if len(pts) >= 2 and g.distance((pts[-1].x(), pts[-1].y()), (pts[-2].x(), pts[-2].y())) \
                    * self.scale_px_mm <= fm.CLOSE_PX:
                pts.pop()
                self._line_alcas.pop(len(pts), None)
            self._finish_line()
            return
        # items() e não itemAt(): a caixa de seleção fica por cima do texto selecionado.
        grupo = next((i for i in self.items(e.position().toPoint()) if isinstance(i, ob.GroupShape)), None)
        if e.button() == Qt.LeftButton and grupo is not None and not (self.measure_mode or self.text_mode
                                                                      or self.draw_tool or self.node_mode):
            self.grupoAbrir.emit(grupo)
            return
        it = next((i for i in self.items(e.position().toPoint()) if isinstance(i, ob.TextShape)), None)
        if e.button() == Qt.LeftButton and it is not None and not (self.measure_mode or self.text_mode):
            self.editTextRequested.emit(it)
            return
        if (e.button() == Qt.LeftButton and not (self.measure_mode or self.text_mode or self.draw_tool or self.node_mode)
                and not any(isinstance(i, ob.Shape) for i in self.items(e.position().toPoint()))):
            self.duploCliqueVazio.emit(self.mapToScene(e.position().toPoint()))
            return
        super().mouseDoubleClickEvent(e)

    def _alinhar_arraste(self, mods):
        """Guias inteligentes: bordas/centro da seleção grudam nas bordas/centros dos outros objetos e da mesa,
        com linha tracejada mostrando o alinhamento. Desliga com o Encaixe (F9) ou segurando Alt."""
        sel = self.selected()
        if not sel or not self.encaixe_ativo or mods & Qt.AltModifier:
            self._guias.setPath(QPainterPath())
            return
        if self._guias_alvos is None:
            rs = [ob.bounds([s]) for s in self.shapes() if s.isVisible() and not s.isSelected()]
            self._guias_alvos = [r.getCoords() for r in rs] + [(0.0, 0.0, g.BED_W, g.BED_H)]
        dx, dy, segs = enc.guias_alinhamento(ob.bounds(sel).getCoords(), self._guias_alvos,
                                             self.snap_px / self.scale_px_mm)
        if dx or dy:
            for it in sel:
                it.moveBy(dx, dy)  # o Qt recalcula a posição a partir do clique a cada movimento: não acumula
        p = QPainterPath()
        for a, b in segs:
            p.moveTo(*a)
            p.lineTo(*b)
        self._guias.setPath(p)

    def _na_linha(self, item, scene_pt):
        return item.contorno_clique().contains(item.mapFromScene(scene_pt))

    def _tem_pecas_dentro(self, item):
        r = ob.geom_rect(item)
        return any(s is not item and s.isVisible() and r.contains(ob.geom_rect(s)) for s in self.shapes())

    def _caixa_selecao(self):
        """Caixa de seleção: pega as peças INTEIRAS dentro dela e as que têm a LINHA cruzada por ela (o miolo
        de uma peça grande não conta: uma caixa dentro da base pega só os furos). Aplicada depois da do Qt."""
        rect_vp = self.rubberBandRect()
        if rect_vp.isNull():
            return
        caixa = self.mapToScene(rect_vp).boundingRect()
        inicial = getattr(self, "_sel_inicial", set())
        for s in self.shapes():
            if not s.isVisible():
                continue
            r = ob.geom_rect(s)
            quer = s in inicial or caixa.contains(r) or (caixa.intersects(r) and self._linha_na_caixa(s, caixa))
            if s.isSelected() != quer:
                s.setSelected(quer)

    @staticmethod
    def _linha_na_caixa(s, caixa):
        poly = s.mapFromScene(caixa)
        area = QPainterPath()
        area.addPolygon(poly)
        area.closeSubpath()
        return s.contorno_clique().intersects(area)

    def _escala_para_objetos(self):
        ob.ESCALA_TELA = self.scale_px_mm  # área de clique dos objetos acompanha o zoom

    def _mais_de_dentro(self, view_pos):
        """(objeto escolhido pelo clique, objetos acima dele no ponto). Com uma peça dentro da outra (furo dentro
        da base), o clique pega a MENOR que está sob o cursor; a de fora se pega pela borda ou fora dos furos."""
        sob = [i for i in self.items(view_pos) if isinstance(i, ob.Shape)]  # do topo para baixo
        if len(sob) < 2:
            return (sob[0] if sob else None), []
        area = lambda it: (lambda r: r.width() * r.height())(ob.geom_rect(it))  # noqa: E731
        escolhido = min(sob, key=area)
        return escolhido, sob[:sob.index(escolhido)]

    def set_pan_mode(self, on: bool):
        self.modo_mao = on
        self._update_cursor()

    def set_text_mode(self, on: bool):
        self.text_mode = on
        self._update_cursor()

    def leaveEvent(self, e):
        self.cursorMoved.emit(None)
        if self._shape_start is None and self._node_drag is None and self._measure_start is None:
            self.snap_ind.set_alvo(None)
        super().leaveEvent(e)

    # ---------- medição ----------
    def set_measure_mode(self, on: bool):
        self.measure_mode = on
        self._measure_start = None
        self.snap_ind.set_alvo(None)
        if not on:
            self._measure_line.hide()
            self._measure_sombra.hide()
            self.medidas.set("medida", None)
        self._update_cursor()

    def _set_measure(self, end: QPointF):
        a, b = self._measure_start, end
        self._measure_line.setLine(QLineF(a, b))
        self._measure_line.show()
        self._measure_sombra.setLine(QLineF(a, b))
        self._measure_sombra.show()
        self.medidas.set("medida", QLineF(a, b))
        dx, dy = b.x() - a.x(), -(b.y() - a.y())  # dy em exibição (Y para cima)
        d = g.distance((a.x(), a.y()), (b.x(), b.y()))
        self.measured.emit(f"Medição: {d:.2f} mm   (ΔX {dx:+.2f}  ΔY {dy:+.2f} mm)".replace(".", ","))

    def _update_cursor(self):
        if (self._space or self.modo_mao):
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif self.measure_mode:
            self.viewport().setCursor(Qt.CrossCursor)
        elif self.text_mode:
            self.viewport().setCursor(Qt.IBeamCursor)
        elif self.draw_tool:
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().unsetCursor()

    # ---------- desenho ----------
    def set_tema(self, nome):
        self.tema = TEMAS.get(nome, TEMAS["cinza"])
        if hasattr(self, "_preview"):  # amarelo some na mesa clara: azul-escuro nela, amarelo só no tema escuro
            pen = self._preview.pen()
            pen.setColor(QColor("#ffcc33" if nome == "escuro" else COR_PREVIA_CLARA))
            self._preview.setPen(pen)
        self.resetCachedContent()
        self.viewport().update()

    destaque = None  # QPainterPath (cena): peça de um grupo fechado escolhida na lista Objetos
    cabecote = None  # QPointF (cena, mm): onde está o cabeçote do laser (máquina conectada)
    cabecote_laser = False  # laser ligado agora (gravando)

    def definir_cabecote(self, ponto, laser=False):
        """Novo ponto do cabeçote. A mira desliza do ponto mostrado até o novo no tempo entre duas leituras da
        máquina (em vez de pular de leitura em leitura)."""
        import time
        agora = time.monotonic()
        if ponto is None or self.cabecote is None:
            self._cab_anim = None
            if ponto != self.cabecote or laser != self.cabecote_laser:
                self.cabecote, self.cabecote_laser = ponto, laser
                self.viewport().update()
            self._cab_t = agora
            return
        if ponto == getattr(self, "_cab_alvo", None) and laser == self.cabecote_laser:
            return
        dur = min(max(agora - getattr(self, "_cab_t", agora), 0.04), 0.4)  # = intervalo entre leituras
        self._cab_t, self._cab_alvo, self.cabecote_laser = agora, ponto, laser
        self._cab_anim = (QPointF(self.cabecote), ponto, agora, dur)
        if not hasattr(self, "_cab_timer"):
            self._cab_timer = QTimer(self, interval=16, timeout=self._passo_cabecote)
        self._cab_timer.start()

    @property
    def cabecote_alvo(self):
        """Onde a mira vai parar (última leitura da máquina), mesmo no meio do deslize."""
        return getattr(self, "_cab_alvo", None) if self._cab_anim_ativo() else self.cabecote

    def _cab_anim_ativo(self):
        return getattr(self, "_cab_anim", None) is not None

    def _passo_cabecote(self):
        import time
        if self._cab_anim is None:
            self._cab_timer.stop()
            return
        a, b, t0, dur = self._cab_anim
        f = min(1.0, (time.monotonic() - t0) / dur)
        self.cabecote = a + (b - a) * f
        if f >= 1.0:
            self._cab_anim = None
            self._cab_timer.stop()
        self.viewport().update()

    def destacar(self, caminho):
        self.destaque = caminho
        self.viewport().update()

    def drawForeground(self, p: QPainter, rect: QRectF):
        super().drawForeground(p, rect)
        if self.cabecote is not None:  # cabeçote do laser: mira vermelha (preenchida quando o laser está ligado)
            esc = self.transform().m11() or 1.0
            c, raio = self.cabecote, 9 / esc
            cor = QColor("#ff2a2a")
            pen = QPen(cor, 2)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(QColor(255, 42, 42, 140) if self.cabecote_laser else Qt.NoBrush)
            p.drawEllipse(c, raio, raio)
            p.drawLine(QPointF(c.x() - 2 * raio, c.y()), QPointF(c.x() + 2 * raio, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 2 * raio), QPointF(c.x(), c.y() + 2 * raio))
        if self.destaque is not None and not self.destaque.isEmpty():
            cor = QColor("#ff2bd6")
            preench = QColor(cor)
            preench.setAlpha(60)
            p.fillPath(self.destaque, preench)
            pen = QPen(cor, 3)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(self.destaque)

    def drawBackground(self, p: QPainter, rect: QRectF):
        _, fora, mesa, menor, maior = self.tema
        p.fillRect(rect, QColor(fora))
        bed = QRectF(0, 0, g.BED_W, g.BED_H)
        p.fillRect(bed, QColor(mesa))
        area = rect.intersected(bed)
        if area.isEmpty():
            return
        minor, major = g.steps_for(self.scale_px_mm)
        for step, color in ((minor, menor), (major, maior)):
            p.setPen(QPen(QColor(color), 0))
            for x in g.ticks(area.left(), area.right(), step):
                p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            # linhas horizontais alinhadas às coordenadas de exibição (a partir da origem inferior)
            for d in g.ticks(g.BED_H - area.bottom(), g.BED_H - area.top(), step):
                y = g.BED_H - d
                p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))


class Ruler(QWidget):
    def __init__(self, view: BedView, horizontal: bool):
        super().__init__()
        self.view, self.horizontal = view, horizontal
        self.cursor_value = None
        if horizontal:
            self.setFixedHeight(RULER)
        else:
            self.setFixedWidth(RULER)
        view.viewChanged.connect(self.update)
        view.cursorMoved.connect(self._on_cursor)

    def _on_cursor(self, pos):
        self.cursor_value = None if pos is None else pos[0 if self.horizontal else 1]
        self.update()

    def _px(self, value: float) -> float:
        """Valor de exibição (mm) -> posição em pixels na régua."""
        off = self.view.viewport().pos()
        if self.horizontal:
            return self.view.mapFromScene(QPointF(value, 0)).x() + off.x()
        return self.view.mapFromScene(QPointF(0, g.BED_H - value)).y() + off.y()

    def tick_positions(self):
        """[(valor_mm, px, principal)] visíveis — usado na pintura e nos testes."""
        vp = self.view.viewport().rect()
        a, b = self.view.mapToScene(vp.topLeft()), self.view.mapToScene(vp.bottomRight())
        lo, hi = (a.x(), b.x()) if self.horizontal else (g.BED_H - b.y(), g.BED_H - a.y())
        minor, major = g.steps_for(self.view.scale_px_mm)
        majors = set(g.ticks(lo, hi, major))
        return [(v, self._px(v), v in majors) for v in g.ticks(lo, hi, minor)], major

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#22252a"))
        p.setFont(QFont(self.font().family(), 7))
        p.setPen(QColor("#9aa0aa"))
        ticks, major = self.tick_positions()
        for v, px, is_major in ticks:
            length = 10 if is_major else 4
            if self.horizontal:
                p.drawLine(QPointF(px, RULER - length), QPointF(px, RULER))
                if is_major:
                    p.drawText(QPointF(px + 2, 10), g.fmt_mm(v, major))
            else:
                p.drawLine(QPointF(RULER - length, px), QPointF(RULER, px))
                if is_major:
                    p.save()
                    p.translate(10, px - 2)
                    p.rotate(-90)
                    p.drawText(0, 0, g.fmt_mm(v, major))
                    p.restore()
        if self.cursor_value is not None:
            p.setPen(QPen(QColor("#e0313b"), 1))
            c = self._px(self.cursor_value)
            if self.horizontal:
                p.drawLine(QPointF(c, 0), QPointF(c, RULER))
            else:
                p.drawLine(QPointF(0, c), QPointF(RULER, c))
        p.end()


_MESA = 0x5ED  # chave de data dos itens da mesa/origem (redesenhados quando a mesa muda)


def desenhar_mesa(s: QGraphicsScene) -> None:
    """(Re)desenha a borda da mesa e a marca da origem com g.BED_W/g.BED_H/g.ORIGEM atuais."""
    for it in [i for i in s.items() if i.data(_MESA)]:
        s.removeItem(it)
    # Espaço extra em volta da mesa para permitir deslocar a vista.
    s.setSceneRect(QRectF(-2 * g.BED_W, -2 * g.BED_H, 5 * g.BED_W, 5 * g.BED_H))
    itens = [s.addRect(QRectF(0, 0, g.BED_W, g.BED_H), QPen(QColor("#e0313b"), 0))]
    ox, oy = g.canto_origem()
    o = QPen(QColor("#e08a00"), 2)
    o.setCosmetic(True)
    itens += [s.addEllipse(QRectF(ox - 4, oy - 4, 8, 8), o), s.addLine(ox - 7, oy, ox + 7, oy, o),
              s.addLine(ox, oy - 7, ox, oy + 7, o)]
    lbl = s.addSimpleText("Origem (a confirmar)", QFont("Segoe UI", 5))
    lbl.setBrush(QColor("#e08a00"))  # âmbar escuro: legível no fundo claro e no escuro
    lbl.setPos(ox + 6 if ox == 0 else ox - 6 - lbl.boundingRect().width(), oy - 13 if oy else oy + 6)
    for it in itens + [lbl]:
        it.setData(_MESA, True)
        it.setZValue(-1)


def _build_scene() -> QGraphicsScene:
    s = QGraphicsScene()
    desenhar_mesa(s)
    for shape in demo_shapes():
        s.addItem(shape)
    return s


def demo_shapes():
    """Objetos de demonstração editáveis (salvar/abrir projeto vem na Etapa 4)."""
    rect, ell, txt = QPainterPath(), QPainterPath(), QPainterPath()
    rect.addRect(QRectF(40, 40, 60, 30))
    ell.addEllipse(QRectF(130, 60, 50, 30))
    # Texto convertido em contorno só para demonstração; ferramenta de texto na Etapa 7.
    txt.addText(QPointF(40, 130), QFont("Segoe UI", 14, QFont.Bold), "RedBlack")
    return [ob.Shape(rect, "RedBlack Retângulo", "C01", cor("C01")),
            ob.Shape(ell, "RedBlack Elipse", "C02", cor("C02")),
            ob.Shape(txt, "RedBlack Texto “RedBlack”", "C01", cor("C01"))]


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.scene = _build_scene()  # manter referência: o PySide destrói cenas sem dono
        self.view = BedView(self.scene)
        self.top, self.left = Ruler(self.view, True), Ruler(self.view, False)
        corner = QWidget()
        corner.setFixedSize(RULER, RULER)
        corner.setStyleSheet("background:#22252a")
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(corner, 0, 0)
        lay.addWidget(self.top, 0, 1)
        lay.addWidget(self.left, 1, 0)
        lay.addWidget(self.view, 1, 1)
