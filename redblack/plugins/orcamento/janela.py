"""Janela do orçamento (duas abas).

• Orçamento: cliente, modelo, quantidade, tempo de laser puxado do plano aberto, tabela com o valor de cada item
  (confirmado × estimativa), preço / total / lucro em destaque, tabela por quantidade e "Gerar PDF".
• Configurações: preços dos materiais, horas, margem, descontos por quantidade e dados da empresa (nome, logo,
  contatos, validade e prazo) usados no PDF.
"""
import datetime
import json
import os

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from ... import percurso as pc
from . import CAMPOS, CONFIRMADOS_INICIAIS, DESCONTOS, INTEIROS, MODELOS_INICIAIS, dicas, orcar, reais

DINHEIRO = ("chapa_preco", "tinta_preco", "cola_preco", "insumos", "custo_oper_hora", "hora_maquina", "hora_manual",
            "fixos", "preco_manual", "preco_placa", "pintura_preco", "pintura_extra")
GRUPOS_CFG = (("MDF", ("chapa_preco", "placas_por_chapa")),
              ("Preço por placa (cobrança)", ("preco_placa", "pintura_preco", "pintura_limite", "pintura_extra")),
              ("Pintura e colagem", ("tinta_preco", "tinta_ml", "tinta_ml_peca", "cola_preco", "cola_pecas",
                                     "insumos")),
              ("Máquina", ("hora_maquina",)),
              ("Trabalho manual", ("hora_manual",)),
              ("Preço", ("margem_pct",)))
POR_MODELO = ("laser_min", "manual_min", "preco_manual", "tinta_ml_peca", "insumos", "camadas", "pintura")
PLANO = "📐 Plano aberto"  # produto = o projeto aberto agora: tempo de laser do plano, preço pela margem
CHAVE = "orcamento_v3"
EMPRESA_PADRAO = {"nome": "RedBlack", "slogan": "Corte e gravação a laser", "telefone": "", "instagram": "",
                  "email": "", "cidade": "", "logo": "", "cor": "#b3121b", "validade_dias": 7, "prazo_dias": 5,
                  "pagamento": "PIX, dinheiro ou cartão", "pix": "",
                  "observacoes": "Peças em MDF 3 mm, cortadas a laser e pintadas à mão.\n"
                                 "Pagamento: 50% no pedido e 50% na entrega."}
COR_ESCURA = "#141416"


class _Marca(QCheckBox):
    """Caixa de marcar com a mesma interface dos campos numéricos (value/setValue/valueChanged)."""

    def value(self):
        return 1 if self.isChecked() else 0

    def setValue(self, x):
        self.setChecked(bool(x))

    @property
    def valueChanged(self):
        return self.toggled


def _spin(chave):
    if chave == "pintura":
        return _Marca("Projeto pintado")
    if chave in INTEIROS:
        w = QSpinBox()
        w.setRange(1, 100000)
    else:
        w = QDoubleSpinBox()
        w.setRange(0, 1_000_000)
        w.setDecimals(2 if chave in DINHEIRO else 1)
        if chave in DINHEIRO:
            w.setPrefix("R$ ")
    return w


