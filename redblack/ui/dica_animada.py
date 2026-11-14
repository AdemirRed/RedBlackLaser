"""Dicas animadas das ferramentas: ao parar o mouse num botão, uma janelinha mostra o nome, o que faz e uma
animação curta da ferramenta sendo usada (desenhada pelo próprio programa, sem vídeo)."""
import math

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolButton, QWidget

AZUL, VERMELHO, AMARELO, CINZA = QColor("#2f6bff"), QColor("#e0313b"), QColor("#ffcc33"), QColor("#9aa3b2")
CICLO_MS = 2600


def _suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _fase(t, a, b):
    """0→1 entre os instantes a e b do ciclo."""
    return _suave((t - a) / (b - a)) if b > a else 1.0


def _cursor(p, x, y, apertado=False):
    seta = QPainterPath()
    seta.moveTo(x, y)
    for dx, dy in ((0, 16), (4, 12), (7, 19), (10, 18), (7, 11), (12, 11)):
        seta.lineTo(x + dx, y + dy)
    seta.closeSubpath()
    p.setPen(QPen(QColor("#101215"), 1.2))
    p.setBrush(QColor("#ffffff") if not apertado else AMARELO)
    p.drawPath(seta)


def _caneta(cor=AZUL, larg=2.0, tracejado=False):
    pen = QPen(cor, larg, Qt.DashLine if tracejado else Qt.SolidLine)
    pen.setCapStyle(Qt.RoundCap)
    return pen


# ---------- demos: (painter, t de 0 a 1, W, H) ----------
def demo_select(p, t, W, H):
    r = QRectF(60, 50, 80, 50)
    mov = _fase(t, 0.45, 0.85) * 50
    sel = t > 0.3
    p.setPen(_caneta(AZUL))
    p.drawRect(r.translated(mov, 0))
    if sel:
        p.setPen(_caneta(QColor("#ff2bd6"), 1.5, True))
        p.drawRect(r.translated(mov, 0).adjusted(-4, -4, 4, 4))
    x = 40 + _fase(t, 0, 0.3) * 50 + mov
    _cursor(p, x, 75, 0.3 < t < 0.85)


def demo_pan(p, t, W, H):
    d = math.sin(t * 2 * math.pi) * 30
    p.setPen(_caneta(CINZA, 1))
    for i in range(-2, 14):
        x = i * 20 + d % 20
        p.drawLine(QPointF(x, 10), QPointF(x, H - 10))
    p.setPen(_caneta(AZUL))
    p.drawEllipse(QPointF(W / 2 + d, H / 2), 25, 18)
    _cursor(p, W / 2 + d + 30, H / 2 + 10, True)


def demo_node(p, t, W, H):
    k = math.sin(t * 2 * math.pi) * 40
    a, b = QPointF(30, 110), QPointF(W - 30, 110)
    c1, c2 = QPointF(80, 30 + k), QPointF(W - 80, 30 - k)
    curva = QPainterPath(a)
    curva.cubicTo(c1, c2, b)
    p.setPen(_caneta(AZUL))
    p.drawPath(curva)
    p.setPen(_caneta(CINZA, 1, True))
    p.drawLine(a, c1)
    p.drawLine(b, c2)
    p.setPen(QPen(QColor("#ffffff"), 1))
    for q in (a, b):
        p.setBrush(AZUL)
        p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))
    for q in (c1, c2):
        p.setBrush(AMARELO)
        p.drawEllipse(q, 4.5, 4.5)
    _cursor(p, c1.x() + 2, c1.y() + 2, True)


def demo_pen(p, t, W, H):
    pts = [QPointF(30, 110), QPointF(90, 40), QPointF(150, 110), QPointF(W - 30, 50)]
    n = 1 + int(t * 4.2)
    caminho = QPainterPath(pts[0])
    for i in range(1, min(n, len(pts))):
        if i == 2:  # este ponto foi arrastado: vira curva
            caminho.quadTo(QPointF(120, 150), pts[i])
        else:
            caminho.lineTo(pts[i])
    p.setPen(_caneta(AZUL))
    p.drawPath(caminho)
    p.setBrush(AMARELO)
    p.setPen(Qt.NoPen)
    for q in pts[:n]:
        p.drawEllipse(q, 3.5, 3.5)
    alvo = pts[min(n, len(pts) - 1)]
    _cursor(p, alvo.x(), alvo.y(), False)


