"""Janela do plugin Cilindros e copos: medidas (boca, meio, base), perfil com o meio arrastável, prévia 3D com a
arte do projeto aplicada (360° no rotativo), render na placa de vídeo (Blender) e parâmetros salvos por projeto."""
import dataclasses
import json
import math
import os
import tempfile

from PySide6.QtCore import QPointF, QProcess, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QShortcut,
                           QTransform)
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem,
                               QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from ... import camadas as cm
from ... import formas as fm
from ... import objetos as ob
from . import arte as art
from . import calc, render
from .vista3d import MATERIAIS, Vista3D

CAMADA_REF = "C29"  # área de gravação e guias: referência, Saída desligada
CAMADA_MOLDE = "C01"
FONTES = ("Área 360° do projeto (rotativo)", "Formas selecionadas", "Projeto inteiro")


def _n(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


class Perfil(QWidget):
    """Peça de lado com os pontos do perfil. Arrastar um ponto: para cima/baixo muda a distância da boca, para os
    lados o diâmetro. Duplo clique na parede: novo ponto. Botão direito num ponto: remove. Boca e base: só o
    diâmetro (arrastando para os lados)."""

    def __init__(self, ao_mudar):
        super().__init__()
        self.p, self.ao_mudar, self._arr = calc.Peca(), ao_mudar, None
        self.setMinimumSize(240, 360)
        self.setFocusPolicy(Qt.StrongFocus)
        self._faixa = None
        self.setToolTip("Arraste os pontos (para cima/baixo = altura, para os lados = diâmetro) · duplo clique na "
                        "parede = novo ponto · botão direito no ponto = remover · arraste a faixa vermelha (ou ↑↓, "
                        "Shift = 10 mm) para subir/descer a arte")

    def _geo(self):
        p = self.p
        larg = calc.diametro_max(p) * 1.35
        area = QRectF(10, 30, self.width() - 20, self.height() - 50)
        esc = min(area.width() / larg, area.height() / p.altura)
        return area.center().x(), area.center().y() - p.altura * esc / 2, esc

    def _pt(self, d, z, lado):
        cx, y0, esc = self._geo()
        return QPointF(cx + lado * d / 2 * esc, y0 + z * esc)

    def _mm(self, pos):
        cx, y0, esc = self._geo()
        return (pos.y() - y0) / esc, abs(pos.x() - cx) * 2 / esc

    def _perto(self, pos):
        for k, (z, d) in enumerate(calc.nos(self.p)):
            if (pos - self._pt(d, z, 1)).manhattanLength() < 16:
                return k
        return None

    def paintEvent(self, ev):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.Antialiasing)
        pt.fillRect(self.rect(), QColor("#f4f5f7"))
        p = self.p
        if calc.erros(p):
            pt.setPen(QColor("#c0392b"))
            pt.drawText(self.rect(), Qt.AlignCenter, "Medidas inválidas")
            return
        n = 120
        dir_ = [self._pt(calc.diametro_em(p, p.altura * i / n), p.altura * i / n, 1) for i in range(n + 1)]
        esq = [self._pt(calc.diametro_em(p, p.altura * i / n), p.altura * i / n, -1) for i in range(n + 1)]
        pt.setPen(QPen(QColor("#5b6270"), 1.5))
        pt.setBrush(QColor("#d9dde3"))
        pt.drawPolygon(QPolygonF(dir_ + esq[::-1]))
        z0, z1 = p.inicio, p.inicio + p.altura_arte
        fx = [self._pt(calc.diametro_em(p, z0 + (z1 - z0) * i / 30), z0 + (z1 - z0) * i / 30, 1) for i in range(31)]
        fe = [self._pt(calc.diametro_em(p, z0 + (z1 - z0) * i / 30), z0 + (z1 - z0) * i / 30, -1) for i in range(31)]
        pt.setPen(QPen(QColor("#e0313b"), 1.2))
        pt.setBrush(QColor(224, 49, 59, 50))
        pt.drawPolygon(QPolygonF(fx + fe[::-1]))
        pts = calc.nos(p)
        for k, (z, d) in enumerate(pts):
            a = self._pt(d, z, 1)
            meio = 0 < k < len(pts) - 1
            pt.setPen(QPen(QColor("#d9a400") if meio else QColor("#8a919c"), 1, Qt.DashLine))
            pt.drawLine(self._pt(d, z, -1), a)
            pt.setPen(QPen(QColor("#7a5a00") if meio else QColor("#454b55"), 1.2))
            pt.setBrush(QColor("#ffcc33") if meio else QColor("#cfd4db"))
            if meio:
                pt.drawEllipse(a, 7, 7)
            else:
                pt.drawRect(QRectF(a.x() - 6, a.y() - 6, 12, 12))
            pt.setPen(QColor("#222"))
            nome = "boca" if k == 0 else "base" if k == len(pts) - 1 else f"{_n(z, 0)} mm da boca"
            pt.drawText(QRectF(a.x() + 10, a.y() - 9, 150, 18), Qt.AlignLeft | Qt.AlignVCenter, f"Ø {_n(d)} · {nome}")
        pt.setPen(QColor("#222"))
        pt.drawText(QRectF(10, 6, self.width() - 20, 18), Qt.AlignLeft, "Peça de lado (vermelho = arte)")
        pt.end()

    def mousePressEvent(self, e):
        self.setFocus()
        k = self._perto(e.position())
        n = len(calc.nos(self.p))
        if e.button() == Qt.RightButton:
            if k is not None and 0 < k < n - 1:
                self.ao_mudar("remover", k - 1)
            return
        self._arr = k
        z, _ = self._mm(e.position())
        if k is None and self.p.inicio <= z <= self.p.inicio + self.p.altura_arte:
            self._faixa = z - self.p.inicio  # pegou a faixa vermelha (arte): arrasta para cima/baixo
        else:
            self._faixa = None

    def keyPressEvent(self, e):
        passo = 10.0 if e.modifiers() & Qt.ShiftModifier else 1.0
        if e.key() in (Qt.Key_Up, Qt.Key_Down):
            self.ao_mudar("faixa", None, self.p.inicio + (-passo if e.key() == Qt.Key_Up else passo), None)
        else:
            super().keyPressEvent(e)

    def mouseMoveEvent(self, e):
        if self._arr is None:
            if getattr(self, "_faixa", None) is not None:
                z, _ = self._mm(e.position())
                self.ao_mudar("faixa", None, z - self._faixa, None)
            return
        z, d = self._mm(e.position())
        n = len(calc.nos(self.p))
        if self._arr == 0:
            self.ao_mudar("boca", None, None, max(1.0, d))
        elif self._arr == n - 1:
            self.ao_mudar("base", None, None, max(1.0, d))
        else:
            self.ao_mudar("mover", self._arr - 1, min(max(z, 1.0), self.p.altura - 1.0), max(1.0, d))

    def mouseReleaseEvent(self, e):
        self._arr = None
        self._faixa = None

    def mouseDoubleClickEvent(self, e):
        z, d = self._mm(e.position())
        if 0 < z < self.p.altura:
            self.ao_mudar("novo", None, z, max(1.0, d))