class JanelaOrcamento(QDialog):
    def __init__(self, janela):
        super().__init__(janela)
        self.jp = janela
        self.setWindowTitle("Orçamento — RedBlack")
        self.resize(900, 860)
        self.dados = self._ler()
        self._carregando = True
        self.campos, self.confirmado = {}, {}
        raiz = QVBoxLayout(self)
        self.abas = QTabWidget()
        raiz.addWidget(self.abas)
        self.abas.addTab(self._aba_orcamento(), "Orçamento")
        self.abas.addTab(self._aba_config(), "Configurações")
        oper = _spin("custo_oper_hora")  # não aparece: a hora de máquina (R$ 50) já cobre o laser
        oper.setValue(0.0)
        self.campos["custo_oper_hora"] = oper
        self.minutos = self.campos["laser_min"]  # nomes antigos (compatíveis)
        self.valor_hora = self.campos["hora_maquina"]
        self._carregando = False
        atual = self.dados.get("modelo_atual", PLANO)
        self.modelo.setCurrentIndex(max(0, self.modelo.findText(atual)) if atual != PLANO else 0)
        self.atualizar_plano()

    # ================================================================== abas
    def _aba_orcamento(self):
        w = QWidget()
        v = QVBoxLayout(w)
        cab = QGridLayout()
        self.cliente = QLineEdit(self.dados.get("cliente", ""))
        self.cliente.setPlaceholderText("Nome do cliente")
        self.modelo = QComboBox()
        self.modelo.addItem(PLANO)
        self.modelo.addItems([m for m in self.dados["modelos"] if m != PLANO])
        self.modelo.currentTextChanged.connect(self.trocar_modelo)
        salvar_m = QPushButton("Salvar modelo…")
        salvar_m.setToolTip("Guarda tempos, preço e tinta deste produto com um nome")
        salvar_m.clicked.connect(self.salvar_modelo)
        self.origem = QComboBox()
        self.origem.addItem("Do plano aberto (todas as abas)", "total")
        self.origem.addItem("Só da aba aberta", "aba")
        self.origem.addItem("Do modelo salvo", "modelo")
        self.origem.setCurrentIndex(max(0, self.origem.findData(self.dados.get("origem", "total"))))
        self.origem.currentIndexChanged.connect(self.atualizar_tempo)
        self.contato = QLineEdit(self.dados.get("contato", ""))
        self.contato.setPlaceholderText("WhatsApp / telefone do cliente (opcional)")
        self.descricao = QLineEdit(self.dados.get("descricao", ""))
        self.descricao.setPlaceholderText("Descrição para o cliente (ex.: Porta-retrato duplo personalizado em MDF)")
        self.com_imagem = QCheckBox("Imagem do projeto no PDF")
        self.com_imagem.setChecked(bool(self.dados.get("com_imagem", True)))
        cab.addWidget(QLabel("Cliente:"), 0, 0)
        cab.addWidget(self.cliente, 0, 1, 1, 2)
        cab.addWidget(self.contato, 0, 3)
        cab.addWidget(QLabel("Produto:"), 1, 0)
        cab.addWidget(self.modelo, 1, 1, 1, 2)
        cab.addWidget(salvar_m, 1, 3)
        cab.addWidget(QLabel("Descrição:"), 2, 0)
        cab.addWidget(self.descricao, 2, 1, 1, 2)
        cab.addWidget(self.com_imagem, 2, 3)
        cab.addWidget(QLabel("Tempo de laser:"), 3, 0)
        cab.addWidget(self.origem, 3, 1, 1, 3)
        linha = 4
        for k in ("camadas", "pintura", "laser_min", "manual_min", "quantidade", "preco_manual", "fixos"):
            rot = {"camadas": "Placas de MDF por peça:", "pintura": "Pintura:",
                   "laser_min": "Laser por peça (min):", "manual_min": "Trabalho manual por peça (min):",
                   "quantidade": "Quantidade:", "preco_manual": "Preço por peça (0 = por placa):",
                   "fixos": "Custos do pedido (frete, arte):"}[k]
            s = _spin(k)
            s.setValue(self.dados["valores"].get(k, CAMPOS[k][1]))
            s.valueChanged.connect(self.recalcular)
            self.campos[k] = s
            cab.addWidget(QLabel(rot), linha, 0)
            cab.addWidget(s, linha, 1)
            if CAMPOS[k][2] == "dado":
                ok = QCheckBox("confirmado")
                ok.setChecked(bool(self.dados["ok"].get(k, False)))
                ok.toggled.connect(self.recalcular)
                self.confirmado[k] = ok
                cab.addWidget(ok, linha, 2)
            linha += 1
        self.info_projeto = QLabel()
        self.info_projeto.setStyleSheet("color:#9aa3b2")
        cab.addWidget(self.info_projeto, linha, 0, 1, 4)
        v.addLayout(cab)
        # destaque: preço, total, lucro
        topo = QHBoxLayout()
        self.cartoes = {}
        for k, titulo in (("preco", "Preço por peça"), ("total", "Total do pedido"), ("lucro", "Lucro do pedido")):
            box = QLabel()
            box.setAlignment(Qt.AlignCenter)
            box.setStyleSheet("background:#1d2026;border:1px solid #3a4757;border-radius:6px;padding:8px;"
                              "color:#e6e8ec")
            box.setMinimumHeight(64)
            box.setToolTip(titulo)
            self.cartoes[k] = (box, titulo)
            topo.addWidget(box)
        v.addLayout(topo)
        self.tabela = QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(["Item", "Como calcula", "Por peça", "No pedido", "Dado"])
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionMode(QAbstractItemView.NoSelection)
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in (0, 2, 3, 4):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        v.addWidget(self.tabela, 3)
        self.tab_desc = QTableWidget(0, 4)
        self.tab_desc.setHorizontalHeaderLabels(["Quantidade", "Desconto", "Preço por peça", "Lucro por peça"])
        self.tab_desc.verticalHeader().hide()
        self.tab_desc.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tab_desc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tab_desc.setMaximumHeight(150)
        v.addWidget(self.tab_desc)
        self.resultado = QLabel()  # avisos (estimativas, o que falta) e dicas de margem
        self.resultado.setWordWrap(True)
        self.resultado.setStyleSheet("background:#20242b;color:#e6e8ec;padding:8px;border-radius:4px")
        rol = QScrollArea()
        rol.setWidgetResizable(True)
        rol.setWidget(self.resultado)
        rol.setMaximumHeight(170)
        v.addWidget(rol, 1)
        bts = QHBoxLayout()
        pdf = QPushButton("📄 Gerar PDF do orçamento…")
        pdf.setStyleSheet("font-weight:bold;padding:6px 14px")
        pdf.clicked.connect(lambda: self.gerar_pdf())
        cli = QPushButton("Copiar para o cliente")
        cli.clicked.connect(lambda: QApplication.clipboard().setText(self.texto_cliente()))
        interno = QPushButton("Copiar completo (interno)")
        interno.clicked.connect(lambda: QApplication.clipboard().setText(self.texto_interno()))
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.close)
        for b in (pdf, cli, interno):
            bts.addWidget(b)
        bts.addStretch(1)
        bts.addWidget(fechar)
        v.addLayout(bts)
        for w_ in (self.cliente, self.contato, self.descricao):
            w_.textChanged.connect(self.recalcular)
        self.com_imagem.toggled.connect(self.recalcular)
        return w

    def _aba_config(self):
        conteudo = QWidget()
        v = QVBoxLayout(conteudo)
        for titulo, chaves in GRUPOS_CFG:
            g = QGroupBox(titulo)
            f = QGridLayout(g)
            for i, k in enumerate(chaves):
                rot, padrao, tipo = CAMPOS[k]
                s = _spin(k)
                s.setValue(self.dados["valores"].get(k, padrao))
                s.valueChanged.connect(self.recalcular)
                self.campos[k] = s
                f.addWidget(QLabel(rot), i, 0)
                f.addWidget(s, i, 1)
                if tipo == "dado":
                    ok = QCheckBox("confirmado")
                    ok.setToolTip("Marcado = valor real (nota, medida). Desmarcado = estimativa")
                    ok.setChecked(bool(self.dados["ok"].get(k, False)))
                    ok.toggled.connect(self.recalcular)
                    self.confirmado[k] = ok
                    f.addWidget(ok, i, 2)
                else:
                    f.addWidget(QLabel("<i>decisão sua</i>"), i, 2)
            v.addWidget(g)
        g = QGroupBox("Descontos por quantidade")
        f = QGridLayout(g)
        self.descontos = []
        for i, (qmin, desc) in enumerate(self.dados.get("descontos", DESCONTOS)):
            qs, ds = QSpinBox(), QDoubleSpinBox()
            qs.setRange(1, 100000)
            qs.setValue(int(qmin))
            ds.setRange(0, 90)
            ds.setSuffix(" %")
            ds.setValue(float(desc))
            qs.valueChanged.connect(self.recalcular)
            ds.valueChanged.connect(self.recalcular)
            f.addWidget(QLabel("A partir de"), i, 0)
            f.addWidget(qs, i, 1)
            f.addWidget(QLabel("peças:"), i, 2)
            f.addWidget(ds, i, 3)
            self.descontos.append((qs, ds))
        v.addWidget(g)
        g = QGroupBox("Empresa (aparece no PDF)")
        f = QFormLayout(g)
        e = {**EMPRESA_PADRAO, **self.dados.get("empresa", {})}
        self.emp = {}
        for k, rot in (("nome", "Nome da empresa"), ("slogan", "Frase/slogan"), ("telefone", "Telefone/WhatsApp"),
                       ("instagram", "Instagram"), ("email", "E-mail"), ("cidade", "Cidade"),
                       ("pagamento", "Formas de pagamento"), ("pix", "Chave PIX")):
            le = QLineEdit(str(e.get(k, "")))
            le.textChanged.connect(self.recalcular)
            self.emp[k] = le
            f.addRow(rot + ":", le)
        logo = QHBoxLayout()
        self.emp["logo"] = QLineEdit(e.get("logo", ""))
        self.emp["logo"].setPlaceholderText("PNG ou JPG da sua logo (opcional)")
        esc = QPushButton("Escolher…")
        esc.clicked.connect(self._escolher_logo)
        logo.addWidget(self.emp["logo"], 1)
        logo.addWidget(esc)
        f.addRow("Logo:", logo)
        self.emp["cor"] = QLineEdit(e.get("cor", "#b3121b"))
        self.emp["cor"].setToolTip("Cor da marca no PDF (ex.: #b3121b vermelho RedBlack)")
        f.addRow("Cor da marca:", self.emp["cor"])
        self.validade, self.prazo = QSpinBox(), QSpinBox()
        for s, val in ((self.validade, e["validade_dias"]), (self.prazo, e["prazo_dias"])):
            s.setRange(1, 365)
            s.setSuffix(" dias")
            s.setValue(int(val))
            s.valueChanged.connect(self.recalcular)
        f.addRow("Validade do orçamento:", self.validade)
        f.addRow("Prazo de produção:", self.prazo)
        self.obs = QTextEdit()
        self.obs.setPlainText(e.get("observacoes", ""))  # texto puro: preserva as quebras de linha
        self.obs.setMaximumHeight(80)
        self.obs.textChanged.connect(self.recalcular)
        f.addRow("Observações no PDF:", self.obs)
        v.addWidget(g)
        v.addStretch(1)
        rol = QScrollArea()
        rol.setWidgetResizable(True)
        rol.setWidget(conteudo)
        return rol

    def _escolher_logo(self):
        c, _ = QFileDialog.getOpenFileName(self, "Logo da empresa", "", "Imagens (*.png *.jpg *.jpeg *.bmp)")
        if c:
            self.emp["logo"].setText(c)

    # ================================================================== dados
    def _ler(self):
        try:
            d = json.loads(self.jp.settings.value(CHAVE, "") or "{}")
        except ValueError:
            d = {}
        d.setdefault("valores", {})
        d.setdefault("ok", dict(CONFIRMADOS_INICIAIS))
        if not d.get("modelos"):
            d["modelos"] = {k: dict(m) for k, m in MODELOS_INICIAIS.items()}
        return d

    def empresa(self):
        e = {k: w.text().strip() for k, w in self.emp.items()}
        e.update(validade_dias=self.validade.value(), prazo_dias=self.prazo.value(),
                 observacoes=self.obs.toPlainText().strip())
        return e

    def faixas(self):
        return sorted({(q.value(), d.value()) for q, d in self.descontos})

    def _gravar(self):
        self.dados.update(contato=self.contato.text(), descricao=self.descricao.text(),
                          com_imagem=self.com_imagem.isChecked())
        self.dados.update(valores=self.valores(), ok={k: c.isChecked() for k, c in self.confirmado.items()},
                          modelo_atual=self._chave_modelo(), origem=self.origem.currentData(),
                          cliente=self.cliente.text(), empresa=self.empresa(), descontos=self.faixas())
        m = self.dados["modelos"].setdefault(self._chave_modelo(), {})
        for k in POR_MODELO:
            if k != "laser_min" or self.origem.currentData() == "modelo":
                m[k] = self.campos[k].value()
        self.jp.settings.setValue(CHAVE, json.dumps(self.dados))

    def salvar_modelo(self):
        sugestao = (os.path.splitext(os.path.basename(getattr(self.jp, "file_path", "") or ""))[0]
                    if self._chave_modelo() == PLANO else self.modelo.currentText())
        nome, ok = QInputDialog.getText(self, "Salvar modelo", "Nome do produto:", text=sugestao)
        if ok and nome.strip():
            self.dados["modelos"][nome.strip()] = {k: self.campos[k].value() for k in POR_MODELO}
            if self.modelo.findText(nome.strip()) < 0:
                self.modelo.addItem(nome.strip())
            self.modelo.setCurrentText(nome.strip())
            self._gravar()

    def atualizar_plano(self):
        """Chamado ao abrir a janela: o item do plano mostra o arquivo aberto agora."""
        nome = os.path.basename(getattr(self.jp, "file_path", "") or "") or "sem nome"
        self.modelo.setItemText(0, f"{PLANO}: {nome}")
        self.trocar_modelo(self.modelo.currentText())

    def _chave_modelo(self, nome=None):
        nome = nome if nome is not None else self.modelo.currentText()
        return PLANO if nome.startswith(PLANO) else nome

    def trocar_modelo(self, nome):
        if not self.campos:
            return
        chave = self._chave_modelo(nome)
        m = self.dados["modelos"].get(chave, {"preco_manual": 0.0} if chave == PLANO else {})
        self._carregando = True
        for k in POR_MODELO:
            if k in m:
                self.campos[k].setValue(m[k])
        # o plano aberto usa o tempo do plano; um modelo salvo usa o tempo DELE (nunca o de outro projeto)
        self.origem.setCurrentIndex(self.origem.findData("total" if chave == PLANO else "modelo"))
        self._carregando = False
        self.atualizar_tempo()

    def valores(self):
        return {k: w.value() for k, w in self.campos.items()}

    def estimativas(self):
        return [CAMPOS[k][0] for k, ok in self.confirmado.items() if not ok.isChecked()]

    def atualizar_tempo(self, *_):
        if self._carregando or not self.campos:
            return
        modo = self.origem.currentData()
        t = self.jp.tempos_estimados
        if t is None:
            self.jp._calcular_tempo(em_segundo_plano=False)
            t = self.jp.tempos_estimados or {"aba": 0.0, "total": 0.0}
        nome = os.path.basename(getattr(self.jp, "file_path", "") or "") or "projeto sem nome"
        self.info_projeto.setText(f"Plano aberto ({nome}): {pc.fmt_tempo(t['total'])} de laser em todas as abas, "
                                  f"{pc.fmt_tempo(t['aba'])} na aba aberta — estimativa sem aceleração.")
        self.minutos.setReadOnly(modo != "modelo")
        if modo != "modelo" and t[modo] > 0:
            self.minutos.setValue(t[modo] / 60)
            self.confirmado["laser_min"].setChecked(False)
        else:
            m = self.dados["modelos"].get(self._chave_modelo(), {})
            if "laser_min" in m:
                self.minutos.setValue(m["laser_min"])
        self.recalcular()

    # ================================================================== contas
    def desconto_para(self, q):
        d = 0.0
        for qmin, desc in self.faixas():
            if q >= qmin:
                d = desc
        return d

    def calculo(self):
        v = self.valores()
        r = orcar(dict(v))
        desc = self.desconto_para(r["q"])
        preco = r["preco"] * (1 - desc / 100)
        r.update(desconto=desc, preco_base=r["preco"], preco=round(preco, 2), lucro=round(preco - r["custo"], 2),
                 fica_para_voce=round(preco - r["desembolso"], 2), preco_pedido=round(preco * r["q"], 2),
                 lucro_pedido=round((preco - r["custo"]) * r["q"], 2),
                 margem_real_pct=round((preco - r["custo"]) / preco * 100, 1) if preco else 0.0)
        return v, r

    def recalcular(self, *_):
        if self._carregando or len(self.campos) < len(CAMPOS) or not hasattr(self, "obs"):
            return
        self._gravar()
        v, r = self.calculo()
        q = r["q"]
        ok = {k: c.isChecked() for k, c in self.confirmado.items()}

        def st(*ks):
            return "confirmado" if all(ok.get(k, True) for k in ks) else "estimativa"
        linhas = [
            ("MDF", f"{int(v['camadas'])} placas × {reais(r['placa'])} (chapa {reais(v['chapa_preco'])} ÷ "
                    f"{int(v['placas_por_chapa'])})", r["mdf"], st("chapa_preco", "placas_por_chapa", "camadas")),
            ("Tinta", f"{v['tinta_ml_peca']:g} ml × {reais(v['tinta_preco'] / v['tinta_ml'])}/ml", r["tinta"],
             st("tinta_preco", "tinta_ml", "tinta_ml_peca")),
            ("Cola", f"kit {reais(v['cola_preco'])} ÷ {int(v['cola_pecas'])} peças", r["cola"],
             st("cola_preco", "cola_pecas")),
            ("Outros insumos", "embalagem, fita, parafusos…", r["insumos"], st("insumos")),
            ("Seu laser (não é custo)", f"{v['laser_min']:.0f} min × {reais(v['hora_maquina'])}/h — você recebe", r["remun_maquina"],
             st("laser_min")),
            ("Sua mão de obra (não é custo)", f"{v['manual_min']:g} min × {reais(v['hora_manual'])}/h — você recebe",
             r["manual"], st("manual_min")),
            ("= Custo (sai do bolso)", "MDF + tinta + cola + insumos", r["custo"], ""),
            ("Placas cobradas", f"{r['placas']} placas × {reais(v['preco_placa'])}", r["cobr_placas"], ""),
            ("Pintura cobrada", self.como_pintura(v, r), r["cobr_pintura"], ""),
            ("Preço de venda", ("preço informado" if v["preco_manual"] else "placas + pintura" if r["por_placa"]
                                else f"custo + {v['margem_pct']:g} %")
             + (f" − {r['desconto']:g} % (quantidade)" if r["desconto"] else ""), r["preco"], ""),
            ("= Lucro estimado", f"preço − custo ({r['margem_real_pct']:.0f} % do preço): paga o seu tempo", r["lucro"], ""),
        ]
        self.tabela.setRowCount(len(linhas))
        for i, (item, como, valor, estado) in enumerate(linhas):
            cels = [item, como, reais(valor), reais(valor * q), estado]
            for c, txt in enumerate(cels):
                it = QTableWidgetItem(txt)
                if c in (2, 3):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if item.startswith("=") or item == "Preço de venda":
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                if c == 4 and estado == "estimativa":
                    it.setForeground(QColor("#e0a800"))
                elif c == 4 and estado == "confirmado":
                    it.setForeground(QColor("#2e9e4f"))
                if item == "= Lucro estimado" and c in (2, 3):
                    it.setForeground(QColor("#2e9e4f" if valor >= 0 else "#d03030"))
                self.tabela.setItem(i, c, it)
        for k, val in (("preco", r["preco"]), ("total", r["preco_pedido"]), ("lucro", r["lucro_pedido"])):
            box, titulo = self.cartoes[k]
            box.setText(f"<div style='font-size:11px;color:#9aa3b2'>{titulo}</div>"
                        f"<div style='font-size:20px;font-weight:bold'>{reais(val)}</div>")
        faixas = self.faixas()
        self.tab_desc.setRowCount(len(faixas))
        for i, (qmin, desc) in enumerate(faixas):
            preco = r["preco_base"] * (1 - desc / 100)
            for c, txt in enumerate((f"{qmin}+ peças", f"{desc:g} %", reais(preco), reais(preco - r["custo"]))):
                it = QTableWidgetItem(txt)
                it.setTextAlignment(Qt.AlignCenter)
                if c == 3 and preco - r["custo"] < 0:
                    it.setForeground(QColor("#d03030"))
                self.tab_desc.setItem(i, c, it)
        avisos = []
        if r["lucro"] < 0:
            avisos.append(f"<span style='color:#ff6b6b;font-weight:bold'>⚠ PREÇO ABAIXO DO CUSTO: falta "
                          f"{reais(-r['lucro'])} por peça para cobrir o material (MDF {reais(r['mdf'])}, tinta "
                          f"{reais(r['tinta'])}, cola {reais(r['cola'])}): confira o preço por placa e a quantidade "
                          "de placas.</span>")
        avisos += [f"<b>{self.modelo.currentText()}</b>: 1 chapa ({int(v['placas_por_chapa'])} placas) rende "
                  f"<b>{r['pecas_por_chapa']} peças completas</b> de {int(v['camadas'])} camadas"
                  + (f", sobram {r['sobra_placas']} placa(s)" if r["sobra_placas"] else "")
                  + f"; este pedido usa {r['chapas_pedido']} chapa(s)."]
        est = self.estimativas()
        if est:
            avisos.append("<span style='color:#ffd27a'>⚠ ESTIMATIVAS (não confirmadas): " + "; ".join(est)
                          + ". O lucro só é real quando estes valores forem medidos.</span>")
        falta = ["tempo de trabalho manual"] if v["manual_min"] == 0 else []
        if falta:
            avisos.append("<span style='color:#ff9a9a'>Falta informar: " + "; ".join(falta) + ".</span>")
        avisos.append("<span style='color:#9aa3b2'>Fora da conta: impostos, taxas de venda, perdas e retrabalho.</span>")
        avisos += ["<b>Como aumentar a margem</b>"] + [f"• {x}" for x in dicas(r, v)]
        self.resultado.setText("<br>".join(avisos) + "<br><br>PREÇO DE VENDA e LUCRO ESTIMADO na tabela acima.")

    @staticmethod
    def como_pintura(v, r):
        if not r["pintado"]:
            return "sem pintura"
        extra = max(0, r["placas"] - int(v["pintura_limite"]))
        return (f"até {int(v['pintura_limite'])} placas {reais(v['pintura_preco'])}"
                + (f" + {extra} × {reais(v['pintura_extra'])}" if extra else ""))

    @staticmethod
    def composicao(v, r):
        """Texto do cliente: quanto das placas e da pintura compõe o preço (só quando o preço é por placa)."""
        if not r["por_placa"]:
            return ""
        s = f"{r['placas']} placa(s) de MDF × {reais(v['preco_placa'])} = {reais(r['cobr_placas'])}"
        if r["pintado"]:
            s += f" + pintura {reais(r['cobr_pintura'])}"
        return s + " por unidade"

    # ================================================================== saídas
    def texto_cliente(self):
        v, r = self.calculo()
        e = self.empresa()
        linhas = [f"{e['nome'] or 'Orçamento'} — {self.modelo.currentText()}"]
        if self.cliente.text().strip():
            linhas.append(f"Cliente: {self.cliente.text().strip()}")
        linhas.append(f"{r['q']} unidade(s): {reais(r['preco'])} cada — total {reais(r['preco_pedido'])}")
        if self.composicao(v, r):
            linhas.append(self.composicao(v, r))
        for qmin, desc in self.faixas():
            linhas.append(f"{'1 unidade' if qmin == 1 else f'A partir de {qmin} unidades'}: "
                          f"{reais(r['preco_base'] * (1 - desc / 100))} cada")
        linhas.append(f"Prazo de produção: {e['prazo_dias']} dias · Orçamento válido por {e['validade_dias']} dias")
        return "\n".join(linhas)

    def texto_interno(self):
        v, r = self.calculo()
        est = self.estimativas()
        return (f"{self.modelo.currentText()}: desembolso {reais(r['desembolso'])} (MDF {reais(r['mdf'])}, tinta "
                f"{reais(r['tinta'])}, cola {reais(r['cola'])}, laser oper. {reais(r['oper'])}) | mão de obra "
                f"{reais(r['manual'])} | máquina {reais(r['remun_maquina'])} | custo {reais(r['custo'])} | preço "
                f"{reais(r['preco'])} | lucro {reais(r['lucro'])} ({r['margem_real_pct']:.0f} %) | "
                f"{r['pecas_por_chapa']} peças por chapa"
                + (f" | Estimativas: {'; '.join(est)}" if est else " | Valores confirmados"))

    def gerar_pdf(self, caminho=None):
        """PDF A4 para o cliente, com a marca da empresa (sem os custos internos)."""
        if caminho is None:
            cli = "".join(ch for ch in self.cliente.text() if ch.isalnum() or ch in " -_").strip().replace(" ", "_")
            nome = f"orcamento_{cli or 'cliente'}_{datetime.date.today():%Y%m%d}.pdf"
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar orçamento em PDF", nome, "PDF (*.pdf)")
            if not caminho:
                return None
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"
        produto = self.modelo.currentText()
        if produto.startswith(PLANO):  # "📐 Plano aberto: arquivo.rbl" -> nome do arquivo, sem extensão
            produto = os.path.splitext(produto.split(":", 1)[-1].strip())[0].replace("_", " ")
        imagem = None
        if self.com_imagem.isChecked():
            try:
                from ...ui import render_mdf as rm
                imagem = rm.renderizar(self.jp, "MDF cru", px_por_mm=6.0, max_px=2400)
            except Exception:  # sem peças/sem render: segue sem imagem
                imagem = None
        desenhar_pdf(caminho, self.empresa(), {"nome": self.cliente.text().strip(), "contato": self.contato.text().strip()},
                     produto, self.descricao.text().strip(), imagem, *self.calculo(), self.faixas(),
                     self.composicao(*self.calculo()))
        if not getattr(self, "silencioso", False):
            QMessageBox.information(self, "Orçamento", f"PDF salvo em:\n{caminho}")
        return caminho