def _arraste(p, t, forma):
    a = QPointF(50, 35)
    b = QPointF(50 + 120 * _fase(t, 0.1, 0.7), 35 + 80 * _fase(t, 0.1, 0.7))
    r = QRectF(a, b)
    p.setPen(_caneta(AZUL))
    forma(p, r)
    _cursor(p, b.x(), b.y(), t < 0.75)


def demo_rect(p, t, W, H):
    _arraste(p, t, lambda p, r: p.drawRect(r))


def demo_ellipse(p, t, W, H):
    _arraste(p, t, lambda p, r: p.drawEllipse(r))


def _regular(p, r, n, razao=None):
    c, raio = r.center(), min(r.width(), r.height()) / 2
    if raio < 2:
        return
    pts = []
    passos = 2 * n if razao else n
    for k in range(passos):
        rr = raio if (not razao or k % 2 == 0) else raio * razao
        a = math.radians(-90 + 360 * k / passos)
        pts.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
    p.drawPolygon(pts)


def demo_polygon(p, t, W, H):
    _arraste(p, t, lambda p, r: _regular(p, r, 6))


def demo_star(p, t, W, H):
    _arraste(p, t, lambda p, r: _regular(p, r, 5, 0.45))


def demo_text(p, t, W, H):
    txt = "RedBlack"[: int(t * 11)]
    p.setPen(_caneta(AZUL))
    caminho = QPainterPath()
    caminho.addText(QPointF(30, 95), QFont("Segoe UI", 30, QFont.Bold), txt)
    p.drawPath(caminho)
    if int(t * 6) % 2 == 0:
        x = 30 + caminho.boundingRect().width() + 4
        p.drawLine(QPointF(x, 62), QPointF(x, 100))


def demo_measure(p, t, W, H):
    p.setPen(_caneta(AZUL))
    p.drawRect(QRectF(40, 60, 140, 50))
    f = _fase(t, 0.1, 0.7)
    a, b = QPointF(40, 50), QPointF(40 + 140 * f, 50)
    p.setPen(_caneta(AMARELO, 2, True))
    p.drawLine(a, b)
    if f > 0.15:
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor("#ffcc33"))
        p.drawText(QRectF(a.x(), 25, b.x() - a.x(), 18), Qt.AlignCenter, f"{140 * f / 1.4:.0f} mm")
    _cursor(p, b.x(), b.y(), t < 0.75)


def demo_trim(p, t, W, H):
    p.setPen(_caneta(AZUL))
    p.drawLine(QPointF(30, 75), QPointF(W - 30, 75))
    p.drawLine(QPointF(80, 20), QPointF(80, 130))
    p.drawLine(QPointF(160, 20), QPointF(160, 130))
    if t < 0.6:
        p.setPen(_caneta(VERMELHO, 3))
        p.drawLine(QPointF(80, 75), QPointF(160, 75))
    else:
        p.setPen(_caneta(QColor("#2a2d33"), 4))
        p.drawLine(QPointF(82, 75), QPointF(158, 75))
    _cursor(p, 120, 75, 0.5 < t < 0.65)


def demo_bolear(p, t, W, H):
    r = QRectF(50, 35, 140, 80)
    etapa = int(t * 3)  # 0 redondo, 1 45°, 2 vivo
    raio = 28
    c = QPainterPath()
    c.moveTo(r.left(), r.bottom())
    c.lineTo(r.left(), r.top() + raio)
    if etapa == 0:
        c.quadTo(r.topLeft(), QPointF(r.left() + raio, r.top()))
    elif etapa == 1:
        c.lineTo(r.left() + raio, r.top())
    else:
        c.lineTo(r.topLeft())
    c.lineTo(r.topRight())
    c.lineTo(r.bottomRight())
    c.closeSubpath()
    p.setPen(_caneta(AZUL))
    p.drawPath(c)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.setPen(QColor("#ffcc33"))
    p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 18), Qt.AlignCenter,
               ("1º clique: redondo", "2º clique: 45°", "3º clique: canto vivo")[etapa])
    _cursor(p, r.left() + 6, r.top() + 6, (t * 3) % 1 < 0.2)