class JanelaCilindros(QMainWindow):
    def __init__(self, janela_principal, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cilindros e copos — cálculo, prévia 3D e render")
        self.jp = janela_principal
        self.r = None
        self._carregando = False
        self.processo = None
        pd = calc.Peca()
        self.d_topo = self._mm(1, 1000, pd.diametro_topo)
        self.d_base = self._mm(1, 1000, pd.diametro_base)
        self.pontos = []  # [(mm da boca, diâmetro)] entre a boca e a base
        self.tabela = QTableWidget(0, 2)
        self.tabela.setHorizontalHeaderLabels(["mm da boca", "Ø (mm)"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setMaximumHeight(130)
        self.tabela.setToolTip("Pontos do perfil entre a boca e a base (taça, copo bojudo, garrafa…). Também dá "
                               "para arrastar no desenho")
        self.tabela.itemChanged.connect(self._tabela_editada)
        b_mais = QPushButton("+ ponto")
        b_mais.clicked.connect(lambda: self.mudar_perfil("novo", None, None, None))
        b_menos = QPushButton("− ponto")
        b_menos.clicked.connect(lambda: self.mudar_perfil("remover", self.tabela.currentRow()
                                                          if self.tabela.currentRow() >= 0 else len(self.pontos) - 1))
        self.altura = self._mm(1, 1000, pd.altura)
        self.inicio = self._mm(0, 1000, pd.inicio)
        self.alt_arte = self._mm(0.5, 1000, pd.altura_arte)
        self.alca = self._mm(0, 500, pd.alca_mm)
        self.alca.setToolTip("Caneca: largura que a alça ocupa em volta (meça com fita na superfície). 0 = sem alça")
        self.margem = self._mm(0, 100, pd.margem_mm)
        self.repet = QSpinBox()
        self.repet.setRange(1, 24)
        self.repet.setToolTip("Quantas artes iguais em volta da peça (2 = frente e verso)")
        self.foco = self._mm(0.1, 20, pd.foco_mm)
        self.foco.setToolTip("Quanto a altura da superfície pode variar sem perder o foco (diodo: ~1 a 2 mm)")
        form = QFormLayout()
        botoes_pontos = QHBoxLayout()
        botoes_pontos.addWidget(b_mais)
        botoes_pontos.addWidget(b_menos)
        form.addRow("Diâmetro da boca", self.d_topo)
        form.addRow(QLabel("Pontos do perfil (taças, bojudos…)"))
        form.addRow(self.tabela)
        form.addRow(botoes_pontos)
        for t, w in (("Diâmetro da base", self.d_base), ("Altura da peça", self.altura),
                     ("Arte começa abaixo da boca", self.inicio), ("Altura da arte", self.alt_arte),
                     ("Alça (largura na superfície)", self.alca), ("Margem de cada lado", self.margem),
                     ("Artes em volta", self.repet), ("Tolerância de foco", self.foco)):
            form.addRow(t, w)
        self.res = QLabel()
        self.res.setWordWrap(True)
        self.res.setTextFormat(Qt.RichText)
        b_rot = QPushButton("Aplicar no rotativo do RedBlack")
        b_rot.setToolTip("Liga o rotativo com o diâmetro no meio da arte (tipo, rolo e mm/rotação continuam)")
        b_rot.clicked.connect(lambda: self.aplicar_rotativo())
        b_area = QPushButton("Criar área de gravação 360° no projeto")
        b_area.setToolTip("Retângulo do jeito que o rotativo grava: X = ao longo da altura (boca à esquerda), "
                          f"Y = volta inteira. Guias de alça e artes (camada {CAMADA_REF}, não grava)")
        b_area.clicked.connect(lambda: self.criar_area())
        self.b_leque = QPushButton("Criar molde em leque (copo cônico)")
        self.b_leque.clicked.connect(lambda: self.criar_leque())
        self.material = QComboBox()
        self.material.addItems(list(MATERIAIS))
        self.material.setToolTip("Muda o acabamento e as cores padrão do copo e da gravação")
        self.b_cor_corpo = QPushButton()
        self.b_cor_corpo.clicked.connect(lambda: self._escolher_cor("corpo"))
        self.b_cor_arte = QPushButton()
        self.b_cor_arte.clicked.connect(lambda: self._escolher_cor("arte"))
        self.cores = list(MATERIAIS[self.material.currentText()][:2])
        aparencia = QFormLayout()
        aparencia.addRow("Material", self.material)
        aparencia.addRow("Cor do copo", self.b_cor_corpo)
        aparencia.addRow("Cor da gravação", self.b_cor_arte)
        caixa = QGroupBox("Aparência (prévia e render)")
        caixa.setLayout(aparencia)
        esq = QVBoxLayout()
        esq.addLayout(form)
        esq.addWidget(caixa)
        esq.addWidget(self.res)
        for b in (b_rot, b_area, self.b_leque):
            esq.addWidget(b)
        esq.addStretch(1)
        painel = QWidget()
        painel.setLayout(esq)
        rolagem = QScrollArea()
        rolagem.setWidget(painel)
        rolagem.setWidgetResizable(True)
        rolagem.setMinimumWidth(360)

        self.perfil = Perfil(self.mudar_perfil)
        self.vista = Vista3D()
        self.vista.arteMovida.connect(self._arte_movida)
        self.vista.arteSolta.connect(self._arte_solta)
        self.vista.arteAjustada.connect(
            lambda ang, ini: (self.angulo.setValue(round(ang if ang <= 180 else ang - 360, 1)),
                              self.inicio.setValue(round(ini, 1))))
        self._antes_arrasto = None
        self.fonte = QComboBox()
        self.fonte.addItems(FONTES)
        self.fonte.setToolTip("De onde vem a arte para a prévia 3D e o render")
        b_arte = QPushButton("Usar a arte do projeto")
        b_arte.clicked.connect(lambda: self.atualizar_arte())
        self.boca_esq = QCheckBox("Boca à esquerda na área 360°")
        self.boca_esq.setChecked(True)
        self.angulo = QDoubleSpinBox()
        self.angulo.setRange(-360, 360)
        self.angulo.setDecimals(0)
        self.angulo.setSuffix("°")
        self.angulo.setToolTip("Gira a arte em volta da peça (também: arrastar com o botão direito na vista 3D)")
        self.b_render = QPushButton("Renderizar (placa de vídeo)")
        self.b_render.setToolTip("Prévia realista no Blender (Cycles na placa de vídeo), com a vista atual")
        self.b_render.clicked.connect(lambda: self.renderizar())
        b_blender = QPushButton("Blender…")
        b_blender.setToolTip("Escolher o blender.exe (se não for encontrado sozinho)")
        b_blender.clicked.connect(self._escolher_blender)
        self.status_render = QLabel()
        self.status_render.setStyleSheet("color:#6b717a")
        l1 = QHBoxLayout()
        for w in (QLabel("Arte:"), self.fonte, b_arte, self.boca_esq):
            l1.addWidget(w)
        l1.addStretch(1)
        l2 = QHBoxLayout()
        for w in (QLabel("Girar arte"), self.angulo, self.b_render, b_blender):
            l2.addWidget(w)
        l2.addStretch(1)
        direita = QWidget()
        dv = QVBoxLayout(direita)
        dv.addWidget(self.vista, 1)
        dv.addLayout(l1)
        dv.addLayout(l2)
        dv.addWidget(self.status_render)

        div = QSplitter()
        div.addWidget(rolagem)
        div.addWidget(self.perfil)
        div.addWidget(direita)
        div.setStretchFactor(2, 1)
        div.setSizes([380, 260, 640])
        self.setCentralWidget(div)
        self.resize(1320, 760)

        self._t_salvar = QTimer(self, singleShot=True, interval=600, timeout=self.salvar_estado)
        # desfazer do plugin: medidas/aparência (passos próprios) e movimentos da arte (passos do projeto)
        self._hist, self._refazer_hist, self._ultimo_estado = [], [], None
        self._t_hist = QTimer(self, singleShot=True, interval=500, timeout=self._registrar_hist)
        for seq, fn in ((QKeySequence.Undo, self.desfazer), (QKeySequence.Redo, self.refazer),
                        (QKeySequence("Ctrl+Y"), self.refazer)):
            atalho = QShortcut(seq, self)
            atalho.setContext(Qt.WindowShortcut)
            atalho.activated.connect(fn)
        for x in (self.d_topo, self.d_base, self.altura, self.inicio, self.alt_arte,
                  self.alca, self.margem, self.foco, self.angulo):
            x.valueChanged.connect(self.recalcular)
        self.repet.valueChanged.connect(self.recalcular)
        self.material.currentTextChanged.connect(self._material_mudou)
        self.fonte.currentIndexChanged.connect(lambda *_: self.atualizar_arte())
        self._t_arte = QTimer(self, singleShot=True, interval=350, timeout=self._projeto_mudou)
        # métodos (não lambdas): o Qt desliga sozinho quando a janela do plugin é destruída
        self.jp.undo_stack.indexChanged.connect(self._agendar_arte)
        self.jp.canvas.scene.selectionChanged.connect(self._selecao_do_projeto)
        self.boca_esq.toggled.connect(lambda *_: self.atualizar_arte())
        self.recalcular()

    @staticmethod
    def _mm(a, b, v):
        s = QDoubleSpinBox()
        s.setRange(a, b)
        s.setDecimals(1)
        s.setValue(v)
        s.setSuffix(" mm")
        return s

    # ---------- medidas ----------
    def peca(self):
        return calc.Peca(diametro_topo=self.d_topo.value(), diametro_base=self.d_base.value(),
                         altura=self.altura.value(), inicio=self.inicio.value(), altura_arte=self.alt_arte.value(),
                         alca_mm=self.alca.value(), margem_mm=self.margem.value(), repeticoes=self.repet.value(),
                         foco_mm=self.foco.value(), pontos=tuple(self.pontos))

    def mudar_perfil(self, acao, i=None, z=None, d=None):
        """Pontos do perfil: mover/novo/remover (pelo desenho, pela tabela ou pelos botões); boca/base: diâmetro."""
        h = self.altura.value()
        if acao == "faixa":  # sobe/desce a faixa da arte (desenho de lado ou setas)
            self.inicio.setValue(round(min(max(z, 0.0), max(0.0, h - self.alt_arte.value())), 1))
            return
        if acao == "boca":
            self.d_topo.setValue(round(d, 1))
            return
        if acao == "base":
            self.d_base.setValue(round(d, 1))
            return
        if acao == "novo":
            if z is None:  # botão "+ ponto": no meio do maior vão entre pontos
                nos = calc.nos(self.peca())
                a, b = max(zip(nos, nos[1:]), key=lambda par: par[1][0] - par[0][0])
                z = (a[0] + b[0]) / 2
                d = calc.diametro_em(self.peca(), z)
            self.pontos.append((round(z, 1), round(d, 1)))
        elif acao == "mover" and 0 <= i < len(self.pontos):
            self.pontos[i] = (round(min(max(z, 1.0), h - 1.0), 1), round(d, 1))
        elif acao == "remover" and 0 <= (i if i is not None else -1) < len(self.pontos):
            del self.pontos[i]
        else:
            return
        ordem = sorted(range(len(self.pontos)), key=lambda k: self.pontos[k][0])
        if acao == "mover":  # o ponto arrastado continua sendo o mesmo depois de reordenar
            self.perfil._arr = ordem.index(i) + 1 if self.perfil._arr is not None else None
        self.pontos = [self.pontos[k] for k in ordem]
        self._encher_tabela()
        self.recalcular()

    def _encher_tabela(self):
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(self.pontos))
        for r, (z, d) in enumerate(self.pontos):
            for c, v in enumerate((z, d)):
                self.tabela.setItem(r, c, QTableWidgetItem(_n(v)))
        self.tabela.blockSignals(False)

    def _tabela_editada(self, item):
        r, c = item.row(), item.column()
        try:
            v = float(item.text().replace(",", ".").replace("mm", "").strip())
        except ValueError:
            self._encher_tabela()
            return
        z, d = self.pontos[r]
        self.mudar_perfil("mover", r, v if c == 0 else z, v if c == 1 else d)

    def _material_mudou(self, nome):
        self.cores = list(MATERIAIS[nome][:2])  # cada material traz as cores padrão (dá para trocar depois)
        self.recalcular()

    def _pintar_botoes_cor(self):
        for b, c in ((self.b_cor_corpo, self.cores[0]), (self.b_cor_arte, self.cores[1])):
            texto = "#000" if QColor(c).lightness() > 140 else "#fff"
            b.setText(c.upper())
            b.setStyleSheet(f"background:{c};color:{texto};border:1px solid #555;padding:4px")

    def ask_cor(self, atual, titulo):
        c = QColorDialog.getColor(QColor(atual), self, titulo)
        return c.name() if c.isValid() else None

    def _escolher_cor(self, qual):
        i = 0 if qual == "corpo" else 1
        c = self.ask_cor(self.cores[i], "Cor do copo" if i == 0 else "Cor da gravação")
        if c:
            self.cores[i] = c
            self.recalcular()

    def _arte_movida(self, ang, inicio):
        if self._antes_arrasto is None:  # começo do arrasto: guarda de onde saiu
            self._antes_arrasto = (self.angulo.value(), self.inicio.value())
        for w, v in ((self.angulo, ang if ang <= 180 else ang - 360), (self.inicio, inicio)):
            w.blockSignals(True)
            w.setValue(round(v, 1))
            w.blockSignals(False)
        self.recalcular(arrastando=True)

    def _arte_solta(self):
        """Soltou a arte arrastada no 3D. Com a área 360°, as peças MESMO se movem na área de trabalho (um passo de
        desfazer): em volta do copo = eixo Y da área, para cima/baixo = eixo X. A prévia volta para a posição
        guardada e passa a mostrar as peças no lugar novo."""
        if self._antes_arrasto is None:
            return False
        ang0, ini0 = self._antes_arrasto
        self._antes_arrasto = None
        area = art.area_360(self.jp) if self.fonte.currentIndex() == 0 else None
        if area is None:
            self.status_render.setText("Arraste só na prévia. Para o desenho da área de trabalho acompanhar, use a "
                                       "área 360° (\"Criar área de gravação 360°\").")
            return False
        d_ang = ((self.angulo.value() - ang0) + 180) % 360 - 180
        d_ini = self.inicio.value() - ini0
        p = dataclasses.replace(self.peca(), inicio=ini0)
        from .vista3d import raio_rotativo
        du = math.radians(d_ang) * raio_rotativo(p)  # mm em volta (na escala do rotativo)
        boca_esq = self.boca_esq.isChecked()
        dx, dy = (d_ini, -du) if boca_esq else (-d_ini, du)
        for w, v in ((self.angulo, ang0), (self.inicio, ini0)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        movidas = self.mover_arte_na_area(area, dx, dy)
        self.recalcular()
        self.atualizar_arte()
        return movidas > 0

    # ---------- desfazer / refazer dentro do plugin ----------
    def _registrar_hist(self):
        atual = json.dumps(self.estado(), sort_keys=True)
        if self._ultimo_estado is not None and atual != self._ultimo_estado:
            self._hist.append(("medidas", self._ultimo_estado))
            self._refazer_hist.clear()
        self._ultimo_estado = atual

    def _aplicar_estado(self, bruto):
        self._restaurando = True
        try:
            self.jp.settings.setValue(self._chave(), bruto)
            self.carregar_estado()
        finally:
            self._restaurando = False
        self._ultimo_estado = json.dumps(self.estado(), sort_keys=True)

    def desfazer(self):
        """Ctrl+Z no plugin: desfaz a última mudança (medidas/aparência ou arte movida no copo)."""
        self._t_hist.stop()
        self._registrar_hist()
        if not self._hist:
            self.jp.undo_stack.undo()  # nada do plugin: desfaz o projeto
            return
        tipo, valor = self._hist.pop()
        if tipo == "projeto":
            self.jp.undo_stack.undo()
            self._refazer_hist.append(("projeto", None))
        else:
            self._refazer_hist.append(("medidas", json.dumps(self.estado(), sort_keys=True)))
            self._aplicar_estado(valor)
        self.statusBar().showMessage("Desfeito.")

    def refazer(self):
        if not self._refazer_hist:
            self.jp.undo_stack.redo()
            return
        tipo, valor = self._refazer_hist.pop()
        if tipo == "projeto":
            self.jp.undo_stack.redo()
            self._hist.append(("projeto", None))
        else:
            self._hist.append(("medidas", json.dumps(self.estado(), sort_keys=True)))
            self._aplicar_estado(valor)
        self.statusBar().showMessage("Refeito.")

    def mover_arte_na_area(self, area, dx, dy) -> int:
        """Move as peças que estão na área 360° (menos a própria área e as guias); quem passar da borda volta pelo
        outro lado, como no copo. Devolve quantas peças moveram."""
        pecas = [s for s in self.jp.canvas.view.shapes()
                 if s.layer != art.REFERENCIA and not s.bloqueado and ob.geom_rect(s).intersects(area)]
        if not pecas or (abs(dx) < 1e-6 and abs(dy) < 1e-6):
            return 0
        self._t_hist.stop()
        self._registrar_hist()  # mudanças de medidas pendentes entram ANTES do movimento (ordem do desfazer)

        def do():
            for s in pecas:
                ob.move_by([s], dx, dy)
                r = ob.geom_rect(s)
                volta = area.height()
                if r.center().y() > area.bottom():  # em volta do copo: dá a volta
                    ob.move_by([s], 0, -volta)
                elif r.center().y() < area.top():
                    ob.move_by([s], 0, volta)
                # ao longo da altura do copo não há volta: fica dentro da área (encosta na borda)
                if r.width() >= area.width():
                    ob.move_by([s], area.left() - r.left(), 0)
                elif r.left() < area.left():
                    ob.move_by([s], area.left() - r.left(), 0)
                elif r.right() > area.right():
                    ob.move_by([s], area.right() - r.right(), 0)
        self.jp._edit("Mover arte no copo", do)
        self._hist.append(("projeto", None))
        self._refazer_hist.clear()
        self.statusBar().showMessage(f"{len(pecas)} peça(s) movida(s) na área 360°: {dx:+.1f} mm em X, "
                                     f"{dy:+.1f} mm em Y".replace(".", ","))
        return len(pecas)

    def recalcular(self, *_, arrastando=False):
        p = self.peca()
        e = calc.erros(p)
        self.perfil.p = p
        self._pintar_botoes_cor()
        self.vista.definir(p=p, angulo_arte=self.angulo.value(), material=self.material.currentText(),
                           cores=tuple(self.cores))
        if e:
            self.r = None
            self.res.setText("<b style='color:#c0392b'>" + "<br>".join(e) + "</b>")
            self.b_leque.setEnabled(False)
        else:
            r = self.r = calc.calcular(p)
            linhas = [f"<b>Volta no meio da arte (360°):</b> {_n(r['circ'])} mm (Ø {_n(r['d_meio'])} mm)",
                      f"<b>Largura útil da arte:</b> {_n(r['util'])} mm × {_n(p.altura_arte)} mm"]
            if p.repeticoes > 1:
                linhas.append(f"<b>{p.repeticoes} artes:</b> até {_n(r['por_arte'])} mm cada, a cada "
                              f"{_n(r['passo_mm'])} mm ({_n(r['passo_graus'], 0)}°)")
            if r["conico"]:
                linhas += [f"Topo da arte Ø {_n(r['d_cima'])} · base da arte Ø {_n(r['d_baixo'])}",
                           f"<b>Distorção:</b> {_n(r['distorcao_pct'])} % (a arte abre onde a peça é mais larga)"]
                cor = "#1e8449" if r["foco_ok"] else "#c0392b"
                linhas.append(f"<span style='color:{cor}'><b>Foco:</b> a superfície varia {_n(r['variacao_foco'])} "
                              "mm na faixa da arte — " + ("ok." if r["foco_ok"] else
                                                         "calce a base para nivelar ou use faixas menores.")
                              + "</span>")
            rot = self.jp.rotativo
            linhas.append(f"<span style='color:#555'>Rotativo: {rot.tipo}, {_n(rot.mm_por_rotacao)} mm/rotação"
                          + (f", rolo Ø {_n(rot.diametro_rolo_mm)}" if rot.tipo == "rolo" else "")
                          + (" · ligado" if rot.ativo else " · desligado") + "</span>")
            self.res.setText("<br>".join(linhas))
            self.b_leque.setEnabled("leque" in r)
        self.perfil.update()
        if not self._carregando:
            self._t_salvar.start()
            if not getattr(self, "_restaurando", False):
                self._t_hist.start()

    # ---------- arte ----------
    def _agendar_arte(self, *_):
        self._t_arte.start()

    def _selecao_do_projeto(self):
        if self.fonte.currentIndex() == 1:
            self._t_arte.start()

    def _projeto_mudou(self):
        """Algo mudou no projeto (mover, editar, desfazer, aba): a prévia acompanha sem precisar clicar."""
        if self.isVisible():
            self.atualizar_arte()
    def atualizar_arte(self):
        """Lê a arte do projeto para a prévia: área 360° (se existir), seleção ou tudo."""
        fonte = self.fonte.currentIndex()
        dados = None
        if fonte == 0:
            area = art.area_360(self.jp)
            if area is not None:
                dados = art.textura_360(self.jp, area, self.boca_esq.isChecked())
                self.status_render.setText(f"Arte: área 360° ({_n(area.width())} × {_n(area.height())} mm)."
                                           if dados else "A área 360° está vazia: desenhe dentro dela.")
            else:
                self.status_render.setText("Sem área 360° no projeto: usando o projeto inteiro (clique em "
                                           "\"Criar área de gravação 360°\").")
                dados = art.textura(self.jp, False)
        else:
            dados = art.textura(self.jp, fonte == 1)
            self.status_render.setText("Arte: " + ("formas selecionadas." if fonte == 1 else "projeto inteiro.")
                                       if dados else "Nada para aplicar.")
        self.vista.definir(arte=dados)
        if not self._carregando:
            self._t_salvar.start()
        return dados is not None

    # ---------- render ----------
    def _blender(self):
        return render.localizar_blender(self.jp.settings.value("cilindros/blender", ""))

    def _escolher_blender(self):
        c, _ = QFileDialog.getOpenFileName(self, "Onde está o blender.exe?", "", "Blender (blender.exe)")
        if c:
            self.jp.settings.setValue("cilindros/blender", c)
            self.status_render.setText(f"Blender: {c}")

    def renderizar(self, esperar=False, resolucao=1400, amostras=160):
        if not self.r:
            return None
        blender = self._blender()
        if not blender:
            QMessageBox.information(self, "Render", "Blender não encontrado. Instale o Blender (gratuito, "
                                    "blender.org) ou clique em \"Blender…\" para indicar o blender.exe.")
            return None
        pasta = tempfile.mkdtemp(prefix="redblack_copo_")
        script, dados, saida = render.preparar(pasta, self.peca(), self.angulo.value(), self.vista.arte,
                                               self.material.currentText(), self.vista.yaw, self.vista.pitch,
                                               resolucao, amostras, *self.cores)
        self.processo = QProcess(self)
        self.processo.setProgram(blender)
        self.processo.setArguments(render.argumentos(script, dados))
        self.processo.finished.connect(lambda *_: self._render_pronto(saida))
        self.b_render.setEnabled(False)
        self.status_render.setText("Renderizando na placa de vídeo… (pode levar alguns segundos)")
        self.processo.start()
        if esperar:
            self.processo.waitForFinished(300_000)
        return saida

    def _render_pronto(self, saida):
        self.b_render.setEnabled(True)
        log = bytes(self.processo.readAllStandardOutput()).decode("utf-8", "replace")
        if not os.path.isfile(saida):
            self.status_render.setText("O render falhou. Veja se o Blender abre normalmente.")
            self.ultimo_log = log
            return
        gpu = next((ln.split(":", 1)[1].strip() for ln in log.splitlines() if ln.startswith("PLACA DE VIDEO")), None)
        self.status_render.setText(f"Render pronto ({'placa de vídeo ' + gpu if gpu else 'processador'}): {saida}")
        self.ultimo_render = saida
        if not getattr(self, "sem_janela_render", False):
            self._mostrar_render(saida)

    def _mostrar_render(self, saida):
        d = QDialog(self)
        d.setWindowTitle("Prévia renderizada")
        v = QVBoxLayout(d)
        img = QLabel()
        img.setPixmap(QPixmap(saida).scaled(900, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        v.addWidget(img)
        salvar = QPushButton("Salvar imagem…")

        def gravar():
            c, _ = QFileDialog.getSaveFileName(d, "Salvar prévia", "previa_copo.png", "PNG (*.png)")
            if c:
                QPixmap(saida).save(c, "PNG")
        salvar.clicked.connect(gravar)
        v.addWidget(salvar)
        d.show()

    # ---------- parâmetros salvos por projeto ----------
    def _chave(self):
        fp = self.jp.file_path
        return "cilindros/proj/" + (os.path.normcase(os.path.abspath(fp)).replace("\\", "/").replace(":", "")
                                    if fp else "_sem_titulo")

    def estado(self):
        return {"peca": dataclasses.asdict(self.peca()), "angulo": self.angulo.value(), "cores": self.cores,
                "material": self.material.currentText(), "fonte": self.fonte.currentIndex(),
                "boca_esq": self.boca_esq.isChecked(), "yaw": self.vista.yaw, "pitch": self.vista.pitch}

    def salvar_estado(self):
        self.jp.settings.setValue(self._chave(), json.dumps(self.estado()))

    def carregar_estado(self):
        bruto = self.jp.settings.value(self._chave(), "")
        try:
            e = json.loads(bruto) if bruto else None
        except ValueError:
            e = None
        self._carregando = True
        try:
            if e:
                p = calc.Peca(**{k: v for k, v in e["peca"].items() if k in calc.Peca.__dataclass_fields__})
                self.pontos = [tuple(x) for x in calc.nos(p)[1:-1]]  # inclui o "meio" de versões anteriores
                self._encher_tabela()
                for w, v in ((self.d_topo, p.diametro_topo),
                             (self.d_base, p.diametro_base), (self.altura, p.altura), (self.inicio, p.inicio),
                             (self.alt_arte, p.altura_arte), (self.alca, p.alca_mm), (self.margem, p.margem_mm),
                             (self.foco, p.foco_mm), (self.angulo, e.get("angulo", 0.0))):
                    w.setValue(v)
                self.repet.setValue(p.repeticoes)
                if e.get("material") in MATERIAIS:
                    self.material.setCurrentText(e["material"])
                if isinstance(e.get("cores"), list) and len(e["cores"]) == 2:
                    self.cores = [str(c) for c in e["cores"]]
                self.fonte.setCurrentIndex(e.get("fonte", 0))
                self.boca_esq.setChecked(e.get("boca_esq", True))
                self.vista.yaw, self.vista.pitch = e.get("yaw", 0.0), e.get("pitch", 22.0)
            self.recalcular()
            self.atualizar_arte()
        finally:
            self._carregando = False
        return bool(e)

    # ---------- botões do projeto ----------
    def ask_ligar_rotativo(self):
        r = QMessageBox.question(
            self, "Ligar o rotativo",
            "Ligar o ROTATIVO no RedBlack?\n\nCom ele ligado, todo movimento em Y é convertido em giro da peça "
            f"(×{self.jp.rotativo.mm_por_rotacao / (3.14159 * self.jp.rotativo.diametro_referencia):.2f} no caso do "
            "seu rolo). Só faça isso com o rotativo CONECTADO no lugar do motor do eixo Y.\n\nPara voltar a gravar "
            "em chapa plana, desligue em Laser → Configuração do rotativo (ou no aviso vermelho do painel Máquina).",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def aplicar_rotativo(self):
        if not self.r:
            return False
        if not self.ask_ligar_rotativo():
            return False
        r = dataclasses.replace(self.jp.rotativo, ativo=True, diametro_objeto_mm=round(self.r["d_meio"], 2))
        ok = self.jp.definir_rotativo(r)
        if ok:
            self.statusBar().showMessage(f"Rotativo ligado: peça Ø {_n(self.r['d_meio'], 2)} mm.")
            self.recalcular()
        return ok

    def _adicionar(self, itens, texto):
        x0 = 10.0
        b = ob.bounds(itens)
        ob.move_by(itens, x0 - b.left(), x0 - b.top())
        self.jp._edit(texto, lambda: [self.jp.canvas.scene.addItem(i) for i in itens])
        c = self.jp.layer(CAMADA_REF)
        if c is not None and c.saida:
            self.jp.set_layer_fields(CAMADA_REF, {"saida": False, "nome": "Referência (não grava)"},
                                     "Camada de referência")
        self.jp.canvas.view.fit()

    def criar_area(self):
        """Área 360° como o rotativo grava: X = ao longo da altura da arte (boca à esquerda), Y = volta inteira."""
        if not self.r:
            return False
        p, r = self.peca(), self.r
        A, V = p.altura_arte, r["circ"]
        ref = lambda cam, nome: ob.Shape(cam, nome, CAMADA_REF, cm.cor(CAMADA_REF))  # noqa: E731
        itens = [ref(fm.rect_path(QRectF(0, 0, A, V)), f"{art.NOME_AREA} ({_n(A)} × {_n(V)} mm)")]
        guias = QPainterPath()
        n = p.repeticoes
        ini, util = p.alca_mm / 2, V - p.alca_mm  # alça centrada na emenda (Y = 0 e Y = volta)
        for k in range(n):
            a = ini + k * util / n + p.margem_mm
            b = ini + (k + 1) * util / n - p.margem_mm
            if b > a:
                itens.append(ref(fm.rect_path(QRectF(0, a, A, b - a)), f"Área da arte {k + 1} ({_n(b - a)} mm)"))
                guias.moveTo(-3, (a + b) / 2)
                guias.lineTo(A + 3, (a + b) / 2)
        if p.alca_mm > 0:
            for y in (p.alca_mm / 2, V - p.alca_mm / 2):
                guias.moveTo(0, y)
                guias.lineTo(A, y)
        boca = QPainterPath()  # setinha do lado da boca
        boca.moveTo(-6, V / 2 - 4)
        boca.lineTo(-2, V / 2)
        boca.lineTo(-6, V / 2 + 4)
        guias.addPath(boca if self.boca_esq.isChecked() else boca.translated(A + 8, 0))
        itens.append(ref(guias, "Guias: centros das artes, alça e lado da boca (seta)"))
        from ... import texto as tx
        dica = tx.build_path(tx.TextoParams("BOCA ↑ topo da arte (gire a arte 90° para a esquerda)", "Arial", 3.0))
        dica = QTransform().rotate(-90).map(dica)
        bd = dica.boundingRect()
        x_dica = -12 - bd.right() if self.boca_esq.isChecked() else A + 12 - bd.left()
        itens.append(ref(dica.translated(x_dica, V / 2 - bd.center().y()), "Dica de orientação (não grava)"))
        self._adicionar(itens, "Área de gravação 360°")
        self.fonte.setCurrentIndex(0)
        return True

    def criar_leque(self):
        if not self.r or "leque" not in self.r:
            QMessageBox.information(self, "Molde em leque", "Só para copo cônico (base diferente da boca).")
            return False
        cam = calc.caminho_leque(self.peca())
        lq = calc.leque(self.peca())
        it = ob.Shape(cam, f"Molde em leque (R {_n(lq['R'])} / {_n(lq['Rin'])} mm, {_n(lq['angulo_graus'])}°)",
                      CAMADA_MOLDE, cm.cor(CAMADA_MOLDE))
        self._adicionar([it], "Molde em leque")
        return True