def desenhar_pdf(caminho, emp, cliente, produto, descricao, imagem, v, r, faixas, composicao=""):
    """Orçamento A4 para o cliente (sem custos internos): cabeçalho com logo/nome, número, data e validade; cliente;
    imagem do projeto; tabela do pedido; total em destaque; valores por quantidade; condições e pagamento; rodapé.
    Desenhado em pixels a 300 dpi (texto com espaçamento correto; o pintor NÃO é escalado)."""
    dpi = 300
    pdf = QPdfWriter(caminho)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setResolution(dpi)
    pdf.setTitle(f"Orçamento {emp.get('nome', '')} — {cliente.get('nome', '')}")
    pdf.setCreator(emp.get("nome", "") or "RedBlack Laser")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    def mm(x):
        return x * dpi / 25.4

    def R(x, y, w, h):
        return QRectF(mm(x), mm(y), mm(w), mm(h))

    cor = QColor(emp.get("cor") or "#b3121b")
    if not cor.isValid():
        cor = QColor("#b3121b")
    escura, cinza, clara = QColor(COR_ESCURA), QColor("#6b6f76"), QColor("#f5f5f7")

    def fonte(pt, peso=QFont.Normal):
        f = QFont("Segoe UI")
        f.setPixelSize(max(1, round(pt * dpi / 72)))
        f.setWeight(peso)
        f.setHintingPreference(QFont.PreferNoHinting)  # sem "dica" de tela: espaçamento certo no PDF
        f.setKerning(True)
        return f

    def texto(x, y, w, h, s, pt=10, peso=QFont.Normal, c=escura, al=Qt.AlignLeft | Qt.AlignVCenter):
        p.setFont(fonte(pt, peso))
        p.setPen(c)
        p.drawText(R(x, y, w, h), al, s)

    def caixa(x, y, w, h, fundo, borda=None, raio=2.5):
        p.setPen(QPen(borda, mm(0.3)) if borda else Qt.NoPen)
        p.setBrush(fundo)
        p.drawRoundedRect(R(x, y, w, h), mm(raio), mm(raio))
        p.setBrush(Qt.NoBrush)

    hoje = datetime.date.today()
    validade = hoje + datetime.timedelta(days=int(emp.get("validade_dias", 7)))
    numero = f"{hoje:%Y%m%d}-{datetime.datetime.now():%H%M}"

    # ---- cabeçalho
    p.fillRect(R(0, 0, 210, 40), escura)
    p.fillRect(R(0, 40, 210, 1.6), cor)
    x_nome = 15
    logo = QImage(emp.get("logo") or "")
    if not logo.isNull():
        alt = 26
        larg = min(55, alt * logo.width() / max(logo.height(), 1))
        p.drawImage(R(15, 7, larg, alt), logo)
        x_nome = 15 + larg + 6
    texto(x_nome, 8, 110, 14, emp.get("nome") or "", 26, QFont.Bold, QColor("white"))
    texto(x_nome, 22, 110, 8, emp.get("slogan") or "", 10.5, QFont.Normal, QColor("#c9ccd2"))
    texto(120, 7, 75, 11, "ORÇAMENTO", 20, QFont.Bold, cor, Qt.AlignRight | Qt.AlignVCenter)
    for i, (rot, val) in enumerate((("Nº", numero), ("Emitido em", f"{hoje:%d/%m/%Y}"),
                                    ("Válido até", f"{validade:%d/%m/%Y}"))):
        texto(120, 19 + i * 5.6, 75, 5.6, f"{rot}  {val}", 9.5, QFont.Normal, QColor("#c9ccd2"),
              Qt.AlignRight | Qt.AlignVCenter)

    # ---- cliente e produto
    y = 50
    caixa(15, y, 88, 24, clara)
    texto(20, y + 3, 80, 5, "PARA", 8, QFont.Bold, cor)
    texto(20, y + 8, 80, 8, cliente.get("nome") or "Cliente", 14, QFont.DemiBold)
    texto(20, y + 16, 80, 6, cliente.get("contato") or "", 9.5, QFont.Normal, cinza)
    caixa(107, y, 88, 24, clara)
    texto(112, y + 3, 80, 5, "PRODUTO", 8, QFont.Bold, cor)
    p.setFont(fonte(12, QFont.DemiBold))
    p.setPen(escura)
    p.drawText(R(112, y + 8, 80, 14), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, produto)
    y += 30

    # ---- imagem do projeto
    if imagem is not None and not imagem.isNull():
        alt_max, larg_max = 62.0, 180.0  # deixa espaço para condições acima do rodapé
        esc = min(larg_max / imagem.width(), alt_max / imagem.height())
        w_img, h_img = imagem.width() * esc, imagem.height() * esc
        caixa(15, y, 180, h_img + 8, QColor("#eceef1"))
        p.drawImage(R(105 - w_img / 2, y + 4, w_img, h_img), imagem)
        texto(15, y + h_img + 8.5, 180, 5, "Imagem ilustrativa do projeto (cores e acabamento podem variar).", 8,
              QFont.Normal, cinza, Qt.AlignCenter)
        y += h_img + 16

    # ---- tabela do pedido
    cols = ((15, 105, "Descrição", Qt.AlignLeft), (120, 18, "Qtd.", Qt.AlignHCenter),
            (138, 28, "Valor unit.", Qt.AlignRight), (166, 29, "Total", Qt.AlignRight))
    p.fillRect(R(15, y, 180, 8), cor)
    for x, w, t, al in cols:
        texto(x + 2.5, y, w - 5, 8, t, 9.5, QFont.Bold, QColor("white"), al | Qt.AlignVCenter)
    y += 8
    desc = descricao or "Peça personalizada em MDF, cortada a laser."
    p.fillRect(R(15, y, 180, 17), clara)
    p.setFont(fonte(11, QFont.DemiBold))
    p.setPen(escura)
    p.drawText(R(17.5, y + 1.5, 100, 6), Qt.AlignLeft | Qt.AlignVCenter, produto)
    p.setFont(fonte(9))
    p.setPen(cinza)
    p.drawText(R(17.5, y + 7.5, 100, 9), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, desc)
    for (x, w, _t, al), s in zip(cols[1:], (str(r["q"]), reais(r["preco"]), reais(r["preco_pedido"]))):
        texto(x + 2.5, y, w - 5, 17, s, 11, QFont.Normal, escura, al | Qt.AlignVCenter)
    y += 17
    if composicao:
        texto(17.5, y, 175, 7, composicao + ".", 9, QFont.Normal, cinza)
        y += 7
    if r.get("desconto"):
        texto(17.5, y, 150, 7, f"Inclui desconto de {r['desconto']:g} % por quantidade "
                               f"(de {reais(r['preco_base'])} por {reais(r['preco'])} cada).", 9, QFont.Normal, cinza)
        y += 7
    fixos = v.get("fixos") or 0
    if fixos:
        texto(17.5, y, 140, 7, "Arte / frete / custos do pedido", 10)
        texto(166, y, 26.5, 7, reais(fixos), 10, QFont.Normal, escura, Qt.AlignRight | Qt.AlignVCenter)
        y += 7
    total = r["preco_pedido"] + fixos
    y += 3
    caixa(120, y, 75, 15, cor, raio=2)
    texto(124, y, 30, 15, "TOTAL", 12, QFont.Bold, QColor("white"))
    texto(140, y, 51, 15, reais(total), 19, QFont.Bold, QColor("white"), Qt.AlignRight | Qt.AlignVCenter)
    y += 22

    # ---- valores por quantidade
    if len(faixas) > 1 and y < 230:
        texto(15, y, 180, 6, "VALORES POR QUANTIDADE (por unidade)", 8.5, QFont.Bold, cor)
        y += 7
        larg = 180 / len(faixas)
        for i, (qmin, d) in enumerate(faixas):
            x = 15 + i * larg
            caixa(x + 1, y, larg - 2, 16, clara, QColor("#dfe1e5"), 2)
            texto(x + 1, y + 1.5, larg - 2, 5.5, "1 unidade" if qmin == 1 else f"a partir de {qmin}", 9,
                  QFont.DemiBold, cinza, Qt.AlignCenter)
            texto(x + 1, y + 7, larg - 2, 8, reais(r["preco_base"] * (1 - d / 100)), 13, QFont.Bold, cor,
                  Qt.AlignCenter)
        y += 22

    # ---- condições e pagamento
    texto(15, y, 88, 6, "CONDIÇÕES", 8.5, QFont.Bold, cor)
    texto(107, y, 88, 6, "PAGAMENTO", 8.5, QFont.Bold, cor)
    y += 7
    cond = [f"Prazo de produção: {emp.get('prazo_dias', 5)} dias após a confirmação.",
            f"Orçamento válido até {validade:%d/%m/%Y}."] + \
        [ln.strip() for ln in (emp.get("observacoes") or "").splitlines() if ln.strip()]
    yy = y
    p.setFont(fonte(9.5))
    p.setPen(escura)
    for ln in cond:
        rr = p.boundingRect(R(19, yy, 84, 30), Qt.TextWordWrap, ln)
        p.drawText(R(15, yy, 4, 5), Qt.AlignLeft | Qt.AlignTop, "•")
        p.drawText(R(19, yy, 84, 30), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, ln)
        yy += rr.height() * 25.4 / dpi + 1.2
    pag = [emp.get("pagamento") or ""]
    if emp.get("pix"):
        pag.append(f"Chave PIX: {emp['pix']}")
    yp = y
    for ln in (s for s in pag if s):
        p.drawText(R(107, yp, 4, 5), Qt.AlignLeft | Qt.AlignTop, "•")
        p.drawText(R(111, yp, 84, 30), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, ln)
        yp += 6.5
    texto(107, max(yp, yy) + 6, 88, 6, "Aprovado por: ________________________________", 9.5, QFont.Normal, cinza)

    # ---- rodapé
    p.fillRect(R(0, 281, 210, 16), escura)
    p.fillRect(R(0, 280, 210, 1.0), cor)
    contatos = "   ·   ".join(s for s in (emp.get("telefone"), emp.get("instagram"), emp.get("email"),
                                          emp.get("cidade")) if s)
    texto(15, 282.5, 180, 6.5, emp.get("nome") or "", 11, QFont.Bold, QColor("white"), Qt.AlignCenter)
    texto(15, 289, 180, 6, contatos, 9, QFont.Normal, QColor("#c9ccd2"), Qt.AlignCenter)
    p.end()
    return caminho