def demo_juntar(p, t, W, H):
    f = _suave(_fase(t, 0.35, 0.65))  # as duas linhas viram uma só (cor única, sem a marca da emenda)
    meio = QPointF(W / 2, 40)
    p.setPen(_caneta(AZUL))
    p.drawLine(QPointF(40, 120), meio)
    p.setPen(_caneta(AZUL if f > 0.5 else VERMELHO))
    p.drawLine(meio, QPointF(W - 40, 120))
    if f < 0.5:
        p.setPen(Qt.NoPen)
        p.setBrush(AMARELO)
        p.drawEllipse(meio, 5, 5)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.setPen(AMARELO)
    p.drawText(QRectF(0, H - 22, W, 18), Qt.AlignCenter, "2 linhas" if f < 0.5 else "1 linha só (Alt+J)")
    _cursor(p, W / 2 + 30, 90, 0.3 < t < 0.4)


def demo_fechar(p, t, W, H):
    f = _suave(_fase(t, 0.35, 0.7))
    a, b = QPointF(60, 120), QPointF(60 + 30 * (1 - f), 120)
    c = QPainterPath(b)
    c.lineTo(W - 50, 120)
    c.lineTo(W - 50, 35)
    c.lineTo(60, 35)
    c.lineTo(a)
    p.setPen(_caneta(AZUL))
    p.drawPath(c)
    p.setPen(_caneta(AMARELO, 2, True))
    if f < 1:
        p.drawLine(a, b)
    _cursor(p, 75, 125, 0.3 < t < 0.4)


def demo_duplicados(p, t, W, H):
    r = QRectF(60, 35, 120, 80)
    p.setPen(_caneta(AZUL))
    p.drawRect(r)
    if t < 0.5:
        p.setPen(_caneta(VERMELHO, 2, True))
        p.drawRect(r.translated(2, 2))
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.setPen(AMARELO)
    p.drawText(QRectF(0, H - 22, W, 18), Qt.AlignCenter,
               "linha repetida: o laser passaria 2×" if t < 0.5 else "repetida removida (Alt+D)")


def demo_inverter(p, t, W, H):
    p.setPen(_caneta(AZUL))
    p.drawLine(QPointF(40, 75), QPointF(W - 40, 75))
    ida = t < 0.5
    x = 40 + (W - 80) * ((t * 2) % 1)
    x = x if ida else W - x
    p.setBrush(AMARELO)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(x, 75), 6, 6)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.setPen(AMARELO)
    p.drawText(QRectF(0, H - 22, W, 18), Qt.AlignCenter, "o laser começa daqui →" if ida else "← agora do outro lado")


def demo_otimizar(p, t, W, H):
    pts = [QPointF(30 + i * (W - 60) / 16, 75 + 35 * math.sin(i / 2.2) + (6 if i % 2 else -6)) for i in range(17)]
    limpo = t > 0.5
    c = QPainterPath(pts[0])
    for q in (pts[::4] if limpo else pts)[1:]:
        c.lineTo(q)
    p.setPen(_caneta(AZUL))
    p.drawPath(c)
    p.setBrush(AMARELO)
    p.setPen(Qt.NoPen)
    for q in (pts[::4] if limpo else pts):
        p.drawEllipse(q, 2.5, 2.5)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.setPen(AMARELO)
    p.drawText(QRectF(0, H - 22, W, 18), Qt.AlignCenter, "17 nós" if not limpo else "5 nós: corte mais liso")


