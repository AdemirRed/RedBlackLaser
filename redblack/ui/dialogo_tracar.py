"""Janela Traçar imagem (como no original): prévia grande em cima, com o traçado em magenta sobre a imagem; controles
embaixo. Arrastar na prévia limita o traçado a uma área ("Limpar limite" volta à imagem toda)."""
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

from .. import tracar as trc

PREVIA_MAX = 600  # px: a prévia traça uma versão reduzida (rápida); o traçado final usa a imagem inteira
MAGENTA = QColor("#ff00ff")


class _Previa(QWidget):
    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.setMinimumSize(560, 380)
        self._ini = None

    def _quadro(self):
        """Retângulo (em px do widget) onde a imagem é desenhada, mantendo a proporção."""
        img = self.dlg.imagem
        r = QRectF(self.rect()).adjusted(20, 20, -20, -20)
        esc = min(r.width() / img.width(), r.height() / img.height())
        w, h = img.width() * esc, img.height() * esc
        return QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)

    def _fracao(self, pos):
        q = self._quadro()
        return (min(max((pos.x() - q.left()) / q.width(), 0), 1), min(max((pos.y() - q.top()) / q.height(), 0), 1))

    def mousePressEvent(self, e):
        self._ini = self._fracao(e.position())

    def mouseMoveEvent(self, e):
        if self._ini is not None:
            a, b = self._ini, self._fracao(e.position())
            self.dlg.definir_area((min(a[0], b[0]), min(a[1], b[1]), abs(a[0] - b[0]), abs(a[1] - b[1])), refazer=False)

    def mouseReleaseEvent(self, e):
        if self._ini is not None:
            area = self.dlg.op.get("area")
            self._ini = None
            self.dlg.definir_area(area if area and area[2] > 0.01 and area[3] > 0.01 else None)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#bfbfbf"))
        q = self._quadro()
        p.fillRect(q, QColor("white"))
        p.setOpacity(0.3 if self.dlg.desbotar.isChecked() else 1.0)
        p.drawImage(q, self.dlg.imagem)
        p.setOpacity(1.0)
        tf = QTransform(q.width(), 0, 0, q.height(), q.left(), q.top())  # caminho em frações 0–1 -> widget
        cam = tf.map(self.dlg.previa)
        p.setPen(QPen(MAGENTA, 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawPath(cam)
        if self.dlg.pontos.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2f6bff"))
            i = 0
            while i < cam.elementCount():
                el = cam.elementAt(i)
                if el.isCurveTo():  # 2 pontos de controle + o vértice final
                    el, i = cam.elementAt(i + 2), i + 3
                else:
                    i += 1
                p.drawEllipse(QPointF(el.x, el.y), 2.2, 2.2)
        area = self.dlg.op.get("area")
        if area:
            r = QRectF(q.left() + area[0] * q.width(), q.top() + area[1] * q.height(), area[2] * q.width(),
                       area[3] * q.height())
            p.setPen(QPen(QColor("#d9a400"), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)
        p.end()


class DialogoTracar(QDialog):
    def __init__(self, imagem, parent=None, op=None):
        super().__init__(parent)
        self.setWindowTitle("Traçar imagem")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.imagem = imagem
        self.op = {**trc.PADRAO, **(op or {})}
        self.previa = trc.tracar_opcoes(imagem, 1, 1, self.op, PREVIA_MAX)

        self.corte, self.corte_n = self._faixa(self.op["corte"], "Brilho mais baixo incluído no traçado")
        self.limiar, self.limiar_n = self._faixa(self.op["limiar"], "Brilho mais alto incluído no traçado")
        self.ignorar = QSpinBox()
        self.ignorar.setRange(0, 100000)
        self.ignorar.setValue(int(self.op["ignorar"]))
        self.ignorar.setToolTip("Manchas menores que isto (área em pixels) são descartadas")
        self.suavidade = QDoubleSpinBox()
        self.suavidade.setRange(0, 1.33)
        self.suavidade.setDecimals(3)
        self.suavidade.setSingleStep(0.05)
        self.suavidade.setValue(self.op["suavidade"])
        self.suavidade.setToolTip("0 = só retas; mais alto = curvas mais redondas (cantos fortes continuam cantos)")
        self.otimizar = QDoubleSpinBox()
        self.otimizar.setRange(0, 10)
        self.otimizar.setDecimals(1)
        self.otimizar.setSingleStep(0.1)
        self.otimizar.setValue(self.op["otimizar"])
        self.otimizar.setToolTip("Tolerância para tirar pontos desnecessários (mais alto = menos pontos)")
        self.transparencia = QCheckBox("Traçar transparência")
        self.transparencia.setToolTip("Se a imagem tem fundo transparente, traça o contorno das partes opacas")
        self.esboco = QCheckBox("Esboçar traço")
        self.esboco.setToolTip("Melhor para desenhos a lápis, rabiscos e fotos com luz irregular")
        self.central = QCheckBox("Traçado de linha central")
        self.central.setToolTip("Traça o MEIO das linhas escuras (uma linha só), não o contorno delas")
        self.negativo = QCheckBox("Inverter (traçar as áreas claras)")
        self.apagar = QCheckBox("Eliminar a imagem após traçar")
        for c, k in ((self.transparencia, "transparencia"), (self.esboco, "esboco"), (self.central, "linha_central"),
                     (self.negativo, "negativo")):
            c.setChecked(bool(self.op[k]))
        self.desbotar = QPushButton("Desbotar imagem")
        self.desbotar.setCheckable(True)
        self.desbotar.setToolTip("Clareia a imagem na prévia para ver melhor o traçado")
        self.pontos = QPushButton("Mostrar pontos")
        self.pontos.setCheckable(True)
        self.limpar = QPushButton("Limpar limite")
        self.limpar.setToolTip("Traçar a imagem inteira (arraste na prévia para escolher só uma parte)")
        self.limpar.clicked.connect(lambda: self.definir_area(None))
        self.info = QLabel()
        self.info.setStyleSheet("color:#7a808a")

        g = QGridLayout()
        g.addWidget(QLabel("Corte"), 0, 1, Qt.AlignRight)
        g.addWidget(self.corte_n, 0, 2)
        g.addWidget(self.corte, 0, 3, 1, 4)
        g.addWidget(self.transparencia, 0, 7)
        g.addWidget(self.central, 0, 8)
        g.addWidget(QLabel("Limiar"), 1, 1, Qt.AlignRight)
        g.addWidget(self.limiar_n, 1, 2)
        g.addWidget(self.limiar, 1, 3, 1, 4)
        g.addWidget(self.esboco, 1, 7)
        g.addWidget(self.apagar, 1, 8)
        ign = QHBoxLayout()
        ign.addWidget(QLabel("Ignorar inferior a"))
        ign.addWidget(self.ignorar)
        g.addLayout(ign, 2, 0)
        g.addWidget(QLabel("Suavidade"), 2, 1, Qt.AlignRight)
        g.addWidget(self.suavidade, 2, 2)
        g.addWidget(QLabel("Otimizar"), 2, 3, Qt.AlignRight)
        g.addWidget(self.otimizar, 2, 4)
        botoes_previa = QHBoxLayout()
        for b in (self.desbotar, self.pontos, self.limpar):
            botoes_previa.addWidget(b)
        g.addLayout(botoes_previa, 2, 5, 1, 2)
        g.addWidget(self.negativo, 2, 7)
        g.addWidget(self.info, 3, 0, 1, 7)
        g.setColumnStretch(3, 1)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        g.addWidget(botoes, 2, 8, 2, 1, Qt.AlignRight | Qt.AlignBottom)

        self.tela = _Previa(self)
        corpo = QVBoxLayout(self)
        corpo.addWidget(self.tela, 1)
        corpo.addLayout(g)
        self.resize(1150, 760)

        self._timer = QTimer(self, singleShot=True, interval=150, timeout=self._refazer)
        for w in (self.corte, self.limiar, self.ignorar, self.suavidade, self.otimizar):
            w.valueChanged.connect(self._mudou)
        for w in (self.transparencia, self.esboco, self.central, self.negativo):
            w.toggled.connect(self._mudou)
        for w in (self.desbotar, self.pontos):
            w.toggled.connect(self.tela.update)
        self._contar()

    @staticmethod
    def _faixa(v, dica):
        """Campo numérico + barra, ligados (0–255)."""
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 255)
        s.setValue(int(v))
        s.setToolTip(dica)
        s.setMinimumWidth(260)
        n = QSpinBox()
        n.setRange(0, 255)
        n.setValue(int(v))
        n.setToolTip(dica)
        s.valueChanged.connect(n.setValue)
        n.valueChanged.connect(s.setValue)
        return s, n

    def opcoes(self):
        return dict(corte=self.corte.value(), limiar=self.limiar.value(), ignorar=float(self.ignorar.value()),
                    suavidade=self.suavidade.value(), otimizar=self.otimizar.value(),
                    transparencia=self.transparencia.isChecked(), esboco=self.esboco.isChecked(),
                    linha_central=self.central.isChecked(), negativo=self.negativo.isChecked(),
                    area=self.op.get("area"), apagar_imagem=self.apagar.isChecked())

    def definir_area(self, area, refazer=True):
        self.op["area"] = area
        self.tela.update()
        if refazer:
            self._mudou()

    def _mudou(self, *_):
        self._timer.start()

    def _refazer(self):
        op = self.opcoes()
        op.pop("apagar_imagem")
        self.op.update(op)
        self.previa = trc.tracar_opcoes(self.imagem, 1, 1, op, PREVIA_MAX)
        self._contar()
        self.tela.update()

    def _contar(self):
        n = 0 if self.previa.isEmpty() else sum(1 for i in range(self.previa.elementCount())
                                                if self.previa.elementAt(i).isMoveTo())
        self.info.setText(f"{n} forma(s) na prévia · arraste na imagem para traçar só uma parte")
