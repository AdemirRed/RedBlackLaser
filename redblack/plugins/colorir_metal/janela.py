"""Janela do plugin Colorir metal: 1) grade de teste, 2) ler as cores da foto da placa, 3) colorir formas."""
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from . import cores as co


def _fmt(v):
    return f"{v:g}".replace(".", ",")


def _num(s):
    try:
        return float(s.replace(",", ".").strip())
    except ValueError:
        return None


class VistaGrade(QWidget):
    """Desenho da grade (em mm) com as cores esperadas, se houver paleta igual."""

    def __init__(self):
        super().__init__()
        self.cfg, self.cores = dict(co.GRADE_PADRAO), {}
        self.setMinimumSize(420, 300)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#8d9196"))
        w, h = co.tamanho_grade(self.cfg)
        esc = min((self.width() - 30) / max(w, 1), (self.height() - 30) / max(h, 1))
        p.translate(15, 15)
        p.scale(esc, esc)
        p.fillRect(QRectF(-3, -3, w + 6, h + 6), QColor("#b9bdc2"))  # chapa de inox
        for i, j, pot, iv, r in co.celulas(self.cfg):
            cor = self.cores.get((round(pot, 3), round(iv, 4)))
            p.fillRect(r, QColor(cor) if cor else QColor("#5d6168"))
        if self.cfg["rotulos"]:
            p.setPen(QPen(QColor("#111"), 0))
            f = p.font()
            f.setPointSizeF(2.4)
            p.setFont(f)
            passo = self.cfg["lado"] + self.cfg["espaco"]
            for i, pot in enumerate(co.potencias(self.cfg)):
                p.drawText(QRectF(0, i * passo, 13, self.cfg["lado"]), Qt.AlignVCenter | Qt.AlignLeft, f"{_fmt(pot)}%")
            for j, iv in enumerate(self.cfg["intervalos"]):
                p.drawText(QRectF(14 + j * passo, h - 7, self.cfg["lado"], 6), Qt.AlignCenter, _fmt(iv))
        p.end()