DEMOS = {"select": demo_select, "pan": demo_pan, "node": demo_node, "pen": demo_pen, "rect": demo_rect,
         "ellipse": demo_ellipse, "polygon": demo_polygon, "star": demo_star, "text": demo_text,
         "measure": demo_measure, "trim": demo_trim, "bolear": demo_bolear, "juntar": demo_juntar,
         "fechar": demo_fechar, "duplicados": demo_duplicados, "inverter": demo_inverter, "otimizar": demo_otimizar}


class DicaAnimada(QWidget):
    LARG, ALT_ANIM = 260, 150

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.titulo, self.texto, self.demo, self.t = "", "", None, 0.0
        self.timer = QTimer(self, interval=33, timeout=self._passo)
        self.setFixedWidth(self.LARG)

    def mostrar(self, titulo, texto, demo, pos):
        self.titulo, self.texto, self.demo, self.t = titulo, texto, demo, 0.0
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(QFont("Segoe UI", 9))  # a mesma fonte do texto desenhado
        linhas = fm.boundingRect(QRectF(0, 0, self.LARG - 20, 600).toRect(), Qt.TextWordWrap, texto).height()
        self.setFixedHeight(int(self.ALT_ANIM + 46 + linhas))
        self.move(pos)
        self.show()
        self.timer.start()

    def esconder(self):
        self.timer.stop()
        self.hide()

    def _passo(self):
        self.t = (self.t + self.timer.interval() / CICLO_MS) % 1.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1d2026"))
        p.setPen(QPen(QColor("#3a4757"), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(QRectF(10, 6, self.LARG - 20, 20), Qt.AlignLeft | Qt.AlignVCenter, self.titulo)
        area = QRectF(10, 30, self.LARG - 20, self.ALT_ANIM)
        p.fillRect(area, QColor("#2a2d33"))
        if self.demo:
            p.save()
            p.translate(area.topLeft())
            p.setClipRect(QRectF(0, 0, area.width(), area.height()))
            self.demo(p, self.t, area.width(), area.height())
            p.restore()
        p.setPen(QColor("#cfd5de"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(10, area.bottom() + 6, self.LARG - 20, self.height() - area.bottom() - 8),
                   Qt.TextWordWrap, self.texto)
        p.end()


class _Filtro(QObject):
    def __init__(self, ligado):
        super().__init__()
        self.dica = DicaAnimada()
        self.ligado = ligado  # função -> bool (Configurações → Visual)
        self.espera = QTimer(self, singleShot=True, interval=550)
        self.espera.timeout.connect(self._mostrar)
        self.alvo = None

    def eventFilter(self, obj, ev):
        if not isinstance(obj, QToolButton) or obj.defaultAction() is None:
            return False
        demo = obj.defaultAction().property("demo")
        if not demo or not self.ligado():
            return False
        tipo = ev.type()
        if tipo == QEvent.Enter:
            self.alvo = obj
            self.espera.start()
        elif tipo in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.Hide):
            self.espera.stop()
            self.dica.esconder()
        elif tipo == QEvent.ToolTip:
            return True  # a dica animada substitui a dica comum
        return False

    def _mostrar(self):
        b = self.alvo
        if b is None or not b.underMouse():
            return
        a = b.defaultAction()
        titulo, _, resto = a.toolTip().partition(" — ")
        pos = b.mapToGlobal(b.rect().topRight()) + QPointF(8, 0).toPoint()
        self.dica.mostrar(titulo or a.text().replace("&", ""), resto or a.toolTip(), DEMOS.get(a.property("demo")), pos)


def instalar(barra, acoes, ligado=lambda: True):
    """Liga as dicas animadas nos botões da `barra` para {chave_da_demo: ação}."""
    filtro = _Filtro(ligado)
    for chave, acao in acoes.items():
        if chave not in DEMOS:
            continue
        acao.setProperty("demo", chave)
        bt = barra.widgetForAction(acao)
        if bt is not None:
            bt.installEventFilter(filtro)
    barra._filtro_dicas = filtro  # mantém vivo enquanto a barra existir
    return filtro
