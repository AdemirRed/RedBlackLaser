"""Janela do plugin Plano de corte (Qt, separada da janela principal): peças, materiais, plano e configuração."""
import csv
import io
import json
import os

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSlider, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from .plano import Material, Peca, planejar_tudo

MATERIAIS_PADRAO = [Material(1, "MDF cru 3 mm", 3, 600, 400), Material(2, "MDF 6 mm", 6, 600, 400),
                    Material(3, "Acrílico 3 mm", 3, 500, 300)]
COL_QTD, COL_LARG, COL_ALT, COL_MAT, COL_DESC, COL_GIRA = range(6)
LARANJA = QColor("#7a5320")


def _num(txt, padrao=0.0):
    try:
        return float(str(txt).replace(",", ".").strip())
    except ValueError:
        return padrao


def _fmt(v):
    return f"{v:g}".replace(".", ",")


class VistaPlano(QWidget):
    """Desenha as chapas lado a lado com as peças (azul; girada = roxo) e o aproveitamento."""

    def __init__(self):
        super().__init__()
        self.resultado, self.zoom = [], 1.0
        self.setMinimumSize(400, 300)

    def definir(self, resultado, zoom):
        self.resultado, self.zoom = resultado, zoom
        self.updateGeometry()
        self.setMinimumSize(self._tamanho())
        self.update()

    def _blocos(self):
        """[(material, chapa, k, total, rect na tela)] com quebra de linha."""
        x = y = 12
        alt_linha, out, larg_max = 0, [], max(600, self.parentWidget().width() if self.parentWidget() else 900)
        for m, chapas, _ in self.resultado:
            if m is None:
                continue
            esc = min(520 / m.larg, 340 / m.alt) * self.zoom
            w, h = m.larg * esc + 16, m.alt * esc + 40
            for k, ch in enumerate(chapas, 1):
                if x + w > larg_max and x > 12:
                    x, y, alt_linha = 12, y + alt_linha + 12, 0
                out.append((m, ch, k, len(chapas), QRectF(x, y, w, h), esc))
                x += w + 12
                alt_linha = max(alt_linha, h)
        return out, y + alt_linha + 12

    def _tamanho(self):
        from PySide6.QtCore import QSize
        blocos, altura = self._blocos()
        largura = max([r.right() for *_, r, _e in blocos] + [400]) + 12
        return QSize(int(largura), int(max(altura, 300)))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        blocos, _ = self._blocos()
        if not blocos:
            p.setPen(QColor("#9fb0c4"))
            p.drawText(self.rect(), Qt.AlignCenter, "Calcule o plano na aba Peças.")
            return
        for m, ch, k, total, r, esc in blocos:
            p.setPen(QPen(QColor("#3a4757"), 1))
            p.setBrush(QColor("#2a3442"))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor("#9fc4ef"))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            uso = ch.usado(m.larg, m.alt) * 100
            p.drawText(QRectF(r.x() + 8, r.y() + 4, r.width() - 16, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{m.nome} — chapa {k} de {total}")
            p.setPen(QColor("#5fd18a"))
            p.drawText(QRectF(r.x() + 8, r.y() + 4, r.width() - 16, 20), Qt.AlignRight | Qt.AlignVCenter,
                       f"{_fmt(m.larg)} × {_fmt(m.alt)} · {len(ch.pecas)} peça(s) · {uso:.1f} %".replace(".", ","))
            ox, oy = r.x() + 8, r.y() + 30
            p.setPen(QPen(QColor("#c9b48f"), 1))
            p.setBrush(QColor("#f6efe2"))
            p.drawRect(QRectF(ox, oy, m.larg * esc, m.alt * esc))
            p.setFont(QFont("Segoe UI", 8))
            for c in ch.pecas:
                pr = QRectF(ox + c.x * esc, oy + c.y * esc, c.larg * esc, c.alt * esc)
                p.setPen(QPen(QColor("#6a3fbf" if c.girada else "#1a5fb4"), 1))
                p.setBrush(QColor("#d6c8ff" if c.girada else "#bfe3ff"))
                p.drawRect(pr)
                txt = f"{c.desc + ' ' if c.desc else ''}{_fmt(c.larg)}×{_fmt(c.alt)}"
                largura_txt = p.fontMetrics().horizontalAdvance(txt) + 6
                p.setPen(QColor("#12324f"))
                em_pe = pr.height() > pr.width()
                if (pr.height() if em_pe else pr.width()) > largura_txt and (pr.width() if em_pe else pr.height()) > 14:
                    p.save()
                    p.translate(pr.center())
                    if em_pe:
                        p.rotate(-90)
                    p.drawText(QRectF(-largura_txt / 2, -8, largura_txt, 16), Qt.AlignCenter, txt)
                    p.restore()
        p.end()


class JanelaPlanoCorte(QMainWindow):
    def __init__(self, ao_enviar, arquivo_lista, parent=None):
        """ao_enviar(chapas, camada) -> quantas abas criou no projeto."""
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)  # janela própria (não encaixa no layout principal)
        self.setWindowTitle("Plano de corte — RedBlack Laser")
        self.resize(1200, 760)
        self.ao_enviar, self.arquivo = ao_enviar, arquivo_lista
        self.materiais = list(MATERIAIS_PADRAO)
        self.pecas = []
        self.nome, self.espaco, self.margem = "", 3.0, 5.0
        self.resultado = []
        self._preenchendo = False
        self._salvar_timer = QTimer(self, singleShot=True, interval=400, timeout=self.salvar)
        self.abas = QTabWidget()
        self.setCentralWidget(self.abas)
        self.abas.addTab(self._aba_pecas(), "Peças")
        self.abas.addTab(self._aba_materiais(), "Materiais && Chapas")
        self.abas.addTab(self._aba_plano(), "Plano de corte")
        self.abas.addTab(self._aba_config(), "⚙ Config")
        self.carregar()
        QShortcut(QKeySequence("Ins"), self, activated=self.adicionar_peca)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.duplicar_peca)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.calcular)

    # ---------- montagem ----------
    @staticmethod
    def _botao(txt, fn, dica="", verde=False):
        b = QPushButton(txt)
        b.clicked.connect(fn)
        if dica:
            b.setToolTip(dica)
        if verde:
            b.setStyleSheet("QPushButton{background:#2e9e5b;color:white;font-weight:600;padding:5px 12px;"
                            "border-radius:5px}QPushButton:hover{background:#227a45}")
        return b

    @staticmethod
    def _dica(txt):
        lb = QLabel(txt)
        lb.setWordWrap(True)
        lb.setObjectName("banner")
        return lb

    def _aba_pecas(self):
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        barra.addWidget(QLabel("Projeto"))
        self.ed_nome = QLineEdit()
        self.ed_nome.setPlaceholderText("nome do projeto")
        self.ed_nome.setMaximumWidth(220)
        self.ed_nome.textChanged.connect(self._nome_mudou)
        barra.addWidget(self.ed_nome)
        for txt, fn, dica in (("🆕 Nova lista", self.nova_lista, "Apaga todas as peças"),
                              ("➕ Peça (Ins)", self.adicionar_peca, "Nova linha"),
                              ("Duplicar (Ctrl+D)", self.duplicar_peca, "Copia a linha selecionada"),
                              ("✕ Excluir linha", self.excluir_peca, "Apaga a linha selecionada"),
                              ("📂 Importar CSV", self.importar_csv, "Qtd;Largura;Altura;Material;Descricao;Gira"),
                              ("💾 Exportar CSV", self.exportar_csv, "Salva a lista em CSV")):
            barra.addWidget(self._botao(txt, fn, dica))
        barra.addStretch(1)
        barra.addWidget(self._botao("▦ Calcular plano de corte (Ctrl+Enter)", self.calcular, verde=True))
        v.addLayout(barra)
        v.addWidget(self._dica("Medidas em milímetros. Gira = a peça pode ser girada 90° para aproveitar melhor a chapa "
                               "(desligue quando o veio/desenho tiver direção). Linha laranja = peça maior que a chapa."))
        meio = QHBoxLayout()
        t = self.tab = QTableWidget(0, 6)
        t.setHorizontalHeaderLabels(["Qtd", "Largura", "Altura", "Material", "Descrição", "Gira"])
        t.horizontalHeader().setSectionResizeMode(COL_DESC, QHeaderView.Stretch)
        for c, larg in ((COL_QTD, 60), (COL_LARG, 90), (COL_ALT, 90), (COL_MAT, 230), (COL_GIRA, 50)):
            t.setColumnWidth(c, larg)
        t.itemChanged.connect(self._item_mudou)
        meio.addWidget(t, 1)
        lado = QVBoxLayout()
        self.lb_resumo = QLabel()
        self.lb_resumo.setAlignment(Qt.AlignTop)
        self.lb_resumo.setMinimumWidth(220)
        lado.addWidget(QLabel("<b>Resumo</b>"))
        lado.addWidget(self.lb_resumo, 1)
        meio.addLayout(lado)
        v.addLayout(meio, 1)
        self.lb_status = QLabel()
        v.addWidget(self.lb_status)
        return w

    def _aba_materiais(self):
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        barra.addWidget(self._botao("➕ Material", self.adicionar_material, verde=True))
        barra.addWidget(self._botao("✕ Excluir material", self.excluir_material))
        barra.addStretch(1)
        v.addLayout(barra)
        v.addWidget(self._dica("Cada material tem a sua chapa (largura × altura em mm). Para o laser, use o tamanho do "
                               "pedaço de chapa que vai na mesa (ex.: 600 × 400). A espessura é só informativa."))
        t = self.tab_mat = QTableWidget(0, 4)
        t.setHorizontalHeaderLabels(["Nome", "Espessura (mm)", "Chapa largura", "Chapa altura"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        t.itemChanged.connect(self._mat_mudou)
        v.addWidget(t, 1)
        return w

    def _aba_plano(self):
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        barra.addWidget(self._botao("▦ Recalcular", self.calcular))
        barra.addWidget(QLabel("Zoom"))
        self.sl_zoom = QSlider(Qt.Horizontal)
        self.sl_zoom.setRange(3, 25)
        self.sl_zoom.setValue(10)
        self.sl_zoom.setMaximumWidth(160)
        self.sl_zoom.valueChanged.connect(lambda _: self._desenhar())
        barra.addWidget(self.sl_zoom)
        barra.addStretch(1)
        barra.addWidget(QLabel("Camada no RedBlack"))
        self.cb_camada = QComboBox()
        self.cb_camada.addItems([f"C{i:02d}" for i in range(1, 29)])
        barra.addWidget(self.cb_camada)
        self.bt_enviar = self._botao("📤 Enviar ao RedBlack (uma aba por chapa)", self.enviar, verde=True)
        self.bt_enviar.setEnabled(False)
        barra.addWidget(self.bt_enviar)
        v.addLayout(barra)
        self.vista = VistaPlano()
        sc = QScrollArea()
        sc.setWidget(self.vista)
        sc.setWidgetResizable(True)
        v.addWidget(sc, 1)
        self.lb_plano = QLabel()
        v.addWidget(self.lb_plano)
        return w

    def _aba_config(self):
        w = QWidget()
        f = QFormLayout(w)
        self.sp_espaco, self.sp_margem = QDoubleSpinBox(), QDoubleSpinBox()
        for sp in (self.sp_espaco, self.sp_margem):
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix(" mm")
            sp.valueChanged.connect(self._cfg_mudou)
        f.addRow("Espaço entre peças", self.sp_espaco)
        f.addRow("Margem da borda da chapa", self.sp_margem)
        f.addRow(self._dica("O espaço evita que o laser queime a peça vizinha (2 a 5 mm). As peças entram da maior para "
                            "a menor, cada uma no lugar livre onde sobra menos espaço (método MaxRects), pelo "
                            "retângulo da peça."))
        return w

    # ---------- tabelas ----------
    def _mat_por_cod(self, cod):
        return next((m for m in self.materiais if m.cod == cod), None)

    def _grande(self, p):
        m = self._mat_por_cod(p.material)
        if m is None:
            return False
        cabe = lambda w, h: w <= m.larg - 2 * self.margem and h <= m.alt - 2 * self.margem  # noqa: E731
        return not (cabe(p.larg, p.alt) or (p.girar and cabe(p.alt, p.larg)))

    def _preencher_pecas(self):
        self._preenchendo = True
        t = self.tab
        t.setRowCount(len(self.pecas))
        for r, p in enumerate(self.pecas):
            for c, v in ((COL_QTD, str(p.qtd)), (COL_LARG, _fmt(p.larg)), (COL_ALT, _fmt(p.alt)), (COL_DESC, p.desc)):
                it = QTableWidgetItem(v)
                if c != COL_DESC:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(r, c, it)
            g = QTableWidgetItem()
            g.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            g.setCheckState(Qt.Checked if p.girar else Qt.Unchecked)
            t.setItem(r, COL_GIRA, g)
            cb = QComboBox()
            for m in self.materiais:
                cb.addItem(f"{m.cod} — {m.nome} ({_fmt(m.larg)}×{_fmt(m.alt)})", m.cod)
            cb.setCurrentIndex(max(0, cb.findData(p.material)))
            cb.currentIndexChanged.connect(lambda _=0, r=r, cb=cb: self._material_da_peca(r, cb.currentData()))
            t.setCellWidget(r, COL_MAT, cb)
            self._pintar_linha(r)
        self._preenchendo = False
        self._resumo()

    def _pintar_linha(self, r):
        cor = LARANJA if self._grande(self.pecas[r]) else QColor(0, 0, 0, 0)
        for c in range(self.tab.columnCount()):
            it = self.tab.item(r, c)
            if it:
                it.setBackground(cor)

    def _item_mudou(self, it):
        if self._preenchendo:
            return
        p, c = self.pecas[it.row()], it.column()
        if c == COL_QTD:
            p.qtd = max(0, int(_num(it.text(), p.qtd)))
        elif c == COL_LARG:
            p.larg = max(0.0, _num(it.text(), p.larg))
        elif c == COL_ALT:
            p.alt = max(0.0, _num(it.text(), p.alt))
        elif c == COL_DESC:
            p.desc = it.text().strip()
        elif c == COL_GIRA:
            p.girar = it.checkState() == Qt.Checked
        self._preenchendo = True
        self._pintar_linha(it.row())
        self._preenchendo = False
        self._resumo()
        self._mudou()

    def _material_da_peca(self, r, cod):
        if not self._preenchendo and 0 <= r < len(self.pecas):
            self.pecas[r].material = cod
            self._pintar_linha(r)
            self._resumo()
            self._mudou()

    def _preencher_mats(self):
        self._preenchendo = True
        t = self.tab_mat
        t.setRowCount(len(self.materiais))
        for r, m in enumerate(self.materiais):
            for c, v in enumerate((m.nome, _fmt(m.esp), _fmt(m.larg), _fmt(m.alt))):
                it = QTableWidgetItem(v)
                if c:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(r, c, it)
        self._preenchendo = False

    def _mat_mudou(self, it):
        if self._preenchendo:
            return
        m, c = self.materiais[it.row()], it.column()
        if c == 0:
            m.nome = it.text().strip() or m.nome
        else:
            v = _num(it.text(), 0)
            if c == 1:
                m.esp = max(0.0, v)
            elif v >= 1:  # chapa precisa de tamanho
                if c == 2:
                    m.larg = v
                else:
                    m.alt = v
        self._preencher_pecas()
        self._mudou()

    def _resumo(self):
        por_mat, total, area = {}, 0, 0.0
        for p in self.pecas:
            total += p.qtd
            area += p.qtd * p.larg * p.alt
            m = self._mat_por_cod(p.material)
            k = m.nome if m else "sem material"
            por_mat[k] = por_mat.get(k, 0) + p.qtd
        self.lb_resumo.setText("<br>".join(f"{k}: <b>{v}</b> peça(s)" for k, v in por_mat.items()) or "<i>Lista vazia</i>")
        grandes = sum(self._grande(p) for p in self.pecas)
        self.lb_status.setText(f"Linhas: <b>{len(self.pecas)}</b> &nbsp; Peças: <b>{total}</b> &nbsp; Área: "
                               f"<b>{area / 1e6:.3f} m²</b>".replace(".", ",")
                               + (f" &nbsp; <span style='color:#ff8a80'>{grandes} linha(s) maior(es) que a chapa</span>"
                                  if grandes else ""))

    # ---------- ações ----------
    def _linha_atual(self):
        r = self.tab.currentRow()
        return r if 0 <= r < len(self.pecas) else len(self.pecas) - 1

    def adicionar_peca(self, base=None):
        ult = self.pecas[-1] if self.pecas else None
        mat = ult.material if ult else (self.materiais[0].cod if self.materiais else 0)
        self.pecas.append(Peca(**vars(base)) if base else Peca(1, 100, 100, mat, "", True))
        self._preencher_pecas()
        self.tab.setCurrentCell(len(self.pecas) - 1, COL_QTD)
        self._mudou()

    def duplicar_peca(self):
        r = self._linha_atual()
        if r >= 0:
            self.adicionar_peca(self.pecas[r])

    def excluir_peca(self):
        r = self._linha_atual()
        if r >= 0:
            del self.pecas[r]
            self._preencher_pecas()
            self._mudou()

    def nova_lista(self, confirmar=True):
        if confirmar and self.pecas and QMessageBox.question(self, "Nova lista", "Apagar todas as peças?") != \
                QMessageBox.Yes:
            return
        self.pecas, self.resultado = [], []
        self._preencher_pecas()
        self._desenhar()
        self._mudou()

    def adicionar_material(self):
        cod = max([m.cod for m in self.materiais] + [0]) + 1
        self.materiais.append(Material(cod, f"Material {cod}", 3, 600, 400))
        self._preencher_mats()
        self._preencher_pecas()
        self._mudou()

    def excluir_material(self):
        r = self.tab_mat.currentRow()
        if not 0 <= r < len(self.materiais):
            return
        m = self.materiais[r]
        if any(p.material == m.cod for p in self.pecas) and QMessageBox.question(
                self, "Excluir material", f'Há peças usando "{m.nome}". Excluir mesmo assim?') != QMessageBox.Yes:
            return
        del self.materiais[r]
        self._preencher_mats()
        self._preencher_pecas()
        self._mudou()

    def _nome_mudou(self, txt):
        self.nome = txt
        self.setWindowTitle(f"Plano de corte — {txt}" if txt else "Plano de corte — RedBlack Laser")
        self._mudou()

    def _cfg_mudou(self):
        if self._preenchendo:
            return
        self.espaco, self.margem = self.sp_espaco.value(), self.sp_margem.value()
        self._preencher_pecas()
        self._mudou()

    def calcular(self):
        self.resultado = planejar_tudo(self.pecas, self.materiais, self.espaco, self.margem)
        self._desenhar()
        self.abas.setCurrentIndex(2)

    def _desenhar(self):
        self.vista.definir(self.resultado, self.sl_zoom.value() / 10)
        n = sum(len(ch) for _, ch, _f in self.resultado)
        fora = sum(len(f) for _, _c, f in self.resultado)
        usos = [c.usado(m.larg, m.alt) for m, chs, _ in self.resultado if m for c in chs]
        self.bt_enviar.setEnabled(n > 0)
        txt = (f"Chapas: <b>{n}</b> &nbsp; Aproveitamento médio: <b>{(sum(usos) / len(usos) * 100 if usos else 0):.1f} %"
               f"</b>").replace(".", ",")
        if fora:
            nomes = ", ".join(f"{p.desc or 'sem descrição'} {_fmt(p.larg)}×{_fmt(p.alt)}" for _, _c, f in self.resultado
                              for p in f[:5])
            txt += f" &nbsp; <span style='color:#ff8a80'>{fora} peça(s) não couberam: {nomes}</span>"
        self.lb_plano.setText(txt)

    def chapas_para_enviar(self):
        out = []
        for m, chapas, _ in self.resultado:
            if m is None:
                continue
            for k, ch in enumerate(chapas, 1):
                out.append({"nome": f"{m.nome} — chapa {k}"[:60], "largura": m.larg, "altura": m.alt,
                            "pecas": [{"x": c.x, "y": c.y, "largura": c.larg, "altura": c.alt,
                                       "nome": f"{c.desc or 'Peça ' + str(c.n)} {_fmt(c.larg)}×{_fmt(c.alt)}"}
                                      for c in ch.pecas]})
        return out

    def enviar(self):
        chapas = self.chapas_para_enviar()
        if not chapas:
            return 0
        n = self.ao_enviar(chapas, self.cb_camada.currentText())
        self.lb_plano.setText(self.lb_plano.text() + f" &nbsp; <b style='color:#5fd18a'>Enviado: {n} aba(s) no RedBlack</b>")
        return n

    # ---------- CSV ----------
    def exportar_csv(self, caminho=None):
        caminho = caminho or QFileDialog.getSaveFileName(self, "Exportar lista", (self.nome or "lista_de_pecas") + ".csv",
                                                         "CSV (*.csv)")[0]
        if not caminho:
            return False
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Qtd", "Largura", "Altura", "Material", "Descricao", "Gira"])
            for p in self.pecas:
                m = self._mat_por_cod(p.material)
                w.writerow([p.qtd, _fmt(p.larg), _fmt(p.alt), m.nome if m else "", p.desc, "sim" if p.girar else "nao"])
        return True

    def importar_csv(self, caminho=None):
        caminho = caminho or QFileDialog.getOpenFileName(self, "Importar lista", "", "CSV (*.csv *.txt)")[0]
        if not caminho:
            return 0
        with open(caminho, encoding="utf-8-sig", errors="replace") as f:
            texto = f.read()
        sep = ";" if ";" in texto.split("\n", 1)[0] else "\t" if "\t" in texto.split("\n", 1)[0] else ","
        n = 0
        for c in csv.reader(io.StringIO(texto), delimiter=sep):
            if len(c) < 3 or _num(c[1], 0) <= 0 or _num(c[2], 0) <= 0:
                continue  # cabeçalho ou linha inválida
            nome_mat = (c[3] if len(c) > 3 else "").strip()
            m = next((x for x in self.materiais if x.nome.lower() == nome_mat.lower()), None)
            if m is None and nome_mat:
                m = Material(max([x.cod for x in self.materiais] + [0]) + 1, nome_mat, 3, 600, 400)
                self.materiais.append(m)
            girar = not (len(c) > 5 and c[5].strip().lower().startswith("n"))
            self.pecas.append(Peca(max(1, int(_num(c[0], 1))), _num(c[1]), _num(c[2]),
                                   (m or self.materiais[0]).cod if (m or self.materiais) else 0,
                                   c[4].strip() if len(c) > 4 else "", girar))
            n += 1
        self._preencher_mats()
        self._preencher_pecas()
        self._mudou()
        return n

    # ---------- persistência ----------
    def _mudou(self):
        self._salvar_timer.start()

    def estado(self):
        return {"nome": self.nome, "espaco": self.espaco, "margem": self.margem,
                "materiais": [vars(m) for m in self.materiais], "pecas": [vars(p) for p in self.pecas]}

    def salvar(self):
        try:
            os.makedirs(os.path.dirname(self.arquivo), exist_ok=True)
            tmp = self.arquivo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.estado(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.arquivo)  # grava inteiro ou nada
        except OSError:
            pass  # a lista continua na memória; salva na próxima mudança

    def carregar(self):
        try:
            with open(self.arquivo, encoding="utf-8") as f:
                d = json.load(f)
            self.materiais = [Material(int(m["cod"]), str(m["nome"]), float(m["esp"]), float(m["larg"]), float(m["alt"]))
                              for m in d.get("materiais", [])] or list(MATERIAIS_PADRAO)
            self.pecas = [Peca(int(p["qtd"]), float(p["larg"]), float(p["alt"]), int(p["material"]), str(p.get("desc", "")),
                               bool(p.get("girar", True))) for p in d.get("pecas", [])]
            self.nome = str(d.get("nome", ""))
            self.espaco, self.margem = float(d.get("espaco", 3)), float(d.get("margem", 5))
        except (OSError, ValueError, KeyError, TypeError):
            pass  # sem lista salva (ou corrompida): começa com os padrões
        self._preenchendo = True
        self.ed_nome.setText(self.nome)
        self.sp_espaco.setValue(self.espaco)
        self.sp_margem.setValue(self.margem)
        self._preenchendo = False
        self._preencher_mats()
        self._preencher_pecas()