class VistaFoto(QWidget):
    """Foto da placa gravada; dois cliques (centro do 1º e do último quadrado) e mostra onde cada cor será lida."""

    def __init__(self, ao_mudar):
        super().__init__()
        self.img, self.pontos, self.linhas, self.colunas, self.ao_mudar = None, [], 7, 10, ao_mudar
        self.setMinimumSize(520, 420)

    def _quadro(self):
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        esc = min(r.width() / self.img.width(), r.height() / self.img.height())
        return QRectF(r.left(), r.top(), self.img.width() * esc, self.img.height() * esc), esc

    def mousePressEvent(self, e):
        if self.img is None:
            return
        q, esc = self._quadro()
        pt = QPointF((e.position().x() - q.left()) / esc, (e.position().y() - q.top()) / esc)
        self.pontos = [pt] if len(self.pontos) >= 2 else self.pontos + [pt]
        self.update()
        self.ao_mudar()

    def centros(self):
        if len(self.pontos) < 2:
            return []
        a, b = self.pontos
        dx = (b.x() - a.x()) / max(self.colunas - 1, 1)
        dy = (b.y() - a.y()) / max(self.linhas - 1, 1)
        return [QPointF(a.x() + j * dx, a.y() + i * dy) for i in range(self.linhas) for j in range(self.colunas)]

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2a2d33"))
        if self.img is None:
            p.setPen(QColor("#cfd5de"))
            p.drawText(self.rect(), Qt.AlignCenter, "Abra a foto da placa gravada (de frente, bem iluminada).")
            return
        q, esc = self._quadro()
        p.drawImage(q, self.img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#ff00ff"), 2))
        for c in self.centros() or self.pontos:
            p.drawEllipse(QPointF(q.left() + c.x() * esc, q.top() + c.y() * esc), 4, 4)
        p.end()


class JanelaColorir(QMainWindow):
    def __init__(self, janela_principal, arquivo_paletas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colorir metal com laser")
        self.jp, self.arquivo = janela_principal, arquivo_paletas
        self.paletas = co.carregar(arquivo_paletas)
        abas = QTabWidget()
        abas.addTab(self._aba_grade(), "1. Grade de teste")
        abas.addTab(self._aba_foto(), "2. Ler cores da foto")
        abas.addTab(self._aba_colorir(), "3. Colorir")
        self.abas = abas
        self.setCentralWidget(abas)
        self.resize(1050, 680)
        self._grade_mudou()
        self._encher_paletas()

    # ---------- 1. grade ----------
    def _aba_grade(self):
        cfg = co.GRADE_PADRAO
        self.g_pot_ini = self._spin(1, 100, cfg["pot_ini"], " %")
        self.g_pot_fim = self._spin(1, 100, cfg["pot_fim"], " %")
        self.g_pot_passo = self._spin(0.5, 50, cfg["pot_passo"], " %")
        self.g_intervalos = QLineEdit("; ".join(_fmt(v) for v in cfg["intervalos"]))
        self.g_intervalos.setToolTip("Intervalos entre linhas (mm), separados por ponto e vírgula — uma coluna cada")
        self.g_vel = self._spin(10, 60000, cfg["velocidade"], " mm/min", 0)
        self.g_passadas = QSpinBox()
        self.g_passadas.setRange(1, 20)
        self.g_passadas.setValue(cfg["passadas"])
        self.g_lado = self._spin(2, 50, cfg["lado"], " mm")
        self.g_espaco = self._spin(0.5, 20, cfg["espaco"], " mm")
        self.g_rotulos = QCheckBox("Gravar os números (potência e intervalo)")
        self.g_rotulos.setChecked(True)
        self.g_x = self._spin(0, 2000, 5, " mm")
        self.g_y = self._spin(0, 2000, 5, " mm")
        form = QFormLayout()
        for t, w in (("Potência inicial", self.g_pot_ini), ("Potência final", self.g_pot_fim),
                     ("Passo da potência", self.g_pot_passo), ("Intervalos (colunas)", self.g_intervalos),
                     ("Velocidade", self.g_vel), ("Passadas", self.g_passadas), ("Lado do quadrado", self.g_lado),
                     ("Espaço entre quadrados", self.g_espaco), ("Posição X na mesa", self.g_x),
                     ("Posição Y na mesa", self.g_y)):
            form.addRow(t, w)
        form.addRow(self.g_rotulos)
        self.g_info = QLabel()
        self.g_info.setWordWrap(True)
        salvar = QPushButton("Salvar G-code da grade…")
        salvar.clicked.connect(self.salvar_gcode)
        dica = QLabel("Use a mesma velocidade e foco que vai usar no trabalho. Limpe o metal (álcool) antes. "
                      "O inox muda de cor com o calor: deixe esfriar e fotografe com luz branca, de frente.")
        dica.setWordWrap(True)
        dica.setStyleSheet("color:#6b717a")
        lado = QVBoxLayout()
        lado.addLayout(form)
        lado.addWidget(self.g_info)
        lado.addWidget(salvar)
        lado.addWidget(dica)
        lado.addStretch(1)
        self.vista_grade = VistaGrade()
        w = QWidget()
        h = QHBoxLayout(w)
        h.addLayout(lado)
        h.addWidget(self.vista_grade, 1)
        self._t_grade = QTimer(self, singleShot=True, interval=200, timeout=self._grade_mudou)
        for x in (self.g_pot_ini, self.g_pot_fim, self.g_pot_passo, self.g_vel, self.g_passadas, self.g_lado,
                  self.g_espaco):
            x.valueChanged.connect(lambda *_: self._t_grade.start())
        self.g_intervalos.textChanged.connect(lambda *_: self._t_grade.start())
        self.g_rotulos.toggled.connect(lambda *_: self._t_grade.start())
        return w

    @staticmethod
    def _spin(a, b, v, suf, casas=2):
        s = QDoubleSpinBox()
        s.setRange(a, b)
        s.setDecimals(casas)
        s.setValue(v)
        s.setSuffix(suf)
        return s

    def cfg(self):
        ivs = tuple(v for v in (_num(t) for t in self.g_intervalos.text().replace("/", ";").split(";"))
                    if v is not None and 0.005 <= v <= 5)[:30] or co.GRADE_PADRAO["intervalos"]
        return dict(co.GRADE_PADRAO, pot_ini=self.g_pot_ini.value(), pot_fim=max(self.g_pot_fim.value(),
                                                                                 self.g_pot_ini.value()),
                    pot_passo=self.g_pot_passo.value(), intervalos=ivs, velocidade=self.g_vel.value(),
                    passadas=self.g_passadas.value(), lado=self.g_lado.value(), espaco=self.g_espaco.value(),
                    rotulos=self.g_rotulos.isChecked())

    def _grade_mudou(self):
        cfg = self.cfg()
        self.vista_grade.cfg = cfg
        ref = next((p for p in self.paletas if p["referencia"]), None)
        self.vista_grade.cores = {(round(c.potencia, 3), round(c.intervalo, 4)): c.cor for c in ref["cores"]
                                  if abs(c.velocidade - cfg["velocidade"]) < 1} if ref else {}
        w, h = co.tamanho_grade(cfg)
        n = len(co.celulas(cfg))
        try:
            from ... import percurso as pc
            _, perc = co.gcode_grade(cfg, self.g_x.value(), self.g_y.value())
            tempo = pc.fmt_tempo(sum(t.tempo_s for t in perc.trechos))
        except Exception as e:  # fora da mesa, linhas demais…
            tempo = f"não dá para gerar: {e}"
        self.g_info.setText(f"{len(co.potencias(cfg))} potências × {len(cfg['intervalos'])} intervalos = {n} "
                            f"quadrados · {_fmt(round(w, 1))} × {_fmt(round(h, 1))} mm · tempo ≈ {tempo}")
        self.vista_grade.update()

    def ask_arquivo_gcode(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar G-code da grade", "grade_cores_metal.gcode",
                                                 "G-code (*.gcode *.nc)")
        return caminho

    def salvar_gcode(self, caminho=None):
        from ... import gcode as gc
        caminho = caminho or self.ask_arquivo_gcode()
        if not caminho:
            return False
        try:
            txt, _ = co.gcode_grade(self.cfg(), self.g_x.value(), self.g_y.value())
            gc.salvar(caminho, txt)
        except Exception as e:
            QMessageBox.warning(self, "Grade de teste", str(e))
            return False
        self.statusBar().showMessage(f"G-code salvo: {caminho}")
        return True

    # ---------- 2. foto ----------
    def _aba_foto(self):
        self.foto = VistaFoto(self._foto_mudou)
        abrir = QPushButton("Abrir foto da placa…")
        abrir.clicked.connect(lambda: self.abrir_foto())
        self.f_nome = QLineEdit("Inox 304 — minha máquina")
        self.f_info = QLabel("1. Abra a foto.\n2. Clique no CENTRO do quadrado do canto superior esquerdo.\n"
                             "3. Clique no centro do quadrado do canto inferior direito.\n"
                             "A grade (linhas × colunas) é a da aba 1.")
        self.f_info.setWordWrap(True)
        self.f_amostra = QWidget()
        self.f_grade = QGridLayout(self.f_amostra)
        self.f_grade.setSpacing(2)
        salvar = QPushButton("Salvar como paleta")
        salvar.clicked.connect(lambda: self.salvar_paleta_da_foto())
        lado = QVBoxLayout()
        lado.addWidget(abrir)
        lado.addWidget(self.f_info)
        lado.addWidget(QLabel("Nome da paleta (material)"))
        lado.addWidget(self.f_nome)
        lado.addWidget(self.f_amostra)
        lado.addWidget(salvar)
        lado.addStretch(1)
        w = QWidget()
        h = QHBoxLayout(w)
        h.addWidget(self.foto, 1)
        h.addLayout(lado)
        self.lidas = None
        return w

    def ask_foto(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Foto da placa gravada", "", "Imagens (*.png *.jpg *.jpeg)")
        return caminho

    def abrir_foto(self, caminho=None):
        caminho = caminho or self.ask_foto()
        if not caminho:
            return False
        img = QImage(caminho)
        if img.isNull():
            QMessageBox.warning(self, "Foto", "Não foi possível abrir a imagem.")
            return False
        self.foto.img, self.foto.pontos = img, []
        self._foto_mudou()
        return True

    def _foto_mudou(self):
        cfg = self.cfg()
        self.foto.linhas, self.foto.colunas = len(co.potencias(cfg)), len(cfg["intervalos"])
        while self.f_grade.count():
            self.f_grade.takeAt(0).widget().deleteLater()
        self.lidas = None
        if self.foto.img is not None and len(self.foto.pontos) == 2:
            self.lidas = co.ler_foto(self.foto.img, *self.foto.pontos, self.foto.linhas, self.foto.colunas)
            for i, lin in enumerate(self.lidas):
                for j, c in enumerate(lin):
                    q = QLabel()
                    q.setFixedSize(16, 16)
                    q.setStyleSheet(f"background:{c};border:1px solid #333")
                    self.f_grade.addWidget(q, i, j)
        self.foto.update()

    def salvar_paleta_da_foto(self):
        if not self.lidas:
            QMessageBox.information(self, "Paleta", "Abra a foto e clique nos dois quadrados dos cantos.")
            return False
        nome = self.f_nome.text().strip() or "Minha paleta"
        self.paletas = [p for p in self.paletas if p["nome"] != nome] + [co.paleta_da_foto(nome, self.lidas,
                                                                                          self.cfg())]
        co.salvar(self.arquivo, self.paletas)
        self._encher_paletas(nome)
        self.abas.setCurrentIndex(2)
        return True

    # ---------- 3. colorir ----------
    def _aba_colorir(self):
        self.c_paleta = QComboBox()
        self.c_paleta.currentIndexChanged.connect(self._mostrar_paleta)
        self.c_area = QScrollArea()
        self.c_area.setWidgetResizable(True)
        self.c_info = QLabel("Escolha uma cor.")
        self.c_info.setWordWrap(True)
        self.c_aviso = QLabel()
        self.c_aviso.setWordWrap(True)
        self.c_aviso.setStyleSheet("color:#a05a00")
        aplicar = QPushButton("Aplicar às formas selecionadas")
        aplicar.clicked.connect(lambda: self.aplicar())
        proxima = QPushButton("Achar a cor mais próxima de…")
        proxima.clicked.connect(lambda: self.escolher_proxima())
        apagar = QPushButton("Apagar esta paleta")
        apagar.clicked.connect(self._apagar_paleta)
        lado = QVBoxLayout()
        lado.addWidget(QLabel("Paleta"))
        lado.addWidget(self.c_paleta)
        lado.addWidget(self.c_aviso)
        lado.addWidget(self.c_info)
        lado.addWidget(aplicar)
        lado.addWidget(proxima)
        lado.addWidget(apagar)
        explica = QLabel("Cada cor vira uma camada de Preenchimento com a potência, o intervalo e a velocidade dela. "
                         "Selecione as formas no projeto, clique na cor e em Aplicar.")
        explica.setWordWrap(True)
        lado.addWidget(explica)
        lado.addStretch(1)
        painel = QWidget()
        painel.setLayout(lado)
        painel.setFixedWidth(320)
        w = QWidget()
        h = QHBoxLayout(w)
        h.addWidget(self.c_area, 1)
        h.addWidget(painel)
        self.escolhida = None
        return w

    def _encher_paletas(self, nome=None):
        self.c_paleta.blockSignals(True)
        self.c_paleta.clear()
        for p in self.paletas:
            self.c_paleta.addItem(p["nome"])
        self.c_paleta.blockSignals(False)
        idx = next((i for i, p in enumerate(self.paletas) if p["nome"] == nome), 0)
        self.c_paleta.setCurrentIndex(idx)
        self._mostrar_paleta()

    def paleta(self):
        i = self.c_paleta.currentIndex()
        return self.paletas[i] if 0 <= i < len(self.paletas) else None

    def _mostrar_paleta(self, *_):
        p = self.paleta()
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(4)
        if p:
            self.c_aviso.setText("Referência de um anúncio (20 W, inox, 4000 mm/min). As cores reais dependem do "
                                 "SEU metal e máquina: grave a grade e leia a sua paleta." if p["referencia"] else "")
            colunas = len({c.intervalo for c in p["cores"]}) or 10
            for k, c in enumerate(p["cores"]):
                b = QPushButton()
                b.setFixedSize(44, 34)
                b.setToolTip(c.rotulo)
                b.setStyleSheet(f"background:{c.cor};border:1px solid #444")
                b.clicked.connect(lambda _=False, c=c: self.escolher(c))
                g.addWidget(b, k // colunas, k % colunas)
        self.c_area.setWidget(w)

    def escolher(self, c):
        self.escolhida = c
        self.c_info.setText(f"<b style='color:{c.cor}'>■■■</b> {c.cor}<br>{c.rotulo}")

    def escolher_proxima(self, cor=None):
        p = self.paleta()
        if not p:
            return None
        cor = cor or QColorDialog.getColor(QColor("#4a6fd0"), self, "Cor desejada")
        if not QColor(cor).isValid():
            return None
        c = co.mais_proxima(p["cores"], QColor(cor).name())
        self.escolher(c)
        return c

    def aplicar(self, cor=None):
        cor = cor or self.escolhida
        if cor is None:
            QMessageBox.information(self, "Colorir", "Escolha uma cor da paleta.")
            return None
        try:
            lid = co.aplicar(self.jp, cor)
        except ValueError as e:
            QMessageBox.information(self, "Colorir", str(e))
            return None
        self.statusBar().showMessage(f"Formas na camada {lid}: {cor.rotulo}")
        return lid

    def _apagar_paleta(self):
        p = self.paleta()
        if p is None or p["referencia"]:
            return
        self.paletas.remove(p)
        co.salvar(self.arquivo, self.paletas)
        self._encher_paletas()
