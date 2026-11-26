"""Janela principal (Etapas 1–13: interface, edição, projeto, importação, camadas, prévia, G-code, simulador e conexão somente leitura).

Regra da etapa: nada aqui conecta, envia comandos ou emite laser. Funções futuras
ficam desabilitadas e indicam a etapa do ROADMAP em que serão implementadas.
"""
import json
import math
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence, QPainterPath, QTransform, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QProgressBar, QInputDialog, QLineEdit, QListWidgetItem, QMenu, QPlainTextEdit,
    QGridLayout, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QHeaderView, QSpinBox, QTableWidget, QTableWidgetItem, QToolBar, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import CREDITOS, DIREITOS, __version__
from .. import tempo_trabalho as tt
from .. import aparar as apr
from .. import booleanas as bo
from .. import disposicao as dsp
from .. import camadas as cm
from .. import encaixe as enc
from .. import formas as fm
from .. import frisos as fr
from .. import gabarito as gbm
from .. import geometria as g
from .. import nos
from .. import codigo_barras as cbar
from .. import importar_pdf as pdfimp
from .. import plugins
from .. import qrcode_rb
from .. import ranhuras as rnh
from .. import rotativo as rtv
from .. import tracar as trc
from .. import texto_caminho as txc
from .. import objetos as ob
from .. import importar_imagem as imgimp
from .. import raster
from .. import importar_svg as svg
from .. import exportar_svg as esvg
from .. import dxf
from .. import materiais as mt
from .. import matriz as mz
from .. import conexao as cx
from .. import gcode as gc
from .. import transporte as tp
from .. import percurso as pc
from .. import projeto as pj
from .. import texto as tx
from .. import variaveis as vr
from ..simulador import SimuladorGrbl
from .canvas import ZOOM_STEP, Canvas, desenhar_mesa
from .dialogo_deslocar import DeslocarDialog
from .dialogo_forma import FormaDialog
from .dialogo_frisos import FrisosDialog
from .dialogo_gabarito import GabaritoDialog
from .dialogo_matriz import MatrizDialog
from .dialogo_resultado_matriz import ResultadoMatrizDialog
from .dialogo_atalhos import AtalhosDialog
from .dialogo_atalhos import aplicar_salvos as aplicar_atalhos
from .dialogo_atalhos import chave as chave_atalho
from .dialogo_preferencias import PreferenciasDialog
from .dialogo_preferencias import ler as ler_pref
from .dialogo_texto import TextDialog
from .dialogo_valores import ValoresDialog
from .painel_previa import PainelPrevia
from .painel_variaveis import PainelVariaveis
from . import sons
from .icons import icon


COL_SAIDA, COL_EXIBIR = 2, 3  # colunas da tabela de camadas
FEITA = "✓ "  # no início do nome da aba = já cortada/gravada (vai no .rbl sem mudar o formato)
LAYOUT_VERSAO = 5  # aumentar quando barras/painéis mudarem de forma que layouts salvos fiquem ruins


def replace_vars(d, i, por_mesa=1):
    """Dados do i-ésimo arquivo do lote: começa na linha i·por_mesa da planilha (se houver) e no
    contador + i·por_mesa·incremento (por_mesa = peças do gabarito em cada arquivo)."""
    base = replace(d, linha_atual=i * por_mesa) if d.linhas else d
    return replace(base, contador=d.contador + i * por_mesa * d.incremento)


def later(stage: int) -> str:
    return f"Ainda não implementado — previsto na Etapa {stage} do ROADMAP."


def text_name(params) -> str:
    first = params.texto.strip().split("\n")[0]
    return f"Texto “{first[:24]}{'…' if len(first) > 24 else ''}”"


def _cruza(p, q) -> bool:
    """O contorno de p cruza o de q? (p dentro de q sem tocar a borda = não cruza)."""
    from PySide6.QtGui import QPainterPathStroker
    st = QPainterPathStroker()
    st.setWidth(1e-3)
    return st.createStroke(p).intersects(st.createStroke(q))


def _area_caminho(p) -> float:
    """Área (mm²) do contorno externo: escolhe a peça maior na solda fêmea."""
    return max((abs(sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(q, list(q)[1:] + list(q)[:1]))) / 2
                for q in p.toSubpathPolygons()), default=0.0)


def svg_report(res) -> str:
    lines = []
    if res.ignorados:
        lines.append("Elementos sem suporte (não importados):")
        lines += [f"  • {tag}: {n}" for tag, n in sorted(res.ignorados.items())]
    if res.avisos:
        lines.append("Avisos:")
        lines += [f"  • {a}" for a in res.avisos]
    return "\n".join(lines)


class StateCommand(QUndoCommand):
    """Histórico por estado: guarda o documento antes e depois de cada edição.

    shortcut: copia o documento inteiro por passo; trocar por comandos por objeto se projetos
    com milhares de objetos ficarem lentos.
    """

    def __init__(self, win, before, after, text):
        super().__init__(text)
        self.win, self.before, self.after = win, before, after
        self._applied = True  # push() chama redo(); a edição já foi feita

    def redo(self):
        if self._applied:
            self._applied = False
            return
        self.win.set_doc_state(self.after)

    def undo(self):
        self.win.set_doc_state(self.before)


REREF_MIN = 10  # referência ($H) no meio do trabalho a cada tantos minutos (opção na tela da máquina)
MSG_REFERENCIAR_ROTATIVO = 'Com o ROTATIVO ligado não existe referência: o motor do Y agora gira a peça e nunca acha o fim de curso.\n\nPosicione o laser na peça com as setas e use Iniciar a partir da POSIÇÃO ATUAL. Para referenciar, desligue o rotativo e volte o cabo do Y.'


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("RedBlack", "RedBlackLaser")
        self.setAcceptDrops(True)  # soltar fora da mesa (painéis) também importa
        self.resize(1440, 860)
        self.undo_stack = QUndoStack(self)
        self.file_path = None
        self._before = None
        self.undo_stack.cleanChanged.connect(self._update_title)
        self.setDockNestingEnabled(True)
        self._carregar_maquina()  # antes da tela: a mesa desenhada usa o tamanho salvo

        self.canvas = Canvas()
        self.paginas, self.pagina_atual = [None], 0  # páginas guardadas (None = a aberta, que está na mesa)
        self.nomes_paginas = pj.nomes_padrao(1)
        from PySide6.QtWidgets import QStackedWidget
        from .tela_corte import TelaCorte
        self.pilha_central = QStackedWidget()  # 0 = edição (como sempre), 1 = tela de corte (F9)
        self.pilha_central.addWidget(self._area_com_paginas())
        self.tela_corte = TelaCorte(self.canvas.scene)
        self.pilha_central.addWidget(self.tela_corte)
        self.setCentralWidget(self.pilha_central)
        tc = self.tela_corte
        tc.btn_pausar.clicked.connect(lambda: self._pausar_retomar())
        tc.btn_parar.clicked.connect(lambda: self._parar_maquina())
        tc.btn_ar.clicked.connect(lambda on: self.btn_ar.setChecked(on))
        tc.btn_voltar.clicked.connect(lambda: self.act_tela_corte.setChecked(False))
        self._sel_actions, self._clipboard, self._tree_map, self._syncing = [], [], {}, False
        self.layers = []  # Camada, na ordem de saída
        self.vars = vr.DadosVariaveis()  # planilha, linha atual e contador do texto variável
        self.gabarito = None  # gbm.Gabarito na mesa (só guia na tela) ou None
        self.notas = ""  # notas do projeto (texto livre, salvo no projeto)
        self._ultimo_desloc = (2.0, "fora", "redondo", False)
        try:
            self.rotativo = rtv.de_dict(json.loads(self.settings.value("rotativo", "") or "{}"))
        except (TypeError, ValueError):
            self.rotativo = rtv.Rotativo()
        self._tfs_inicio = None  # matrizes no início de um arraste (as âncoras acompanham ao vivo)
        self._ultima_matriz = self._ler_ultima_matriz()  # a peça gravada pode ser avaliada noutro dia
        self.conexao, self._log_visto = None, 0
        self._conexao_timer = QTimer(self)
        self._conexao_timer.setInterval(50)
        self._conexao_timer.timeout.connect(self._tick_conexao)

        self._build_status()
        self._build_toolbars()
        self._build_docks()
        self._build_menus()  # por último: o menu Janela lista docks e barras
        aplicar_atalhos(self.settings, self.todas_acoes())  # teclas personalizadas pelo usuário
        v = self.canvas.view
        v.selectionGeometryChanged.connect(self._on_selection)
        v.editBegin.connect(self._inicio_interativo)
        v.editEnd.connect(self._end_interactive_edit)
        v.arrastando.connect(lambda: self._tfs_inicio and self._seguir_ancoras(self._tfs_inicio))
        v.medidaDigitada.connect(self._medida_digitada)
        self._rebuild_objects()
        self._ensure_layers()
        self._on_selection()
        self._update_title()

        self._atualizar_rotativo_status()
        from .dialogo_calibracao_xy import aplicar as _cal_xy
        self.calibracao_xy_estado(_cal_xy(self.settings))  # calibração X/Y salva (desligada por padrão)
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self.auto_salvar)
        self.aplicar_preferencias()
        layers, machine = self._docks_padrao
        self.resizeDocks([layers, machine], [600, 400], Qt.Vertical)  # Camadas com mais altura que Máquina
        QTimer.singleShot(0, self._garantir_largura_docks)  # depois de aparecer: largura pelo conteúdo
        self._default_state = self.saveState()
        self.restoreGeometry(self.settings.value("geometry", b""))
        # Layout salvo por uma versão com outras barras/painéis é descartado uma vez (posição da janela fica).
        if self.settings.value("layout_versao", 0, type=int) >= LAYOUT_VERSAO:
            self.restoreState(self.settings.value("windowState", b""))
        else:
            self.settings.setValue("windowState", self._default_state)
            self.settings.setValue("layout_versao", LAYOUT_VERSAO)
        self._garantir_quebra_texto()

    # ---------- helpers ----------
    def _act(self, text, icon_name=None, stage=None, shortcut=None, slot=None):
        a = QAction(text, self)
        if icon_name:
            a.setIcon(icon(icon_name))
        if isinstance(shortcut, QKeySequence.StandardKey):
            a.setShortcuts(shortcut)  # todas as combinações da plataforma (ex.: Ctrl++ e Ctrl+=)
        elif shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if stage:
            a.setEnabled(False)
            a.setToolTip(f"{text.replace('&', '').rstrip('…')} — {later(stage)}")
            a.setStatusTip(later(stage))
            a.setProperty("stage", stage)
        if slot:
            a.triggered.connect(slot)
        return a

    def _later_widget(self, w, stage):
        w.setEnabled(False)
        w.setToolTip(later(stage))
        return w

    def _sel_act(self, text, fn, min_items):
        """Ação de seleção: habilitada só com min_items+ objetos selecionados."""
        a = self._act(text, slot=lambda: self._edit(text, fn))
        a.setProperty("min_items", min_items)
        a.setToolTip(f"{text} (requer {min_items}+ objeto{'s' if min_items > 1 else ''} selecionado"
                     f"{'s' if min_items > 1 else ''})")
        self._sel_actions.append(a)
        return a

    # ---------- edição de objetos ----------
    def _sel(self):
        return self.canvas.view.selected()

    def _anchor_selector(self):
        """Seletor de 9 pontos: referência de X/Y, âncora de redimensionamento e centro de rotação."""
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(4, 0, 4, 0)
        grid.setSpacing(1)
        self.anchor_group = QButtonGroup(w)
        names = ("superior esquerdo", "superior centro", "superior direito", "meio esquerdo", "centro",
                 "meio direito", "inferior esquerdo", "inferior centro", "inferior direito")
        for i, n in enumerate(names):
            b = QToolButton()
            b.setCheckable(True)
            b.setFixedSize(12, 12)
            b.setAccessibleName(f"Ponto de referência: {n}")
            b.setToolTip(f"Ponto de referência: {n}")
            b.setStyleSheet("QToolButton{background:#3a3f48;border-radius:6px;padding:0}"
                            "QToolButton:checked{background:#e0313b}")
            self.anchor_group.addButton(b, i)
            grid.addWidget(b, i // 3, i % 3)
        self.anchor_group.button(4).setChecked(True)
        self.anchor_group.idToggled.connect(lambda *_: self._sync_fields())
        return w

    @property
    def anchor(self) -> int:
        return self.anchor_group.checkedId()

    def _campo_digitado(self, key):
        """Valor mudou (digitando ou nas setinhas): aplica depois de uma pausa curta (não a cada dígito)."""
        if self._syncing:
            return
        if not hasattr(self, "_campo_timer"):
            self._campo_timer = QTimer(self, singleShot=True, interval=500)
            self._campo_timer.timeout.connect(lambda: self._on_field(self._campo_chave))
        self._campo_chave = key
        self._campo_timer.start()

    def _campo_confirmado(self, key):
        if hasattr(self, "_campo_timer"):
            self._campo_timer.stop()
        self._on_field(key)

    def _on_field(self, key):
        sel = self._sel()
        if not sel or self._syncing:
            return
        if any(s.bloqueado for s in sel):
            self.statusBar().showMessage("Há objeto bloqueado na seleção (Organizar → Desbloquear formas).")
            self._sync_fields()
            return
        f = self.fields
        r = ob.bounds(sel)

        def change():
            if key in ("x", "y"):
                x, y = g.from_display(f["x"].value(), f["y"].value())
                ob.set_anchor_pos(sel, x, y, self.anchor)
            elif key in ("w", "h"):
                w, h = f["w"].value(), f["h"].value()
                if self.lock.isChecked() and r.width() > ob.EPS and r.height() > ob.EPS:
                    if key == "w":
                        h = w * r.height() / r.width()
                    else:
                        w = h * r.width() / r.height()
                ob.set_size(sel, w, h, self.anchor)
            elif key in ("wp", "hp"):
                fx, fy = f["wp"].value() / 100, f["hp"].value() / 100
                if self.lock.isChecked():
                    fx = fy = fx if key == "wp" else fy
                if abs(fx - 1) > 1e-12 or abs(fy - 1) > 1e-12:
                    ob.scale(sel, fx, fy, ob.anchor_point(r, self.anchor))
            elif key == "rot":  # valor absoluto: o objeto passa a ficar com este ângulo
                delta = f["rot"].value() - ob.angulo(sel[0])
                if abs(delta) > 1e-9:
                    ob.rotate(sel, delta, ob.anchor_point(r, self.anchor))

        self._edit({"x": "Mover", "y": "Mover", "w": "Redimensionar", "h": "Redimensionar", "wp": "Escalar",
                    "hp": "Escalar"}.get(key, "Girar"), change)
        self._sync_fields()

    # ---------- histórico ----------
    def doc_state(self):
        """(objetos, índices selecionados, camadas na ordem de saída, texto variável, gabarito, âncoras)."""
        shapes = self.canvas.view.shapes()
        idx = {id(s): i for i, s in enumerate(shapes)}
        ancoras = tuple((i, idx[id(s.ancora)]) for i, s in enumerate(shapes)
                        if s.ancora is not None and id(s.ancora) in idx)  # âncora apagada = solto
        return (tuple(s.snapshot() for s in shapes), tuple(i for i, s in enumerate(shapes) if s.isSelected()),
                tuple(self.layers), self.vars, self.gabarito, ancoras,
                tuple(i for i, s in enumerate(shapes) if s.bloqueado), self.notas,
                tuple(self.paginas), self.pagina_atual, tuple(self.nomes_paginas),
                tuple((i, *s.grupo_aberto) for i, s in enumerate(shapes) if s.grupo_aberto))

    def set_doc_state(self, state):
        (snaps, selected, layers, self.vars, self.gabarito, ancoras, bloqueados, self.notas, paginas,
         self.pagina_atual, nomes, abertos) = state
        self.paginas, self.nomes_paginas = list(paginas), list(nomes)
        self._mostrar_notas()
        self.canvas.view.gabarito_overlay.set_gabarito(self.gabarito)
        self.layers = list(layers)
        self._colocar_objetos(snaps, selected, ancoras, bloqueados)
        novos = self.canvas.view.shapes()
        for i, gid, nome in abertos:
            novos[i].grupo_aberto = (gid, nome)
        self._rebuild_objects()
        self._refresh_layers()
        self._refresh_vars_panel()
        self._atualizar_abas()

    def _colocar_objetos(self, snaps, selected, ancoras, bloqueados):
        """Troca os objetos da mesa pelos de uma página (com âncoras e bloqueios)."""
        scene = self.canvas.scene
        novos = []
        with self._selecao_em_lote():
            for s in self.canvas.view.shapes():
                scene.removeItem(s)
            for i, snap in enumerate(snaps):
                s = ob.from_snapshot(snap)
                scene.addItem(s)
                s.setSelected(i in selected)
                novos.append(s)
        for f, a in ancoras:
            novos[f].ancora = novos[a]
        for i in bloqueados:
            novos[i].bloqueado = True

    # ---------- páginas ----------
    def _area_com_paginas(self):
        """Abas das páginas embaixo da mesa (como as planilhas do Excel), com + (nova), duplicar e excluir.
        Duplo clique numa aba renomeia."""
        from PySide6.QtWidgets import QTabBar
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        barra = QHBoxLayout()
        barra.setContentsMargins(4, 2, 4, 2)
        self.abas = QTabBar()
        self.abas.setDrawBase(False)
        self.abas.setAccessibleName("Páginas do projeto")
        self.abas.currentChanged.connect(lambda i: None if self._sync_abas else self.ir_para_pagina(i))
        self.abas.tabBarDoubleClicked.connect(self._renomear_pagina_dialogo)
        self.abas.setToolTip("Clique para trocar de página; duplo clique para renomear; botão direito: marcar como "
                             "feita (✓). A aba é marcada sozinha quando o trabalho dela termina na máquina.")
        self.abas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.abas.customContextMenuRequested.connect(self._menu_aba)
        self._sync_abas = False
        barra.addWidget(self.abas)
        for txt, dica, fn in (("+", "Adicionar página (vazia)", lambda: self.adicionar_pagina(False)),
                              ("⧉", "Duplicar página", lambda: self.adicionar_pagina(True)),
                              ("−", "Excluir página", self.excluir_pagina)):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(dica)
            b.setAccessibleName(dica)
            b.clicked.connect(fn)
            barra.addWidget(b)
        barra.addStretch(1)
        self.progresso_abas = QLabel()
        self.progresso_abas.setAccessibleName("Páginas feitas e que faltam")
        barra.addWidget(self.progresso_abas)
        topo = QWidget()
        topo.setLayout(barra)
        topo.setFixedHeight(32)  # altura fixa: trocar/estilizar abas nunca desloca a mesa
        v.addWidget(self.canvas, 1)
        v.addWidget(topo)
        self._atualizar_abas()
        return w

    def _atualizar_abas(self):
        if not hasattr(self, "abas"):
            return
        self._sync_abas = True
        while self.abas.count() > len(self.paginas):
            self.abas.removeTab(self.abas.count() - 1)
        while self.abas.count() < len(self.paginas):
            self.abas.addTab("")
        for i, nome in enumerate(self.nomes_paginas):
            if self.abas.tabText(i) != nome:
                self.abas.setTabText(i, nome)
            self.abas.setTabTextColor(i, QColor("#2e7d32") if self.pagina_feita(i) else QColor())  # inválida = padrão
        if self.abas.currentIndex() != self.pagina_atual:
            self.abas.setCurrentIndex(self.pagina_atual)
        self._sync_abas = False
        feitas = [self.pagina_feita(i) for i in range(len(self.nomes_paginas))]
        falta = [n for n, f in zip(self.nomes_paginas, feitas) if not f]
        if len(feitas) < 2 and not any(feitas):
            txt = ""  # projeto de uma página só, nada marcado: não ocupa a barra
        elif not falta:
            txt = f"✔ Tudo feito ({len(feitas)} de {len(feitas)})"
        else:
            txt = f"Feitas {sum(feitas)} de {len(feitas)}  ·  Falta: " + ", ".join(falta[:4]) + (
                f" e mais {len(falta) - 4}" if len(falta) > 4 else "")
        self.progresso_abas.setText(txt)
        self.progresso_abas.setToolTip("\n".join(("✓ " if f else "○ ") + n.removeprefix(FEITA)
                                                 for n, f in zip(self.nomes_paginas, feitas)))

    # ---------- o que já foi feito e o que falta (marca "✓ " no nome da aba: vai junto ao salvar/duplicar/desfazer) ----
    def pagina_feita(self, i) -> bool:
        return self.nomes_paginas[i].startswith(FEITA)

    def marcar_pagina(self, i, feita=True) -> bool:
        return self._marcar_paginas([i], feita)

    def desmarcar_todas(self) -> bool:
        return self._marcar_paginas(range(len(self.paginas)), False)

    def _marcar_paginas(self, indices, feita) -> bool:
        mudar = [i for i in indices if 0 <= i < len(self.paginas) and self.pagina_feita(i) != feita]
        if not mudar:
            return False

        def fazer():
            for i in mudar:
                n = self.nomes_paginas[i]
                self.nomes_paginas[i] = (FEITA + n)[:pj.MAX_NOME_PAGINA] if feita else n.removeprefix(FEITA)
        self._edit("Marcar página como feita" if feita else "Desmarcar página feita", fazer)
        self._atualizar_abas()
        return True

    def _menu_aba(self, pos):
        i = self.abas.tabAt(pos)
        if i < 0:
            return
        m = QMenu(self)
        a = m.addAction("Feita (já cortada/gravada)")
        a.setCheckable(True)
        a.setChecked(self.pagina_feita(i))
        a.triggered.connect(lambda on: self.marcar_pagina(i, on))
        m.addAction("Renomear…", lambda: self._renomear_pagina_dialogo(i))
        if any(self.pagina_feita(k) for k in range(len(self.paginas))):
            m.addSeparator()
            m.addAction("Desmarcar todas (vai cortar de novo)", self.desmarcar_todas)
        m.exec(self.abas.mapToGlobal(pos))

    def _marcar_aba_do_trabalho(self, c):
        """Trabalho que terminou normalmente (não parado/erro): a aba de onde ele saiu fica feita."""
        pend = getattr(self, "_aba_do_trabalho", None)
        if pend is None or c.trabalho != cx.TRABALHO_FIM or pend[2] is not getattr(self, "_job_visto", None):
            return
        self._aba_do_trabalho = None
        i, nome = pend[0], pend[1]
        if not (0 <= i < len(self.nomes_paginas) and self.nomes_paginas[i] == nome):
            i = self.nomes_paginas.index(nome) if nome in self.nomes_paginas else -1  # abas mudaram durante o corte
        if self.marcar_pagina(i, True):
            self.statusBar().showMessage(f"✓ {nome} marcada como feita.")

    # ---------- tempo estimado de serviço (aba aberta e projeto inteiro) ----------
    tempos_estimados = None  # {"aba": s, "total": s, "por_aba": [s ou None, ...]} depois do cálculo

    def _agendar_tempo(self, *_):
        if not hasattr(self, "_tempo_timer"):
            self._tempo_timer = QTimer(self, singleShot=True, interval=1500)
            self._tempo_timer.timeout.connect(self._calcular_tempo)
        self._tempo_timer.start()

    def _calcular_tempo(self, em_segundo_plano=True):
        """Gera o percurso de cada aba numa thread (imagem grande leva ~1 s) e mostra o resultado acima das
        camadas. Resultado antigo (de antes de outra edição) é descartado."""
        import threading
        self._tempo_geracao = getattr(self, "_tempo_geracao", 0) + 1
        ger = self._tempo_geracao
        abas = [(self._pagina_da_mesa() if i == self.pagina_atual else pg)[0] for i, pg in enumerate(self.paginas)]
        abas = [self.snaps_saida(list(sn), self.vars) for sn in abas]
        camadas, otim, atual = list(self.layers), self.otimizacao(), self.pagina_atual

        def conta():
            por_aba = []
            for sn in abas:
                try:
                    por_aba.append(pc.gerar(sn, camadas, **otim).tempo_s if sn else 0.0)
                except Exception:  # aba com algo que não gera percurso: fica sem tempo
                    por_aba.append(None)
            self._tempo_pronto.emit(ger, atual, por_aba)

        if not hasattr(self, "_tempo_ponte"):
            from PySide6.QtCore import QObject, Signal

            class _Ponte(QObject):
                pronto = Signal(int, int, list)
            self._tempo_ponte = _Ponte(self)
            self._tempo_ponte.pronto.connect(self._mostrar_tempo)
        self._tempo_pronto = self._tempo_ponte.pronto
        self.tempo_label.setText(self.tempo_label.text().split(" (")[0] + " (calculando…)")
        if em_segundo_plano:
            threading.Thread(target=conta, daemon=True).start()
        else:
            conta()

    def _mostrar_tempo(self, ger, atual, por_aba):
        if ger != getattr(self, "_tempo_geracao", 0):
            return  # houve outra mudança: vem um cálculo mais novo
        validos = [t for t in por_aba if t is not None]
        aba = por_aba[atual] if atual < len(por_aba) else None
        self.tempos_estimados = {"aba": aba or 0.0, "total": sum(validos), "por_aba": por_aba}
        txt = f"⏱ Esta aba: {pc.fmt_tempo(aba) if aba is not None else '—'}"
        if len(por_aba) > 1:
            txt += f"   ·   Projeto ({len(por_aba)} abas): {pc.fmt_tempo(sum(validos))}"
        self.tempo_label.setText(txt)

    def renderizar_pecas(self):
        from .render_mdf import DialogoRenderMdf
        d = DialogoRenderMdf(self)
        d.show()
        return d

    def _pagina_da_mesa(self):
        st = self.doc_state()
        return (st[0], st[5], st[6])

    def _abrir_pagina(self, i):
        """Guarda a página da mesa e põe a página i na mesa (sem histórico)."""
        self.paginas[self.pagina_atual] = self._pagina_da_mesa()
        snaps, ancoras, bloqueados = self.paginas[i]
        self.paginas[i] = None
        self.pagina_atual = i
        self._colocar_objetos(snaps, (), ancoras, bloqueados)

    def ir_para_pagina(self, i) -> bool:
        if not 0 <= i < len(self.paginas) or i == self.pagina_atual:
            self._atualizar_abas()
            return False
        self.tools["select"].setChecked(True)
        self.fechar_grupo()
        self._abrir_pagina(i)
        self._aplicar_variaveis()
        self._refresh_layers()
        self._atualizar_abas()
        self._refresh_preview()
        self.statusBar().showMessage(f"{self.nomes_paginas[i]} ({i + 1} de {len(self.paginas)}).")
        return True

    def adicionar_pagina(self, duplicar=False) -> bool:
        self.fechar_grupo()  # a página guardada não lembra grupo aberto: fecha antes de trocar
        if len(self.paginas) >= pj.MAX_PAGINAS:
            self.statusBar().showMessage(f"Limite de {pj.MAX_PAGINAS} páginas.")
            return False

        def fazer():
            nova = self._pagina_da_mesa() if duplicar else ((), (), ())
            nome = self.nomes_paginas[self.pagina_atual].removeprefix(FEITA) + " (cópia)" if duplicar \
                else self._nome_livre()  # a cópia ainda não foi cortada
            self.nomes_paginas.insert(self.pagina_atual + 1, nome[:pj.MAX_NOME_PAGINA])
            self.paginas.insert(self.pagina_atual + 1, nova)
            self._abrir_pagina(self.pagina_atual + 1)
        self._edit("Duplicar página" if duplicar else "Adicionar página", fazer)
        self._atualizar_abas()
        self._refresh_preview()
        return True

    def _nome_livre(self):
        k = len(self.paginas) + 1
        while f"Página {k}" in self.nomes_paginas:
            k += 1
        return f"Página {k}"

    def renomear_pagina(self, i, nome) -> bool:
        nome = (nome or "").strip()[:pj.MAX_NOME_PAGINA]
        if not 0 <= i < len(self.paginas) or not nome or nome == self.nomes_paginas[i]:
            return False

        def fazer():
            self.nomes_paginas[i] = nome
        self._edit("Renomear página", fazer)
        self._atualizar_abas()
        return True

    def _renomear_pagina_dialogo(self, i):
        if i < 0:
            return
        nome, ok = QInputDialog.getText(self, "Renomear página", "Nome da página:", text=self.nomes_paginas[i])
        if ok:
            self.renomear_pagina(i, nome)

    def excluir_pagina(self) -> bool:
        if len(self.paginas) < 2:
            self.statusBar().showMessage("O projeto precisa de pelo menos uma página.")
            return False
        self.fechar_grupo()
        apagar = self.pagina_atual

        def fazer():
            vizinha = apagar + 1 if apagar + 1 < len(self.paginas) else apagar - 1
            self._abrir_pagina(vizinha)
            del self.paginas[apagar]
            del self.nomes_paginas[apagar]
            self.pagina_atual = self.paginas.index(None)
        self._edit("Excluir página", fazer)
        self._atualizar_abas()
        self._refresh_preview()
        return True

    def _edit(self, text, fn):
        before = self.doc_state()
        tfs = self._matrizes()
        with self._selecao_em_lote():  # comandos que mexem em muitos objetos recalculam a janela uma vez só
            fn()
        self._seguir_ancoras(tfs)
        self._aplicar_variaveis()
        self._ensure_layers()
        self._commit(text, before)
        self._refresh_vars_panel()  # avisos de marcadores sem valor acompanham qualquer edição

    # ---------- âncoras ----------
    def _matrizes(self):
        return {id(s): (s, s.sceneTransform()) for s in self.canvas.view.shapes()}

    def _inicio_interativo(self):
        self._before = self.doc_state()
        self._tfs_inicio = self._matrizes()

    def _seguir_ancoras(self, tfs):
        """Objetos presos (não selecionados) repetem o que a âncora sofreu desde `tfs`: mover, girar, escalar.

        Calculado sempre a partir do início (filho_inicial · âncora_inicial⁻¹ · âncora_agora), então pode ser
        chamado a cada movimento do mouse sem acumular erro. Correntes (âncora presa a outra) seguem em cadeia.
        """
        shapes = self.canvas.view.shapes()
        vivos = {id(s) for s in shapes}
        filhos = [s for s in shapes if s.ancora is not None and id(s.ancora) in vivos and not s.isSelected()
                  and id(s) in tfs and id(s.ancora) in tfs]
        for _ in range(len(filhos)):  # passadas suficientes para qualquer corrente
            mudou = False
            for c in filhos:
                inv, ok = tfs[id(c.ancora)][1].inverted()
                novo = tfs[id(c)][1] * inv * c.ancora.sceneTransform() if ok else c.sceneTransform()
                if novo != c.sceneTransform():
                    c.setPos(0, 0)
                    c.setTransform(novo)
                    mudou = True
            if not mudou:
                break
        self._desenhar_ancoras()

    def _desenhar_ancoras(self):
        """Linhas tracejadas âncora → presos, para a seleção atual."""
        view = self.canvas.view
        sel = set(map(id, self._sel()))
        pares = [(s.ancora, s) for s in view.shapes() if s.ancora is not None and s.ancora.scene() is not None
                 and (id(s) in sel or id(s.ancora) in sel)]
        view.set_ancoras([(ob.bounds([a]).center(), ob.bounds([f]).center()) for a, f in pares])

    def bloquear(self, on: bool):
        sel = self._sel()
        if not sel:
            return

        def do():
            for s in sel:
                s.bloqueado = on
            self._rebuild_objects()

        self._edit("Bloquear formas" if on else "Desbloquear formas", do)
        self.canvas.view.refresh_selection()
        self.statusBar().showMessage(f"{len(sel)} objeto(s) " + ("bloqueado(s): não se movem nem mudam de tamanho."
                                                                 if on else "desbloqueado(s)."))

    def prender_ancora(self) -> bool:
        """O 1º objeto selecionado vira a âncora; os demais ficam presos a ele."""
        ordem = [s for s in self.canvas.view.ordem_sel if s.isSelected()]
        if len(ordem) < 2:
            self.statusBar().showMessage("Selecione primeiro a âncora (pai) e depois, com Shift, os que vão junto.")
            return False
        pai, filhos = ordem[0], ordem[1:]
        x = pai
        while x is not None:  # a âncora não pode estar presa (direta ou indiretamente) a um dos filhos
            if x in filhos:
                self.show_error("Âncora em ciclo", f"“{pai.name}” já está preso a “{x.name}”.")
                return False
            x = x.ancora

        def do():
            for f in filhos:
                f.ancora = pai
            self._rebuild_objects()

        self._edit("Prender à âncora", do)
        self.statusBar().showMessage(f"{len(filhos)} objeto(s) preso(s) a “{pai.name}”: ao arrastar a âncora "
                                     "eles vão junto; cada um ainda se move sozinho.")
        return True

    def soltar_ancora(self):
        sel = self._sel()
        alvo = [s for s in sel if s.ancora is not None] or \
            [s for s in self.canvas.view.shapes() if s.ancora in sel]  # âncora selecionada: solta os filhos

        def do():
            for s in alvo:
                s.ancora = None
            self._rebuild_objects()

        if alvo:
            self._edit("Soltar da âncora", do)
        self.statusBar().showMessage(f"{len(alvo)} objeto(s) solto(s).")

    def _trocar_item(self, velho, novo):
        """Substitui um objeto na cena mantendo seleção e âncoras (dele e dos presos a ele)."""
        scene = self.canvas.scene
        novo.ancora = velho.ancora
        for s in self.canvas.view.shapes():
            if s.ancora is velho:
                s.ancora = novo
        sel = velho.isSelected()
        scene.removeItem(velho)
        scene.addItem(novo)
        novo.setSelected(sel)

    def _medida_digitada(self, qual, valor):
        """Valor digitado no rótulo da seleção (ou ao digitar um número com objeto selecionado)."""
        if qual.startswith("d_"):
            return self.definir_distancia(qual[2:], valor)
        self.fields[qual].setValue(valor)
        self._on_field(qual)
        b = ob.bounds(self._sel())
        self.statusBar().showMessage(f"Tamanho: {b.width():.2f} × {b.height():.2f} mm".replace(".", ",")
                                     + (" (proporção mantida)" if self.lock.isChecked() else ""))

    def definir_distancia(self, lado, valor) -> bool:
        """Move a seleção para ficar a `valor` mm do que a linha daquele lado toca (furo a 3 mm da borda)."""
        view = self.canvas.view
        sel = self._sel()
        if not sel or lado not in (view.dist or {}):
            return False
        if any(s.bloqueado for s in sel) or not view.permitir["mover"]:
            self.statusBar().showMessage("Distância: objeto bloqueado ou Mover desligado.")
            return False
        dx, dy = enc.deslocamento_para(lado, view.dist[lado][0], float(valor))
        self._edit("Distância até a borda", lambda: ob.move_by(sel, dx, dy))
        view.refresh_selection()
        nomes = {"esq": "esquerda", "dir": "direita", "cima": "cima", "baixo": "baixo"}
        self.statusBar().showMessage(f"Distância à {nomes[lado]}: {valor:.2f} mm".replace(".", ","))
        return True

    def _commit(self, text, before):
        after = self.doc_state()
        if after[0] != before[0] or after[2:] != before[2:]:  # só seleção não entra
            self.undo_stack.push(StateCommand(self, before, after, text))

    # ---------- texto variável ----------
    def _aplicar_variaveis(self, agora=None):
        """Redesenha textos variáveis para a linha/contador atuais (só os que mudaram)."""
        agora = agora or datetime.now()
        ctx = lambda k: vr.contexto(self.vars.peca(k), agora)  # cada peça do gabarito tem sua linha
        for s in self.canvas.view.shapes():
            snap = s.snapshot()
            novo = ob.renderizar_variaveis(snap, ctx)
            if novo is not snap:
                self._trocar_item(s, ob.from_snapshot(novo))
        self._rebuild_objects()

    def set_vars(self, novo, texto):
        """Altera planilha/linha/contador (desfazível) e redesenha os textos variáveis."""
        if novo == self.vars:
            return

        def do():
            self.vars = novo

        self._edit(texto, do)
        self._refresh_vars_panel()

    def carregar_csv(self, path) -> bool:
        try:
            with open(path, "rb") as f:
                dados = vr.ler_csv(f.read(), os.path.basename(path))
        except (OSError, vr.CsvInvalido) as e:
            self.show_error("Não foi possível carregar a planilha", str(e))
            return False
        self.set_vars(replace(dados, contador=self.vars.contador, incremento=self.vars.incremento),
                      f"Carregar planilha {os.path.basename(path)}")
        self._remember_dir(path)
        return True

    def _carregar_csv_dialogo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carregar planilha", self._last_dir(),
                                              "Planilha CSV (*.csv *.txt)")
        if path:
            self.carregar_csv(path)

    def _refresh_vars_panel(self):
        if hasattr(self, "vars_panel"):
            modelos = [p.texto for p in self._textos_variaveis()]
            faltando = sorted({f for m in modelos for f in vr.renderizar(m, vr.contexto(self.vars))[1]})
            por_mesa = self.pecas_por_mesa()
            sem = sum(self.vars.sem_dados(k) for k in range(por_mesa))
            self.vars_panel.set_dados(self.vars, faltando, len(modelos), por_mesa, sem)

    def _textos_variaveis(self):
        out = []

        def visita(snap):
            extra = snap[5]
            if isinstance(extra, ob.GroupData):
                for c in extra.children:
                    visita(c)
            elif isinstance(extra, tx.TextoParams) and extra.variavel:
                out.append(extra)

        for s in self.canvas.view.shapes():
            visita(s.snapshot())
        return out

    def pecas_por_mesa(self) -> int:
        """Peças do gabarito preenchido (maior `peca` dos textos variáveis + 1); 1 sem gabarito."""
        ks = set().union(*(ob.pecas(s.snapshot()) for s in self.canvas.view.shapes()))
        return max(ks) + 1 if ks else 1

    @staticmethod
    def snaps_saida(snaps, d):
        """Objetos que vão para o laser: peças do gabarito sem linha na planilha ficam de fora."""
        return [s for s in snaps if not any(d.sem_dados(k) for k in ob.pecas(s))]

    def avancar_mesa(self):
        """Próxima peça (sem gabarito) ou próxima mesa: avança tantas linhas quantas peças houver."""
        n = self.pecas_por_mesa()
        if n == 1:
            self.set_vars(self.vars.avancar(), "Avançar texto variável")
        elif self.vars.sem_dados(n):
            self.statusBar().showMessage("A planilha acabou: não há linhas para a próxima mesa.")
        else:
            self.set_vars(self.vars.peca(n), f"Próxima mesa ({n} peças)")

    def exportar_lote(self, pasta, quantidade=None, agora=None) -> list:
        """Um G-code por linha da planilha (ou `quantidade` números de série). Não altera o documento.

        Com gabarito preenchido, cada arquivo é uma mesa inteira (N peças, N linhas da planilha).
        Não sobrescreve arquivos existentes: se algum já existir, nada é gravado.
        """
        d = self.vars
        por_mesa = self.pecas_por_mesa()
        n = -(-len(d.linhas) // por_mesa) if d.linhas else (quantidade or 1)
        base = os.path.splitext(os.path.basename(self.file_path))[0] if self.file_path else "lote"
        snaps = [s.snapshot() for s in self.canvas.view.shapes()]
        agora = agora or datetime.now()
        trabalhos = []
        for i in range(n):
            di = replace_vars(d, i, por_mesa)
            rotulo = (di.linhas[di.linha_atual][0] if di.linhas else str(di.contador))
            nome = f"{base}_{i + 1:03d}_{vr.nome_arquivo_seguro(rotulo)}.gcode"
            caminho = os.path.join(pasta, nome)
            rend = [ob.renderizar_variaveis(s, lambda k, di=di: vr.contexto(di.peca(k), agora))
                    for s in self.snaps_saida(snaps, di)]
            trabalhos.append((caminho, rend))
        existentes = [c for c, _ in trabalhos if os.path.exists(c)]
        if existentes:
            raise gc.GcodeInvalido(f"Já existe {os.path.basename(existentes[0])} na pasta "
                                   f"({len(existentes)} arquivo(s)). Escolha outra pasta para não sobrescrever.")
        if any(not rend for _, rend in trabalhos):
            raise gc.GcodeInvalido("Algum arquivo do lote ficaria vazio.")
        textos = [gc.gerar(pc.gerar(rend, self.layers, **self.otimizacao()), self.layers, rotativo=self.rotativo)
                  for _, rend in trabalhos]  # valida tudo antes
        for (caminho, _), texto in zip(trabalhos, textos):
            gc.salvar(caminho, texto)
        return [c for c, _ in trabalhos]

    def _exportar_lote_dialogo(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para os arquivos do lote", self._last_dir())
        if not pasta:
            return
        try:
            feitos = self.exportar_lote(pasta, self.vars_panel.quantidade.value())
        except (gc.GcodeInvalido, pc.LimiteExcedido, OSError) as e:
            self.show_error("Lote não gerado", str(e))
            return
        self.show_info("Lote gerado", f"{len(feitos)} arquivo(s) G-code em {pasta}.\n\nPerfil da máquina NÃO "
                       "confirmado; nada foi enviado à máquina.")

    # ---------- camadas ----------
    def layer(self, layer_id):
        return next((c for c in self.layers if c.id == layer_id), None)

    def used_layers(self):
        snaps = [s.snapshot() for s in self.canvas.view.shapes()]
        used = set().union(*(ob.leaf_layers(s) for s in snaps)) if snaps else set()
        images = set().union(*(ob.image_layers(s) for s in snaps)) if snaps else set()
        return used, images

    def _ensure_layers(self):
        """Cria camadas que passaram a ser usadas e fixa o modo Imagem onde há imagens."""
        used, images = self.used_layers()
        for lid in sorted(used - {c.id for c in self.layers}):
            if lid in cm.IDS:
                self.layers.append(cm.nova(lid, imagem=lid in images))
        for i, c in enumerate(self.layers):
            if c.id in images and c.modo != "imagem":
                self.layers[i] = cm.alterar(c, modo="imagem")  # como na referência: camada com imagem = Imagem
            elif c.id in used and c.id not in images and c.modo == "imagem":
                self.layers[i] = cm.alterar(c, modo="linha")
        self._refresh_layers()

    def _refresh_layers(self):
        """Tabela de camadas usadas (na ordem) + visibilidade dos objetos na tela."""
        used, images = self.used_layers()
        visible = {c.id: c.visivel for c in self.layers}
        ob.definir_preenchidas(c.id for c in self.layers if c.modo == "preenchimento")
        self.canvas.view.viewport().update()
        for s in self.canvas.view.shapes():
            show = any(visible.get(lid, True) for lid in ob.leaf_layers(s.snapshot()))
            s.setVisible(show)
            if not show:
                s.setSelected(False)  # objeto oculto não fica selecionado
        rows = [c for c in self.layers if c.id in used]
        t = self.layer_table
        current = self._current_layer_id()
        self._syncing = True
        t.setRowCount(len(rows))
        for r, c in enumerate(rows):
            sw = QTableWidgetItem(c.id[1:])
            sw.setBackground(QColor(c.cor))
            sw.setForeground(QColor("#000" if QColor(c.cor).lightness() > 120 else "#fff"))
            sw.setData(Qt.UserRole, c.id)
            checks = []
            for flag_val in (c.saida, c.visivel):
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                it.setCheckState(Qt.Checked if flag_val else Qt.Unchecked)
                checks.append(it)
            texts = [QTableWidgetItem(v) for v in (
                c.nome, c.modo.capitalize(),
                f"{c.velocidade_mm_min:g} / {c.potencia_max:g} %".replace(".", ","), str(c.passadas))]
            for it in [sw] + texts:
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            # Colunas: Cor, Camada, Saída, Exibir, Modo, Vel/Pot, Passadas (chaves visíveis sem rolar)
            for col, it in enumerate([sw, texts[0], *checks, *texts[1:]]):
                t.setItem(r, col, it)
        t.resizeColumnsToContents()
        ids = [c.id for c in rows]
        if current in ids:
            t.selectRow(ids.index(current))
        elif ids:
            t.selectRow(0)
        self._syncing = False
        self._fill_layer_form()

    def _current_layer_id(self):
        rows = self.layer_table.selectionModel().selectedRows() if self.layer_table.selectionModel() else []
        if not rows:
            return None
        item = self.layer_table.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    def _fill_layer_form(self):
        c = self.layer(self._current_layer_id())
        f = self.layer_form
        self._syncing = True
        for w in f.values():
            w.setEnabled(c is not None)
        if c:
            f["nome"].setText(c.nome)
            f["modo"].clear()
            f["modo"].addItems([m.capitalize() for m in (cm.MODOS if c.modo == "imagem" else cm.MODOS_VETOR)])
            f["modo"].setCurrentText(c.modo.capitalize())
            f["modo"].setEnabled(c.modo != "imagem")  # camada com imagem fica em Imagem
            f["velocidade_mm_min"].setValue(c.velocidade_mm_min)
            f["potencia_max"].setValue(c.potencia_max)
            f["potencia_min"].setValue(c.potencia_min)
            f["passadas"].setValue(c.passadas)
            f["intervalo_mm"].setValue(c.intervalo_mm)
            f["intervalo_mm"].setEnabled(c.modo != "linha")  # só preenchimento/imagem usam intervalo
            f["kerf_mm"].setValue(c.kerf_mm)
            for k in ("angulo_graus", "angulo_inc_graus", "sobrevarredura_mm"):
                f[k].setValue(getattr(c, k))
                f[k].setEnabled(c.modo != "linha")
            f["varrer_y"].setChecked(abs(c.angulo_graus % 180 - 90) < 0.5)
            f["varrer_y"].setEnabled(c.modo != "linha")
            for k in ("bidirecional", "hachura_cruzada", "preencher_juntas"):
                f[k].setChecked(getattr(c, k))
                f[k].setEnabled(c.modo != "linha")
            f["modo_imagem"].setCurrentIndex(max(0, f["modo_imagem"].findData(c.modo_imagem)))
            for k in ("modo_imagem", "limiar_pct", "negativo", "brilho_pct", "contraste_pct", "gama"):
                f[k].setEnabled(c.modo == "imagem")
            for k in ("limiar_pct", "brilho_pct", "contraste_pct", "gama"):
                f[k].setValue(getattr(c, k))
            f["negativo"].setChecked(c.negativo)
            for k in ("guias_qtd", "guias_mm", "sobrecorte_mm"):
                f[k].setValue(getattr(c, k))
                f[k].setEnabled(c.modo == "linha")
            f["kerf_mm"].setEnabled(c.modo == "linha")  # compensação só faz sentido em contorno
            f["air"].setChecked(c.air)
            for k in ("meio_tom_cpi", "meio_tom_angulo"):
                f[k].setValue(getattr(c, k))
                f[k].setEnabled(c.modo == "imagem")
            for k in ("entrada_mm", "saida_corte_mm"):
                f[k].setValue(getattr(c, k))
                f[k].setEnabled(c.modo == "linha")
        self._encher_subcamadas(c)
        self._syncing = False

    # ---------- subcamadas ----------
    def _encher_subcamadas(self, c):
        if not hasattr(self, "sub_lista"):
            return
        self.sub_lista.clear()
        for k, sub in enumerate(c.subcamadas if c else (), 1):
            v = cm.sub_aplicada(c, sub)
            self.sub_lista.addItem(f"{k}. {v.modo.capitalize()} — {v.velocidade_mm_min:g} mm/min, "
                                   f"{v.potencia_max:g} %, {v.passadas}×".replace(".", ","))
        pode = c is not None and c.modo != "imagem"
        self.sub_botoes["add"].setEnabled(pode and len(c.subcamadas) < cm.MAX_SUB)
        for k in ("edit", "del"):
            self.sub_botoes[k].setEnabled(pode and self.sub_lista.count() > 0)

    def _pedir_sub(self, base):
        """Diálogo com os ajustes da subcamada (partindo de `base`, uma camada). dict ou None."""
        return self.ask_valores("Subcamada", [
            ("modo", "Modo", base.modo, [("linha", "Linha (contorno)"), ("preenchimento", "Preenchimento")]),
            ("velocidade_mm_min", "Velocidade", base.velocidade_mm_min, (*cm.LIMITES["velocidade_mm_min"], 0, " mm/min")),
            ("potencia_max", "Potência máx.", base.potencia_max, (*cm.LIMITES["potencia_max"], 1, " %")),
            ("potencia_min", "Potência mín.", base.potencia_min, (*cm.LIMITES["potencia_min"], 1, " %")),
            ("passadas", "Passadas", base.passadas, (*cm.LIMITES["passadas"], 0, "")),
            ("intervalo_mm", "Intervalo (preenchimento)", base.intervalo_mm, (*cm.LIMITES["intervalo_mm"], 3, " mm")),
            ("angulo_graus", "Ângulo de varredura", base.angulo_graus, (*cm.LIMITES["angulo_graus"], 1, " °"))],
            "Passe extra sobre os mesmos objetos, feito logo depois da camada (ex.: preencher e depois cortar o "
            "contorno). O resto dos ajustes vem da camada.")

    def subcamada(self, acao, valores=None) -> bool:
        """acao: "add", "edit" ou "del" (na subcamada escolhida na lista). Desfazível."""
        c = self.layer(self._current_layer_id())
        if c is None or c.modo == "imagem":
            return False
        subs = list(c.subcamadas)
        i = self.sub_lista.currentRow() if self.sub_lista.currentRow() >= 0 else len(subs) - 1
        if acao == "del":
            if not subs:
                return False
            del subs[i]
        else:
            if acao == "edit" and not subs:
                return False
            base = cm.sub_aplicada(c, subs[i]) if acao == "edit" else c
            v = valores or self._pedir_sub(base)
            if not v:
                return False
            v["passadas"] = int(v["passadas"])
            novo = tuple((k, v[k]) for k in cm.SUB_CAMPOS if k in v and v[k] != getattr(c, k))
            if acao == "edit":
                subs[i] = novo
            else:
                subs.append(novo)
        return self.set_layer_fields(c.id, {"subcamadas": tuple(subs)}, f"Camada {c.id}: subcamadas")

    def set_layer_field(self, layer_id, field, value) -> bool:
        """Altera um parâmetro de uma camada (desfazível). Valores inválidos são recusados."""
        return self.set_layer_fields(layer_id, {field: value}, f"Camada {layer_id}: {field}")

    def set_layer_fields(self, layer_id, campos, texto) -> bool:
        c = self.layer(layer_id)
        if c is None:
            return False
        try:
            new = cm.alterar(c, **campos)
        except ValueError as e:
            self.statusBar().showMessage(f"Valor recusado na camada {layer_id}: {e}")
            self._fill_layer_form()
            return False
        if new == c:
            return True

        def do():
            self.layers[self.layers.index(c)] = new

        self._edit(texto, do)
        self._fill_layer_form()
        return True

    def _on_layer_form(self, field):
        if self._syncing:
            return
        lid, w = self._current_layer_id(), self.layer_form[field]
        if field == "nome":
            value = w.text().strip() or lid
        elif field == "modo":
            value = w.currentText().lower()
        elif field in ("air", "bidirecional", "hachura_cruzada", "preencher_juntas", "negativo"):
            value = w.isChecked()
        elif field == "modo_imagem":
            value = w.currentData()
        elif field == "varrer_y":
            field, value = "angulo_graus", 90.0 if w.isChecked() else 0.0
        else:
            value = w.value()
        self.set_layer_field(lid, field, value)

    def _on_layer_item_changed(self, item):
        if self._syncing or item.column() not in (COL_SAIDA, COL_EXIBIR):
            return
        lid = self.layer_table.item(item.row(), 0).data(Qt.UserRole)
        field = "saida" if item.column() == COL_SAIDA else "visivel"
        self.set_layer_field(lid, field, item.checkState() == Qt.Checked)

    # ---------- máquina (mesa, origem, perfil do G-code) ----------
    MAQUINA_PADRAO = {"largura": 365.0, "altura": 370.0, "origem": "inf_esq", "comando": "M4", "s_max": 1000,
                      "f_max": 20000.0, "corte_m3": True}

    def _carregar_maquina(self):
        try:
            v = {**self.MAQUINA_PADRAO, **json.loads(self.settings.value("maquina", "") or "{}")}
            if not self.settings.value("laser_m4_padrao", False, type=bool):  # 0.52.2: gravação em M4 vira o padrão
                self.settings.setValue("laser_m4_padrao", True)            # (uma vez; depois vale o que escolher)
                if v["comando"] != "M4" and self.settings.value("maquina", ""):
                    v["comando"] = "M4"
                    self.settings.setValue("maquina", json.dumps(v))
            g.definir_mesa(v["largura"], v["altura"], v["origem"])
            gc.definir_perfil(v["comando"], int(v["s_max"]), v["f_max"], bool(v.get("corte_m3", True)))
        except (TypeError, ValueError, KeyError):  # valor salvo corrompido: volta ao padrão
            g.definir_mesa(400.0, 400.0, "inf_esq")
            gc.definir_perfil()

    def definir_maquina(self, v) -> bool:
        """Aplica e lembra mesa/origem/perfil. Valores inválidos não mudam nada."""
        try:
            g.definir_mesa(v["largura"], v["altura"], v["origem"])
            gc.definir_perfil(v["comando"], int(v["s_max"]), v["f_max"], bool(v.get("corte_m3", True)))
        except ValueError as e:
            self._carregar_maquina()  # desfaz uma aplicação parcial
            self.show_error("Configurações da máquina", str(e))
            return False
        self.settings.setValue("maquina", json.dumps({**v, "s_max": int(v["s_max"])}))
        desenhar_mesa(self.canvas.scene)
        self.canvas.view.viewport().update()
        self.canvas.top.update()
        self.canvas.left.update()
        if hasattr(self, "mesa_label"):
            self.mesa_label.setText(self._texto_mesa())
        self._refresh_preview()
        return True

    def _texto_mesa(self):
        return f"Mesa {g.BED_W:g} × {g.BED_H:g} mm, origem {g.CANTOS[g.ORIGEM].lower()}"

    def _maquina_dialogo(self):
        p = gc.PERFIL
        v = self.ask_valores("Configurações da máquina", [
            ("largura", "Largura da área de trabalho", g.BED_W, (g.MESA_MIN, g.MESA_MAX, 1, " mm")),
            ("altura", "Altura da área de trabalho", g.BED_H, (g.MESA_MIN, g.MESA_MAX, 1, " mm")),
            ("origem", "Canto da origem (onde fica o 0,0 da máquina)", g.ORIGEM, list(g.CANTOS.items())),
            ("comando", "Modo do laser", p.comando, [("M3", "M3 — potência constante"),
                                                    ("M4", "M4 — potência dinâmica (acompanha a velocidade)")]),
            ("corte_m3", f"Cortes (camadas em Linha com {gc.CORTE_POT_MIN:g} % ou mais) em M3 — potência constante, "
                         "vara a chapa por igual; gravação fica em M4",
             p.corte_m3, None),
            ("s_max", "Potência máxima S (GRBL $30)", p.s_max, (1, 100000, 0, "")),
            ("f_max", "Velocidade máxima aceita", p.f_max_mm_min, (1, gc.F_MAX_LIMITE, 0, " mm/min"))],
            "Confira na máquina: área = $130/$131, S máximo = $30, velocidade = $110/$111 (painel Máquina → "
            "Salvar relatório). Valores da SCULPFUN S30 Pro Max ainda NÃO verificados.")
        if v:
            self.definir_maquina(v)

    # ---------- rotativo ----------
    def definir_rotativo(self, r) -> bool:
        e = rtv.erros(r)
        if e:
            self.show_error("Rotativo", "; ".join(e))
            return False
        self.rotativo = r
        self.settings.setValue("rotativo", json.dumps(rtv.para_dict(r)))
        self._atualizar_rotativo_status()
        return True

    def _atualizar_rotativo_status(self):
        r = self.rotativo
        if hasattr(self, "rotativo_label"):
            self.rotativo_label.setVisible(r.ativo)
            self.rotativo_label.setText(f" ROTATIVO ({r.tipo}, ×{r.fator:.3f}) ")
        if hasattr(self, "aviso_rotativo"):
            self.aviso_rotativo.setVisible(r.ativo)
            self.btn_desligar_rot.setVisible(r.ativo)
            self.aviso_rotativo.setText(f"⚠ ROTATIVO LIGADO ({r.tipo}): todo Y vira giro da peça (×{r.fator:.2f}). "
                                        "Em chapa plana o cabeçote vai muito além do desenho — desligue para gravar "
                                        "na mesa.")

    def desligar_rotativo(self):
        return self.definir_rotativo(replace(self.rotativo, ativo=False))

    def _rotativo_dialogo(self):
        r = self.rotativo
        v = self.ask_valores("Configuração do rotativo", [
            ("ativo", "Ativar rotativo (o eixo Y passa a girar a peça)", r.ativo, None),
            ("tipo", "Tipo", r.tipo, [("rolo", "Rolo (peça apoiada em rolos)"), ("mandril", "Mandril (peça presa)")]),
            ("eixo", "Motor do rotativo ligado no", r.eixo,
             [("Y", "Eixo Y (peça deitada da esquerda p/ direita)"), ("X", "Eixo X (peça deitada de frente p/ trás)")]),
            ("mm_por_rotacao", "mm por rotação (calibrar na máquina)", r.mm_por_rotacao, (0.1, 100000, 3, " mm")),
            ("diametro_objeto_mm", "Diâmetro da peça", r.diametro_objeto_mm, (0.1, 2000, 3, " mm")),
            ("diametro_rolo_mm", "Diâmetro do rolo (tipo Rolo)", r.diametro_rolo_mm, (0.1, 500, 3, " mm")),
            ("vel_giro_max", "Velocidade máxima de giro (peça não patina)", r.vel_giro_max, (50, 20000, 0, " mm/min")),
            ("espelhar", "Espelhar a saída", r.espelhar, None)],
            "Desenhe na medida real da superfície (altura do desenho = volta na peça; a circunferência da peça é "
            "π × diâmetro). Valores NÃO validados: calibre 'mm por rotação' na máquina antes de gravar.")
        if v:
            self.definir_rotativo(rtv.Rotativo(**v))

    def inserir_teste_rotativo(self, n) -> bool:
        """Teste do rotativo numa aba nova (o desenho do usuário fica intacto). Gravar com Iniciar normal."""
        from .. import teste_rotativo as trt
        r = self.rotativo
        if not r.ativo:
            self.show_error("Teste do rotativo", "Ligue o rotativo antes (Laser → Configuração do rotativo) e "
                                                 "confira o diâmetro da peça.")
            return False
        if not self.adicionar_pagina():
            return False
        self.renomear_pagina(self.pagina_atual, f"Teste {n} do rotativo")
        cx, y0 = g.BED_W / 2, 10.0
        lid = "C25" if n == 1 else "C26"
        itens = (trt.volta_completa(r.diametro_objeto_mm, cx, y0) if n == 1 else trt.medidas(cx, y0))
        shapes = [ob.Shape(pa, nome, lid, cm.cor(lid)) for pa, nome in itens]
        self._edit(f"Teste {n} do rotativo", lambda: [self.canvas.scene.addItem(s) for s in shapes])
        self.set_layer_fields(lid, {"nome": f"Teste {n} rotativo (ajuste a potência ao material)", "modo": "linha",
                                    "velocidade_mm_min": 1000.0, "potencia_max": 30.0, "passadas": 1 if n == 1 else 2},
                              "Camada do teste do rotativo")
        self._rebuild_objects()
        self._refresh_preview()
        self.statusBar().showMessage(f"Teste {n} do rotativo pronto nesta aba: posicione o laser na peça e use "
                                     "Iniciar (a partir da posição atual).")
        return True

    def _conexao_pronta(self, titulo):
        c = self.conexao
        if c is None or c.estado != cx.CONECTADO:
            self.show_error(titulo, "Conecte à máquina primeiro (painel Máquina → Conectar).")
            return None
        return c

    def ask_sim(self, titulo, texto) -> bool:
        """Pergunta sim/não. Substituível nos testes."""
        return QMessageBox.question(self, titulo, texto) == QMessageBox.Yes

    def limite_grbl(self, ligado) -> bool:
        """$20=1/0 na placa, com confirmação (é configuração gravada no GRBL)."""
        titulo = "Limite de curso do GRBL ($20)"
        c = self._conexao_pronta(titulo)
        if c is None:
            return False
        txt = ("Religar o limite de curso por software ($20=1)? Use quando voltar para a MESA PLANA."
               if ligado else
               "Desligar o limite de curso por software ($20=0)?\n\nNecessário para o ROTATIVO: o eixo que gira "
               "passa do tamanho da mesa e o GRBL travaria em ALARME. Fica gravado na placa até você religar "
               "(Laser → Rotativo: religar limite de curso).")
        if not self.ask_sim(titulo, txt):
            return False
        try:
            c.limite_software(ligado)
        except cx.ComandoProibido as e:
            self.show_error(titulo, str(e))
            return False
        self.statusBar().showMessage(f"Enviado $20={1 if ligado else 0}.", 6000)
        return True

    def girar_uma_volta(self) -> bool:
        """Teste 0: o eixo do rotativo anda 'mm por rotação' (laser desligado). Tem que dar uma volta exata."""
        titulo = "Teste 0 do rotativo"
        r = self.rotativo
        if not r.ativo:
            self.show_error(titulo, "Ligue o rotativo antes (Laser → Configuração do rotativo).")
            return False
        c = self._conexao_pronta(titulo)
        if c is None:
            return False
        if c.info.valor(20, 0) == 1:
            self.show_error(titulo, "A placa está com $20=1: use antes Laser → Rotativo: liberar GRBL ($20=0).")
            return False
        volta = r.circunferencia_objeto * r.fator  # comando para a PEÇA dar uma volta
        try:
            if r.eixo == "Y":
                c.jog(0.0, volta, r.vel_giro_max)
            else:
                c.jog(volta, 0.0, r.vel_giro_max)
        except cx.ComandoProibido as e:
            self.show_error(titulo, str(e))
            return False
        voltas = self.ask_voltas()
        if voltas is None or abs(voltas - 1) < 0.01:
            if voltas is not None:
                self.statusBar().showMessage("Deu uma volta certa: rotativo calibrado.", 8000)
            return True
        novo = r.mm_por_rotacao / voltas
        self.definir_rotativo(replace(r, mm_por_rotacao=round(novo, 3)))
        self.show_info(titulo, f"Corrigido: {r.mm_por_rotacao:g} → {novo:.3f}.\n\nFaça o teste de novo: agora tem "
                       "que dar UMA volta certinha.")
        return True

    def ask_voltas(self):
        """Quantas voltas a peça deu no teste (ou None). Substituível nos testes."""
        v = self.ask_valores("Quantas voltas a peça deu?", [
            ("voltas", "Voltas que a PEÇA deu (1 = certo; 1,5 = uma e meia; 0,75 = três quartos)", 1.0,
             (0.05, 50, 2, ""))],
            "Olhe o risco que você fez na PEÇA (não no rolo). Espere o giro terminar e diga quantas voltas ela deu.")
        return v["voltas"] if v else None

    def ask_erro_rotativo(self):
        """Erro lido no teste 1 (mm) ou None. Substituível nos testes."""
        v = self.ask_valores("Corrigir mm por rotação", [
            ("erro", "A linha B caiu em qual traço da escala?", 0.0, (-50, 50, 2, " mm"))],
            "No teste 1, veja onde a linha B (2ª volta) caiu na escala ao lado da linha A: traço +2 = passou 2 mm "
            "(use números positivos), -2 = faltou 2 mm. Se caiu entre traços, estime (ex.: 1,5).")
        return v["erro"] if v else None

    def _corrigir_rotativo_dialogo(self):
        from .. import teste_rotativo as trt
        r = self.rotativo
        e = self.ask_erro_rotativo()
        if e is None:
            return False
        try:
            novo = trt.corrigir(r.mm_por_rotacao, r.diametro_objeto_mm, e)
        except ValueError as err:
            self.show_error("Corrigir mm por rotação", str(err))
            return False
        ok = self.definir_rotativo(replace(r, mm_por_rotacao=round(novo, 3)))
        if ok:
            self.show_info("Rotativo corrigido", f"mm por rotação: {r.mm_por_rotacao:g} → {novo:.3f}\n\n"
                           "Grave o teste 1 de novo: a linha B tem que cair no 0 (±0,5 mm).")
        return ok

    def otimizacao(self) -> dict:
        """Opções de ordem de corte (Configurações → Otimização de corte)."""
        return {"internas_primeiro": ler_pref(self.settings, "otim_internas_primeiro"),
                "vizinho": ler_pref(self.settings, "otim_vizinho"),
                "remover_sobrepostas": ler_pref(self.settings, "otim_remover_sobrepostas")}

    # ---------- configurações ----------
    def aplicar_preferencias(self):
        v = self.canvas.view
        v.zoom_invertido = ler_pref(self.settings, "zoom_invertido")
        v.passo_seta = ler_pref(self.settings, "passo_seta_mm")
        v.passo_seta_shift = ler_pref(self.settings, "passo_seta_shift_mm")
        v.snap_px = ler_pref(self.settings, "encaixe_px")
        v.encaixe_grade = ler_pref(self.settings, "encaixe_grade")
        v.set_tema(ler_pref(self.settings, "tema_mesa"))
        ob.definir_espessura(ler_pref(self.settings, "espessura_linha"))
        for s in v.shapes():  # objetos já na mesa passam a usar a nova espessura
            pen = s.pen()
            if pen.widthF() != ob.ESPESSURA:
                pen.setWidthF(ob.ESPESSURA)
                s.setPen(pen)
        minutos = ler_pref(self.settings, "auto_salvar_min")
        self._auto_timer.stop()
        if minutos > 0:
            self._auto_timer.start(minutos * 60_000)

    def ask_preferencias(self):
        """dict com os valores ou None. Substituível nos testes."""
        dlg = PreferenciasDialog(self, self.settings)
        return dlg.valores() if dlg.exec() == PreferenciasDialog.Accepted else None

    def _preferencias_dialogo(self):
        v = self.ask_preferencias()
        if v is None:
            return
        for k, val in v.items():
            self.settings.setValue(k, val)
        self.aplicar_preferencias()
        self._refresh_preview()
        self.statusBar().showMessage("Configurações salvas.")

    # ---------- modelos de projeto e preferências ----------
    def pasta_modelos(self) -> str:
        from PySide6.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
        return os.path.join(base, "RedBlackLaser", "modelos")

    def modelos(self) -> list:
        pasta = self.pasta_modelos()
        if not os.path.isdir(pasta):
            return []
        return sorted((f for f in os.listdir(pasta) if f.lower().endswith(pj.EXT)), key=str.casefold)

    def salvar_modelo(self, nome) -> bool:
        """Guarda o projeto atual como modelo (não muda o arquivo aberto nem o estado de 'salvo')."""
        nome = vr.nome_arquivo_seguro(nome.strip(), 60) if nome and nome.strip() else ""
        if not nome:
            return False
        os.makedirs(self.pasta_modelos(), exist_ok=True)
        st = self.doc_state()
        try:
            pj.save(os.path.join(self.pasta_modelos(), nome + pj.EXT), st[0], self.layers, self.vars, self.gabarito,
                    st[5], st[6], self.notas, st[8], st[9], st[10])
        except OSError as e:
            self.show_error("Modelo não salvo", str(e))
            return False
        self.statusBar().showMessage(f"Modelo salvo: {nome}")
        return True

    def novo_de_modelo(self, arquivo) -> bool:
        """Novo projeto (sem nome) com o conteúdo do modelo; o modelo não é alterado."""
        if not self._maybe_save():
            return False
        try:
            snaps, layers, variaveis, gabarito, ancoras, bloqueados, notas, paginas = pj.load_full(
                os.path.join(self.pasta_modelos(), arquivo))
        except pj.ProjetoInvalido as e:
            self.show_error("Modelo inválido", str(e))
            return False
        self._reset_document(snaps, None, layers, variaveis, gabarito, ancoras, bloqueados, notas, paginas)
        self.statusBar().showMessage(f"Novo projeto a partir do modelo {arquivo}")
        return True

    def _salvar_modelo_dialogo(self):
        nome, ok = QInputDialog.getText(self, "Salvar como modelo", "Nome do modelo:")
        if ok:
            self.salvar_modelo(nome)

    def _montar_modelos(self):
        m = self.modelos_menu
        m.clear()
        for f in self.modelos():
            m.addAction(os.path.splitext(f)[0]).triggered.connect(lambda _=False, a=f: self.novo_de_modelo(a))
        if not m.actions():
            m.addAction("(nenhum modelo salvo)").setEnabled(False)

    def exportar_preferencias(self, path) -> bool:
        dados = {k: self.settings.value(k) for k in self.settings.allKeys()
                 if k not in ("geometry", "windowState") and not k.startswith("recentes")}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"formato": "redblack-preferencias", "valores": dados}, f, ensure_ascii=False, indent=1,
                          default=str)
        except OSError as e:
            self.show_error("Preferências não exportadas", str(e))
            return False
        return True

    def importar_preferencias(self, path) -> bool:
        """Aceita só o arquivo exportado pelo próprio programa; tipos simples; aplica na hora."""
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if not (isinstance(d, dict) and d.get("formato") == "redblack-preferencias"
                    and isinstance(d.get("valores"), dict)):
                raise ValueError("arquivo não é de preferências do RedBlack Laser")
        except (OSError, ValueError) as e:
            self.show_error("Preferências não importadas", str(e))
            return False
        for k, v in d["valores"].items():
            if isinstance(k, str) and isinstance(v, (str, int, float, bool)) and len(k) < 200:
                self.settings.setValue(k, v)
        self.aplicar_preferencias()
        aplicar_atalhos(self.settings, self.todas_acoes())
        self.statusBar().showMessage("Preferências importadas.")
        return True

    def _preferencias_arquivo_dialogo(self, exportar):
        if exportar:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar preferências",
                                                  os.path.join(self._last_dir(), "redblack_preferencias.json"),
                                                  "Preferências (*.json)")
            if path:
                self.exportar_preferencias(path)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Importar preferências", self._last_dir(),
                                                  "Preferências (*.json)")
            if path:
                self.importar_preferencias(path)

    # ---------- texto ao longo do caminho ----------
    def texto_no_caminho(self, v=None) -> bool:
        """Texto selecionado ao longo do caminho clicado por último; o texto vira curvas (o original sai)."""
        sel = self._sel_ordem()
        textos = [s for s in sel if isinstance(s, ob.TextShape)]
        guia = sel[-1] if sel and not isinstance(sel[-1], ob.TextShape) else None
        if len(textos) != 1 or guia is None or isinstance(guia, ob.ImageShape):
            self.statusBar().showMessage("Selecione um texto e, por último, o caminho (linha, círculo…).")
            return False
        v = v or self.ask_valores("Texto ao longo do caminho", [
            ("inicio", "Posição no caminho", 25.0, (0, 100, 1, " %")),
            ("deslocamento", "Afastar do caminho", 0.0, (-1000, 1000, 2, " mm")),
            ("inverter", "Do outro lado (sentido contrário)", False, None)],
            "Com alinhamento Centro, a posição é o meio do texto. O resultado é um contorno (curvas).")
        if not v:
            return False
        t = textos[0]
        try:
            path = txc.aplicar(t.params, guia.sceneTransform().map(guia.path()), v["inicio"], v["deslocamento"],
                               v["inverter"])
        except ValueError as e:
            self.show_error("Texto ao longo do caminho", str(e))
            return False
        self._trocar_por_caminhos([t], [(path, f"{t.name} (no caminho)", t.layer)], "Texto ao longo do caminho")
        return True

    # ---------- traçar imagem ----------
    def ask_tracar(self, imagem):
        """Janela Traçar imagem com prévia ao vivo; devolve as opções ou None."""
        from .dialogo_tracar import DialogoTracar
        d = DialogoTracar(imagem, self, getattr(self, "_ultimo_tracar", None))
        if d.exec() != DialogoTracar.Accepted:
            return None
        self._ultimo_tracar = {k: v for k, v in d.opcoes().items() if k not in ("area", "apagar_imagem")}
        return d.opcoes()

    def _imagens_sel(self, comando):
        imgs = [s for s in self._sel() if isinstance(s, ob.ImageShape)]
        if not imgs:
            self.statusBar().showMessage(f"{comando}: selecione uma imagem.")
        return imgs

    def ask_ajustar_imagem(self, img, camada):
        from .dialogo_ajustar_imagem import DialogoAjustarImagem
        r_ = ob.geom_rect(img)
        d = DialogoAjustarImagem(img.extra.qimage, r_.width(), r_.height(), camada, self)
        return d.campos() if d.exec() == DialogoAjustarImagem.Accepted else None

    def ajustar_imagem(self, campos=None) -> bool:
        """Brilho, contraste, gama, modo e resolução da imagem, com prévia de como o laser vai gravar (na camada)."""
        imgs = self._imagens_sel("Ajustar imagem")
        if not imgs:
            return False
        camada = self.layer(imgs[0].layer)
        if camada is None:
            return False
        campos = campos or self.ask_ajustar_imagem(imgs[0], camada)
        if not campos:
            return False
        return self.set_layer_fields(camada.id, campos, "Ajustar imagem")

    def ask_salvar_bitmap(self, sugestao):
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar bitmap processado", sugestao, "Imagem PNG (*.png)")
        return caminho

    def salvar_bitmap_processado(self, caminho=None) -> bool:
        """PNG com o que o laser vai gravar (pontilhado/cinza/limiar já aplicados), na resolução do intervalo."""
        imgs = self._imagens_sel("Salvar bitmap processado")
        if not imgs:
            return False
        im_ = imgs[0]
        camada = self.layer(im_.layer)
        base = os.path.splitext(im_.name)[0] or "imagem"
        caminho = caminho or self.ask_salvar_bitmap(os.path.join(self._last_dir(), f"{base}_processado.png"))
        if not caminho:
            return False
        r_ = ob.geom_rect(im_)
        try:
            out = raster.imagem_processada(im_.extra.qimage, r_.width(), r_.height(), camada)
        except raster.RasterGrandeDemais as e:
            self.show_error("Salvar bitmap processado", str(e))
            return False
        if not out.save(caminho, "PNG"):
            self.show_error("Salvar bitmap processado", f"Não foi possível gravar {caminho}.")
            return False
        self.statusBar().showMessage(f"Bitmap processado salvo: {caminho} ({out.width()} × {out.height()} px).")
        return True

    def tracar_imagem(self, v=None) -> bool:
        """Contornos vetoriais da imagem selecionada (opções como no original: corte/limiar, suavidade, otimizar,
        transparência, esboço, linha central, área). A imagem continua, a menos que se peça para apagá-la."""
        imgs = [s for s in self._sel() if isinstance(s, ob.ImageShape)]
        if not imgs:
            self.statusBar().showMessage("Traçar imagem: selecione uma imagem.")
            return False
        v = v or self.ask_tracar(imgs[0].extra.qimage)
        if not v:
            return False
        if "suavizar" in v:  # formato antigo: limiar em %, simplificar, mínimo, negativo
            v = dict(corte=0, limiar=max(0, round(v["limiar"] / 100 * 255) - 1), otimizar=max(v["suavizar"] - 0.5, 0),
                     ignorar=v["minimo"], negativo=v["negativo"], suavidade=0)
        op = {k: x for k, x in v.items() if k != "apagar_imagem"}
        QApplication.setOverrideCursor(Qt.WaitCursor)  # foto grande leva alguns segundos
        try:
            return self._tracar(imgs, v, op)
        finally:
            QApplication.restoreOverrideCursor()

    def _tracar(self, imgs, v, op) -> bool:
        novos = []
        for im_ in imgs:
            r_ = im_.path().boundingRect()
            try:
                local = trc.tracar_opcoes(im_.extra.qimage, r_.width(), r_.height(), op)
            except ValueError as e:
                self.show_error("Traçar imagem", str(e))
                return False
            if not local.isEmpty():
                tf = QTransform.fromTranslate(r_.left(), r_.top()) * im_.sceneTransform()
                novos.append((tf.map(local), f"Traçado de {im_.name}", "C01"))
        if not novos:
            self.statusBar().showMessage("Nada para traçar com esses valores de Corte/Limiar.")
            return False
        self._trocar_por_caminhos(imgs if v.get("apagar_imagem") else [], novos, "Traçar imagem")
        return True

    # ---------- imprimir ----------
    def imprimir(self, printer=None, cores=False) -> bool:
        """Desenho em escala real (1:1) na impressora: contornos pretos (ou na cor da camada) e preenchimento das
        imagens. Útil para conferir medidas no papel. `printer` = QPrinter já configurado (diálogo se None)."""
        from PySide6.QtGui import QPainter, QPen
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        itens = [s for s in self.canvas.view.shapes() if s.isVisible()]
        if not itens:
            self.statusBar().showMessage("Nada para imprimir.")
            return False
        if printer is None:
            printer = QPrinter(QPrinter.HighResolution)
            if self.ask_impressao(printer) is None:
                return False
        r = ob.bounds(itens)
        p = QPainter()
        if not p.begin(printer):
            self.show_error("Imprimir", "Não foi possível iniciar a impressão.")
            return False
        px_mm = printer.resolution() / 25.4
        p.scale(px_mm, px_mm)                      # 1 unidade = 1 mm no papel
        p.translate(-r.left() + 5, -r.top() + 5)   # 5 mm de margem a partir da borda imprimível
        for s in itens:
            if isinstance(s, ob.ImageShape):
                p.save()
                p.setTransform(s.sceneTransform() * p.transform())
                p.drawImage(s.path().boundingRect(), s.extra.qimage)
                p.restore()
                continue
            pen = QPen(QColor(cm.cor(s.layer) if cores else "black"), 0.1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(s.sceneTransform().map(s.path()))
        p.end()
        self.statusBar().showMessage(f"Impressão enviada em escala 1:1 ({r.width():.1f} × {r.height():.1f} mm)."
                                     .replace(".", ",", 2))
        return True

    def ask_impressao(self, printer):
        """Diálogo da impressora; True se confirmado, None se cancelado. Substituível nos testes."""
        from PySide6.QtPrintSupport import QPrintDialog
        dlg = QPrintDialog(printer, self)
        return True if dlg.exec() == QPrintDialog.Accepted else None

    # ---------- converter em bitmap ----------
    def converter_em_bitmap(self, dpi=254) -> bool:
        """Desenha a seleção (vetores e textos) numa imagem preta sobre branco no DPI dado e a põe no lugar."""
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QImage, QPainter
        sel = self._vetoriais(self._sel())
        if not sel:
            return False
        r = ob.bounds(sel)
        px_mm = dpi / 25.4
        w_px, h_px = max(1, round(r.width() * px_mm)), max(1, round(r.height() * px_mm))
        if w_px * h_px > 40_000_000:
            self.show_error("Converter em bitmap", "Imagem grande demais; diminua a seleção.")
            return False
        img = QImage(w_px, h_px, QImage.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(w_px / r.width(), h_px / r.height())
        p.translate(-r.left(), -r.top())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("black"))
        for s in sel:
            p.drawPath(s.sceneTransform().map(s.path()))
        p.end()
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        img.setDotsPerMeterX(round(dpi / 0.0254))
        img.setDotsPerMeterY(round(dpi / 0.0254))
        img.save(buf, "PNG")
        res = imgimp.from_bytes(bytes(ba), "convertido.png")

        def do():
            scene = self.canvas.scene
            for s in sel:
                scene.removeItem(s)
            scene.clearSelection()
            it = ob.ImageShape(res.imagem, r.width(), r.height(), "Bitmap convertido")
            it.setTransform(QTransform.fromTranslate(r.left(), r.top()))
            scene.addItem(it)
            it.setSelected(True)
            self._rebuild_objects()

        self._edit("Converter em bitmap", do)
        return True

    def _mostrar_notas(self):
        if hasattr(self, "notas_edit") and self.notas_edit.toPlainText() != self.notas:
            self._syncing_notas = True
            self.notas_edit.setPlainText(self.notas)
            self._syncing_notas = False

    def _notas_editadas(self):
        texto = self.notas_edit.toPlainText()[:pj.MAX_NOTAS]
        if texto != self.notas:
            self._edit("Notas do projeto", lambda: setattr(self, "notas", texto))

    def todas_acoes(self):
        """Comandos dos menus (inclui submenus), sem separadores nem os de etapas futuras."""
        # QAction.menu() no PySide pode tomar posse do menu e apagá-lo: usa um mapa ação → menu.
        submenus = {id(m.menuAction()): m for m in self.findChildren(QMenu)}
        out, vistos = [], set()

        def visita(acoes):
            for a in acoes:
                sub = submenus.get(id(a))
                if sub is not None:
                    visita(sub.actions())
                elif not a.isSeparator() and not a.property("stage") and id(a) not in vistos:
                    vistos.add(id(a))
                    out.append(a)

        visita(self.menuBar().actions())
        return out

    def ask_atalhos(self):
        """{comando: tecla} ou None. Substituível nos testes."""
        dlg = AtalhosDialog(self, self.todas_acoes())
        return dlg.mapa() if dlg.exec() == AtalhosDialog.Accepted else None

    def editar_atalhos(self, mapa=None) -> bool:
        mapa = mapa if mapa is not None else self.ask_atalhos()
        if mapa is None:
            return False
        for a in self.todas_acoes():
            k = chave_atalho(a)
            if k in mapa:
                self.settings.setValue("atalhos/" + k, mapa[k])
                a.setShortcut(QKeySequence(mapa[k]))
        self.statusBar().showMessage("Teclas de atalho salvas.")
        return True

    def pasta_auto(self) -> str:
        """Pasta das cópias automáticas (não substitui o arquivo do usuário)."""
        from PySide6.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
        return os.path.join(base, "RedBlackLaser", "autosave")

    def auto_salvar(self):
        """Salvamento automático. Projeto com arquivo: grava no próprio arquivo (o histórico do Desfazer continua);
        sem arquivo ainda, com grupo aberto ou com a opção desligada: cópia de recuperação na pasta automática,
        reaberta no próximo início se o programa fechar sem salvar."""
        if self.undo_stack.isClean():
            return None
        grupo_aberto = any(s.grupo_aberto for s in self.canvas.view.shapes())
        if self.file_path and ler_pref(self.settings, "auto_salvar_arquivo") and not grupo_aberto:
            st = self.doc_state()
            try:
                pj.save(self.file_path, st[0], self.layers, self.vars, self.gabarito, st[5], st[6], self.notas,
                        st[8], st[9], st[10])
            except OSError as e:
                self.statusBar().showMessage(f"Salvamento automático falhou: {e}")
                return None
            self.undo_stack.setClean()  # só marca como salvo: os passos do Desfazer continuam
            self._update_title()
            self._limpar_recuperacao()
            self.statusBar().showMessage(f"Salvo automaticamente às {datetime.now():%H:%M}: {self.file_path}")
            return self.file_path
        pasta = self.pasta_auto()
        os.makedirs(pasta, exist_ok=True)
        nome = os.path.splitext(os.path.basename(self.file_path))[0] if self.file_path else "sem_titulo"
        destino = os.path.join(pasta, nome + ".autosave" + pj.EXT)
        st = self.doc_state()
        try:
            pj.save(destino, st[0], self.layers, self.vars, self.gabarito, st[5], st[6], self.notas, st[8], st[9], st[10])
        except OSError as e:
            self.statusBar().showMessage(f"Cópia automática falhou: {e}")
            return None
        self.settings.setValue("sessao/recuperar", destino)
        self.settings.setValue("sessao/recuperar_de", self.file_path or "")
        self.statusBar().showMessage(f"Cópia de recuperação salva às {datetime.now():%H:%M}"
                                     + (" (grupo aberto: o arquivo é salvo quando o grupo fechar)"
                                        if grupo_aberto and self.file_path else ""))
        return destino

    def _limpar_recuperacao(self):
        rec = self.settings.value("sessao/recuperar", "")
        if rec and os.path.isfile(rec):
            try:
                os.remove(rec)
            except OSError:
                pass
        self.settings.remove("sessao/recuperar")
        self.settings.remove("sessao/recuperar_de")

    def restaurar_sessao(self) -> bool:
        """No início: reabre a cópia de recuperação (programa fechou com alterações sem salvar) ou o último
        projeto aberto."""
        if not ler_pref(self.settings, "abrir_ultimo"):
            return False
        rec = self.settings.value("sessao/recuperar", "")
        if rec and os.path.isfile(rec):
            origem = self.settings.value("sessao/recuperar_de", "") or None
            if self.open_path(rec):
                self.file_path = origem  # salvar grava no arquivo de verdade (ou pede um nome)
                self.undo_stack.resetClean()  # continua marcado como "não salvo"
                self._update_title()
                self.statusBar().showMessage("Projeto recuperado: o programa fechou sem salvar as últimas "
                                             "alterações. Salve (Ctrl+S) para manter.")
                return True
        ultimo = self.settings.value("sessao/ultimo", "")
        if ultimo and os.path.isfile(ultimo):
            return self.open_path(ultimo)
        return False

    ACOES_CAMADAS = (
        ("saida_todas", "Ativar a saída de todas as camadas"), ("saida_nenhuma", "Desativar a saída de todas"),
        ("saida_so_esta", "Saída só nesta camada (desativar as outras)"), ("saida_inverter", "Inverter saídas"),
        (None, None),
        ("ver_todas", "Mostrar todas as camadas"), ("ver_so_esta", "Ocultar todas, exceto esta"),
        ("ver_inverter", "Inverter camadas visíveis"), (None, None),
        ("ar_todas", "Ligar air assist em todas"), ("ar_nenhuma", "Desligar air assist em todas"),
        ("ar_inverter", "Inverter air assist"))

    def acao_camadas(self, acao, lid=None) -> bool:
        """Mudança em lote nas camadas em uso (desfazível em um passo)."""
        used, _ = self.used_layers()
        alvo = [c for c in self.layers if c.id in used]
        campo, regra = {
            "saida_todas": ("saida", lambda c: True), "saida_nenhuma": ("saida", lambda c: False),
            "saida_so_esta": ("saida", lambda c: c.id == lid), "saida_inverter": ("saida", lambda c: not c.saida),
            "ver_todas": ("visivel", lambda c: True), "ver_so_esta": ("visivel", lambda c: c.id == lid),
            "ver_inverter": ("visivel", lambda c: not c.visivel),
            "ar_todas": ("air", lambda c: True), "ar_nenhuma": ("air", lambda c: False),
            "ar_inverter": ("air", lambda c: not c.air)}[acao]
        novos = {c.id: cm.alterar(c, **{campo: regra(c)}) for c in alvo}
        if all(novos[c.id] == c for c in alvo):
            return False

        def do():
            self.layers = [novos.get(c.id, c) for c in self.layers]

        self._edit(dict(a for a in self.ACOES_CAMADAS if a[0])[acao], do)
        self._refresh_layers()
        return True

    def _menu_camadas(self, pos):
        item = self.layer_table.itemAt(pos)
        lid = self.layer_table.item(item.row(), 0).data(Qt.UserRole) if item else self._current_layer_id()
        m = QMenu(self)
        for chave, txt in self.ACOES_CAMADAS:
            if chave is None:
                m.addSeparator()
            else:
                a = m.addAction(txt)
                a.setEnabled(lid is not None or "so_esta" not in chave)
                a.triggered.connect(lambda _=False, k=chave: self.acao_camadas(k, lid))
        m.exec(self.layer_table.viewport().mapToGlobal(pos))
        m.deleteLater()

    def move_layer(self, lid, delta):
        """Sobe (-1) ou desce (+1) a camada entre as camadas em uso; a ordem é a ordem de saída."""
        used, _ = self.used_layers()
        order = [c.id for c in self.layers if c.id in used]
        i = order.index(lid)
        j = i + delta
        if not 0 <= j < len(order):
            return

        def do():
            a, b = (self.layers.index(self.layer(x)) for x in (order[i], order[j]))
            self.layers[a], self.layers[b] = self.layers[b], self.layers[a]

        self._edit(f"Ordem da camada {lid}", do)

    def _move_current_layer(self, delta):
        lid = self._current_layer_id()
        if lid:
            self.move_layer(lid, delta)

    def assign_layer(self, lid):
        sel = self._sel()
        if not sel:
            self.statusBar().showMessage(f"Selecione objetos para atribuir à camada {lid}.")
            return

        def do():
            scene = self.canvas.scene
            for it in sel:
                new = ob.from_snapshot(ob.with_layer(it.snapshot(), lid))
                scene.removeItem(it)
                scene.addItem(new)
                new.setSelected(True)
            self._rebuild_objects()

        self._edit(f"Camada {lid}", do)
        self.statusBar().showMessage(f"{len(sel)} objeto(s) na camada {lid}.")

    def _end_interactive_edit(self, text):
        if self._tfs_inicio:
            self._seguir_ancoras(self._tfs_inicio)
            self._tfs_inicio = None
        if self._before is not None:
            before, self._before = self._before, None
            self._commit(text, before)

    # ---------- arquivo ----------
    def _update_title(self, *_):
        name = os.path.basename(self.file_path) if self.file_path else "sem título"
        mark = "" if self.undo_stack.isClean() else "*"
        self.setWindowTitle(f"{name}{mark} — RedBlack Laser")

    def ask_save(self) -> str:
        """'save', 'discard' ou 'cancel'. Substituível nos testes."""
        r = QMessageBox.question(self, "Alterações não salvas",
                                 "O projeto tem alterações não salvas. Deseja salvar antes de continuar?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        return {QMessageBox.Save: "save", QMessageBox.Discard: "discard"}.get(r, "cancel")

    def _maybe_save(self) -> bool:
        if self.undo_stack.isClean():
            return True
        choice = self.ask_save()
        if choice == "save":
            return self.save()
        return choice == "discard"

    def _reset_document(self, snaps, path, layers=(), variaveis=None, gabarito=None, ancoras=(), bloqueados=(),
                        notas="", paginas=None):
        self.tools["select"].setChecked(True)  # descarta linha/forma/medição em andamento
        lista, atual, nomes = paginas or ([None], 0, pj.nomes_padrao(1))
        lista = tuple(None if p is None else (tuple(ob.normalize_layers(s) for s in p[0]), p[1], p[2]) for p in lista)
        self.set_doc_state((tuple(ob.normalize_layers(s) for s in snaps), (), tuple(layers),
                            variaveis or vr.DadosVariaveis(), gabarito, tuple(ancoras), tuple(bloqueados), notas,
                            lista, atual, tuple(nomes), ()))
        self._aplicar_variaveis()  # data/hora do momento da abertura
        self._ensure_layers()  # projetos antigos não têm camadas: cria as padrão
        self.undo_stack.clear()
        self._refresh_preview()
        self.file_path = path
        self._update_title()
        self.canvas.view.fit()

    def new_document(self):
        if self._maybe_save():
            self._reset_document([], None)
            self.statusBar().showMessage("Novo projeto.")

    def open_dialog(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", self._last_dir(),
                                              f"Projeto RedBlack Laser (*{pj.EXT})")
        if path:
            self.open_path(path)

    def open_path(self, path) -> bool:
        """Abre sem perguntar; em erro, o documento atual fica intacto."""
        try:
            snaps, layers, variaveis, gabarito, ancoras, bloqueados, notas, paginas = pj.load_full(path)
        except pj.ProjetoInvalido as e:
            self.statusBar().showMessage(f"Falha ao abrir: {e}")
            self.show_error("Não foi possível abrir o projeto", str(e))
            return False
        self._reset_document(snaps, path, layers, variaveis, gabarito, ancoras, bloqueados, notas, paginas)
        self._remember_dir(path)
        self._registrar_recente(path)
        self.statusBar().showMessage(f"Projeto aberto: {path}")
        missing = sorted({s[5].fonte for s in snaps if isinstance(s[5], tx.TextoParams)
                          and not tx.font_available(s[5].fonte)})
        if missing:
            self.show_info("Fontes não instaladas",
                           "Fontes usadas no projeto que não estão instaladas: " + ", ".join(missing) + ".\n\n"
                           "Os textos aparecem com o contorno salvo no projeto, sem alteração. Ao editar um "
                           "desses textos será preciso escolher outra fonte; converter em curvas preserva o desenho.")
        return True

    # ---------- texto ----------
    def default_font(self) -> str:
        f = ler_pref(self.settings, "texto_fonte")
        return f if tx.font_available(f) else "Arial" if tx.font_available("Arial") else self.font().family()

    def ask_text(self, initial):
        """Abre o diálogo; devolve TextoParams ou None. Substituível nos testes."""
        dlg = TextDialog(self, initial, vr.contexto(self.vars))
        return dlg.params() if dlg.exec() else None

    def _on_text_click(self, scene_pos):
        params = self.ask_text(tx.TextoParams("", self.default_font(), ler_pref(self.settings, "texto_altura_mm")))
        self.tools["select"].setChecked(True)
        if params:
            self.create_text(params, scene_pos)

    # ---------- formas e grupos ----------
    SHAPE_NAMES = {"rect": "Retângulo", "ellipse": "Elipse", "polygon": "Polígono", "line": "Linha", "star": "Estrela"}

    def _nome_forma(self, kind):
        return self.canvas.view.forma_pronta if kind == "preset" else self.SHAPE_NAMES[kind]

    def _on_draw_tool(self, kind, on):
        view = self.canvas.view
        if on:
            view.set_draw_tool(kind)
            view.setFocus()  # Enter/Esc da ferramenta Linhas
        elif view.draw_tool == kind:  # a ordem dos sinais ao trocar de ferramenta não é garantida
            view.set_draw_tool(None)

    def _poligono_preset(self, lados, ferramenta="polygon"):
        """Compatibilidade: polígono/estrela regular de `lados` como forma pronta (não muda as ferramentas)."""
        nomes = {3: "Triângulo", 5: "Pentágono", 6: "Hexágono", 8: "Octógono"}
        self.usar_forma_pronta(f"Estrela de {lados} pontas" if ferramenta == "star" else nomes.get(lados, "Hexágono"))

    def usar_forma_pronta(self, nome):
        """Escolhe uma forma do menu suspenso: arraste na mesa para desenhá-la (Shift = proporcional)."""
        self.canvas.view.forma_pronta = nome
        self.tools["preset"].setChecked(True)
        self._on_draw_tool("preset", True)  # já ativa mesmo se a ferramenta já estava marcada
        self.statusBar().showMessage(f"{nome}: arraste na mesa para desenhar (Shift = mesma largura e altura; "
                                     "Ctrl = a partir do centro).", 10000)

    def _menu_formas_prontas(self):
        from .. import formas_prontas as fp
        m = QMenu("Formas prontas", self)
        for grupo, nomes in fp.grupos().items():
            m.addSection(grupo)
            for nome in nomes:
                m.addAction(nome, lambda n=nome: self.usar_forma_pronta(n))
        return m

    def _ferramenta_campo_lados(self):
        """O campo da barra edita os lados do Polígono ou as pontas da Estrela, conforme a ferramenta."""
        v = self.canvas.view
        estrela = self.tools["star"].isChecked()
        self.sides.blockSignals(True)
        self.sides.setValue(v.star_pontas if estrela else v.polygon_sides)
        self.sides.blockSignals(False)
        self.lb_lados.setText(" Pontas " if estrela else " Lados ")

    def _lados_mudou(self, valor):
        v = self.canvas.view
        if self.tools["star"].isChecked():
            v.star_pontas = valor
        else:
            v.polygon_sides = valor

    # ---------- contorno retangular ao redor ----------
    MODOS_ENCAIXE = [("caber", "Caber: aumenta ou diminui, mantendo a proporção"),
                     ("diminuir", "Manter o tamanho; só diminui se não couber (proporcional)"),
                     ("esticar", "Preencher tudo: estica e deforma para ocupar a caixa inteira")]

    def encaixar_na_caixa(self, v=None) -> bool:
        """Coloca o que está selecionado DENTRO da caixa (a 1ª peça clicada; ou a maior, se a ordem não for
        conhecida), centralizado: cabendo com a proporção, só diminuindo, ou esticando para preencher."""
        sel = self._sel_ordem()
        if len(sel) < 2:
            self.statusBar().showMessage("Encaixar na caixa: clique primeiro na caixa e depois, com Shift, no que "
                                         "vai dentro (imagem, forma, texto, grupo…).")
            return False
        ordem = [s for s in self.canvas.view.ordem_sel if s.isSelected()]
        caixa = ordem[0] if ordem else max(sel, key=lambda s: ob.geom_rect(s).width() * ob.geom_rect(s).height())
        conteudo = [s for s in sel if s is not caixa]
        if any(s.bloqueado for s in conteudo):
            self.statusBar().showMessage("Encaixar na caixa: há peça bloqueada no que vai dentro.")
            return False
        v = v or self.ask_valores("Encaixar na caixa", [
            ("modo", "Como encaixar", "caber", self.MODOS_ENCAIXE),
            ("margem", "Margem dentro da caixa", 0.0, (0, 1000, 2, " mm"))],
            f"Caixa: {caixa.name}. O que vai dentro fica centralizado nela (usa o retângulo da caixa).")
        if not v:
            return False
        alvo = ob.geom_rect(caixa).adjusted(v["margem"], v["margem"], -v["margem"], -v["margem"])
        r = ob.bounds(conteudo)
        if alvo.width() <= 0 or alvo.height() <= 0 or r.width() <= 0 or r.height() <= 0:
            self.statusBar().showMessage("Encaixar na caixa: caixa pequena demais para a margem (ou peça sem "
                                         "largura/altura).")
            return False
        sx, sy = alvo.width() / r.width(), alvo.height() / r.height()
        if v["modo"] != "esticar":
            sx = sy = min(sx, sy) if v["modo"] == "caber" else min(sx, sy, 1.0)
        tf = (QTransform.fromTranslate(-r.center().x(), -r.center().y()) * QTransform.fromScale(sx, sy)
              * QTransform.fromTranslate(alvo.center().x(), alvo.center().y()))

        def do():
            ob.apply(conteudo, tf)
        self._edit("Encaixar na caixa", do)
        nomes = {"caber": "cabendo", "diminuir": "só diminuindo" if min(sx, sy) < 1 else "sem mudar o tamanho",
                 "esticar": "esticado"}
        self.statusBar().showMessage(f"Encaixado em {caixa.name} ({nomes[v['modo']]}): "
                                     f"{ob.bounds(conteudo).width():.1f} × {ob.bounds(conteudo).height():.1f} mm"
                                     .replace(".", ","))
        return True

    def contorno_ao_redor(self, v=None) -> bool:
        """Retângulo em volta da seleção (ex.: quadrado em volta de um círculo), com margem e raio de canto."""
        sel = self._sel()
        if not sel:
            self.statusBar().showMessage("Contorno ao redor: selecione o que vai ficar dentro.")
            return False
        v = v or self.ask_valores("Contorno retangular ao redor", [
            ("margem", "Margem (distância até o desenho)", 5.0, (0, 1000, 2, " mm")),
            ("raio", "Raio dos cantos (0 = cantos vivos)", 0.0, (0, 1000, 2, " mm")),
            ("quadrado", "Quadrado (lados iguais)", False, None)],
            "Cria um retângulo novo em volta da caixa da seleção. Diferente de Deslocar formas, que segue o "
            "desenho (em volta de um círculo, Deslocar dá outro círculo).")
        if not v:
            return False
        r = ob.bounds(sel)
        m = v["margem"]
        caixa = r.adjusted(-m, -m, m, m)
        if v["quadrado"]:
            lado = max(caixa.width(), caixa.height())
            c = caixa.center()
            caixa = QRectF(c.x() - lado / 2, c.y() - lado / 2, lado, lado)
        caminho = fm.arredondar(fm.rect_path(caixa), v["raio"])[0] if v["raio"] > 0 else fm.rect_path(caixa)
        camada = sel[0].layer if sel[0].layer in cm.IDS else "C01"
        self.create_shape(caminho, "rect", camada)
        return True

    # ---------- pesquisa de comandos ----------
    def ask_pesquisa(self):
        """Ação escolhida na pesquisa (F4) ou None. Substituível nos testes."""
        from .dialogo_pesquisa import DialogoPesquisa
        dlg = DialogoPesquisa(self)
        return dlg.escolhida if dlg.exec() else None

    def pesquisar_comando(self):
        acao = self.ask_pesquisa()
        if acao is not None:
            acao.trigger()

    def create_shape(self, path, kind, layer="C01"):
        base = self._nome_forma(kind)
        n = 1 + sum(s.name.startswith(base + " ") for s in self.canvas.view.shapes())

        def add():
            scene = self.canvas.scene
            scene.clearSelection()
            s = ob.Shape(path, f"{base} {n}", layer, cm.cor(layer))  # padrão C01; trocar pela paleta
            scene.addItem(s)
            s.setSelected(True)
            self._rebuild_objects()

        self._edit(f"Desenhar {base.lower()}", add)
        # Volta a Selecionar (padrão): a forma nova fica selecionada para ajuste numérico exato.
        if ler_pref(self.settings, "voltar_selecionar"):
            self.tools["select"].setChecked(True)

    def ask_forma(self):
        """(caminho, tipo, camada) ou None. Substituível nos testes."""
        dlg = FormaDialog(self, self._current_layer_id() or "C01")
        return dlg.forma() if dlg.exec() == FormaDialog.Accepted else None

    def _forma_dialogo(self):
        r = self.ask_forma()
        if r:
            self.create_shape(*r)
            b = ob.bounds(self._sel())
            self.statusBar().showMessage(f"Forma inserida: {b.width():.3f} × {b.height():.3f} mm.".replace(".", ","))

    def inserir_frisos(self, f, cam_contorno, cam_frisos) -> bool:
        """Contorno (opcional) + frisos num só passo desfazível. A camada dos frisos fica em Preenchimento
        (traçar só as bordas não rebaixa) e sai ANTES do contorno (frisos antes do recorte externo)."""
        e = fr.erros(f, g.BED_W, g.BED_H)
        if cam_contorno == cam_frisos:
            e.append("contorno e frisos precisam de camadas diferentes")
        if e:
            self.show_error("Frisos não gerados", "; ".join(e).capitalize() + ".")
            return False

        def do():
            scene = self.canvas.scene
            scene.clearSelection()
            itens = [ob.Shape(f.frisos(), f"Frisos ({f.quantidade} × {f.largura_friso_mm:g} mm)".replace(".", ","),
                              cam_frisos, cm.cor(cam_frisos))]
            if cam_contorno:
                itens.insert(0, ob.Shape(f.contorno(), f"Contorno {f.largura_mm:.2f} × {f.altura_mm:g} mm"
                                         .replace(".", ","), cam_contorno, cm.cor(cam_contorno)))
            for it in itens:
                scene.addItem(it)
                it.setSelected(True)
            for lid in filter(None, (cam_frisos, cam_contorno)):
                if self.layer(lid) is None:
                    self.layers.append(cm.nova(lid))
            c = self.layer(cam_frisos)
            if c.modo == "linha":
                self.layers[self.layers.index(c)] = cm.alterar(c, modo="preenchimento")
            if cam_contorno:
                cf, cc = self.layer(cam_frisos), self.layer(cam_contorno)
                if self.layers.index(cf) > self.layers.index(cc):
                    self.layers.remove(cf)
                    self.layers.insert(self.layers.index(cc), cf)
            self._rebuild_objects()

        self._edit("Frisos para dobra", do)
        self._refresh_layers()
        self.statusBar().showMessage(f"{f.quantidade} frisos, passo {f.passo:.6f} mm. Camada {cam_frisos} em "
                                     f"Preenchimento e antes do contorno.".replace(".", ",", 1))
        return True

    def ask_frisos(self):
        """(Frisos, camada do contorno ou None, camada dos frisos) ou None. Substituível nos testes."""
        dlg = FrisosDialog(self)
        return dlg.resultado() if dlg.exec() == FrisosDialog.Accepted else None

    def _frisos_dialogo(self):
        r = self.ask_frisos()
        if r:
            self.inserir_frisos(*r)

    # ---------- organizar: matrizes, encostar, página, distribuir, mesma medida, espelhar na linha ----------
    def ask_valores(self, titulo, campos, nota=""):
        """dict com os valores ou None. Substituível nos testes."""
        dlg = ValoresDialog(self, titulo, campos, nota)
        return dlg.valores() if dlg.exec() == ValoresDialog.Accepted else None

    def _copias(self, snaps, k, incrementar):
        return [ob.from_snapshot(ob.com_peca(sn, k) if incrementar else sn) for sn in snaps]

    def _por_na_cena(self, grupos, agrupar):
        scene = self.canvas.scene
        with self._selecao_em_lote():
            scene.clearSelection()
            for itens in grupos:
                alvo = [ob.group(itens)] if agrupar and len(itens) > 1 else itens
                for it in alvo:
                    scene.addItem(it)
                    it.setSelected(True)
        self._rebuild_objects()

    def matriz_grade(self, v=None) -> bool:
        sel = self._sel()
        if not sel:
            self.statusBar().showMessage("Matriz em grade: selecione o que vai ser repetido.")
            return False
        v = v or self.ask_valores("Matriz em grade", [
            ("colunas", "Colunas", 3, (1, 200, 0, "")), ("linhas", "Linhas", 2, (1, 200, 0, "")),
            ("esp_x", "Espaçamento X", 5.0, (-10000, 10000, 3, " mm")),
            ("esp_y", "Espaçamento Y", 5.0, (-10000, 10000, 3, " mm")),
            ("centro", "Espaçamento de centro a centro (senão: vão entre bordas)", False, None),
            ("desloc_col", "Deslocamento de coluna em Y", 0.0, (-10000, 10000, 3, " mm")),
            ("desloc_lin", "Deslocamento de linha em X", 0.0, (-10000, 10000, 3, " mm")),
            ("espelhar_col", "Espelhar colunas alternadas", False, None),
            ("espelhar_lin", "Espelhar linhas alternadas", False, None),
            ("agrupar", "Agrupar cada cópia", False, None),
            ("incrementar", "Texto variável: cada cópia usa a próxima linha/número", True, None)],
            "A seleção fica na 1ª posição (canto superior esquerdo).")
        if not v:
            return False
        r = ob.bounds(sel)
        px = v["esp_x"] if v["centro"] else r.width() + v["esp_x"]
        py = v["esp_y"] if v["centro"] else r.height() + v["esp_y"]
        snaps = [x.snapshot() for x in sel]

        def do():
            grupos = []
            for lin in range(v["linhas"]):
                for col in range(v["colunas"]):
                    if lin == col == 0:
                        continue
                    itens = self._copias(snaps, lin * v["colunas"] + col, v["incrementar"])
                    if v["espelhar_col"] and col % 2:
                        ob.mirror(itens, True)
                    if v["espelhar_lin"] and lin % 2:
                        ob.mirror(itens, False)
                    ob.move_by(itens, col * px + lin * v["desloc_lin"], lin * py + col * v["desloc_col"])
                    grupos.append(itens)
            self._por_na_cena(grupos, v["agrupar"])
            for x in sel:
                x.setSelected(True)

        self._edit("Matriz em grade", do)
        self.statusBar().showMessage(f"Matriz {v['colunas']} × {v['linhas']}: {v['colunas'] * v['linhas'] - 1} cópia(s).")
        return True

    def matriz_circular(self, v=None) -> bool:
        sel = self._sel()
        if not sel:
            self.statusBar().showMessage("Matriz circular: selecione o que vai ser repetido.")
            return False
        r = ob.bounds(sel)
        v = v or self.ask_valores("Matriz circular", [
            ("quantidade", "Quantidade total (com o original)", 6, (2, 1000, 0, "")),
            ("raio", "Raio (do centro do círculo ao centro da seleção)", round(max(r.width(), r.height()) * 1.5, 1),
             (0.001, 10000, 3, " mm")),
            ("angulo", "Ângulo total", 360.0, (-360, 360, 2, " °")),
            ("girar", "Girar as cópias (acompanhar o círculo)", True, None),
            ("agrupar", "Agrupar cada cópia", False, None),
            ("incrementar", "Texto variável: cada cópia usa a próxima linha/número", True, None)],
            "O centro do círculo fica abaixo da seleção, à distância do raio.")
        if not v:
            return False
        n, total = v["quantidade"], v["angulo"]
        passo = total / (n if abs(total) >= 360 else n - 1)
        c = QPointF(r.center().x(), r.center().y() + v["raio"])
        snaps = [x.snapshot() for x in sel]

        def do():
            grupos = []
            for k in range(1, n):
                itens = self._copias(snaps, k, v["incrementar"])
                if v["girar"]:
                    ob.rotate(itens, passo * k, c)
                else:
                    pos = QTransform().translate(c.x(), c.y()).rotate(passo * k).translate(-c.x(), -c.y()).map(r.center())
                    ob.move_by(itens, pos.x() - r.center().x(), pos.y() - r.center().y())
                grupos.append(itens)
            self._por_na_cena(grupos, v["agrupar"])
            for x in sel:
                x.setSelected(True)

        self._edit("Matriz circular", do)
        return True

    def dois_pontos(self) -> bool:
        """Dimensionar/rotacionar por dois pontos: 1º clique = ponto fixo, 2º = ponto da peça, 3º = onde ele vai."""
        if not self._sel():
            self.statusBar().showMessage("Dois pontos: selecione o que vai girar/escalar.")
            return False
        self.canvas.view.coleta = []
        self.canvas.view.setFocus()
        self.statusBar().showMessage("Dois pontos: clique no ponto FIXO (Esc cancela; os cliques grudam nos cantos).")
        return True

    def _ponto_coletado(self, n, p):
        view = self.canvas.view
        if n == 0:
            self.statusBar().showMessage("Dois pontos: cancelado.")
            return
        if n == 1:
            self.statusBar().showMessage("Dois pontos: clique num ponto da peça (referência).")
            return
        if n == 2:
            self.statusBar().showMessage("Dois pontos: clique onde a referência deve ficar.")
            return
        a, b, c = view.coleta
        view.coleta = None
        view.snap_ind.set_alvo(None)
        self.aplicar_dois_pontos(a, b, c)

    def aplicar_dois_pontos(self, fixo, ref, alvo) -> bool:
        """Gira e escala a seleção em volta de `fixo` para que `ref` vá para `alvo` (escala igual em X e Y)."""
        rx, ry = ref.x() - fixo.x(), ref.y() - fixo.y()
        ax, ay = alvo.x() - fixo.x(), alvo.y() - fixo.y()
        d0, d1 = math.hypot(rx, ry), math.hypot(ax, ay)
        if d0 < 1e-6 or d1 < 1e-6:
            self.statusBar().showMessage("Dois pontos: os pontos coincidem com o ponto fixo; nada feito.")
            return False
        ang = math.degrees(math.atan2(ay, ax) - math.atan2(ry, rx))
        k = d1 / d0
        sel = self._sel()

        def fazer():
            ob.rotate(sel, ang, fixo)
            ob.scale(sel, k, k, fixo)
        self._edit("Dimensionar/rotacionar por dois pontos", fazer)
        self.statusBar().showMessage(f"Dois pontos: girou {ang:+.2f}° e escalou {k * 100:.2f} %".replace(".", ","))
        return True

    def redimensionar_slots(self, v=None) -> bool:
        """Troca a largura dos encaixes (slots e furos retangulares) das formas selecionadas, centrados."""
        formas = [s for s in self._sel() if type(s) is ob.Shape and not s.bloqueado]
        if not formas:
            self.statusBar().showMessage("Redimensionar slots: selecione formas (textos e imagens não têm slots).")
            return False
        v = v or self.ask_valores("Redimensionar slots", [
            ("largura", "Largura atual dos slots", 3.0, (0.01, 1000, 3, " mm")),
            ("nova", "Nova largura (ex.: espessura real da chapa)", 3.0, (0.01, 1000, 3, " mm")),
            ("tol", "Tolerância para achar a largura atual", 0.05, (0.0, 5, 3, " mm"))],
            "Acha encaixes retos com a largura atual (fundo reto e duas paredes paralelas) e muda para a nova, "
            "mantendo o centro. Meça a espessura da chapa com paquímetro e some a folga desejada.")
        if not v:
            return False
        trocas, total = [], 0
        for s in formas:
            try:
                novo, n = rnh.redimensionar(s.sceneTransform().map(s.path()), v["largura"], v["nova"], v["tol"])
            except ValueError as e:
                self.show_error("Redimensionar slots", str(e))
                return False
            if n:
                trocas.append((s, novo))
                total += n
        if not trocas:
            self.statusBar().showMessage(f"Redimensionar slots: nenhum slot de {v['largura']:g} mm encontrado.")
            return False
        self._trocar_por_caminhos([s for s, _ in trocas], [(p, s.name, s.layer) for s, p in trocas],
                                  "Redimensionar slots")
        self.statusBar().showMessage(f"Redimensionar slots: {total} slot(s) de {v['largura']:g} → {v['nova']:g} mm.")
        return True

    def reunir(self, horizontal: bool) -> bool:
        """Reunir em H/V: encosta as peças selecionadas umas nas outras (sem vão), na ordem em que estão,
        a partir da primeira (mais à esquerda / mais acima); a outra coordenada não muda."""
        sel = [s for s in self._sel() if not s.bloqueado]
        if len(sel) < 2:
            self.statusBar().showMessage("Reunir: selecione 2 ou mais objetos.")
            return False

        def fazer():
            ordem = sorted(sel, key=lambda s: ob.geom_rect(s).left() if horizontal else ob.geom_rect(s).top())
            r0 = ob.geom_rect(ordem[0])
            borda = r0.right() if horizontal else r0.bottom()
            for s in ordem[1:]:
                r = ob.geom_rect(s)
                if horizontal:
                    ob.move_by([s], borda - r.left(), 0)
                    borda += r.width()
                else:
                    ob.move_by([s], 0, borda - r.top())
                    borda += r.height()
        self._edit("Reunir em " + ("H" if horizontal else "V"), fazer)
        return True

    def dispor_na_mesa(self, v=None) -> bool:
        """Disposição automática: arruma a seleção (ou tudo) na mesa sem sobrepor, com vão e margem.
        Objetos não envolvidos e bloqueados ficam onde estão e são contornados."""
        shapes = [s for s in self.canvas.view.shapes() if s.isVisible()]
        alvo = [s for s in (self._sel() or shapes) if not s.bloqueado]
        if not alvo:
            self.statusBar().showMessage("Disposição automática: nada para arrumar (objetos bloqueados ficam).")
            return False
        v = v or self.ask_valores("Disposição automática na mesa", [
            ("espaco", "Espaço entre as peças", 2.0, (0, 100, 2, " mm")),
            ("margem", "Margem até a borda da mesa", 2.0, (0, 500, 2, " mm")),
            ("girar", "Permitir girar 90° para aproveitar melhor", True, None)],
            "Arruma a seleção (sem seleção: todos os objetos) pelo retângulo de cada peça, das maiores para as "
            "menores. Objetos não selecionados e bloqueados não se movem e são contornados. Peças que não "
            "couberem ficam onde estão.")
        if not v:
            return False
        ids = set(map(id, alvo))
        ocup = [ob.geom_rect(s) for s in shapes if id(s) not in ids]
        rects = [ob.geom_rect(s) for s in alvo]
        try:
            pos = dsp.dispor([(r.width(), r.height()) for r in rects], g.BED_W, g.BED_H, v["espaco"], v["margem"],
                             v["girar"], [(o.x(), o.y(), o.width(), o.height()) for o in ocup])
        except ValueError as e:
            self.show_error("Disposição automática", str(e))
            return False

        def fazer():
            for s, p in zip(alvo, pos):
                if p is None:
                    continue
                x, y, girada = p
                if girada:
                    ob.rotate([s], 90, ob.geom_rect(s).center())
                r = ob.geom_rect(s)
                ob.move_by([s], x - r.left(), y - r.top())
        self._edit("Disposição automática", fazer)
        fora = sum(p is None for p in pos)
        self.statusBar().showMessage(f"Disposição automática: {len(pos) - fora} peça(s) arrumada(s)"
                                     + (f"; {fora} não couberam e ficaram onde estavam." if fora else "."))
        return True

    def encostar(self, lado) -> bool:
        """Empurra a seleção até encostar no objeto mais próximo daquele lado (ou na borda da mesa)."""
        sel = self._sel()
        if not sel:
            return False
        R = ob.bounds(sel)
        ids = set(map(id, sel))
        obst = [ob.geom_rect(o) for o in self.canvas.view.shapes() if id(o) not in ids and o.isVisible()]
        e = 1e-9
        if lado in ("esquerda", "direita"):
            faixa = [o for o in obst if o.top() < R.bottom() - e and o.bottom() > R.top() + e]
            if lado == "esquerda":
                lim = max([o.right() for o in faixa if o.right() <= R.left() + e] + [0.0])
                d = (lim - R.left(), 0)
            else:
                lim = min([o.left() for o in faixa if o.left() >= R.right() - e] + [float(g.BED_W)])
                d = (lim - R.right(), 0)
        else:
            faixa = [o for o in obst if o.left() < R.right() - e and o.right() > R.left() + e]
            if lado == "cima":
                lim = max([o.bottom() for o in faixa if o.bottom() <= R.top() + e] + [0.0])
                d = (0, lim - R.top())
            else:
                lim = min([o.top() for o in faixa if o.top() >= R.bottom() - e] + [float(g.BED_H)])
                d = (0, lim - R.bottom())
        if abs(d[0]) + abs(d[1]) < 1e-9:
            return False
        self._edit("Encostar", lambda: ob.move_by(sel, *d))
        return True

    def mover_para_pagina(self, idx) -> bool:
        """Ponto idx (0 = canto superior esquerdo … 8 = inferior direito) da seleção vai ao mesmo ponto da mesa."""
        sel = self._sel()
        if not sel:
            return False
        alvo = ob.anchor_point(QRectF(0, 0, g.BED_W, g.BED_H), idx)
        p = ob.anchor_point(ob.bounds(sel), idx)
        self._edit("Mover para a página", lambda: ob.move_by(sel, alvo.x() - p.x(), alvo.y() - p.y()))
        return True

    def distribuir_espacado(self, horizontal) -> bool:
        """Vãos iguais entre as bordas dos objetos (o primeiro e o último ficam onde estão)."""
        sel = self._sel()
        if len(sel) < 3:
            self.statusBar().showMessage("Distribuir espaçado: selecione 3 ou mais objetos.")
            return False
        ini = (lambda b: b.left()) if horizontal else (lambda b: b.top())
        tam = (lambda b: b.width()) if horizontal else (lambda b: b.height())
        itens = sorted(sel, key=lambda x: ini(ob.geom_rect(x)))
        bs = [ob.geom_rect(x) for x in itens]
        vao = (ini(bs[-1]) + tam(bs[-1]) - ini(bs[0]) - sum(tam(b) for b in bs)) / (len(bs) - 1)

        def do():
            pos = ini(bs[0]) + tam(bs[0]) + vao
            for x, b in zip(itens[1:-1], bs[1:-1]):
                d = pos - ini(b)
                ob.move_by([x], d if horizontal else 0, 0 if horizontal else d)
                pos += tam(b) + vao

        self._edit("Distribuir espaçado", do)
        return True

    def mesma_medida(self, largura) -> bool:
        """Todos com a largura (ou altura) do primeiro objeto clicado; proporção conforme o cadeado."""
        sel = self._sel_ordem()
        if len(sel) < 2:
            self.statusBar().showMessage("Selecione 2 ou mais objetos (o primeiro clicado é a referência).")
            return False
        ref = ob.geom_rect(sel[0])

        def do():
            for x in sel[1:]:
                b = ob.geom_rect(x)
                if largura and b.width() > ob.EPS:
                    w, h = ref.width(), (b.height() * ref.width() / b.width() if self.lock.isChecked() else b.height())
                elif not largura and b.height() > ob.EPS:
                    w, h = (b.width() * ref.height() / b.height() if self.lock.isChecked() else b.width()), ref.height()
                else:
                    continue
                ob.set_size([x], w, h, 4)

        self._edit("Mesma largura" if largura else "Mesma altura", do)
        return True

    def alinhar_centros(self) -> bool:
        sel = self._sel()
        if len(sel) < 2:
            return False

        def do():
            ob.align(sel, "hcenter")
            ob.align(sel, "vcenter")

        self._edit("Alinhar centros", do)
        return True

    def espelhar_na_linha(self) -> bool:
        """Espelha a seleção em relação à linha selecionada por último (que fica como está)."""
        sel = self._sel_ordem()
        if len(sel) < 2:
            self.statusBar().showMessage("Selecione os objetos e, por último, a linha do espelho.")
            return False
        linha = sel[-1].sceneTransform().map(sel[-1].path())
        pts = [linha.elementAt(i) for i in range(linha.elementCount())]
        if len(pts) < 2:
            return False
        a, b = QPointF(pts[0].x, pts[0].y), QPointF(pts[-1].x, pts[-1].y)
        if (b - a).manhattanLength() < 1e-9:  # contorno fechado: usa o 1º segmento
            b = QPointF(pts[1].x, pts[1].y)
        ang = math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))
        m = (QTransform.fromTranslate(-a.x(), -a.y()) * QTransform().rotate(-ang) * QTransform.fromScale(1, -1)
             * QTransform().rotate(ang) * QTransform.fromTranslate(a.x(), a.y()))
        self._edit("Espelhar ao longo da linha", lambda: ob.apply(sel[:-1], m))
        return True

    def autoagrupar(self) -> int:
        """Cada objeto que não está dentro de outro vira um grupo com tudo o que está dentro dele."""
        sel = [s for s in self._sel_ordem() if not isinstance(s, ob.ImageShape)]
        if len(sel) < 2:
            return 0
        cena = {id(s): s.sceneTransform().map(s.path()) for s in sel}
        caixa = {id(s): cena[id(s)].boundingRect() for s in sel}

        def dentro(a, b):  # a dentro de b (área)
            return (a is not b and caixa[id(b)].contains(caixa[id(a)])
                    and cena[id(b)].contains(cena[id(a)].pointAtPercent(0)))
        externos = [s for s in sel if not any(dentro(s, o) for o in sel)]
        grupos = [(e, [x for x in sel if x is e or dentro(x, e)]) for e in externos]
        grupos = [(e, g) for e, g in grupos if len(g) > 1]
        if not grupos:
            self.statusBar().showMessage("Nada para agrupar: nenhum objeto dentro de outro.")
            return 0

        def do():
            scene = self.canvas.scene
            usados = set()
            scene.clearSelection()
            for e, membros in grupos:
                membros = [m for m in membros if id(m) not in usados]
                if len(membros) < 2:
                    continue
                usados.update(map(id, membros))
                grp = ob.group(membros)
                grp.name = f"Grupo: {e.name}"
                for m in membros:
                    scene.removeItem(m)
                scene.addItem(grp)
                grp.setSelected(True)
            self._rebuild_objects()

        self._edit("Autoagrupar", do)
        self.statusBar().showMessage(f"{len(grupos)} grupo(s) criado(s).")
        return len(grupos)

    def contorno_elastico(self) -> bool:
        """Contorno convexo (como um elástico) em volta de tudo que está selecionado."""
        sel = self._sel()
        pts = sorted({(round(q.x(), 9), round(q.y(), 9)) for s in sel
                      for poly in s.sceneTransform().map(s.path()).toSubpathPolygons() for q in poly})
        if len(pts) < 3:
            return False

        def cruz(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        baixo, cima = [], []
        for pt in pts:
            while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], pt) <= 0:
                baixo.pop()
            baixo.append(pt)
        for pt in reversed(pts):
            while len(cima) >= 2 and cruz(cima[-2], cima[-1], pt) <= 0:
                cima.pop()
            cima.append(pt)
        casco = baixo[:-1] + cima[:-1]
        path = fm.polyline_path([QPointF(*q) for q in casco], closed=True)
        lid = sel[0].layer if sel[0].layer in cm.IDS else "C01"
        self._trocar_por_caminhos([], [(path, "Contorno elástico", lid)], "Contorno elástico")
        return True

    def cisalhar(self, v=None) -> bool:
        sel = self._sel()
        if not sel:
            return False
        v = v or self.ask_valores("Cisalhar", [("ax", "Inclinação horizontal", 15.0, (-80, 80, 2, " °")),
                                               ("ay", "Inclinação vertical", 0.0, (-80, 80, 2, " °"))],
                                  "Em torno do ponto escolhido no seletor de 9 pontos.")
        if not v:
            return False
        c = ob.anchor_point(ob.bounds(sel), self.anchor)
        t = QTransform(1, math.tan(math.radians(v["ay"])), math.tan(math.radians(v["ax"])), 1, 0, 0)
        m = QTransform.fromTranslate(-c.x(), -c.y()) * t * QTransform.fromTranslate(c.x(), c.y())
        self._edit("Cisalhar", lambda: ob.apply(sel, m))
        return True

    def copiar_ao_longo(self, v=None) -> bool:
        """Cópias da seleção distribuídas ao longo do caminho selecionado por último."""
        sel = self._sel_ordem()
        if len(sel) < 2:
            self.statusBar().showMessage("Selecione o que copiar e, por último, o caminho.")
            return False
        guia, objs = sel[-1], sel[:-1]
        poly = [(q.x(), q.y()) for q in guia.sceneTransform().map(guia.path()).toSubpathPolygons(
            QTransform.fromScale(20, 20))[0]]
        poly = [(x / 20, y / 20) for x, y in poly]
        cum = [0.0]
        for a, b in zip(poly, poly[1:]):
            cum.append(cum[-1] + math.dist(a, b))
        L = cum[-1]
        if L <= 0:
            return False
        fechado = math.dist(poly[0], poly[-1]) < 1e-6
        v = v or self.ask_valores("Copiar ao longo do caminho", [
            ("quantidade", "Quantidade de cópias", 6, (1, 1000, 0, "")),
            ("girar", "Girar acompanhando o caminho", True, None),
            ("incrementar", "Texto variável: cada cópia usa a próxima linha/número", True, None)],
            "O caminho é o último objeto clicado; as cópias ficam igualmente espaçadas.")
        if not v:
            return False
        n = v["quantidade"]
        r = ob.bounds(objs)
        snaps = [x.snapshot() for x in objs]

        def no_caminho(dist):
            for i in range(len(cum) - 1):
                if cum[i] - 1e-9 <= dist <= cum[i + 1] + 1e-9:
                    a, b = poly[i], poly[i + 1]
                    seg = cum[i + 1] - cum[i]
                    t = 0 if seg < 1e-12 else (dist - cum[i]) / seg
                    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.degrees(
                        math.atan2(b[1] - a[1], b[0] - a[0]))
            return poly[-1], 0.0

        def do():
            grupos = []
            for k in range(n):
                dist = L * k / (n if fechado else max(n - 1, 1)) if n > 1 else L / 2
                (x, y), ang = no_caminho(dist)
                itens = self._copias(snaps, k + 1, v["incrementar"])
                ob.move_by(itens, x - r.center().x(), y - r.center().y())
                if v["girar"]:
                    ob.rotate(itens, ang, QPointF(x, y))
                grupos.append(itens)
            self._por_na_cena(grupos, False)

        self._edit("Copiar ao longo do caminho", do)
        return True

    def criar_qr(self, v=None) -> bool:
        v = v or self.ask_valores("Criar código QR", [
            ("texto", "Conteúdo (link, texto…)", "https://", None),
            ("lado", "Lado do símbolo", 30.0, (5, 400, 2, " mm")),
            ("camada", "Camada", self._current_layer_id() or "C01", [(i, i) for i in cm.IDS])],
            "Correção de erros nível M. Deixe uma margem livre de 4 módulos em volta para a leitura. "
            "Grave em camada de Preenchimento.")
        if not v or not v["texto"].strip():
            return False
        try:
            path = qrcode_rb.caminho(v["texto"], v["lado"])
        except qrcode_rb.TextoLongoDemais as e:
            self.show_error("Código QR", str(e))
            return False
        path.translate((g.BED_W - v["lado"]) / 2, (g.BED_H - v["lado"]) / 2)
        nome = "QR: " + v["texto"][:30] + ("…" if len(v["texto"]) > 30 else "")
        self._trocar_por_caminhos([], [(path, nome, v["camada"])], "Criar código QR")
        return True

    def criar_ean13(self, v=None) -> bool:
        v = v or self.ask_valores("Criar código de barras EAN-13", [
            ("numero", "Número (12 dígitos; o 13º é calculado)", "", None),
            ("largura", "Largura das barras", 31.35, (10, 400, 2, " mm")),
            ("altura", "Altura das barras", 22.85, (3, 400, 2, " mm")),
            ("legenda", "Escrever os números embaixo", True, None),
            ("camada", "Camada", self._current_layer_id() or "C01", [(i, i) for i in cm.IDS])],
            "Tamanho padrão (100 %): 31,35 × 22,85 mm. Deixe margem clara dos lados. Grave em Preenchimento.")
        if not v:
            return False
        try:
            bits, completo = cbar.barras(v["numero"])
        except cbar.NumeroInvalido as e:
            self.show_error("Código de barras", str(e))
            return False
        path = cbar.caminho(completo, v["largura"], v["altura"])
        x0, y0 = (g.BED_W - v["largura"]) / 2, (g.BED_H - v["altura"]) / 2
        path.translate(x0, y0)
        novos = [(path, f"EAN-13 {completo}", v["camada"])]
        if v["legenda"]:
            alt = max(1.0, v["largura"] / 95 * 7)  # números com ~7 módulos de altura
            txt = tx.build_path(tx.TextoParams(f"{completo[0]}  {completo[1:7]}  {completo[7:]}", self.default_font(),
                                               alt, alinhamento="centro"))
            b = txt.boundingRect()
            txt.translate(g.BED_W / 2 - b.center().x(), y0 + v["altura"] + alt * 0.4 - b.top())
            novos.append((txt, f"EAN-13 {completo} (números)", v["camada"]))
        self._trocar_por_caminhos([], novos, "Criar código de barras")
        return True

    # ---------- booleanas e deslocamento ----------
    def _sel_ordem(self):
        """Selecionados na ordem em que foram clicados (o 1º é a base; o último, o cortador)."""
        sel = list(dict.fromkeys(s for s in self.canvas.view.ordem_sel if s.isSelected()))  # sem repetidos
        return sel + [s for s in self._sel() if s not in sel]

    def _vetoriais(self, itens):
        return [s for s in itens if not isinstance(s, ob.ImageShape)]

    def _trocar_por_caminhos(self, remover, novos, texto):
        """novos: [(caminho em mm de cena, nome, camada)]; remove `remover`; resultado fica selecionado."""
        def do():
            scene = self.canvas.scene
            for s in remover:
                scene.removeItem(s)
            scene.clearSelection()
            for path, nome, lid in novos:
                it = ob.Shape(path, nome, lid, cm.cor(lid))
                scene.addItem(it)
                it.setSelected(True)
            self._rebuild_objects()

        self._edit(texto, do)

    def booleana(self, tipo) -> bool:
        """tipo: "solda", "uniao", "subtrair", "intersecao", "cortar" (cortador de biscoito)."""
        sel = self._vetoriais(self._sel_ordem())
        minimo = 1 if tipo == "solda" else 2
        nomes = {"solda": "Solda", "uniao": "União", "subtrair": "Subtração", "intersecao": "Interseção",
                 "cortar": "Corte", "macho": "Solda macho", "femea": "Solda fêmea"}
        if len(sel) < minimo:
            self.statusBar().showMessage(f"{nomes[tipo]}: selecione {minimo} ou mais formas fechadas "
                                         "(imagens não entram).")
            return False
        paths = [s.sceneTransform().map(s.path()) for s in sel]
        if not all(bo.fechado(p) for p in paths):
            self.show_error(nomes[tipo], "Operações booleanas só funcionam com formas fechadas. Feche os caminhos "
                            "(Editar → Fechar caminho) ou desmarque as linhas abertas.")
            return False
        base = sel[0]
        if tipo == "femea":  # a maior é a base; as que encostam nela abrem o rasgo e somem
            i_base = max(range(len(sel)), key=lambda i: abs(_area_caminho(paths[i])))
            base = sel[i_base]
            cortam = [i for i in range(len(sel)) if i != i_base and paths[i].intersects(paths[i_base])]
            if not cortam:
                self.statusBar().showMessage("Solda fêmea: as formas menores não encostam na maior — nada para "
                                             "recortar.")
                return False
            res = [(bo.subtrair(paths[i_base], [paths[i] for i in cortam]), base.name, base.layer)]
            remover = [base] + [sel[i] for i in cortam]
        elif tipo in ("solda", "uniao", "macho"):
            # Peça inteira dentro de outra (texto, furo, gravação em cima da placa) não entra na união: ficaria
            # engolida. Só se juntam as que se sobrepõem de verdade.
            dentro = {i for i, p in enumerate(paths) for j, q in enumerate(paths)
                      if i != j and q.contains(p) and not _cruza(p, q)}
            juntar = [i for i in range(len(sel)) if i not in dentro]
            if len(juntar) < minimo or (tipo in ("uniao", "macho") and len(juntar) < 2):
                self.statusBar().showMessage(f"{nomes[tipo]}: as outras peças estão inteiras dentro da maior e "
                                             "ficam como estão — nada para juntar.")
                return False
            base = sel[juntar[0]]
            res = [(bo.uniao([paths[i] for i in juntar]), nomes[tipo], base.layer)]
            remover = [sel[i] for i in juntar]
        elif tipo == "subtrair":
            res = [(bo.subtrair(paths[0], paths[1:]), f"{base.name} − {len(paths) - 1}", base.layer)]
            remover = sel
        elif tipo == "intersecao":
            res = [(bo.intersecao(paths), nomes[tipo], base.layer)]
            remover = sel
        else:  # cortar: o último selecionado corta os demais; ele mesmo continua
            cortador, alvos = sel[-1], sel[:-1]
            res = [(parte, f"{s.name} ({k})", s.layer)
                   for s, p in zip(alvos, paths) for k, parte in enumerate(bo.cortar(p, paths[-1]), 1)]
            remover = alvos
        res = [x for x in res if not x[0].isEmpty()]
        if not res:
            self.statusBar().showMessage(f"{nomes[tipo]}: o resultado ficou vazio (as formas não se sobrepõem?).")
            return False
        self._trocar_por_caminhos(remover, res, nomes[tipo])
        ficaram = len(sel) - len(remover) if tipo in ("solda", "uniao", "macho", "femea") else 0
        self.statusBar().showMessage(f"{nomes[tipo]}: {len(res)} forma(s) resultante(s)."
                                     + (f" {ficaram} peça(s) de dentro ficaram como estavam." if ficaram else ""))
        return True

    # ---------- edição de nós por teclas ----------
    def _aviso_nos(self):
        """Editar nós só funciona numa forma comum: explica o que fazer com grupo, texto e imagem."""
        sel = self._sel()
        if len(sel) != 1:
            msg = "Editar nós: selecione uma forma."
        elif isinstance(sel[0], ob.GroupShape):
            msg = ("Editar nós: isto é um GRUPO. Desagrupe primeiro (Ctrl+U ou botão direito → Desagrupar) e "
                   "selecione a peça.")
        elif isinstance(sel[0], ob.TextShape):
            msg = "Editar nós: isto é um TEXTO. Converta em curvas (Ctrl+Shift+C) para editar os nós."
        elif isinstance(sel[0], ob.ImageShape):
            msg = "Editar nós: imagens não têm nós."
        else:
            msg = ("Editar nós: arraste os quadrados (nós) e as bolinhas (alças das curvas). Sobre um trecho: L troca "
                   "reta/curva, I insere nó, D exclui.")
        self.statusBar().showMessage(msg, 15000)
        return msg

    def operacao_no(self, tecla, ponto) -> bool:
        """Editar nós: D exclui nó (ou o trecho), I insere nó no ponto, M insere no meio do trecho, L trecho em
        reta, C nó em canto, S nó suave, B quebra no nó. Age no objeto em edição, no que estiver sob o cursor."""
        view = self.canvas.view
        item = view.node_overlay.item
        if item is None:
            return False
        inv, ok = item.sceneTransform().inverted()
        if not ok:
            return False
        local = inv.map(ponto)
        escala = ob.escala_uniforme(item) or 1.0
        alvo = nos.localizar(item.path(), (local.x(), local.y()), 8 / view.scale_px_mm / escala)
        if alvo is None:
            self.statusBar().showMessage("Editar nós: coloque o cursor sobre um nó ou trecho e tecle D, I, M, L, C, S ou B.")
            return False
        p = item.path()
        if alvo[0] == "no":
            _, ci, k = alvo
            novo = {"D": lambda: nos.excluir_no(p, ci, k), "C": lambda: nos.em_canto(p, ci, k),
                    "S": lambda: nos.suavizar(p, ci, k),
                    "B": lambda: nos.quebrar(p, ci, k)}.get(tecla)
        else:
            _, ci, k, t = alvo
            novo = {"D": lambda: nos.excluir_seg(p, ci, k), "I": lambda: nos.inserir_no(p, ci, k, t),
                    "M": lambda: nos.inserir_no(p, ci, k, 0.5),
                    "L": lambda: nos.alternar_reta_curva(p, ci, k)}.get(tecla)
        if novo is None:
            return False
        caminho = novo()
        nomes = {"D": "Excluir nó", "I": "Inserir nó", "M": "Inserir nó no meio", "L": "Trecho reta/curva",
                 "C": "Nó em canto", "S": "Nó suave", "B": "Quebrar no nó"}

        def do():
            if caminho.isEmpty():
                self.canvas.scene.removeItem(item)
            else:
                item.setPath(caminho)
            self._rebuild_objects()

        self._edit(nomes[tecla], do)
        view.refresh_selection()
        return True

    # ---------- aparar (tesoura) ----------
    def _aparo(self, ponto):
        """(objeto, novo caminho, trecho removido) para um clique da tesoura, ou None."""
        view = self.canvas.view
        tol = 6 / view.scale_px_mm  # 6 px na tela
        cands = [s for s in view.shapes() if s.isVisible() and type(s) is ob.Shape
                 and ob.geom_rect(s).adjusted(-tol, -tol, tol, tol).contains(ponto)]
        melhor = None
        for s in cands:
            cena = s.sceneTransform().map(s.path())
            caixa = cena.boundingRect().adjusted(-tol, -tol, tol, tol)
            outros = [o.sceneTransform().map(o.path()) for o in view.shapes()
                      if o is not s and o.isVisible() and not isinstance(o, ob.ImageShape)
                      and ob.geom_rect(o).intersects(caixa)]
            r = apr.aparar(cena, outros, ponto, tol)
            if r is not None:
                d = r[1].boundingRect()
                if melhor is None or d.width() + d.height() < melhor[3]:
                    melhor = (s, r[0], r[1], d.width() + d.height())
        return melhor[:3] if melhor else None

    def _aparo_realce(self, ponto):
        r = self._aparo(ponto)
        self.canvas.view.realcar(r[2] if r else None)

    def aparar_em(self, ponto) -> bool:
        r = self._aparo(ponto)
        if r is None:
            return False
        s, novo, _ = r

        def do():
            if novo.isEmpty():
                self.canvas.scene.removeItem(s)
            else:
                s.setPos(0, 0)
                s.setTransform(QTransform())
                s.setPath(novo)
            self._rebuild_objects()

        self._edit("Aparar", do)
        self.canvas.view.realcar(None)
        return True

    def ask_deslocar(self):
        """(distância, direção, canto, apagar originais) ou None. Substituível nos testes."""
        dlg = DeslocarDialog(self, self._ultimo_desloc)
        return dlg.valores() if dlg.exec() == DeslocarDialog.Accepted else None

    def deslocar_formas(self, valores=None) -> bool:
        sel = self._vetoriais(self._sel())
        if not sel:
            self.statusBar().showMessage("Deslocar formas: selecione uma ou mais formas.")
            return False
        valores = valores or self.ask_deslocar()
        if not valores:
            return False
        self._ultimo_desloc = valores
        dist, direcao, canto, apagar = valores
        novos = []
        for s in sel:
            p = bo.deslocar(s.sceneTransform().map(s.path()), dist, direcao, canto)
            if not p.isEmpty():
                novos.append((p, f"{s.name} desloc. {dist:g} mm".replace(".", ","), s.layer))
        if not novos:
            self.statusBar().showMessage("Deslocar para dentro sumiu com as formas (distância maior que a peça).")
            return False
        self._trocar_por_caminhos(sel if apagar else [], novos, "Deslocar formas")
        return True

    def duplicate(self):
        """Cópia no mesmo lugar (como a referência); não usa a área de transferência."""
        sel = self._sel()
        if not sel:
            return

        def do():
            scene = self.canvas.scene
            copias = [ob.from_snapshot(s.snapshot(), f"{s.name} (cópia)") for s in sel]
            scene.clearSelection()
            for c in copias:
                scene.addItem(c)
                c.setSelected(True)
            self._rebuild_objects()

        self._edit("Duplicar", do)
        self.statusBar().showMessage(f"{len(sel)} objeto(s) duplicado(s) no mesmo lugar — arraste ou use as setas.")

    # ---------- gabarito e produção em lote na mesa ----------
    def definir_gabarito(self, gb) -> bool:
        """Mostra/troca o gabarito (None remove). Desfazível; recusa grade fora da mesa."""
        if gb is not None and (e := gbm.erros(gb, g.BED_W, g.BED_H)):
            self.show_error("Gabarito inválido", "; ".join(e).capitalize() + ".")
            return False
        if gb == self.gabarito:
            return True
        self._edit("Gabarito" if gb else "Remover gabarito", lambda: setattr(self, "gabarito", gb))
        self.canvas.view.gabarito_overlay.set_gabarito(self.gabarito)
        return True

    def ask_gabarito(self, inicial, tamanho_sel):
        """Abre o diálogo; devolve Gabarito ou None. Substituível nos testes."""
        dlg = GabaritoDialog(self, inicial, self.settings, tamanho_sel)
        return dlg.gabarito() if dlg.exec() == GabaritoDialog.Accepted else None

    def _gabarito_dialogo(self):
        sel = self._sel()
        r = ob.bounds(sel) if sel else None
        gb = self.ask_gabarito(self.gabarito or gbm.Gabarito(), (r.width(), r.height()) if r else None)
        if gb is not None and self.definir_gabarito(gb):
            self.statusBar().showMessage(f"Gabarito com {gb.total} célula(s). Selecione o desenho e use "
                                         "Produção → Preencher gabarito.")

    def preencher_gabarito(self) -> bool:
        """Uma cópia da seleção centrada em cada célula; textos variáveis viram peça 1, 2, 3…

        A seleção original é substituída pelas cópias (desfazível). Cada cópia usa a linha atual + k
        da planilha; "Próxima mesa" avança todas de uma vez.
        """
        gb, sel = self.gabarito, self._sel()
        if gb is None:
            self.statusBar().showMessage("Defina um gabarito primeiro (Produção → Gabarito na mesa…).")
            return False
        if not sel:
            self.statusBar().showMessage("Selecione o desenho que vai em cada célula do gabarito.")
            return False
        r = ob.bounds(sel)
        snaps = [s.snapshot() for s in sel]
        teste = [ob.from_snapshot(sn) for sn in snaps]
        ob.rotate(teste, gb.giro_graus, r.center())
        rg = ob.bounds(teste)  # caixa já girada: é ela que precisa caber e ficar centrada
        if rg.width() > gb.largura_mm + 1e-6 or rg.height() > gb.altura_mm + 1e-6:
            girado = f" (girada {gb.giro_graus:g}°)" if gb.giro_graus else ""
            self.show_error("Desenho maior que a célula",
                            f"A seleção{girado} tem {rg.width():.1f} × {rg.height():.1f} mm e a célula "
                            f"{gb.largura_mm:.1f} × {gb.altura_mm:.1f} mm. Diminua o desenho ou aumente a célula."
                            .replace(".", ","))
            return False

        def do():
            scene = self.canvas.scene
            for s in sel:
                scene.removeItem(s)
            scene.clearSelection()
            for k, (x, y, w, h) in enumerate(gb.celulas()):
                itens = [ob.from_snapshot(ob.com_peca(sn, k)) for sn in snaps]
                ob.rotate(itens, gb.giro_graus, r.center())
                ob.move_by(itens, x + w / 2 - rg.center().x(), y + h / 2 - rg.center().y())
                item = ob.group(itens) if len(itens) > 1 else itens[0]
                item.name = f"Peça {k + 1:03d}" + ("" if len(itens) > 1 else f" — {itens[0].name}")
                scene.addItem(item)
                item.setSelected(True)
            self._rebuild_objects()

        self._edit("Preencher gabarito", do)
        sem = sum(self.vars.sem_dados(k) for k in range(gb.total))
        self.statusBar().showMessage(f"{gb.total} peça(s) no gabarito" + (
            f"; {sem} sem linha na planilha (não vão para o laser)." if sem else "."))
        return True

    # ---------- bolear ----------
    RAIO_BOLEAR_PADRAO = 5.0

    def _bolear_calculo(self, ponto, total):
        """(objeto, novo caminho local, quantos cantos, raio mm, só um canto?) para um clique em `ponto` — ou None."""
        view = self.canvas.view
        alvo, _ = view._mais_de_dentro(view.mapFromScene(ponto))
        if alvo is None or type(alvo) is not ob.Shape or alvo.bloqueado:
            return None
        escala = ob.escala_uniforme(alvo) or ob._escala_item(alvo)
        local = alvo.mapFromScene(ponto)
        if total:  # pontas totalmente redondas: raio = metade do lado menor
            r_local = min(alvo.path().boundingRect().width(), alvo.path().boundingRect().height()) / 2
            novo, n = nos.bolear(alvo.path(), r_local)
            return (alvo, novo, n, r_local * escala, False) if n else None
        r_mm = self.raio.value() or self.RAIO_BOLEAR_PADRAO
        tol = 12 / view.scale_px_mm / escala
        perto = lambda pt: math.hypot(pt[0] - local.x(), pt[1] - local.y()) <= tol  # noqa: E731
        redondo = next(((ci, k) for ci, k, pt in nos.cantos_redondos(alvo.path()) if perto(pt)), None)
        if redondo:  # 2º clique no canto: vira 45°
            return alvo, nos.chanfrar(alvo.path(), *redondo), 1, r_mm, "chanfro"
        chanfro = next(((ci, k) for ci, k, pt in nos.chanfros(alvo.path()) if perto(pt)), None)
        if chanfro:  # 3º clique: volta a canto vivo
            novo = nos.canto_vivo(alvo.path(), *chanfro)
            return (alvo, novo, 1, r_mm, "vivo") if novo is not None else None
        cantos = [(ci, k, pt) for ci, k, pt in nos.cantos_boleaveis(alvo.path())
                  if math.hypot(pt[0] - local.x(), pt[1] - local.y()) <= tol]
        alvos = [min(cantos, key=lambda c: math.hypot(c[2][0] - local.x(), c[2][1] - local.y()))[:2]] if cantos else None
        novo, n = nos.bolear(alvo.path(), r_mm / escala, alvos)
        return (alvo, novo, n, r_mm, bool(cantos)) if n else None

    def _raio_bolear_mudou(self, v):
        """O campo abaixo do botão e o "Raio do bolear" da barra são o mesmo valor; a prévia acompanha."""
        if self.tools["bolear"].isChecked() and abs(self.raio.value() - v) > 1e-9:
            self.raio.blockSignals(True)
            self.raio.setValue(v)
            self.raio.blockSignals(False)
            if getattr(self, "_bolear_ultimo", None):
                self._bolear_previa(*self._bolear_ultimo)

    def _bolear_ativado(self, on):
        """Bolear ligado: o campo Raio vira "Raio do bolear" e já fica pronto para digitar."""
        self.lb_raio.setText(" Raio do bolear " if on else " Raio ")
        self.lb_raio.setStyleSheet("color:#ffcc33;font-weight:600" if on else "")
        if on:
            self.raio.blockSignals(True)
            self.raio.setValue(self.raio_bolear.value())  # o campo do Bolear manda no raio usado
            self.raio.blockSignals(False)
            self.raio_bolear.setFocus()
            self.raio_bolear.selectAll()
            self.statusBar().showMessage(f"Bolear: raio {self.raio.value():.2f} mm — digite outro no campo "
                                         "\"Raio do bolear\" lá em cima. Clique perto de um canto (só ele), na peça "
                                         "(todos) ou Shift+clique (pontas redondas).".replace(".", ","), 15000)

    def _bolear_previa(self, ponto, total=False):
        self._bolear_ultimo = (ponto, total)
        calc = self._bolear_calculo(ponto, total)
        self.canvas.view.realcar(calc[0].sceneTransform().map(calc[1]) if calc else None)

    def bolear_em(self, ponto, total=False) -> bool:
        calc = self._bolear_calculo(ponto, total)
        if calc is None:
            self.statusBar().showMessage("Bolear: clique numa forma com cantos retos (textos, imagens e grupos: "
                                         "desagrupe ou converta em curvas antes).")
            return False
        alvo, novo, n, r_mm, um = calc

        def do():
            alvo.setPath(novo)
            self._rebuild_objects()
        self._edit("Bolear", do)
        self.canvas.view.realcar(None)
        self.canvas.view.refresh_selection()
        if um in ("chanfro", "vivo"):
            self.statusBar().showMessage("Bolear: canto em 45° (clique de novo para canto vivo)." if um == "chanfro"
                                         else "Bolear: canto vivo de novo.")
            return True
        txt = ("pontas totalmente redondas" if total else f"raio {r_mm:.2f} mm".replace(".", ","))
        self.statusBar().showMessage(f"Bolear: {n} canto(s) — {txt}." + ("" if um or total else
                                     " (Clique perto de um canto para bolear só ele.)"))
        return True

    def round_corners(self):
        """Organizar → Arredondar cantos: aplica o Raio da barra à seleção (o mesmo que editar o campo)."""
        r = self.raio.value()
        if r <= 0:
            self.statusBar().showMessage("Defina o Raio (mm) na barra de propriedades antes de arredondar.")
            return
        self._aplicar_raio(self._sel(), r)

    def group_selected(self):
        sel = self._sel()
        if len(sel) < 2:
            return

        def do():
            scene = self.canvas.scene
            grp = ob.group(sel)
            for it in sel:
                scene.removeItem(it)
            scene.addItem(grp)
            grp.setSelected(True)
            self._rebuild_objects()

        self._edit("Agrupar", do)

    @staticmethod
    def _partes(s):
        """Objeto vetorial com vários contornos -> um objeto por contorno (mesma matriz, camada e cor)."""
        partes = fm.subcaminhos(s.path()) if type(s) is ob.Shape else []
        if len(partes) < 2:
            return []
        out = []
        for k, sub in enumerate(partes, 1):
            c = ob.Shape(sub, f"{s.name} {k:03d}", s.layer, s.color)
            c.setTransform(s.sceneTransform())
            out.append(c)
        return out

    def ungroup_selected(self):
        """Desfaz grupos e separa objetos compostos (vários contornos num objeto, ex.: frisos) em partes.
        As partes ficam no lugar do original na ordem dos objetos (= ordem de corte na camada)."""
        alvos = []
        for s in self._sel():
            filhos = ob.ungroup(s) if isinstance(s, ob.GroupShape) else self._partes(s)
            if filhos:
                alvos.append((s, filhos))
        if not alvos:
            self.statusBar().showMessage("Nada para desagrupar: selecione um grupo ou um objeto com vários contornos.")
            return
        troca = {id(s): f for s, f in alvos}

        def do():
            scene = self.canvas.scene
            ordem = []
            for it in self.canvas.view.shapes():
                ordem += troca.get(id(it), [it])
            for s, filhos in alvos:
                for x in self.canvas.view.shapes():
                    if x.ancora is s:
                        x.ancora = filhos[0]  # presos ao original passam para a 1ª parte
                scene.removeItem(s)
            scene.clearSelection()
            self._reordenar(ordem, selecionar=[c for _, f in alvos for c in f])
            self._rebuild_objects()

        self._edit("Desagrupar", do)
        n = sum(len(f) for _, f in alvos)
        self.statusBar().showMessage(f"{n} objeto(s) separados; a ordem na lista Objetos é a ordem de corte.")

    # ---------- ordem dos objetos (= ordem de corte dentro da camada) ----------
    def _reordenar(self, ordem, selecionar=None):
        """Recoloca os objetos na cena nesta ordem (mesmos objetos: âncoras e nomes ficam)."""
        scene = self.canvas.scene
        sel = set(map(id, selecionar if selecionar is not None else self._sel()))
        with self._selecao_em_lote():
            for it in self.canvas.view.shapes():
                scene.removeItem(it)
            for it in ordem:
                scene.addItem(it)
                it.setSelected(id(it) in sel)

    def mover_ordem(self, modo) -> bool:
        """modo: "subir" / "descer" (uma posição), "primeiro" / "ultimo"."""
        lista = self.canvas.view.shapes()
        sel = {id(s) for s in self._sel()}
        if not sel:
            self.statusBar().showMessage("Selecione os objetos para mudar a ordem.")
            return False
        nova = list(lista)
        if modo == "primeiro":
            nova = [x for x in lista if id(x) in sel] + [x for x in lista if id(x) not in sel]
        elif modo == "ultimo":
            nova = [x for x in lista if id(x) not in sel] + [x for x in lista if id(x) in sel]
        else:
            idx = range(1, len(nova)) if modo == "subir" else range(len(nova) - 2, -1, -1)
            d = -1 if modo == "subir" else 1
            for i in idx:
                if id(nova[i]) in sel and id(nova[i + d]) not in sel:
                    nova[i], nova[i + d] = nova[i + d], nova[i]
        if nova == lista:
            return False

        def do():
            self._reordenar(nova)
            self._rebuild_objects()

        self._edit("Mudar ordem", do)
        return True

    def create_text(self, params, scene_pos):
        def add():
            scene = self.canvas.scene
            scene.clearSelection()
            s = ob.TextShape(params, text_name(params))
            ob.move_by([s], scene_pos.x(), scene_pos.y())  # linha de base da 1ª linha no clique
            scene.addItem(s)
            s.setSelected(True)
            self._rebuild_objects()

        self._edit("Criar texto", add)

    def edit_text(self, item):
        params = self.ask_text(item.params)
        if params:
            params = replace(params, peca=item.params.peca)  # continua na mesma célula do gabarito
        if not params or params == item.params:
            return

        def change():
            item.set_params(params)
            item.name = text_name(params)
            self._rebuild_objects()

        self._edit("Editar texto", change)

    def edit_selected_text(self):
        texts = [s for s in self._sel() if isinstance(s, ob.TextShape)]
        if len(texts) == 1:
            self.edit_text(texts[0])

    def convert_to_curves(self):
        def do():
            scene = self.canvas.scene
            for it in [s for s in self._sel() if isinstance(s, ob.TextShape)]:
                self._trocar_item(it, ob.to_curves(it))
            self._rebuild_objects()

        self._edit("Converter em curvas", do)

    def save(self) -> bool:
        return self.save_to(self.file_path) if self.file_path else self.save_as()

    def save_as(self) -> bool:
        start = self.file_path or os.path.join(self._last_dir(), "sem título" + pj.EXT)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", start, f"Projeto RedBlack Laser (*{pj.EXT})")
        if not path:
            return False
        if not path.lower().endswith(pj.EXT):
            path += pj.EXT
        return self.save_to(path)

    def save_to(self, path) -> bool:
        self.fechar_grupo()  # o arquivo guarda o grupo inteiro, nunca "meio aberto"
        try:
            st = self.doc_state()
            pj.save(path, st[0], self.layers, self.vars, self.gabarito, st[5], st[6], self.notas, st[8], st[9], st[10])
        except OSError as e:
            self.show_error("Não foi possível salvar o projeto", str(e))
            return False
        self.file_path = path
        self.undo_stack.setClean()
        self._update_title()
        self._remember_dir(path)
        self._registrar_recente(path)
        self._limpar_recuperacao()
        self.statusBar().showMessage(f"Projeto salvo: {path}")
        return True

    # ---------- arquivos recentes ----------
    MAX_RECENTES = 8

    def recentes(self) -> list:
        v = self.settings.value("recentes", [])
        if isinstance(v, str):  # QSettings devolve str quando há um item só
            v = [v]
        return [p for p in (v or []) if isinstance(p, str)][:self.MAX_RECENTES]

    def _registrar_recente(self, path):
        path = os.path.abspath(path)
        if os.path.normcase(path).startswith(os.path.normcase(os.path.abspath(self.pasta_auto()))):
            return  # cópia de recuperação não vira "recente"
        self.settings.setValue("sessao/ultimo", path)  # reaberto no próximo início
        lista = [path] + [p for p in self.recentes() if os.path.normcase(p) != os.path.normcase(path)]
        self.settings.setValue("recentes", lista[:self.MAX_RECENTES])

    def _limpar_recentes(self):
        self.settings.setValue("recentes", [])

    def _montar_recentes(self):
        m = self.recent_menu
        m.clear()
        lista = self.recentes()
        for i, p in enumerate(lista, 1):
            pasta = os.path.dirname(p)
            a = m.addAction(f"&{i} {os.path.basename(p)}  —  {pasta}")
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, caminho=p: self.abrir_recente(caminho))
        if not lista:
            m.addAction("(nenhum projeto recente)").setEnabled(False)
        m.addSeparator()
        limpar = m.addAction("Limpar lista")
        limpar.setEnabled(bool(lista))
        limpar.triggered.connect(self._limpar_recentes)

    def abrir_recente(self, path) -> bool:
        if not os.path.exists(path):
            self.settings.setValue("recentes", [p for p in self.recentes() if p != path])
            self.show_error("Projeto não encontrado", f"O arquivo não existe mais e foi retirado da lista:\n{path}")
            return False
        if not self._maybe_save():
            return False
        return self.open_path(path)

    def show_error(self, title, text):
        QMessageBox.warning(self, title, text)

    def show_info(self, title, text):
        QMessageBox.information(self, title, text)

    # ---------- importação ----------
    def exportar_svg(self, path, so_selecao=False) -> bool:
        """Grava os vetores (todos ou só a seleção) em SVG, mm reais."""
        itens = self._sel() if so_selecao else self.canvas.view.shapes()
        if not itens:
            self.show_error("Nada para exportar", "Não há objetos" + (" selecionados." if so_selecao else "."))
            return False
        texto, ign = esvg.gerar([s.snapshot() for s in itens], g.BED_W, g.BED_H)
        try:
            esvg.salvar(path, texto)
        except OSError as e:
            self.show_error("Não foi possível salvar o SVG", str(e))
            return False
        self._remember_dir(path)
        self.statusBar().showMessage(f"SVG salvo: {path}" + (f" ({ign} imagem(ns) não exportada(s))" if ign else ""))
        return True

    def exportar_dxf(self, path, so_selecao=False) -> bool:
        """Grava os vetores em DXF R12 (mm; origem no canto inferior esquerdo da mesa)."""
        itens = [s for s in (self._sel() if so_selecao else self.canvas.view.shapes())
                 if not isinstance(s, ob.ImageShape)]
        if not itens:
            self.show_error("Nada para exportar", "Não há vetores para exportar.")
            return False
        texto = dxf.gerar([s.sceneTransform().map(s.path()) for s in itens], g.BED_H)
        try:
            esvg.salvar(path, texto)
        except OSError as e:
            self.show_error("Não foi possível salvar o DXF", str(e))
            return False
        self._remember_dir(path)
        self.statusBar().showMessage(f"DXF salvo: {path}")
        return True

    def _exportar_dxf_dialogo(self, so_selecao=False):
        nome = os.path.splitext(os.path.basename(self.file_path))[0] if self.file_path else "desenho"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar vetores (DXF)", os.path.join(self._last_dir(), nome + ".dxf"),
                                              "DXF (*.dxf)")
        if path:
            self.exportar_dxf(path if path.lower().endswith(".dxf") else path + ".dxf", so_selecao)

    def _exportar_svg_dialogo(self, so_selecao=False):
        nome = os.path.splitext(os.path.basename(self.file_path))[0] if self.file_path else "desenho"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar vetores (SVG)", os.path.join(self._last_dir(), nome + ".svg"),
                                              "SVG (*.svg)")
        if path:
            self.exportar_svg(path if path.lower().endswith(".svg") else path + ".svg", so_selecao)

    def import_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar", self._last_dir(),
            "Arquivos suportados (*.svg *.dxf *.pdf *.ai *.png *.jpg *.jpeg);;SVG (*.svg);;DXF (*.dxf);;"
            "PDF e Illustrator (*.pdf *.ai);;"
            "Imagens (*.png *.jpg *.jpeg)")
        if path:
            self.import_path(path)

    def import_path(self, path) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".svg", ".dxf", ".pdf", ".ai"):
            return self.import_image(path)  # tipo real decidido pelo conteúdo (assinatura PNG/JPEG)
        try:
            if ext in (".pdf", ".ai"):
                res = pdfimp.load(path)
            else:
                res = svg.load(path) if ext == ".svg" else dxf.load(path, g.BED_H)
        except (svg.SvgInvalido, dxf.DxfInvalido, pdfimp.PdfInvalido, OSError) as e:
            self.show_error(f"Não foi possível importar o {ext[1:].upper()}", str(e))
            return False
        self._remember_dir(path)
        if not res.objetos:
            self.show_error("Nada para importar", f"O {ext[1:].upper()} não contém elementos suportados.\n\n"
                            + svg_report(res))
            return False

        def add():
            itens = [ob.Shape(p, name, "C01", cm.cor("C01")) for name, p in res.objetos]
            self._ao_importar(itens)
            self._por_na_cena([itens], ler_pref(self.settings, "importar_agrupar"))

        self._edit(f"Importar {os.path.basename(path)}", add)
        msg = f"{len(res.objetos)} objeto(s) importado(s) de {os.path.basename(path)}."
        self.statusBar().showMessage(msg)
        if res.ignorados or res.avisos:
            self.show_info(f"Importação de {ext[1:].upper()}", msg + "\n\n" + svg_report(res))
        return True

    def _ao_importar(self, itens):
        if itens and ler_pref(self.settings, "importar_centralizar"):
            r = ob.bounds(itens)
            ob.move_by(itens, g.BED_W / 2 - r.center().x(), g.BED_H / 2 - r.center().y())

    def import_image(self, path) -> bool:
        try:
            res = imgimp.load(path)
        except imgimp.ImagemInvalida as e:
            self.show_error("Não foi possível importar a imagem", str(e))
            return False
        self._remember_dir(path)
        name = os.path.basename(path)

        def add():
            scene = self.canvas.scene
            scene.clearSelection()
            s = ob.ImageShape(res.imagem, res.largura_mm, res.altura_mm, name)
            self._ao_importar([s])
            scene.addItem(s)
            s.setSelected(True)
            self._rebuild_objects()

        self._edit(f"Importar {name}", add)
        q = res.imagem.qimage
        dpi = f"{res.dpi[0]:.0f}" if abs(res.dpi[0] - res.dpi[1]) < 0.5 else f"{res.dpi[0]:.0f}×{res.dpi[1]:.0f}"
        size = f"{res.largura_mm:.2f} × {res.altura_mm:.2f}".replace(".", ",")  # só os números, não o nome
        msg = f"{name}: {q.width()}×{q.height()} px a {dpi} dpi = {size} mm"
        self.statusBar().showMessage(msg)
        if not res.dpi_do_arquivo:
            self.show_info("Importação de imagem",
                           f"{msg}.\n\nO arquivo não informa a resolução (DPI); foi assumido "
                           f"{imgimp.DEFAULT_DPI:.0f} dpi. Ajuste Largura/Altura se o tamanho físico for outro.")
        return True

    def _last_dir(self):
        return self.settings.value("lastDir", os.path.expanduser("~/Documents"))

    def _remember_dir(self, path):
        self.settings.setValue("lastDir", os.path.dirname(path))

    def _rotate(self, deg):
        sel = self._sel()
        ob.rotate(sel, deg, ob.anchor_point(ob.bounds(sel), self.anchor))

    MIME_INTERNO = "application/x-redblack-laser"

    def copy(self):
        self._clipboard = [it.snapshot() for it in self._sel()]
        if self._clipboard:  # marca a área de transferência do sistema: Ctrl+V sabe que a cópia é nossa
            from PySide6.QtCore import QMimeData
            md = QMimeData()
            md.setData(self.MIME_INTERNO, b"1")
            md.setText(", ".join(snap[2] for snap in self._clipboard))
            QApplication.clipboard().setMimeData(md)

    def _atualizar_colar(self):
        """Colar fica ativo com cópia interna OU com imagem/arquivo/texto copiado de outro programa."""
        cb = QApplication.clipboard()
        if not getattr(self, "_ouvindo_clipboard", False):
            self._ouvindo_clipboard = True
            cb.dataChanged.connect(self._atualizar_colar)  # copiou algo em outro programa
        md = cb.mimeData()
        de_fora = md is not None and (md.hasImage() or md.hasUrls() or bool(md.hasText() and md.text().strip()))
        if "paste" in getattr(self, "actions_by_key", {}):
            self.actions_by_key["paste"].setEnabled(bool(self._clipboard) or de_fora)

    def _centro_da_tela(self):
        v = self.canvas.view
        return v.mapToScene(v.viewport().rect().center())

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        e.acceptProposedAction()
        self.soltar(e.mimeData())

    def colar_do_sistema(self, md=None) -> bool:
        """Imagem, arquivos ou texto copiados de outro programa (navegador, Word, Paint, Explorer…)."""
        md = md or QApplication.clipboard().mimeData()
        if md is None or md.hasFormat(self.MIME_INTERNO):
            return False
        if md.hasImage():
            from PySide6.QtCore import QBuffer, QIODevice
            q = QApplication.clipboard().image() if md is QApplication.clipboard().mimeData() else md.imageData()
            if q is None or q.isNull():
                return False
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            q.save(buf, "PNG")
            res = imgimp.from_bytes(bytes(buf.data()), "Imagem colada.png")
            centro = self._centro_da_tela()

            def add():
                scene = self.canvas.scene
                scene.clearSelection()
                s = ob.ImageShape(res.imagem, res.largura_mm, res.altura_mm, "Imagem colada")
                ob.move_by([s], centro.x() - res.largura_mm / 2, centro.y() - res.altura_mm / 2)
                scene.addItem(s)
                s.setSelected(True)
                self._rebuild_objects()
            self._edit("Colar imagem", add)
            self.statusBar().showMessage(f"Imagem colada: {q.width()}×{q.height()} px a 96 dpi = "
                                         f"{res.largura_mm:.1f} × {res.altura_mm:.1f} mm".replace(".", ","))
            return True
        arquivos = [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []
        arquivos = [a for a in arquivos if os.path.splitext(a)[1].lower() in
                    (".png", ".jpg", ".jpeg", ".svg", ".dxf", ".pdf", ".ai") and os.path.isfile(a)]
        if arquivos:
            return any([self.import_path(a) for a in arquivos])
        texto = md.text().strip() if md.hasText() else ""
        if not texto:
            return False
        if "<svg" in texto[:2000]:  # código SVG copiado (Inkscape, Illustrator, sites de ícones)
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                arq = os.path.join(tmp, "colado.svg")
                with open(arq, "w", encoding="utf-8") as f:
                    f.write(texto)
                return self.import_path(arq)
        params = tx.TextoParams(texto[:5000], self.default_font(), ler_pref(self.settings, "texto_altura_mm"))
        centro = self._centro_da_tela()
        self.create_text(params, centro)
        self.statusBar().showMessage("Texto colado como objeto de texto (duplo clique para editar).")
        return True

    def soltar(self, md, ponto=None) -> bool:
        """Arrastar e soltar: projeto .rbl abre; SVG/DXF/PDF/AI/imagem entram no projeto onde foram soltos."""
        arquivos = [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []
        projetos = [a for a in arquivos if a.lower().endswith(pj.EXT)]
        if projetos:
            return self._maybe_save() and self.open_path(projetos[0])
        aceitos = [a for a in arquivos if os.path.splitext(a)[1].lower() in
                   (".png", ".jpg", ".jpeg", ".svg", ".dxf", ".pdf", ".ai") and os.path.isfile(a)]
        if arquivos and not aceitos:
            self.show_error("Arquivo não suportado", "Solte projeto (.rbl), SVG, DXF, PDF, AI, PNG ou JPG.")
            return False
        ok = any([self.import_path(a) for a in aceitos]) if aceitos else self.colar_do_sistema(md)
        sel = self._sel()
        if ok and ponto is not None and sel:  # o que entrou fica centrado onde foi solto
            c = ob.bounds(sel).center()
            self._edit("Posicionar o que foi solto", lambda: ob.move_by(sel, ponto.x() - c.x(), ponto.y() - c.y()))
        return ok

    def paste(self):
        if self.colar_do_sistema():
            return
        if not self._clipboard:
            return

        def do():
            scene = self.canvas.scene
            scene.clearSelection()
            for snap in self._clipboard:
                it = ob.from_snapshot(snap, f"{snap[2]} (cópia)")
                ob.move_by([it], 5, 5)  # deslocada para não ficar escondida sobre a original
                scene.addItem(it)
                it.setSelected(True)
            self._clipboard = [it.snapshot() for it in self._sel()]  # colar de novo desloca outra vez
            self._rebuild_objects()

        self._edit("Colar", do)

    def cut(self):
        self.copy()
        if self._clipboard:
            self.delete()

    def paste_in_place(self):
        """Colar no mesmo lugar de onde foi copiado (sem deslocar)."""
        if not self._clipboard:
            return

        def do():
            scene = self.canvas.scene
            scene.clearSelection()
            for snap in self._clipboard:
                it = ob.from_snapshot(snap, f"{snap[2]} (cópia)")
                scene.addItem(it)
                it.setSelected(True)
            self._rebuild_objects()

        self._edit("Colar no lugar", do)

    def inverter_selecao(self):
        with self._selecao_em_lote():
            for it in self.canvas.view.shapes():
                it.setSelected(not it.isSelected())

    def _selecionar_se(self, cond, texto):
        alvo = [s for s in self.canvas.view.shapes() if s.isVisible() and cond(s)]
        with self._selecao_em_lote():
            self.canvas.scene.clearSelection()
            for s in alvo:
                s.setSelected(True)
        self.statusBar().showMessage(f"{texto}: {len(alvo)} objeto(s).")
        return alvo

    def selecionar_abertas(self, so_preenchimento=False):
        def cond(s):
            if type(s) is not ob.Shape or not fm.tem_aberto(s.path()):
                return False
            c = self.layer(s.layer)
            return not so_preenchimento or (c is not None and c.modo == "preenchimento")
        return self._selecionar_se(cond, "Formas abertas" + (" em camada de preenchimento" if so_preenchimento else ""))

    def selecionar_da_camada(self):
        lid = self._current_layer_id()
        return self._selecionar_se(lambda s: lid in ob.leaf_layers(s.snapshot()), f"Camada {lid}")

    def selecionar_contidas(self):
        """Objetos totalmente dentro da(s) forma(s) selecionada(s)."""
        sel = self._sel()
        caixas = [s.sceneTransform().map(s.path()) for s in sel]
        return self._selecionar_se(lambda s: s not in sel and any(
            c.contains(s.sceneTransform().map(s.path()).boundingRect()) and c.contains(s.sceneTransform().map(s.path()))
            for c in caixas), "Formas contidas")

    def selecionar_menores(self):
        sel = self._sel()
        if not sel:
            return []
        lim = min(ob.geom_rect(s).width() * ob.geom_rect(s).height() for s in sel)
        return self._selecionar_se(lambda s: ob.geom_rect(s).width() * ob.geom_rect(s).height() < lim - 1e-9,
                                   "Formas menores")

    def selecionar_circulos(self):
        return self._selecionar_se(lambda s: type(s) is ob.Shape and fm.e_circulo(s.sceneTransform().map(s.path())),
                                   "Círculos")

    def fechar_caminhos(self, tol=None) -> int:
        alvos = [s for s in self._sel() if type(s) is ob.Shape and fm.tem_aberto(s.path())]
        res = {}
        for s in alvos:
            novo, n = fm.fechar_contornos(s.path(), tol)
            if n:
                res[id(s)] = (s, novo, n)
        if res:
            def do():
                for s, novo, _ in res.values():
                    s.setPath(novo)
            self._edit("Fechar caminho", do)
        total = sum(n for *_, n in res.values())
        self.statusBar().showMessage(f"{total} contorno(s) fechado(s)" + ("" if tol is None else
                                     f" (vão até {tol:g} mm)".replace(".", ",")) + ".")
        return total

    def _fechar_tolerancia_dialogo(self):
        v = self.ask_valores("Fechar caminhos com tolerância", [("tol", "Vão máximo", 0.5, (0.001, 100, 3, " mm"))])
        if v:
            self.fechar_caminhos(v["tol"])

    def juntar_formas(self, tol=0.05) -> int:
        """Une linhas/contornos abertos selecionados cujas pontas se tocam (até tol mm) num só objeto."""
        alvos = [s for s in self._sel() if type(s) is ob.Shape]
        if not alvos:
            return 0
        paths, unioes = fm.juntar_abertos([s.sceneTransform().map(s.path()) for s in alvos], tol)
        if not unioes:
            self.statusBar().showMessage("Nenhuma ponta encostada para juntar.")
            return 0
        junto = QPainterPath()
        for p in paths:
            junto.addPath(p)
        lid = alvos[0].layer
        self._trocar_por_caminhos(alvos, [(junto, "Formas associadas", lid)], "Associar formas")
        fechados = sum(not fm.aberto(c) for c in fm.subcaminhos(junto))
        self.statusBar().showMessage(f"{unioes} união(ões); {fechados} contorno(s) fechado(s).")
        return unioes

    def otimizar_formas(self, tol=None) -> int:
        """Menos nós em contornos de retas (ex.: depois de traçar imagem ou importar DXF)."""
        alvos = [s for s in self._sel() if type(s) is ob.Shape]
        if not alvos:
            return 0
        if tol is None:
            v = self.ask_valores("Otimizar formas", [("tol", "Tolerância", 0.05, (0.001, 10, 3, " mm"))],
                                 "Tira nós de contornos feitos de retas sem sair mais que a tolerância do original. "
                                 "Curvas ficam como estão.")
            if not v:
                return 0
            tol = v["tol"]
        res = []
        for s in alvos:
            esc = ob.escala_uniforme(s) or 1.0
            novo, a, d = fm.simplificar(s.path(), tol / esc)
            if d < a:
                res.append((s, novo, a - d))
        if not res:
            self.statusBar().showMessage("Nada para simplificar com essa tolerância.")
            return 0
        self._edit("Otimizar formas", lambda: [s.setPath(n) for s, n, _ in res])
        total = sum(k for *_, k in res)
        self.statusBar().showMessage(f"{total} nó(s) removido(s).")
        return total

    def eliminar_duplicados(self) -> int:
        """Remove objetos com geometria igual (em mm de cena) a um anterior; fica o primeiro."""
        vistos, dup = [], []
        for s in self.canvas.view.shapes():
            g = s.sceneTransform().map(s.path())
            if any(fm._iguais(g, v, 1e-4) for v in vistos):
                dup.append(s)
            else:
                vistos.append(g)
        if dup:
            def do():
                for s in dup:
                    self.canvas.scene.removeItem(s)
                self._rebuild_objects()
            self._edit("Eliminar duplicados", do)
        self.statusBar().showMessage(f"{len(dup)} duplicado(s) eliminado(s)." if dup else "Sem duplicados.")
        return len(dup)

    def inverter_direcao(self):
        alvos = [s for s in self._sel() if type(s) is ob.Shape]
        if alvos:
            self._edit("Inverter direção", lambda: [s.setPath(s.path().toReversed()) for s in alvos])

    def delete(self):
        def do():
            for it in self._sel():
                self.canvas.scene.removeItem(it)
            self._rebuild_objects()

        self._edit("Excluir", do)

    @contextmanager
    def _selecao_em_lote(self):
        """Muitas mudanças de seleção viram um único recálculo da janela (o Qt avisa a cada objeto)."""
        sc = self.canvas.scene
        antes = sc.signalsBlocked()
        sc.blockSignals(True)
        try:
            yield
        finally:
            sc.blockSignals(antes)
            if not antes:
                self.canvas.view.refresh_selection()
                self._on_selection()

    def select_all(self):
        with self._selecao_em_lote():
            for it in self.canvas.view.shapes():
                it.setSelected(True)

    def _on_selection(self):
        if not getattr(self, "_destacando", False) and self.canvas.view.destaque is not None:
            self.canvas.view.destacar(None)  # a seleção mudou na mesa: some o destaque da peça do grupo
        sel = self._sel()
        n = len(sel)
        if self.tools["node"].isChecked() and sel:
            self._aviso_nos()
        for a in self._sel_actions:
            a.setEnabled(n >= a.property("min_items"))
        for k in ("copy", "delete"):
            self.actions_by_key[k].setEnabled(n > 0)
        self._atualizar_colar()
        texts =sum(isinstance(s, ob.TextShape) for s in sel)
        self.act_edit_text.setEnabled(texts == 1 and n == 1)
        self.act_curves.setEnabled(texts > 0)
        self.act_group.setEnabled(n >= 2)
        self.act_ungroup.setEnabled(any(isinstance(s, ob.GroupShape) or (type(s) is ob.Shape and fm.n_contornos(s.path()) > 1) for s in sel))
        for a in self.acts_ordem:
            a.setEnabled(n > 0)
        self.act_duplicate.setEnabled(n > 0)
        self.act_round.setEnabled(any(type(s) is ob.Shape for s in sel))
        self.act_prender.setEnabled(n >= 2)
        pais = {id(x.ancora) for x in self.canvas.view.shapes() if x.ancora is not None}
        self.act_soltar.setEnabled(any(s.ancora is not None or id(s) in pais for s in sel))
        self._sync_fields()
        self._sync_texto()
        self._sync_objects()
        self._desenhar_ancoras()
        # Seleção numa única camada: destaca essa camada na tabela (como a referência).
        layers = set().union(*(ob.leaf_layers(s.snapshot()) for s in sel)) if sel else set()
        if len(layers) == 1:
            lid = layers.pop()
            for r in range(self.layer_table.rowCount()):
                if self.layer_table.item(r, 0).data(Qt.UserRole) == lid:
                    self.layer_table.selectRow(r)

    def _sync_fields(self):
        sel = self._sel()
        self._syncing = True
        for sb in self.fields.values():
            sb.setEnabled(bool(sel))
        if sel:
            r = ob.bounds(sel)
            x, y = g.to_display(*ob.anchor_point(r, self.anchor).toTuple())
            for k, v in (("x", x), ("y", y), ("w", r.width()), ("h", r.height()), ("wp", 100.0), ("hp", 100.0),
                         ("rot", ob.angulo(sel[0]))):
                self.fields[k].setValue(v)
            raios = {r for r in map(self._raio_obj, sel) if r is not None}
            if len(raios) == 1:  # retângulos com o mesmo raio; outros tipos não contam
                self.raio.setValue(raios.pop())
        else:
            self.raio.setValue(self.canvas.view.raio_canto)  # sem seleção: raio dos próximos retângulos
        self._syncing = False

    # ---------- raio dos cantos da peça ----------
    @staticmethod
    def _raio_obj(s):
        """Raio (mm) de um retângulo/retângulo arredondado; None se não for retângulo."""
        if type(s) is not ob.Shape:
            return None
        e = ob.escala_uniforme(s)
        if e is not None:
            r = fm.raio_retangulo(s.path())
            return None if r is None else round(r * e, 6)
        return fm.raio_retangulo(s.sceneTransform().map(s.path()))

    @staticmethod
    def _arredondar_obj(s, r) -> int:
        """Aplica o raio r (mm) à peça, no lugar (mesmo objeto: âncoras e ordem ficam). Retângulo arredondado
        volta ao retângulo original antes, então o raio pode ser trocado quantas vezes quiser.
        Devolve quantos cantos ficaram arredondados (0 se nada mudou)."""
        e = ob.escala_uniforme(s)
        base = s.path()
        if fm.raio_retangulo(base) is not None:  # retângulo (arredondado ou não): parte do retângulo original
            base = fm.rect_path(base.boundingRect())
        if e is not None:
            path, rr = base, r / e
        else:  # peça esticada: trabalha em mm reais (a matriz é incorporada ao caminho)
            path, rr = s.sceneTransform().map(base), r
        novo, n = fm.arredondar(path, rr)
        if not (fm._iguais(novo, s.path()) and e is not None):
            if e is None:
                s.setPos(0, 0)
                s.setTransform(QTransform())
            s.setPath(novo)
        return n

    def _raio_editado(self):
        if self._syncing:
            return
        r = self.raio.value()
        sel = self._sel()
        if not sel:
            self.canvas.view.raio_canto = r
            return
        self._aplicar_raio(sel, r)

    def _aplicar_raio(self, sel, r):
        alvos = [s for s in sel if type(s) is ob.Shape]
        res = {}

        def do():
            for s in alvos:
                res[id(s)] = self._arredondar_obj(s, r)
            self._rebuild_objects()

        self._edit("Raio dos cantos", do)
        feitos = sum(1 for v in res.values() if v)
        ignorados = len(sel) - feitos
        msg = (f"{sum(res.values())} canto(s) com raio {r:g} mm em {feitos} objeto(s)" if feitos else
               "Cantos vivos" if r == 0 else "Nenhum canto reto para arredondar na seleção").replace(".", ",")
        self.statusBar().showMessage(msg + (f"; {ignorados} objeto(s) sem cantos retos ignorado(s) (curvas, texto, "
                                            "imagens e grupos ficam como estão)." if ignorados and r else "."))
        self._sync_fields()
        return feitos

    # ---------- menus ----------
    def _build_menus(self):
        mb = self.menuBar()

        self._menus_vivos = []  # guarda cada menu: sem referência no Python, a limpeza de memória apagava o menu

        def menu(title, items):
            m = mb.addMenu(title)
            self._menus_vivos.append(m)
            for it in items:
                if it is None:
                    m.addSeparator()
                    continue
                if it.property("stage"):
                    # Etapa visível no próprio menu: itens desabilitados não mostram dica.
                    it.setText(f"{it.text()}\tEtapa {it.property('stage')}")
                m.addAction(it)
            return m

        A = self.actions_by_key
        self.recent_menu = QMenu("Abrir &recente", self)
        self.recent_menu.aboutToShow.connect(self._montar_recentes)
        self.act_lote = self._act("Exportar G-code em &lote (texto variável)…", slot=self._exportar_lote_dialogo)
        arquivo = menu("&Arquivo", [A["new"], A["open"], A["save"], A["save_as"], None,
                                    A["import"], A["export"], self.act_lote,
                                    self._act("Exportar vetores do projeto (SVG)…", slot=lambda: self._exportar_svg_dialogo()),
                                    self._act("Exportar vetores selecionados (SVG)…",
                                              slot=lambda: self._exportar_svg_dialogo(True)),
                                    self._act("Exportar vetores do projeto (DXF)…", slot=lambda: self._exportar_dxf_dialogo()),
                                    None,
                                    self._act("&Sair", shortcut="Ctrl+Q", slot=self.close)])
        arquivo.insertMenu(A["save"], self.recent_menu)  # logo depois de Abrir
        self.modelos_menu = QMenu("Novo a partir de &modelo", self)
        self.modelos_menu.aboutToShow.connect(self._montar_modelos)
        arquivo.insertMenu(A["open"], self.modelos_menu)
        sair = arquivo.actions()[-1]
        for act in (self._act("&Imprimir (somente preto)…", shortcut="Ctrl+P", slot=lambda: self.imprimir()),
                    self._act("Imprimir (com as cores das camadas)…", shortcut="Ctrl+Shift+P",
                              slot=lambda: self.imprimir(cores=True))):
            arquivo.insertAction(sair, act)
        self.act_notas = self.notas_dock.toggleViewAction()
        self.act_notas.setText("Mostrar &notas")
        self.act_notas.setShortcut(QKeySequence("Ctrl+Alt+N"))
        arquivo.insertAction(sair, self.act_notas)
        for act in (self._act("Salvar como mo&delo…", slot=self._salvar_modelo_dialogo),
                    self._act("Exportar preferências…", slot=lambda: self._preferencias_arquivo_dialogo(True)),
                    self._act("Importar preferências…", slot=lambda: self._preferencias_arquivo_dialogo(False))):
            arquivo.insertAction(sair, act)
        arquivo.insertSeparator(sair)
        self.act_group = self._act("&Agrupar", shortcut="Ctrl+G", slot=self.group_selected)
        self.act_autogrupo = self._act("Autoagrupar (o que está dentro vai junto)", slot=lambda: self.autoagrupar())
        self.act_ungroup = self._act("&Desagrupar / separar", shortcut="Ctrl+U", slot=self.ungroup_selected)
        self.act_ungroup.setToolTip("Desfaz grupos e separa objetos com vários contornos (ex.: frisos) em partes")
        self.acts_ordem = [
            self._act("Subir na ordem de corte", shortcut="PgUp", slot=lambda: self.mover_ordem("subir")),
            self._act("Descer na ordem de corte", shortcut="PgDown", slot=lambda: self.mover_ordem("descer")),
            self._act("Cortar primeiro", shortcut="Ctrl+PgUp", slot=lambda: self.mover_ordem("primeiro")),
            self._act("Cortar por último", shortcut="Ctrl+PgDown", slot=lambda: self.mover_ordem("ultimo"))]
        self.act_edit_text = self._act("Editar &texto…", "text", slot=self.edit_selected_text)
        self.act_curves = self._act("Converter em &curvas", shortcut="Ctrl+Shift+C",
                                    slot=self.convert_to_curves)
        self.act_curves.setToolTip("Transforma textos em contornos comuns; as propriedades de texto são descartadas")
        self.act_prender = self._act("Prender à &âncora", "anchor", shortcut="Ctrl+Shift+A", slot=self.prender_ancora)
        self.act_prender.setToolTip("Clique primeiro no objeto pai (âncora) e depois, com Shift, nos que vão junto. "
                                    "Arrastar/girar/escalar a âncora leva os presos; cada um ainda se move sozinho.")
        self.act_soltar = self._act("&Soltar da âncora", slot=self.soltar_ancora)
        self.acts_bool = [
            self._act("&Deslocar formas…", shortcut="Alt+O", slot=lambda: self.deslocar_formas()),
            self._act("Formas de &solda", shortcut="Ctrl+W", slot=lambda: self.booleana("solda")),
            self._act("&União booleana", shortcut="Alt++", slot=lambda: self.booleana("uniao")),
            self._act("&Subtrair (booleana)", shortcut="Alt+-", slot=lambda: self.booleana("subtrair")),
            self._act("&Interseção booleana", shortcut="Alt+*", slot=lambda: self.booleana("intersecao")),
            self._act("&Cortar formas (cortador)", shortcut="Alt+Shift+C", slot=lambda: self.booleana("cortar"))]
        for a, dica in zip(self.acts_bool, (
                "Contorno paralelo para fora, para dentro ou ambos (cantos redondos, vivos ou em bisel)",
                "Funde todas as formas selecionadas numa só (sobreposições somem)",
                "União das formas selecionadas",
                "Subtrai da primeira forma clicada as demais",
                "Mantém só a área comum às formas selecionadas",
                "A última forma clicada corta as outras como um cortador de biscoito (ela continua)")):
            a.setToolTip(dica)
        self.act_macho = self._act("Soldar &macho (dente para fora)", "weld_male", slot=lambda: self.booleana("macho"))
        self.act_macho.setToolTip("Soldar macho — junte a peça com um retângulo que passa da borda: o pedaço de fora "
                                  "vira um dente (encaixe macho). Selecione 2 ou mais formas fechadas.")
        self.act_femea = self._act("Soldar &fêmea (rasgo para dentro)", "weld_female",
                                   slot=lambda: self.booleana("femea"))
        self.act_femea.setToolTip("Soldar fêmea — o retângulo menor abre um rasgo na peça maior (encaixe fêmea) e "
                                  "some. A maior é sempre a base, não importa a ordem do clique.")
        self.acts_bool += [self.act_macho, self.act_femea]
        self.act_rename = self._act("Re&nomear objeto…", shortcut="F2", slot=self.rename_selected)
        self.act_duplicate = self._act("D&uplicar", shortcut="Ctrl+D", slot=self.duplicate)
        self.act_duplicate.setToolTip("Duplicar no mesmo lugar (Ctrl+D); as cópias ficam selecionadas para mover")
        self.act_round = self._act("Arredondar &cantos", slot=self.round_corners)
        self.act_round.setToolTip("Arredonda os cantos retos de retângulos, polígonos e linhas selecionados com o "
                                  "raio da barra de propriedades")
        self.act_historico = self.historico_dock.toggleViewAction()
        self.act_historico.setText("&Histórico de anulações")
        E = self.acts_editar = {
            "cut": self._act("Recor&tar", shortcut=QKeySequence.Cut, slot=self.cut),
            "paste_in_place": self._act("Colar no &lugar", shortcut="Alt+V", slot=self.paste_in_place),
            "invert": self._act("&Inverter seleção", shortcut="Ctrl+Shift+I", slot=self.inverter_selecao),
            "close": self._act("&Fechar caminho", slot=lambda: self.fechar_caminhos()),
            "close_tol": self._act("Fechar caminhos com tolerância…", slot=self._fechar_tolerancia_dialogo),
            "dups": self._act("Eliminar &duplicados", shortcut="Alt+D", slot=self.eliminar_duplicados),
            "juntar": self._act("Associar formas selecionadas (juntar pontas)", shortcut="Alt+J",
                                slot=lambda: self.juntar_formas()),
            "otimizar": self._act("Otimizar formas selecionadas…", shortcut="Alt+Shift+O",
                                  slot=lambda: self.otimizar_formas()),
            "reverse": self._act("Inverter direção da forma", slot=self.inverter_direcao),
            "bitmap": self._act("Converter em &bitmap", shortcut="Ctrl+Shift+B", slot=lambda: self.converter_em_bitmap()),
            "tracar": self._act("&Traçar imagem…", shortcut="Alt+T", slot=lambda: self.tracar_imagem()),
            "ajustar_imagem": self._act("Ajustar &imagem…", shortcut="Alt+I", slot=lambda: self.ajustar_imagem()),
            "salvar_bitmap": self._act("Salvar bitmap processado…", slot=lambda: self.salvar_bitmap_processado()),
            "texto_caminho": self._act("Aplicar caminho ao te&xto…", slot=lambda: self.texto_no_caminho())}
        selm = QMenu("Selecionar &formas", self)
        for txt, fn in (("Abertas", lambda: self.selecionar_abertas()),
                        ("Abertas em camada de preenchimento", lambda: self.selecionar_abertas(True)),
                        ("Todas da camada atual", self.selecionar_da_camada),
                        ("Contidas na seleção", self.selecionar_contidas),
                        ("Menores do que a seleção", self.selecionar_menores),
                        ("Círculos", self.selecionar_circulos)):
            selm.addAction(self._act(txt, slot=fn))
        menu("&Editar", [A["undo"], A["redo"], self.act_historico, None, E["cut"], A["copy"], A["paste"], E["paste_in_place"],
                         self.act_duplicate, A["delete"], self.act_rename, None,
                         A["select_all"], E["invert"], selm.menuAction(), None, self.act_edit_text, self.act_curves,
                         E["bitmap"], E["tracar"], E["ajustar_imagem"], E["salvar_bitmap"], E["texto_caminho"], None, E["close"], E["close_tol"], E["juntar"], E["otimizar"], E["dups"], E["reverse"], None, A["settings"],
                         self._act("Teclas de &atalho…", slot=lambda: self.editar_atalhos())])
        formas_m = self._menu_formas_prontas()
        formas_m.setTitle("Desenhar &forma")
        self.act_qr = self._act("Criar código &QR…", slot=lambda: self.criar_qr())
        self.act_render_mdf = self._act("Ver peças cortadas em MDF (renderizar)…", "preview",
                                        slot=lambda: self.renderizar_pecas())
        self.act_render_mdf.setToolTip("Prévia das peças desta aba como sairiam do laser: textura de MDF, bordas "
                                       "queimadas e furos vazados")
        formas_m.addSeparator()
        formas_m.addAction(self.act_qr)
        formas_m.addAction(self._act("Criar código de &barras EAN-13…", slot=lambda: self.criar_ean13()))
        self.menu_ferramentas = menu("&Ferramentas", [formas_m.menuAction()] + [self.tools[k] for k in ("select", "node", "pen", "rect", "ellipse",
                                                       "polygon", "star", "text", "measure", "trim", "bolear")] + [None, self.act_render_mdf, self.act_forma, None] + self.acts_bool + [None, E["juntar"], E["close"], E["close_tol"], E["otimizar"], None, self.act_snap,
                                                                     self.act_medidas])
        org = []
        for mode, text in (("left", "Alinhar à esquerda"), ("hcenter", "Alinhar centros na horizontal"),
                           ("right", "Alinhar à direita"), ("top", "Alinhar ao topo"),
                           ("vcenter", "Alinhar centros na vertical"), ("bottom", "Alinhar à base")):
            org.append(self._sel_act(text, lambda m=mode: ob.align(self._sel(), m), 2))
        org += [None,
                self._sel_act("Distribuir na horizontal", lambda: ob.distribute(self._sel(), True), 3),
                self._sel_act("Distribuir na vertical", lambda: ob.distribute(self._sel(), False), 3), None,
                self._sel_act("Espelhar na horizontal", lambda: ob.mirror(self._sel(), True), 1),
                self._sel_act("Espelhar na vertical", lambda: ob.mirror(self._sel(), False), 1), None,
                self._sel_act("Girar 90° horário", lambda: self._rotate(90), 1),
                self._sel_act("Girar 90° anti-horário", lambda: self._rotate(-90), 1), None,
                self.act_round, None,
                self.act_group, self.act_autogrupo, self.act_ungroup, None] + self.acts_ordem
        alinhar_dist_esp = org[:6] + org[7:9] + org[10:12]  # 6 alinhar, 2 distribuir, 2 espelhar
        mais = [self._act("Alinhar centros (H e V)", slot=self.alinhar_centros),
                self._act("Distribuir espaçado na horizontal", slot=lambda: self.distribuir_espacado(True)),
                self._act("Distribuir espaçado na vertical", slot=lambda: self.distribuir_espacado(False)),
                self._act("Mesma largura (do 1º clicado)", slot=lambda: self.mesma_medida(True)),
                self._act("Mesma altura (do 1º clicado)", slot=lambda: self.mesma_medida(False))]
        enc = QMenu("&Encostar", self)
        for lado, txt in (("esquerda", "À esquerda"), ("direita", "À direita"), ("cima", "Em cima"), ("baixo", "Embaixo")):
            enc.addAction(self._act(txt, slot=lambda _=False, l=lado: self.encostar(l)))
        pag = QMenu("Mover para a &página", self)
        for i, txt in enumerate(("Canto superior esquerdo", "Centro em cima", "Canto superior direito", "Centro à esquerda",
                                 "Centro da página", "Centro à direita", "Canto inferior esquerdo", "Centro embaixo",
                                 "Canto inferior direito")):
            pag.addAction(self._act(txt, slot=lambda _=False, k=i: self.mover_para_pagina(k)))
        self.act_grade = self._act("Matriz em &grade…", slot=lambda: self.matriz_grade())
        self.act_circular = self._act("Matriz &circular…", slot=lambda: self.matriz_circular())
        self.act_espelho_linha = self._act("Espelhar ao longo da &linha", shortcut="Ctrl+Shift+M",
                                           slot=self.espelhar_na_linha)
        self.act_espelho_linha.setToolTip("Espelha a seleção em relação à linha selecionada por último")
        self.act_contorno_redor = self._act("Contorno retangular ao &redor…", slot=lambda: self.contorno_ao_redor())
        self.act_contorno_redor.setToolTip("Retângulo/quadrado em volta da seleção, com margem e raio de canto")
        self.act_encaixar = self._act("&Encaixar na caixa…", shortcut="Ctrl+Alt+E",
                                      slot=lambda: self.encaixar_na_caixa())
        self.act_encaixar.setToolTip("Clique na caixa e depois (Shift) no que vai dentro: cabe proporcional, só "
                                     "diminui ou estica para preencher")
        self.act_pesquisa = self._act("Pesquisar comando…", shortcut="F4", slot=self.pesquisar_comando)
        self.addAction(self.act_pesquisa)  # F4 funciona em qualquer lugar da janela
        self.act_copiar_caminho = self._act("Copiar ao longo do caminho…", slot=lambda: self.copiar_ao_longo())
        org += [None] + mais + [enc.menuAction(), pag.menuAction(), None, self.act_grade, self.act_circular,
                                self.act_copiar_caminho,
                                self.act_espelho_linha, self._act("Cisal&har…", slot=lambda: self.cisalhar()),
                                self._act("Contorno elástico da seleção", slot=self.contorno_elastico)]
        self.act_dispor = self._act("Disposição &automática na mesa…", "grid_array", shortcut="Ctrl+Alt+D",
                                    slot=lambda: self.dispor_na_mesa())
        self.act_dispor.setToolTip("Arruma as peças na mesa sem sobrepor, com espaço e margem (nesting)")
        self.act_reunir_h = self._act("Reunir em &H (encostar lado a lado)", slot=lambda: self.reunir(True))
        self.act_reunir_v = self._act("Reunir em &V (encostar um sobre o outro)", slot=lambda: self.reunir(False))
        self.act_dois_pontos = self._act("Dimensionar/rotacionar por &dois pontos", shortcut="Ctrl+2",
                                         slot=self.dois_pontos)
        self.act_dois_pontos.setToolTip("Clique no ponto fixo, num ponto da peça e onde ele deve ficar")
        self.canvas.view.pontoColetado.connect(self._ponto_coletado)
        self.act_slots = self._act("Redimensionar &slots…", slot=lambda: self.redimensionar_slots())
        self.act_slots.setToolTip("Muda a largura dos encaixes para a espessura real da chapa")
        org += [None, self.act_reunir_h, self.act_reunir_v, self.act_dispor, self.act_slots, self.act_dois_pontos,
                self.act_contorno_redor, self.act_encaixar]
        self.act_bloquear = self._act("&Bloquear formas selecionadas", slot=lambda: self.bloquear(True))
        self.act_desbloquear = self._act("Desb&loquear formas selecionadas", slot=lambda: self.bloquear(False))
        org += [None, self.act_prender, self.act_soltar, None, self.act_bloquear, self.act_desbloquear]
        self._reorganizar_menu(menu("&Organizar", org))
        self.act_gabarito = self._act("&Gabarito na mesa…", slot=self._gabarito_dialogo)
        self.act_gabarito.setToolTip("Grade de células na mesa para produzir várias peças de uma vez")
        self.act_preencher = self._act("&Preencher gabarito com a seleção", slot=self.preencher_gabarito)
        self.act_preencher.setToolTip("Uma cópia da seleção em cada célula; textos variáveis usam linhas seguidas "
                                      "da planilha")
        self.act_mesa = self._act("Pró&xima mesa (avançar texto variável)", slot=self.avancar_mesa)
        self.act_frisos = self._act("&Frisos para dobra…", slot=self._frisos_dialogo)
        self.act_frisos.setToolTip("Painel com rebaixos paralelos para curvar MDF/compensado (kerf bending)")
        menu("&Produção", [self.act_frisos, None, self.act_gabarito, self.act_preencher,
                           self._act("&Remover gabarito", slot=lambda: self.definir_gabarito(None)), None,
                           self.act_mesa, self.act_lote])
        self.laser_menu = menu("&Laser", [self._act("Conectar ao equipamento", "connect", 13),
                        self._act("Enquadrar", "frame", 14), self._act("Ir para origem", "home", 14),
                        None, self._act("Iniciar trabalho", "play", 15),
                        self._act("Pausar", "pause", 15), self._act("Parar", "stop", 15), None,
                        self.act_preview, self.act_gcode, self.act_matriz, self.act_precisao, self.act_cal_xy,
                        self.act_comp_x, self.act_resultado,
                        self.act_rotativo, self.act_rot_liberar, self.act_rot_volta, self.act_rot_teste1,
                        self.act_rot_teste2, self.act_rot_corrigir, self.act_rot_religar,
                        self.act_maquina])

        win = mb.addMenu("&Janela")
        self._menus_vivos.append(win)
        for k in ("zoom_in", "zoom_out", "zoom_fit", "zoom_sel"):
            win.addAction(A[k])
        win.addSeparator()
        for d in self.docks:
            win.addAction(d.toggleViewAction())
        win.addSeparator()
        for tb in self.toolbars:
            win.addAction(tb.toggleViewAction())
        win.addSeparator()
        win.addAction(self._act("Restaurar layout padrão", slot=self.reset_layout))

        hlp = mb.addMenu("A&juda")
        self._menus_vivos.append(hlp)
        hlp.addAction(self.act_pesquisa)
        hlp.addSeparator()
        hlp.addAction(self._act("Sobre o RedBlack Laser", "info", slot=self._about))
        self._botoes_organizar(alinhar_dist_esp, mais[0])
        tools = self.barra_ferramentas
        tools.addSeparator()  # comandos de contorno que antes só estavam nos menus
        E = self.acts_editar
        self.acoes_contorno = {}
        for chave, k, ic, dica in (
                ("juntar", "juntar", "juntar", "Juntar pontas (Alt+J) — selecione linhas cujas pontas se tocam: viram "
                                               "uma linha só"),
                ("fechar", "close", "fechar_caminho", "Fechar caminho — liga a ponta final ao começo de uma linha "
                                                      "aberta"),
                ("duplicados", "dups", "duplicados", "Eliminar duplicados (Alt+D) — remove linhas repetidas por cima "
                                                     "(o laser não passa duas vezes)"),
                ("inverter", "reverse", "inverter_dir", "Inverter direção — troca o lado por onde o laser começa a "
                                                        "linha"),
                ("otimizar", "otimizar", "otimizar", "Otimizar formas (Alt+Shift+O) — tira nós em excesso (traçados de "
                                                     "imagem): corte mais liso e rápido")):
            a = E[k]
            a.setIcon(icon(ic))
            a.setToolTip(dica)
            tools.addAction(a)
            self.acoes_contorno[chave] = a
        from .dica_animada import instalar as instalar_dicas
        acoes_demo = dict(self.tools)
        acoes_demo["pan"] = self.tools["pan"]
        acoes_demo.update(self.acoes_contorno)
        acoes_demo.update(solda_macho=self.act_macho, solda_femea=self.act_femea)
        instalar_dicas(self.barra_ferramentas, acoes_demo, lambda: ler_pref(self.settings, "dicas_animadas"))
        instalar_dicas(self.barra_principal, {"pan": self.tools["pan"]}, lambda: ler_pref(self.settings, "dicas_animadas"))
        self._agrupar_barras()
        self.menu_plugins = self.menu_ferramentas.addMenu("&Plugins")  # plugins só acrescentam itens aqui
        self.menu_ferramentas.insertSeparator(self.menu_plugins.menuAction())
        plugins.carregar(self, self.menu_plugins)
        A = self.actions_by_key
        self.act_abrir_grupo = self._act("Abrir grupo (editar as peças)", slot=lambda: self.abrir_grupo())
        self.act_fechar_grupo = self._act("Fechar grupo", slot=lambda: self.fechar_grupo())
        E = self.acts_editar
        alinhar = QMenu("Alinhar e espelhar", self)
        for a in [*alinhar_dist_esp[:6], None, *alinhar_dist_esp[6:]]:
            alinhar.addSeparator() if a is None else alinhar.addAction(a)
        # mesma ordem do menu do botão direito do programa de referência
        self._contexto_itens = lambda: [E["cut"], A["copy"], A["paste"], E["paste_in_place"], self.act_duplicate, A["delete"],
                               None, A["select_all"], None, self.act_group, self.act_ungroup, self.act_abrir_grupo,
                               self.act_fechar_grupo, self.act_bloquear, None, self.act_curves, E["juntar"], E["close"],
                               E["bitmap"], None,
                               self.act_preview, E["tracar"], E["ajustar_imagem"], E["salvar_bitmap"], None,
                               self.act_encaixar, alinhar.menuAction(), self.act_rename]
        view = self.canvas.view
        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(self._menu_desenho)

    @property
    def _menu_contexto(self):
        """Itens do menu do botão direito (montados na hora: algumas ações são criadas depois)."""
        return self._contexto_itens()

    def _menu_desenho(self, pos):
        """Botão direito na área de desenho: comandos mais usados (inclui Agrupar/Desagrupar)."""
        view = self.canvas.view
        sob = next((i for i in view.items(pos) if isinstance(i, ob.Shape)), None)
        if sob is not None and not sob.isSelected():
            view.scene().clearSelection()  # clicar com o direito num objeto não selecionado seleciona só ele
            sob.setSelected(True)
        m = QMenu(self)
        for a in self._menu_contexto:
            m.addSeparator() if a is None else m.addAction(a)
        m.exec(view.viewport().mapToGlobal(pos))

    def _botoes_organizar(self, alinhar_dist_esp, act_centros):
        """Botões na barra Principal (organizar) e na barra Ferramentas (formas), como no programa de referência.
        Reaproveita os comandos dos menus: mesmo atalho, mesma habilitação, mesmo desfazer."""
        A = self.actions_by_key
        nomes = ("align_left", "align_hcenter", "align_right", "align_top", "align_vcenter", "align_bottom",
                 "dist_h", "dist_v", "flip_h", "flip_v")
        for a, nome in zip(alinhar_dist_esp, nomes):
            a.setIcon(icon(nome))
        for a, nome in ((A["zoom_sel"], "zoom_sel"), (self.act_group, "group"), (self.act_ungroup, "ungroup"),
                        (self.act_espelho_linha, "mirror_line"), (act_centros, "align_centers"),
                        (self.act_grade, "grid_array"), (self.act_circular, "circ_array"),
                        (self.act_copiar_caminho, "copy_path")):
            a.setIcon(icon(nome))
        for a, nome in zip(self.acts_bool, ("offset", "weld", "union", "subtract", "intersect")):
            a.setIcon(icon(nome))
        main = self.barra_principal
        main.insertAction(A["zoom_in"], self.tools["pan"])
        main.insertAction(A["zoom_out"], A["zoom_sel"])  # ordem: mover vista, aproximar, ajustar seleção, afastar
        main.addAction(self.act_maquina)
        self.act_tela_corte = self._act("Tela de corte", "tela_corte", shortcut="F9")
        self.act_tela_corte.setCheckable(True)
        self.act_tela_corte.setToolTip("Tela de corte (F9): só para acompanhar o trabalho — tempo decorrido e "
                                       "restante, Pausar e PARAR grandes. F9 de novo volta para a edição.")
        self.act_tela_corte.toggled.connect(self._modo_corte)
        main.addAction(self.act_tela_corte)
        main.addSeparator()
        for a in [self.act_group, self.act_ungroup, None, *alinhar_dist_esp[8:], self.act_espelho_linha, None,
                  act_centros, *alinhar_dist_esp[:8]]:
            main.addSeparator() if a is None else main.addAction(a)
        ferr = self.barra_ferramentas
        ferr.addSeparator()
        for a in [*self.acts_bool[:5], self.act_macho, self.act_femea, None, self.act_grade, self.act_circular, self.act_copiar_caminho]:
            ferr.addSeparator() if a is None else ferr.addAction(a)

    # ---------- barras ----------
    def _build_toolbars(self):
        self.toolbars = []
        view = self.canvas.view
        undo = self.undo_stack.createUndoAction(self, "&Desfazer")
        undo.setIcon(icon("undo"))
        undo.setShortcuts(QKeySequence.Undo)
        redo = self.undo_stack.createRedoAction(self, "&Refazer")
        redo.setIcon(icon("redo"))
        redo.setShortcuts(QKeySequence.Redo)
        A = self.actions_by_key = {
            "new": self._act("&Novo", "new", shortcut=QKeySequence.New, slot=self.new_document),
            "open": self._act("&Abrir…", "open", shortcut=QKeySequence.Open, slot=self.open_dialog),
            "save": self._act("&Salvar", "save", shortcut=QKeySequence.Save, slot=self.save),
            "save_as": self._act("Salvar &como…", shortcut=QKeySequence.SaveAs, slot=self.save_as),
            "import": self._act("&Importar…", "import", shortcut="Ctrl+I", slot=self.import_dialog),
            "export": self._act("&Exportar G-code…", "export", shortcut="Ctrl+Shift+G", slot=self.export_gcode),
            "undo": undo,
            "redo": redo,
            "copy": self._act("&Copiar", "copy", shortcut=QKeySequence.Copy, slot=self.copy),
            "paste": self._act("C&olar", "paste", shortcut=QKeySequence.Paste, slot=self.paste),
            "delete": self._act("E&xcluir", "delete", shortcut=QKeySequence.Delete, slot=self.delete),
            "select_all": self._act("Selecionar &tudo", shortcut=QKeySequence.SelectAll, slot=self.select_all),
            "zoom_in": self._act("Aproximar", "zoom_in", shortcut=QKeySequence.ZoomIn,
                                 slot=lambda: view.zoom_center(ZOOM_STEP)),
            "zoom_out": self._act("Afastar", "zoom_out", shortcut=QKeySequence.ZoomOut,
                                  slot=lambda: view.zoom_center(1 / ZOOM_STEP)),
            "zoom_fit": self._act("Ajustar à mesa", "zoom_fit", shortcut="Ctrl+0", slot=view.fit),
            "zoom_sel": self._act("Ajustar à &seleção", shortcut="Ctrl+Shift+0",
                                  slot=lambda: view.ajustar_a(ob.bounds(view.selected()) if view.selected() else QRectF())),
            "settings": self._act("&Configurações…", "settings", slot=self._preferencias_dialogo),
        }
        main = self.barra_principal = self._toolbar("Principal", Qt.TopToolBarArea)
        self.act_preview = self._act("&Prévia do percurso", "preview", shortcut="Alt+P",
                                     slot=None)
        self.act_preview.setCheckable(True)
        self.act_preview.setToolTip("Prévia do percurso e estimativa de tempo (Alt+P) — nada é enviado à máquina")
        self.act_preview.toggled.connect(self._toggle_preview)
        A["preview"] = self.act_preview
        self.act_matriz = self._act("&Matriz de testes de materiais…", "material", slot=self._matriz_dialogo)
        self.act_precisao = self._act("Teste de &precisão (escala e esquadro)…", slot=lambda: self.teste_precisao())
        self.act_cal_xy = self._act("Compensação do eixo &X…", slot=lambda: self.abrir_calibracao_xy())
        self.act_cal_xy.setToolTip("Cortes em X mais devagar que em Y (padrão −250 mm/min, mínimo 150): ajuste, "
                                   "teste SEM × COM")
        self.act_comp_x = self._act("Compensação do eixo X ligada")
        self.act_comp_x.setCheckable(True)
        self.act_comp_x.setToolTip("Liga/desliga a compensação do eixo X nos cortes (fica salvo)")
        self.act_comp_x.toggled.connect(self._ligar_comp_x)
        self.act_precisao.setToolTip("Quadrado de 100 mm, círculo, diagonais e régua: meça com paquímetro para "
                                     "conferir escala dos eixos e esquadro da máquina")
        self.act_matriz.setToolTip("Gera um G-code com quadrados em várias potências e velocidades para achar os "
                                   "parâmetros do material — nada é enviado à máquina")
        self.act_rotativo = self._act("Configuração do &rotativo…", slot=self._rotativo_dialogo)
        self.act_rot_teste1 = self._act("Rotativo: teste 1 — volta completa", slot=lambda: self.inserir_teste_rotativo(1))
        self.act_rot_teste1.setToolTip("Duas linhas a uma volta da peça de distância + escala: mostra quanto o "
                                       "'mm por rotação' está errado")
        self.act_rot_teste2 = self._act("Rotativo: teste 2 — medidas e escorregamento",
                                        slot=lambda: self.inserir_teste_rotativo(2))
        self.act_rot_teste2.setToolTip("Quadrado 20 mm, círculo, linhas e texto em 2 passadas: confere medida em "
                                       "volta, espelhado e se a peça escorrega")
        self.act_rot_corrigir = self._act("Rotativo: corrigir mm por rotação pelo teste 1…",
                                          slot=self._corrigir_rotativo_dialogo)
        self.act_rot_liberar = self._act("Rotativo: liberar GRBL ($20=0)…", slot=lambda: self.limite_grbl(False))
        self.act_rot_liberar.setToolTip("Desliga o limite de curso por software: com o rotativo o eixo gira sem fim")
        self.act_rot_religar = self._act("Rotativo: religar limite de curso ($20=1)…",
                                         slot=lambda: self.limite_grbl(True))
        self.act_rot_volta = self._act("Rotativo: CALIBRAR — girar uma volta da peça (sem laser)",
                                       slot=self.girar_uma_volta)
        self.act_rot_volta.setToolTip("Faça um risco na peça: ela tem que dar exatamente UMA volta. Depois diga "
                                      "quantas deu e o programa corrige sozinho")
        self.act_maquina = self._act("Configurações da &máquina…", "machine", slot=self._maquina_dialogo)
        self.act_maquina.setToolTip("Configurações da máquina: área da mesa, canto da origem, M3/M4, S máximo")
        self.act_resultado = self._act("Salvar material do &quadrado escolhido…", slot=self._resultado_matriz_dialogo)
        self.act_resultado.setToolTip("Depois de gravar a matriz: clique no melhor quadrado e salve como material")
        self.act_gcode = A["export"]  # mesmo comando em Arquivo e em Laser
        self.act_gcode.setToolTip("Gerar e salvar G-code (arquivo de texto) — nada é enviado à máquina")
        self.act_snap = self._act("&Encaixe em cantos e pontos", "snap", shortcut="F9")
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.setToolTip("Encaixe (F9): Medir, formas, linhas, texto e nós grudam em cantos, centros e "
                                 "pontos próximos. Segure Alt para desligar momentaneamente.")
        self.act_snap.toggled.connect(lambda on: setattr(view, "encaixe_ativo", on))
        A["snap"] = self.act_snap
        self.act_medidas = self._act("Mostrar &medidas", "measure", shortcut="F10")
        self.act_medidas.setCheckable(True)
        self.act_medidas.setToolTip("Mostrar medidas (F10): comprimento em cima da linha medida, largura e "
                                    "altura da seleção e das formas em desenho")
        self.act_medidas.toggled.connect(view.medidas.set_ativo)
        self.act_medidas.toggled.connect(lambda _: (setattr(view, "_sel_rect", QRectF()), view.refresh_selection()))
        self.act_medidas.toggled.connect(lambda on: self.settings.setValue("mostrar_medidas", on))
        self.act_medidas.setChecked(self.settings.value("mostrar_medidas", True, type=bool))
        view.medidas.set_ativo(self.act_medidas.isChecked())
        A["medidas"] = self.act_medidas
        self.act_forma = self._act("&Forma com medidas exatas…", shortcut="Ctrl+Shift+F", slot=self._forma_dialogo)
        self.act_forma.setToolTip("Círculo por diâmetro ou raio, elipse, retângulo com raio de canto ou polígono, "
                                  "com centro exato (Ctrl+Shift+F)")
        for k in ("new", "open", "save", None, "import", "export", None, "undo", "redo", None,
                  "copy", "paste", "delete", None, "zoom_in", "zoom_out", "zoom_fit", "snap", "medidas", "preview", None,
                  "settings"):
            main.addSeparator() if k is None else main.addAction(A[k])

        self.addToolBarBreak()
        props = self._toolbar("Propriedades do objeto", Qt.TopToolBarArea)
        props.addWidget(self._anchor_selector())
        self.fields = {}
        for key, label, suffix, lo, hi in (("x", "X", " mm", -10000, 10000), ("y", "Y", " mm", -10000, 10000),
                                           ("w", "Largura", " mm", 0.01, 10000), ("h", "Altura", " mm", 0.01, 10000),
                                           ("wp", "Escala L", " %", 0.1, 100000), ("hp", "Escala A", " %", 0.1, 100000),
                                           ("rot", "Girar", " °", -360, 360)):
            props.addWidget(QLabel(f" {label} "))
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(2)
            sb.setSuffix(suffix)
            sb.setMinimumWidth(96)
            sb.setAccessibleName(label)
            sb.valueChanged.connect(lambda _v, k=key: self._campo_digitado(k))  # aplica enquanto digita
            sb.editingFinished.connect(lambda k=key: self._campo_confirmado(k))
            props.addWidget(sb)
            self.fields[key] = sb
        self.fields["rot"].setToolTip("Ângulo da peça (positivo = horário), em torno do ponto escolhido no seletor "
                                      "de 9 pontos; digite o ângulo que a peça deve ficar.")
        for k in ("wp", "hp"):
            self.fields[k].setValue(100.0)
            self.fields[k].setMinimumWidth(78)
            self.fields[k].setToolTip("Escala em % do tamanho atual (com Manter proporção, as duas juntas); volta "
                                      "a 100 % depois de aplicar")
        props.addSeparator()
        self.lock = QCheckBox("Manter proporção")
        self.lock.setChecked(True)
        props.addWidget(self.lock)
        props.addSeparator()
        self.lb_lados = QLabel(" Lados ")
        props.addWidget(self.lb_lados)
        self.sides = QSpinBox()
        self.sides.setRange(3, 64)
        self.sides.setValue(6)
        self.sides.setAccessibleName("Lados do polígono ou pontas da estrela")
        self.sides.setToolTip("Lados da ferramenta Polígono / pontas da ferramenta Estrela")
        self.sides.valueChanged.connect(self._lados_mudou)
        props.addWidget(self.sides)
        self.lb_raio = QLabel(" Raio ")
        props.addWidget(self.lb_raio)
        self.raio = QDoubleSpinBox()
        self.raio.setRange(0, 1000)
        self.raio.setDecimals(2)
        self.raio.setSuffix(" mm")
        self.raio.setAccessibleName("Raio de canto")
        self.raio.setToolTip("Raio de canto: usado ao desenhar retângulos e por Organizar → Arredondar cantos "
                             "(0 = cantos vivos)")
        self.raio.setKeyboardTracking(False)
        self.raio.valueChanged.connect(lambda _v: self._raio_editado())
        self.raio.valueChanged.connect(lambda _v: self._bolear_previa(*self._bolear_ultimo) if
                                       self.tools["bolear"].isChecked() and getattr(self, "_bolear_ultimo", None)
                                       else None)  # prévia acompanha o raio digitado
        props.addWidget(self.raio)

        tools = self.barra_ferramentas = self._toolbar("Ferramentas", Qt.LeftToolBarArea)
        group = QActionGroup(self)
        self.tools = {}
        for key, text, stage in (("select", "Selecionar", None), ("node", "Editar nós", None),
                                 ("pen", "Desenhar linhas", None), ("rect", "Retângulo", None),
                                 ("ellipse", "Elipse", None), ("polygon", "Polígono", None),
                                 ("star", "Estrela", None), ("text", "Texto", None), ("measure", "Medir", None),
                                 ("trim", "Aparar formas", None), ("bolear", "Bolear (arredondar cantos)", None)):
            a = self._act(text, key, stage)
            a.setCheckable(True)
            group.addAction(a)
            tools.addAction(a)
            self.tools[key] = a
        pre = self.tools["preset"] = self._act("Forma pronta")
        pre.setCheckable(True)
        group.addAction(pre)
        pre.toggled.connect(lambda on: self._on_draw_tool("preset", on))
        for k in ("star", "polygon"):
            self.tools[k].toggled.connect(lambda _=False: self._ferramenta_campo_lados())
        self.raio_bolear = QDoubleSpinBox()
        self.raio_bolear.setRange(0.1, 1000)
        self.raio_bolear.setDecimals(1)
        self.raio_bolear.setValue(self.RAIO_BOLEAR_PADRAO)
        self.raio_bolear.setSuffix(" mm")
        self.raio_bolear.setMaximumWidth(78)
        self.raio_bolear.setToolTip("Raio do Bolear (passe o mouse num canto para ver a prévia)")
        self.raio_bolear.setAccessibleName("Raio do bolear")
        self.raio_bolear.valueChanged.connect(self._raio_bolear_mudou)
        acoes = tools.actions()
        depois = acoes[acoes.index(self.tools["bolear"]) + 1] if self.tools["bolear"] in acoes[:-1] else None
        if depois is not None:
            tools.insertWidget(depois, self.raio_bolear)
        else:
            tools.addWidget(self.raio_bolear)
        menu_fp = self._menu_formas_prontas()
        for k in ("rect", "ellipse", "polygon", "star"):  # segurar o botão (ou a setinha) abre as formas prontas
            bt = tools.widgetForAction(self.tools[k])
            if bt is not None:
                bt.setMenu(menu_fp)
                bt.setPopupMode(QToolButton.DelayedPopup)
                bt.setToolTip(bt.toolTip() + "  —  segure para escolher uma forma pronta")
        pan = self.tools["pan"] = self._act("Mover a vista", "pan")
        pan.setCheckable(True)
        pan.setShortcut(QKeySequence("H"))
        pan.setToolTip("Mover a vista (H) — arraste com o botão esquerdo; também: segure Espaço ou o botão do meio")
        group.addAction(pan)  # vai para a barra Principal em _botoes_organizar
        pan.toggled.connect(view.set_pan_mode)
        self.tools["select"].setChecked(True)
        m = self.tools["measure"]
        m.setShortcut(QKeySequence("M"))
        m.setToolTip("Medir (M) — arraste na área de desenho; Esc encerra")
        m.toggled.connect(self._on_measure_toggled)
        view.toolExit.connect(lambda: self.tools["select"].setChecked(True))
        t = self.tools["text"]
        t.setShortcut(QKeySequence("T"))
        t.setToolTip("Texto (T) — clique na área de desenho; duplo clique num texto para editar")
        t.toggled.connect(view.set_text_mode)
        view.textRequested.connect(self._on_text_click)
        view.editTextRequested.connect(self.edit_text)
        view.duploCliqueVazio.connect(self.laser_ate_ponto)
        view.soltouArquivos.connect(self.soltar)
        # Formas: atalhos da referência (Ctrl+R, Ctrl+E, Ctrl+L, Ctrl+`).
        for key, kind, sc, tip in (
            ("rect", "rect", "Ctrl+R", "Retângulo (Ctrl+R) — arraste; Shift: quadrado; Ctrl: a partir do centro"),
            ("ellipse", "ellipse", "Ctrl+E", "Elipse (Ctrl+E) — arraste; Shift: círculo; Ctrl: a partir do centro"),
            ("polygon", "polygon", None, "Polígono — arraste do centro até um vértice; lados na barra de propriedades"),
            ("star", "star", None, "Estrela — arraste do centro até uma ponta; número de pontas no campo Lados"),
            ("trim", "trim", "Ctrl+K", "Aparar formas (Ctrl+K) — clique num trecho entre dois cruzamentos para "
                                       "apagá-lo (o trecho fica vermelho antes); Esc encerra"),
            ("bolear", "bolear", "Ctrl+Shift+R", "Bolear (Ctrl+Shift+R) — passe o mouse num canto: prévia em "
                                                 "vermelho; clique: arredonda; clique de novo: 45°; de novo: canto "
                                                 "vivo. Clique na peça: todos os cantos; Shift+clique: pontas "
                                                 "totalmente redondas (pega). Raio no campo logo abaixo do botão."),
            ("pen", "line", "Ctrl+L", "Linhas (Ctrl+L) — clique ponto a ponto; clique no 1º ponto fecha; "
                                      "duplo clique/Enter termina; Shift: 45°; Esc cancela"),
        ):
            a = self.tools[key]
            if sc:
                a.setShortcut(QKeySequence(sc))
            a.setToolTip(tip)
            a.toggled.connect(lambda on, k=kind: self._on_draw_tool(k, on))
        n = self.tools["node"]
        n.setShortcut(QKeySequence("Ctrl+`"))
        n.setToolTip("Editar nós (Ctrl+`) — arraste os pontos (quadrados) e as alças das curvas (bolinhas); com o "
                     "cursor sobre um nó/trecho: D exclui, I insere, M insere no meio, L troca reta/curva, C canto, "
                     "S suave, B quebra. Grupos: desagrupe antes (Ctrl+U); textos: converta em curvas.")
        n.toggled.connect(lambda on: on and self._aviso_nos())
        n.toggled.connect(view.set_node_mode)
        view.shapeCreated.connect(self.create_shape)
        view.aparoPedido.connect(self.aparar_em)
        view.noOperacao.connect(self.operacao_no)
        view.aparoSobre.connect(self._aparo_realce)
        view.grupoAbrir.connect(self.abrir_grupo)
        view.bolearPedido.connect(self.bolear_em)
        self.tools["bolear"].toggled.connect(self._bolear_ativado)
        view.bolearSobre.connect(self._bolear_previa)
        self.tools["select"].setShortcut(QKeySequence("V"))

        self._barra_texto()
        pal = self._toolbar("Paleta de camadas", Qt.BottomToolBarArea)
        for lid, c in zip(cm.IDS, cm.PALETA):
            b = QToolButton()
            b.setText(lid[1:])
            fg = "#000" if QColor(c).lightness() > 120 else "#fff"
            b.setStyleSheet(f"QToolButton{{background:{c};color:{fg};min-width:26px;border-radius:2px}}")
            b.setAccessibleName(f"Atribuir camada {lid}")
            b.setToolTip(f"Atribuir a seleção à camada {lid}")
            b.clicked.connect(lambda _=False, x=lid: self.assign_layer(x))
            pal.addWidget(b)

    def _garantir_quebra_texto(self):
        """Layouts salvos antes da barra Texto a punham na linha das propriedades (fica cortada)."""
        if not self.toolBarBreak(self.barra_texto):
            self.insertToolBarBreak(self.barra_texto)

    def _barra_texto(self):
        """Propriedades do texto selecionado, editáveis direto (como no programa de referência)."""
        from PySide6.QtWidgets import QFontComboBox
        self.addToolBarBreak()  # linha própria: na mesma linha das propriedades ela ficava cortada
        tb = self.barra_texto = self._toolbar("Texto", Qt.TopToolBarArea)
        t = self.texto_campos = {}
        t["fonte"] = QFontComboBox()
        t["fonte"].setMaximumWidth(180)
        t["fonte"].setAccessibleName("Fonte do texto")
        t["altura_mm"] = QDoubleSpinBox()
        t["altura_mm"].setRange(0.1, 1000)
        t["altura_mm"].setDecimals(2)
        t["altura_mm"].setSuffix(" mm")
        t["altura_mm"].setKeyboardTracking(False)
        t["altura_mm"].setToolTip("Altura do X maiúsculo")
        t["espacamento"] = QDoubleSpinBox()
        t["espacamento"].setRange(0.1, 10)
        t["espacamento"].setDecimals(2)
        t["espacamento"].setKeyboardTracking(False)
        t["espacamento"].setToolTip("Entrelinha (multiplicador)")
        t["negrito"], t["italico"] = QCheckBox("Negrito"), QCheckBox("Itálico")
        t["maiusculas"], t["distorcer"], t["soldado"] = (QCheckBox("Maiúsculas"), QCheckBox("Distorcer"),
                                                         QCheckBox("Soldado"))
        t["maiusculas"].setToolTip("Forçar o texto a ser maiúsculo (o que foi digitado é mantido)")
        t["distorcer"].setToolTip("No texto ao longo do caminho, as letras curvam junto com o caminho")
        t["soldado"].setToolTip("Funde as letras que se tocam num contorno só (corta sem passar duas vezes)")
        t["alinhamento"] = QComboBox()
        for k in tx.ALINHAMENTOS:
            t["alinhamento"].addItem(k.capitalize(), k)
        for rot, chave in ((" Fonte ", "fonte"), (" Altura ", "altura_mm"), (None, "negrito"), (None, "italico"),
                           (None, "maiusculas"), (None, "distorcer"), (None, "soldado"),
                           (" Alinhar ", "alinhamento"), (" Entrelinha ", "espacamento")):
            if rot:
                tb.addWidget(QLabel(rot))
            tb.addWidget(t[chave])
        t["fonte"].currentFontChanged.connect(lambda f: self._texto_campo("fonte", f.family()))
        t["altura_mm"].valueChanged.connect(lambda v: self._texto_campo("altura_mm", v))
        t["espacamento"].valueChanged.connect(lambda v: self._texto_campo("espacamento", v))
        t["negrito"].toggled.connect(lambda v: self._texto_campo("negrito", v))
        t["italico"].toggled.connect(lambda v: self._texto_campo("italico", v))
        for k in ("maiusculas", "distorcer", "soldado"):
            t[k].toggled.connect(lambda v, k=k: self._texto_campo(k, v))
        t["alinhamento"].activated.connect(lambda _=0: self._texto_campo("alinhamento",
                                                                          t["alinhamento"].currentData()))
        self._sync_texto()

    def _textos_sel(self):
        return [s for s in self._sel() if isinstance(s, ob.TextShape)]

    def _sync_texto(self):
        if not hasattr(self, "texto_campos"):
            return
        textos = self._textos_sel()
        t = self.texto_campos
        self._syncing_texto = True
        for w in t.values():
            w.setEnabled(bool(textos))
        if textos:
            pr = textos[0].params
            from PySide6.QtGui import QFont
            t["fonte"].setCurrentFont(QFont(pr.fonte))
            t["altura_mm"].setValue(pr.altura_mm)
            t["espacamento"].setValue(pr.espacamento)
            t["negrito"].setChecked(pr.negrito)
            t["italico"].setChecked(pr.italico)
            for k in ("maiusculas", "distorcer", "soldado"):
                t[k].setChecked(getattr(pr, k))
            t["alinhamento"].setCurrentIndex(max(0, t["alinhamento"].findData(pr.alinhamento)))
        self._syncing_texto = False

    def _texto_campo(self, campo, valor) -> bool:
        """Aplica a mudança a todos os textos selecionados (desfazível); a matriz da peça fica."""
        if getattr(self, "_syncing_texto", False):
            return False
        textos = [x for x in self._textos_sel() if getattr(x.params, campo) != valor]
        if not textos:
            return False
        if campo == "fonte" and not tx.font_available(valor):
            return False

        def do():
            for x in textos:
                x.set_params(replace(x.params, **{campo: valor}))
            self._rebuild_objects()

        self._edit("Texto: " + campo, do)
        self.canvas.view.refresh_selection()
        return True

    # ---------- barras agrupadas (clique e segure para trocar) e menu Organizar em submenus ----------
    GRUPOS_BARRA = (
        ("Ferramentas", "Formas", ("Retângulo", "Elipse", "Polígono", "Estrela")),
        ("Ferramentas", "Aparar e bolear", ("Aparar formas", "Bolear (arredondar cantos)")),
        ("Ferramentas", "Deslocar e booleanas", ("Deslocar formas…", "Formas de solda", "União booleana",
                                                 "Subtrair (booleana)", "Interseção booleana")),
        ("Ferramentas", "Matrizes", ("Matriz em grade…", "Matriz circular…", "Copiar ao longo do caminho…")),
        ("Ferramentas", "Contornos", ("Associar formas selecionadas (juntar pontas)", "Fechar caminho",
                                      "Eliminar duplicados", "Inverter direção da forma",
                                      "Otimizar formas selecionadas…")),
        ("Principal", "Arquivo", ("Importar…", "Exportar G-code…")),
        ("Principal", "Zoom", ("Aproximar", "Afastar", "Ajustar à mesa")),  # "à seleção" fica fora: desabilita sem seleção
        ("Principal", "Configurações", ("Configurações…", "Configurações da máquina…")),
        ("Principal", "Agrupar", ("Agrupar", "Desagrupar / separar")),
        ("Principal", "Espelhar", ("Espelhar na horizontal", "Espelhar na vertical", "Espelhar ao longo da linha")),
        ("Principal", "Alinhar", ("Alinhar centros (H e V)", "Alinhar à esquerda", "Alinhar centros na horizontal",
                                  "Alinhar à direita", "Alinhar ao topo", "Alinhar centros na vertical",
                                  "Alinhar à base")),
        ("Principal", "Distribuir", ("Distribuir na horizontal", "Distribuir na vertical")),
    )

    def _agrupar_barras(self):
        """Junta ferramentas parecidas num só botão: clique usa a última escolhida; clique e segure (ou o botão
        direito) abre as outras. Menos botões = as barras cabem em telas menores."""
        self.grupos_barra = []
        barras = {tb.windowTitle(): tb for tb in self.toolbars}
        for nome_barra, titulo, textos in self.GRUPOS_BARRA:
            tb = barras.get(nome_barra)
            if tb is None:
                continue
            por_texto = {a.text().replace("&", ""): a for a in tb.actions()}
            acoes = [por_texto[t] for t in textos if t in por_texto]
            if len(acoes) < 2:
                continue
            bt = QToolButton(tb)
            bt.setObjectName(f"grupo_{titulo}")
            bt.setPopupMode(QToolButton.DelayedPopup)
            bt.setAutoRaise(True)
            menu = QMenu(titulo, bt)
            for a in acoes:
                menu.addAction(a)
            if titulo == "Formas":
                menu.addSeparator()
                menu.addMenu(self._menu_formas_prontas())
            bt.setMenu(menu)
            chave = f"grupo_barra/{titulo}"
            salvo = self.settings.value(chave, "")
            padrao = next((a for a in acoes if a.text().replace("&", "") == salvo), acoes[0])
            nomes = ", ".join(a.text().replace("&", "").rstrip("…") for a in acoes)

            def escolher(a, bt=bt, chave=chave, nomes=nomes):
                bt.setDefaultAction(a)
                bt.setToolTip(f"{a.toolTip()}  —  clique e segure para: {nomes}")
                self.settings.setValue(chave, a.text().replace("&", ""))
            escolher(padrao)
            for a in acoes:
                a.triggered.connect(lambda _=False, a=a, f=escolher, bt=bt: bt.defaultAction() is a or f(a))
                if a.isCheckable():  # ferramenta ativada por atalho: o botão passa a mostrar ela
                    a.toggled.connect(lambda on, a=a, f=escolher, bt=bt: on and bt.defaultAction() is not a and f(a))
            bt.setContextMenuPolicy(Qt.CustomContextMenu)
            bt.customContextMenuRequested.connect(lambda _p, bt=bt: bt.showMenu())
            tb.insertWidget(acoes[0], bt)
            for a in acoes:
                tb.removeAction(a)
            filtro = getattr(tb, "_filtro_dicas", None)
            if filtro is not None:
                bt.installEventFilter(filtro)
            self.grupos_barra.append((titulo, acoes))
        self._ajustar_icones()

    def _garantir_largura_docks(self):
        """O painel lateral nunca fica mais estreito que o conteúdo (tabela de camadas, botões da Máquina): mede o
        mínimo de cada painel na tela real (fonte e zoom do Windows) e alarga só se faltar espaço."""
        docks = [d for d in self.docks if d.isVisible() and self.dockWidgetArea(d) == Qt.RightDockWidgetArea]
        if not docks:
            return
        precisa = max(d.widget().widget().minimumSizeHint().width() for d in docks) + 28  # + barra de rolagem
        precisa = min(precisa, int(self.width() * 0.45))  # nunca mais que 45 % da janela
        if docks[0].width() < precisa:
            self.resizeDocks([docks[0]], [precisa], Qt.Horizontal)

    def _ajustar_icones(self):
        """Ícones menores em telas baixas (notebook): as barras cabem sem esconder itens."""
        tela = self.screen().availableGeometry() if self.screen() else None
        alt = tela.height() if tela else 1080
        lado = 18 if alt < 800 else 20 if alt < 1000 else 22
        for tb in self.toolbars:
            tb.setIconSize(QSize(lado, lado))
        self._alinhar_barra_lateral(lado)

    def _alinhar_barra_lateral(self, lado):
        """Barra lateral em coluna: todos os botões do mesmo tamanho (os com setinha de menu ficavam mais largos e
        encostados à esquerda) e o campo do raio do bolear na mesma largura (passava da barra)."""
        tb = getattr(self, "barra_ferramentas", None)
        if tb is None:
            return
        larg, alt = lado + 18, lado + 12
        for bt in tb.findChildren(QToolButton):
            if bt.parent() is tb and bt.objectName() != "qt_toolbar_ext_button":
                bt.setFixedSize(larg, alt)
        r = getattr(self, "raio_bolear", None)
        if r is not None:
            r.setButtonSymbols(QAbstractSpinBox.NoButtons)  # roda do mouse e setas do teclado ainda mudam o valor
            r.setSuffix("")
            r.setAlignment(Qt.AlignCenter)
            r.setFixedWidth(larg)

    def _reorganizar_menu(self, m):
        """O menu Organizar tinha ~55 itens numa lista só: agrupa em submenus por assunto."""
        regras = (("Alinhar", ("Alinhar",)),
                  ("Distribuir e igualar", ("Distribuir", "Mesma ", "Reunir")),
                  ("Espelhar, girar e transformar", ("Espelhar", "Girar", "Cisalhar", "Dimensionar/rotacionar")),
                  ("Agrupar", ("Agrupar", "Autoagrupar", "Desagrupar")),
                  ("Ordem de corte", ("ordem de corte", "Cortar primeiro", "Cortar por último")),
                  ("Matrizes e cópias", ("Matriz", "Copiar ao longo")),
                  ("Âncora e bloqueio", ("âncora", "Bloquear", "Desbloquear")))
        subs = {t: QMenu(t, m) for t, _ in regras}
        restantes = []
        for a in list(m.actions()):
            texto = a.text().replace("&", "")
            alvo = None if a.isSeparator() or a.menu() else next(
                (t for t, chaves in regras if any(texto.startswith(k) or k in texto for k in chaves)), None)
            m.removeAction(a)
            if alvo:
                subs[alvo].addAction(a)
            elif not a.isSeparator():
                restantes.append(a)
        for t, _ in regras:
            if not subs[t].isEmpty():
                m.addMenu(subs[t])
        m.addSeparator()
        for a in restantes:
            m.addAction(a)
        self._submenus_organizar = list(subs.values())  # mantém vivos (ver _menus_vivos)
        return m

    def _toolbar(self, title, area):
        tb = QToolBar(title, self)
        tb.setObjectName("tb_" + title)
        tb.setIconSize(QSize(22, 22))
        self.addToolBar(area, tb)
        self.toolbars.append(tb)
        return tb

    # ---------- painéis ----------
    def _dock(self, title, widget, area):
        d = QDockWidget(title, self)
        d.setObjectName("dock_" + title)
        # Rolagem: painéis podem encolher em telas baixas sem forçar a altura da janela.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(widget)
        d.setWidget(scroll)
        self.addDockWidget(area, d)
        self.docks.append(d)
        return d

    def _build_docks(self):
        self.docks = []
        layers = self._dock("Camadas", self._layers_panel(), Qt.RightDockWidgetArea)
        machine = self._dock("Máquina", self._machine_panel(), Qt.RightDockWidgetArea)
        objects = self.objects_dock = self._dock("Objetos", self._objects_panel(), Qt.RightDockWidgetArea)
        materials = self._dock("Materiais", self._materials_panel(), Qt.RightDockWidgetArea)
        self.vars_panel = PainelVariaveis()
        variaveis = self._dock("Texto variável", self.vars_panel, Qt.RightDockWidgetArea)
        p = self.vars_panel
        p.btn_csv.clicked.connect(self._carregar_csv_dialogo)
        p.btn_lote.clicked.connect(self._exportar_lote_dialogo)
        p.linhaEscolhida.connect(lambda i: self.set_vars(self.vars.na_linha(i), f"Linha {i + 1} da planilha"))
        p.contadorAlterado.connect(lambda n, inc: self.set_vars(replace(self.vars, contador=n, incremento=inc),
                                                                "Contador do texto variável"))
        p.avancarPedido.connect(self.avancar_mesa)
        p.limparPedido.connect(lambda: self.set_vars(vr.DadosVariaveis(), "Remover planilha"))
        self.preview_panel = PainelPrevia()
        self.preview_dock = self._dock("Prévia do percurso", self.preview_panel, Qt.BottomDockWidgetArea)
        self.preview_dock.hide()  # só abre pela ação Prévia (Alt+P)
        ov = self.canvas.view.percurso_overlay
        self.preview_panel.tempoChanged.connect(ov.set_tempo)
        self.preview_panel.mostrarVaziosChanged.connect(ov.set_mostrar_vazios)
        self.preview_panel.rapidoChanged.connect(lambda _: self._refresh_preview())
        self.preview_dock.visibilityChanged.connect(self._on_preview_visibility)
        self.undo_stack.indexChanged.connect(self._refresh_preview)
        self.undo_stack.indexChanged.connect(self._agendar_tempo)
        self.abas.currentChanged.connect(self._agendar_tempo)
        self._agendar_tempo()
        self.splitDockWidget(layers, machine, Qt.Vertical)
        self._docks_padrao = (layers, machine)
        self.tabifyDockWidget(layers, objects)
        self.tabifyDockWidget(objects, variaveis)
        self.notas_edit = QPlainTextEdit()
        self.notas_edit.setPlaceholderText("Notas deste projeto (material, foco, ajustes que deram certo…). "
                                           "Ficam salvas dentro do projeto.")
        self.notas_edit.setAccessibleName("Notas do projeto")
        self._notas_timer = QTimer(self)
        self._notas_timer.setSingleShot(True)
        self._notas_timer.setInterval(800)  # digitando: vira um passo no desfazer depois de uma pausa
        self._notas_timer.timeout.connect(self._notas_editadas)
        self.notas_edit.textChanged.connect(lambda: None if self._syncing_notas else self._notas_timer.start())
        self._syncing_notas = False
        self.notas_dock = self._dock("Notas", self.notas_edit, Qt.RightDockWidgetArea)
        self.notas_dock.hide()
        from PySide6.QtWidgets import QUndoView
        hist = QUndoView(self.undo_stack)
        hist.setEmptyLabel("(projeto aberto)")
        hist.setAccessibleName("Histórico de anulações")
        hist.setToolTip("Clique num passo para voltar até ele; clique num passo abaixo para refazer")
        self.historico_dock = self._dock("Histórico", hist, Qt.RightDockWidgetArea)
        self.tabifyDockWidget(variaveis, self.historico_dock)
        self.tabifyDockWidget(machine, materials)
        layers.raise_()
        machine.raise_()
        self.resizeDocks([layers], [430], Qt.Horizontal)

    def _demo_note(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("banner")
        lbl.setWordWrap(True)
        return lbl

    def _layers_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.tempo_label = QLabel("Tempo estimado: calculando…")
        self.tempo_label.setToolTip("Tempo de laser estimado (percurso + deslocamentos, sem aceleração). "
                                    "Recalcula sozinho 1,5 s depois de cada mudança. Orçamento: Ferramentas → Plugins")
        self.tempo_label.setStyleSheet("font-weight:bold;padding:4px 2px")
        self.tempo_label.setWordWrap(True)
        v.addWidget(self.tempo_label)
        v.addWidget(self._demo_note("Valores padrão NÃO validados para máquina/material: teste antes de usar "
                                    "(matriz de testes na Etapa 18). Velocidade em mm/min."))
        t = self.layer_table = QTableWidget(0, 7)
        t.setContextMenuPolicy(Qt.CustomContextMenu)
        t.customContextMenuRequested.connect(self._menu_camadas)
        t.setHorizontalHeaderLabels(["Cor", "Camada", "Saída", "Exibir", "Modo", "Vel. mm/min / Pot.", "Pass."])
        t.horizontalHeaderItem(COL_SAIDA).setToolTip("Enviar esta camada ao laser")
        t.horizontalHeaderItem(COL_EXIBIR).setToolTip("Mostrar na área de desenho (não afeta a saída)")
        t.horizontalHeaderItem(6).setToolTip("Passadas")
        t.verticalHeader().hide()
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # nome da camada ocupa a sobra (sem vão cinza)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setAccessibleName("Camadas em uso, na ordem de saída")
        t.setMinimumHeight(140)
        t.itemSelectionChanged.connect(lambda: None if self._syncing else self._fill_layer_form())
        t.itemChanged.connect(self._on_layer_item_changed)
        v.addWidget(t, 1)

        order = QHBoxLayout()
        for text, delta, tip in (("▲ Subir", -1, "Sai antes"), ("▼ Descer", 1, "Sai depois")):
            b = QPushButton(text)
            b.setToolTip(f"{tip}: a lista é processada de cima para baixo")
            b.clicked.connect(lambda _=False, d=delta: self._move_current_layer(d))
            order.addWidget(b)
        order.addStretch(1)
        v.addLayout(order)

        form = QFormLayout()
        f = self.layer_form = {}
        f["nome"] = QLineEdit()
        f["nome"].editingFinished.connect(lambda: self._on_layer_form("nome"))
        form.addRow("Nome", f["nome"])
        f["modo"] = QComboBox()
        f["modo"].activated.connect(lambda _=0: self._on_layer_form("modo"))
        form.addRow("Modo", f["modo"])
        for key, label, (lo, hi), suf, dec in (
            ("velocidade_mm_min", "Velocidade", cm.LIMITES["velocidade_mm_min"], " mm/min", 0),
            ("potencia_max", "Potência máx.", cm.LIMITES["potencia_max"], " %", 1),
            ("potencia_min", "Potência mín.", cm.LIMITES["potencia_min"], " %", 1),
            ("passadas", "Passadas", cm.LIMITES["passadas"], "", None),
            ("intervalo_mm", "Intervalo de linhas", cm.LIMITES["intervalo_mm"], " mm", 3),
            ("kerf_mm", "Kerf (largura do corte)", cm.LIMITES["kerf_mm"], " mm", 3),
            ("angulo_graus", "Ângulo de varredura", cm.LIMITES["angulo_graus"], " °", 1),
            ("angulo_inc_graus", "Incremento de ângulo por passada", cm.LIMITES["angulo_inc_graus"], " °", 1),
            ("sobrevarredura_mm", "Sobrevarredura", cm.LIMITES["sobrevarredura_mm"], " mm", 2),
            ("guias_qtd", "Guias (pontes) por contorno", cm.LIMITES["guias_qtd"], "", None),
            ("guias_mm", "Largura das guias", cm.LIMITES["guias_mm"], " mm", 2),
            ("sobrecorte_mm", "Sobrecorte", cm.LIMITES["sobrecorte_mm"], " mm", 2),
            ("entrada_mm", "Entrada do corte (lead-in)", cm.LIMITES["entrada_mm"], " mm", 2),
            ("saida_corte_mm", "Saída do corte (lead-out)", cm.LIMITES["saida_corte_mm"], " mm", 2),
            ("limiar_pct", "Limiar da imagem", cm.LIMITES["limiar_pct"], " %", 0),
            ("brilho_pct", "Brilho da imagem", cm.LIMITES["brilho_pct"], " %", 0),
            ("contraste_pct", "Contraste da imagem", cm.LIMITES["contraste_pct"], " %", 0),
            ("gama", "Gama da imagem", cm.LIMITES["gama"], "", 2),
            ("meio_tom_cpi", "Meio-tom: células por polegada", cm.LIMITES["meio_tom_cpi"], "", 1),
            ("meio_tom_angulo", "Meio-tom: ângulo", cm.LIMITES["meio_tom_angulo"], " °", 1),
        ):
            sb = QSpinBox() if dec is None else QDoubleSpinBox()
            if dec is not None:
                sb.setDecimals(dec)
            sb.setRange(lo, hi)
            sb.setSuffix(suf)
            sb.setKeyboardTracking(False)
            sb.setAccessibleName(label)
            sb.editingFinished.connect(lambda k=key: self._on_layer_form(k))
            form.addRow(label, sb)
            f[key] = sb
        f["varrer_y"] = QCheckBox("↕ Varrer no eixo Y (linhas verticais)")
        f["varrer_y"].setToolTip("Gravação (preenchimento/imagem) indo e voltando no eixo Y em vez do X: "
                                 "mesmo que Ângulo de varredura = 90°")
        f["varrer_y"].toggled.connect(lambda _=False: self._on_layer_form("varrer_y"))
        form.insertRow(form.getWidgetPosition(f["angulo_graus"])[0], "", f["varrer_y"])
        f["kerf_mm"].setToolTip("Compensação automática (só no modo Linha): meça a largura que o feixe remove "
                                "(ex.: corte um quadrado de 20 mm; k = 20 − medida) e digite aqui. Peças crescem "
                                "k/2 e furos diminuem k/2 no G-code; o desenho não muda. 0 = sem compensação.")
        f["potencia_min"].setToolTip("Usada em controladores que variam a potência nas curvas/cantos "
                                     "e em imagens em tons de cinza")
        for chave, txt, dica in (("bidirecional", "Varredura bidirecional (ida e volta)",
                                  "Desligado: todas as linhas no mesmo sentido (mais lento, às vezes mais uniforme)"),
                                 ("hachura_cruzada", "Hachura cruzada (+90°)",
                                  "Faz uma segunda varredura perpendicular à primeira"),
                                 ("negativo", "Imagem em negativo (inverte claro e escuro)",
                                  "Para materiais que clareiam ao gravar"),
                                 ("preencher_juntas", "Preencher todas as formas de uma vez",
                                  "Uma varredura só para todos os objetos da camada (menos idas e vindas); "
                                  "desligado = um objeto por vez")):
            cb = QCheckBox(txt)
            cb.setToolTip(dica)
            cb.toggled.connect(lambda _=False, k=chave: self._on_layer_form(k))
            form.addRow("", cb)
            f[chave] = cb
        mi = QComboBox()
        for k, t in (("pontilhado", "Pontilhado Floyd–Steinberg (simula tons)"), ("jarvis", "Pontilhado Jarvis (mais suave)"),
                     ("stucki", "Pontilhado Stucki"), ("atkinson", "Pontilhado Atkinson (mais contraste)"),
                     ("limiar", "Limiar (preto e branco)"), ("cinza", "Tons de cinza (potência variável)"),
                     ("meio_tom", "Meio-tom (pontos redondos, como jornal)")):
            mi.addItem(t, k)
        mi.setToolTip("Como a imagem vira laser; branco nunca grava")
        mi.activated.connect(lambda _=0: self._on_layer_form("modo_imagem"))
        form.addRow("Modo da imagem", mi)
        f["modo_imagem"] = mi
        f["gama"].setToolTip("Maior que 1 clareia os meios-tons; menor que 1 escurece")
        f["meio_tom_cpi"].setToolTip("Modo Meio-tom: pontos por polegada (mais = pontos menores e mais juntos; "
                                     "não passe de 25,4 ÷ (2 × intervalo))")
        f["meio_tom_angulo"].setToolTip("Modo Meio-tom: ângulo da grade de pontos (45° esconde melhor o padrão)")
        f["entrada_mm"].setToolTip("Modo Linha: o corte começa nesta distância, numa reta perpendicular do lado da "
                                   "sobra, para a marca do início não ficar na peça (não vale com guias)")
        f["saida_corte_mm"].setToolTip("Modo Linha: ao terminar, o laser segue esta distância para o lado da sobra")
        f["angulo_graus"].setToolTip("0 = linhas horizontais, 90 = verticais (ex.: frisos verticais)")
        f["sobrevarredura_mm"].setToolTip("O laser passa apagado esta distância além de cada linha de preenchimento, "
                                          "para acelerar e frear fora da peça (precisa caber na mesa)")
        sub_box = QGroupBox("Subcamadas (passes extras sobre os mesmos objetos)")
        sv = QVBoxLayout(sub_box)
        self.sub_lista = QListWidget()
        self.sub_lista.setMaximumHeight(90)
        self.sub_lista.setAccessibleName("Subcamadas da camada escolhida")
        self.sub_lista.itemDoubleClicked.connect(lambda _=None: self.subcamada("edit"))
        sv.addWidget(self.sub_lista)
        sh = QHBoxLayout()
        self.sub_botoes = {}
        for k, txt, dica in (("add", "+ Subcamada", "Novo passe sobre os mesmos objetos (ex.: cortar depois de gravar)"),
                             ("edit", "Editar", "Mudar a subcamada escolhida"),
                             ("del", "Remover", "Apagar a subcamada escolhida")):
            b = QPushButton(txt)
            b.setToolTip(dica)
            b.clicked.connect(lambda _=False, a=k: self.subcamada(a))
            sh.addWidget(b)
            self.sub_botoes[k] = b
        sv.addLayout(sh)
        form.addRow(sub_box)
        f["air"] = QCheckBox("Air assist nesta camada")
        f["air"].setToolTip("Só registra a preferência; o comando de air assist vem na Etapa 16")
        f["air"].toggled.connect(lambda _=False: self._on_layer_form("air"))
        form.addRow("", f["air"])
        v.addLayout(form)
        return w

    def _objects_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._demo_note("Formas: Ctrl+R/E/L. Texto: T. Importar: Ctrl+I. Prévia: Alt+P. Desfazer: Ctrl+Z. Salvar: Ctrl+S."))
        self.obj_tree = QTreeWidget()
        self.obj_tree.setHeaderLabels(["Objeto", "Camada", "Tamanho (mm)"])
        self.obj_tree.setAccessibleName("Lista de objetos")
        self.obj_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.obj_tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.obj_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)  # só o nome, por duplo clique ou F2
        self.obj_tree.itemDoubleClicked.connect(self._duplo_clique_lista)
        self.obj_tree.itemChanged.connect(self._on_tree_renamed)
        self.obj_tree.setToolTip("Duplo clique no nome (ou F2) para renomear. A ordem da lista é a ordem de corte "
                                 "dentro de cada camada.")
        v.addWidget(self.obj_tree)
        h = QHBoxLayout()
        hg = QHBoxLayout()
        for txt, fn, dica in (("📂 Abrir grupo", lambda: self.abrir_grupo(), "Editar as peças do grupo selecionado "
                                                                           "sem desagrupar (ou duplo clique nele)"),
                              ("📁 Fechar grupo", lambda: self.fechar_grupo(), "Junta de novo as peças do grupo aberto")):
            b = QPushButton(txt)
            b.setToolTip(dica)
            b.clicked.connect(fn)
            hg.addWidget(b)
        v.addLayout(hg)
        for txt, modo, dica in (("▲ Subir", "subir", "PgUp"), ("▼ Descer", "descer", "PgDown"),
                                ("⤒ Primeiro", "primeiro", "Ctrl+PgUp"), ("⤓ Último", "ultimo", "Ctrl+PgDown")):
            b = QPushButton(txt)
            b.setToolTip(f"Ordem de corte dos objetos selecionados ({dica})")
            b.clicked.connect(lambda _=False, m=modo: self.mover_ordem(m))
            h.addWidget(b)
        v.addLayout(h)
        return w

    def rename_object(self, item, nome) -> bool:
        """Renomeia um objeto (desfazível). Nome vazio é recusado."""
        nome = " ".join(nome.split())[:120]
        if not nome or nome == item.name:
            self._rebuild_objects()  # devolve o texto anterior na lista
            return False

        def do():
            item.name = nome
            self._rebuild_objects()

        self._edit("Renomear", do)
        return True

    def _duplo_clique_lista(self, node, _col):
        """Duplo clique na lista renomeia (objetos, grupos e grupo aberto). Abrir grupo: duplo clique na mesa,
        botão 📂 ou botão direito."""
        if node.flags() & Qt.ItemIsEditable:
            if isinstance(next((i for i, n in self._tree_map.values() if n is node), None), ob.GroupShape):
                self._syncing = True
                node.setText(0, node.text(0).removeprefix("📁 "))  # edita o nome sem o ícone
                self._syncing = False
            self.obj_tree.editItem(node, 0)

    # ---------- abrir/fechar grupo (editar as peças sem desagrupar) ----------
    def abrir_grupo(self, grupo=None) -> bool:
        if grupo is None:
            sel = [s for s in self._sel() if isinstance(s, ob.GroupShape)]
            grupo = sel[0] if len(sel) == 1 else None
        if grupo is None:
            self.statusBar().showMessage("Abrir grupo: selecione um grupo (ou dê duplo clique nele).")
            return False
        if grupo.bloqueado:
            self.statusBar().showMessage("Grupo bloqueado: desbloqueie antes de abrir.")
            return False
        self._seq_grupo = getattr(self, "_seq_grupo", 0) + 1
        gid = max([s.grupo_aberto[0] for s in self.canvas.view.shapes() if s.grupo_aberto] + [self._seq_grupo])
        self._seq_grupo = gid
        filhos = ob.ungroup(grupo)
        for c in filhos:
            c.grupo_aberto = (gid, grupo.name)

        def do():
            ordem = []
            for it in self.canvas.view.shapes():
                ordem += filhos if it is grupo else [it]
            for x in self.canvas.view.shapes():
                if x.ancora is grupo:
                    x.ancora = filhos[0]
            self.canvas.scene.removeItem(grupo)
            self.canvas.scene.clearSelection()
            self._reordenar(ordem, selecionar=[])
            self._rebuild_objects()

        self._edit("Abrir grupo", do)
        self.objects_dock.show()
        self.statusBar().showMessage(f"Grupo “{grupo.name}” aberto: clique em cada peça para mexer. "
                                     "📁 Fechar grupo (painel Objetos) junta de novo.", 15000)
        return True

    def renomear_grupo_aberto(self, gid, nome) -> bool:
        membros = [s for s in self.canvas.view.shapes() if s.grupo_aberto and s.grupo_aberto[0] == gid]
        nome = (nome or "").strip()
        if not membros or not nome or nome == membros[0].grupo_aberto[1]:
            self._rebuild_objects()
            return False

        def do():
            for s in membros:
                s.grupo_aberto = (gid, nome)
            self._rebuild_objects()
        self._edit("Renomear grupo", do)
        return True

    def fechar_grupo(self, gid=None) -> int:
        """Junta de novo as peças dos grupos abertos (todos, ou só `gid`). Devolve quantos grupos fechou."""
        shapes = self.canvas.view.shapes()
        abertos = {}
        for s in shapes:
            if s.grupo_aberto and (gid is None or s.grupo_aberto[0] == gid):
                abertos.setdefault(s.grupo_aberto, []).append(s)
        if not abertos:
            return 0

        def do():
            novos = {}
            for (g, nome), membros in abertos.items():
                for m in membros:
                    m.grupo_aberto = None
                if len(membros) < 2:
                    continue  # sobrou uma peça só: fica solta
                grp = ob.group(membros)
                grp.name = nome
                novos[id(membros[0])] = (grp, set(map(id, membros)))
            ordem, fora = [], set()
            for it in self.canvas.view.shapes():
                if id(it) in novos:
                    ordem.append(novos[id(it)][0])
                    fora |= novos[id(it)][1]
                elif id(it) not in fora:
                    ordem.append(it)
            for grp, ids in novos.values():
                for x in self.canvas.view.shapes():
                    if x.ancora is not None and id(x.ancora) in ids and id(x) not in ids:
                        x.ancora = grp
            self._reordenar(ordem, selecionar=[g for g, _ in novos.values()])
            self._rebuild_objects()

        self._edit("Fechar grupo", do)
        self.statusBar().showMessage(f"{len(abertos)} grupo(s) fechado(s).")
        return len(abertos)

    def _on_tree_renamed(self, node, col):
        if self._syncing or col != 0:
            return
        gid = node.data(0, Qt.UserRole)
        if gid is not None and node in getattr(self, "_grupo_nodes", {}).values():  # nome do grupo aberto
            novo = node.text(0).removeprefix("📂 ").strip()
            QTimer.singleShot(0, lambda: self.renomear_grupo_aberto(gid, novo))
            return
        it = next((i for i, n in self._tree_map.values() if n is node), None)
        if it is not None:  # depois do evento: a lista é reconstruída e o editor ainda usa o item
            QTimer.singleShot(0, lambda t=node.text(0): self.rename_object(it, t))

    def rename_selected(self):
        sel = self._sel()
        if len(sel) != 1:
            self.statusBar().showMessage("Selecione um único objeto para renomear.")
            return
        self.objects_dock.show()
        self.objects_dock.raise_()
        node = self._tree_map[id(sel[0])][1]
        self.obj_tree.setCurrentItem(node)
        self.obj_tree.editItem(node, 0)

    def _rebuild_objects(self):
        self._syncing = True
        self.obj_tree.clear()
        self._tree_map = {}
        shapes = self.canvas.view.shapes()
        presos_de = {}
        for x in shapes:
            if x.ancora is not None:
                presos_de[id(x.ancora)] = presos_de.get(id(x.ancora), 0) + 1
        nodes, self._grupo_nodes = [], {}
        for it in shapes:
            node = QTreeWidgetItem([it.name, it.layer, ""])
            if isinstance(it, ob.GroupShape):  # grupo fechado: mostra as peças (só para ver; abrir para editar)
                node.setText(0, f"📁 {it.name}")
                node.setToolTip(0, "Grupo — duplo clique (ou 📂 Abrir grupo) para editar as peças sem desagrupar")
                for k, c in enumerate(it.extra.children):
                    filho = QTreeWidgetItem([c[2], c[3], ""])
                    filho.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # clicar mostra a peça na mesa
                    filho.setData(0, Qt.UserRole + 1, k)
                    filho.setForeground(0, QColor("#8a97a6"))
                    node.addChild(filho)
            node.setFlags(node.flags() | Qt.ItemIsEditable)
            presos = presos_de.get(id(it), 0)
            if it.bloqueado:
                node.setText(1, f"{it.layer} 🔒")
            if it.ancora is not None and it.ancora.scene() is not None:
                node.setIcon(0, icon("anchor"))
                node.setToolTip(0, f"Preso a “{it.ancora.name}”")
            elif presos:
                node.setToolTip(0, f"Âncora de {presos} objeto(s)")
            self._tree_map[id(it)] = (it, node)
            if it.grupo_aberto:  # peça de um grupo aberto: entra como filha do nó do grupo
                gid, nome = it.grupo_aberto
                pai = self._grupo_nodes.get(gid)
                if pai is None:
                    pai = self._grupo_nodes[gid] = QTreeWidgetItem([f"📂 {nome}", "grupo aberto", ""])
                    pai.setToolTip(0, "Grupo aberto: edite cada peça; 📁 Fechar grupo junta de novo")
                    pai.setData(0, Qt.UserRole, gid)
                    pai.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    nodes.append(pai)
                pai.addChild(node)
            else:
                nodes.append(node)
        self.obj_tree.addTopLevelItems(nodes)  # de uma vez: muito mais rápido com muitos objetos
        for pai in self._grupo_nodes.values():
            pai.setExpanded(True)
        self._syncing = False
        self._sync_objects()

    def _sync_objects(self):
        self._syncing = True
        self.obj_tree.blockSignals(True)
        # Percorre a cena, não o mapa: o mapa pode conter objetos já removidos/destruídos.
        for it in self.canvas.view.shapes():
            if id(it) not in self._tree_map:
                continue
            node = self._tree_map[id(it)][1]
            r = ob.geom_rect(it)
            txt = f"{r.width():.2f} × {r.height():.2f}".replace(".", ",")
            if node.text(2) != txt:
                node.setText(2, txt)
            if node.isSelected() != it.isSelected():  # só o que mudou: marcar nó a nó é caro
                node.setSelected(it.isSelected())
        self.obj_tree.blockSignals(False)
        self.obj_tree.viewport().update()
        self.obj_tree.resizeColumnToContents(0)
        self._syncing = False

    def _on_tree_selection(self):
        if self._syncing:
            return
        grupos_marcados = {gid for gid, pai in getattr(self, "_grupo_nodes", {}).items() if pai.isSelected()}
        # peça dentro de grupo fechado: seleciona o grupo e destaca a peça na mesa
        destaque, grupos_de_pecas = QPainterPath(), set()
        for it, node in self._tree_map.values():
            if not isinstance(it, ob.GroupShape):
                continue
            for i in range(node.childCount()):
                filho = node.child(i)
                if filho.isSelected():
                    path, tf = it.extra.children[filho.data(0, Qt.UserRole + 1)][:2]
                    destaque.addPath(it.sceneTransform().map(tf.map(path)))
                    grupos_de_pecas.add(id(it))
        self.canvas.view.destacar(destaque if grupos_de_pecas else None)
        self._destacando = True
        try:
            self._selecionar_pela_lista(grupos_de_pecas, grupos_marcados)
        finally:
            self._destacando = False

    def _selecionar_pela_lista(self, grupos_de_pecas, grupos_marcados):
        with self._selecao_em_lote():
            for it, node in self._tree_map.values():  # nó do grupo aberto marcado = todas as peças dele
                it.setSelected(node.isSelected() or id(it) in grupos_de_pecas
                               or bool(it.grupo_aberto and it.grupo_aberto[0] in grupos_marcados))

    def _machine_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._demo_note("Conectar só LÊ a máquina. Para mover, enquadrar e gravar, clique em \"Liberar "
                                    "controle\". Use óculos de proteção, ar ligado e nunca deixe a máquina sozinha."))
        top = QHBoxLayout()
        self.machine_state = QLabel("Estado: Desconectado")
        self.machine_state.setObjectName("machineState")
        self.machine_state.setWordWrap(True)
        top.addWidget(self.machine_state, 1)
        self.btn_connect = QPushButton(icon("connect"), "Conectar")
        self.btn_connect.setToolTip("Abre a porta e lê $I, $$ e o status (somente leitura)")
        self.btn_connect.clicked.connect(self._toggle_conexao)
        top.addWidget(self.btn_connect)
        v.addLayout(top)

        porta = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setAccessibleName("Porta")
        self.port_combo.addItem("Simulador (sem máquina)", None)
        porta.addWidget(self.port_combo, 1)
        self.baud_combo = QComboBox()
        self.baud_combo.setAccessibleName("Velocidade da porta (baud)")
        self.baud_combo.addItems(["115200", "250000", "57600", "9600"])
        self.baud_combo.setToolTip("GRBL usa 115200 na maioria das placas")
        porta.addWidget(self.baud_combo)
        b = QPushButton("Procurar portas")
        b.setToolTip("Lista as portas seriais do computador (não abre nenhuma)")
        b.clicked.connect(self._procurar_portas)
        porta.addWidget(b)
        v.addLayout(porta)

        self.machine_info = QLabel("Não conectado.")
        self.machine_info.setWordWrap(True)
        self.machine_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.machine_info)
        self.machine_warn = QLabel()
        self.machine_warn.setObjectName("banner")
        self.machine_warn.setWordWrap(True)
        self.machine_warn.hide()
        v.addWidget(self.machine_warn)
        self.machine_log = QPlainTextEdit()
        self.machine_log.setReadOnly(True)
        self.machine_log.setMaximumBlockCount(400)
        self.machine_log.setFixedHeight(90)
        self.machine_log.setAccessibleName("Registro da comunicação")
        self.machine_log.setPlaceholderText("Registro da comunicação (→ enviado, ← recebido)")
        v.addWidget(self.machine_log)
        self.btn_report = QPushButton("Salvar relatório da máquina…")
        self.btn_report.setEnabled(False)
        self.btn_report.setToolTip("Grava firmware, configurações ($$) e avisos em JSON para conferência")
        self.btn_report.clicked.connect(self._salvar_relatorio_dialogo)
        v.addWidget(self.btn_report)

        linha_rot = QHBoxLayout()
        self.aviso_rotativo = QLabel()
        self.aviso_rotativo.setWordWrap(True)
        self.aviso_rotativo.setStyleSheet("background:#5a1418;color:#ffd0d0;padding:6px;border-radius:3px;"
                                          "font-weight:bold")
        self.btn_desligar_rot = QPushButton("Desligar rotativo")
        self.btn_desligar_rot.clicked.connect(self.desligar_rotativo)
        linha_rot.addWidget(self.aviso_rotativo, 1)
        linha_rot.addWidget(self.btn_desligar_rot)
        self.aviso_rotativo.setVisible(False)
        self.btn_desligar_rot.setVisible(False)
        v.addLayout(linha_rot)
        self.btn_controle = QPushButton("🔓 Liberar controle da máquina")
        self.btn_controle.setCheckable(True)
        self.btn_controle.setToolTip("Permite mover o cabeçote, enquadrar e enviar trabalhos (pede confirmação)")
        self.btn_controle.toggled.connect(self._liberar_controle)
        v.addWidget(self.btn_controle)
        jog = QGridLayout()
        self.jog_btns = {}
        for name, r, c, tip, d in (("up", 0, 1, "Mover Y+", (0, 1)), ("left", 1, 0, "Mover X−", (-1, 0)),
                                   ("home", 1, 1, "Ir para a origem (0, 0)", None),
                                   ("right", 1, 2, "Mover X+", (1, 0)), ("down", 2, 1, "Mover Y−", (0, -1))):
            b = QToolButton()
            b.setIcon(icon(name))
            b.setIconSize(QSize(26, 26))
            b.setAccessibleName(tip)
            b.setToolTip(tip + " (laser desligado)")
            b.clicked.connect(lambda _=False, d=d: self._mover_cabecote(d))
            b.setFocusPolicy(Qt.StrongFocus)  # depois do clique, as setas do teclado movem o cabeçote
            b.installEventFilter(self)
            self.jog_btns[name] = b
            jog.addWidget(b, r, c)
        self._jog_seta = None  # (direção, passo) da seta apertada
        self._jog_segurar = QTimer(self, singleShot=True, interval=350)  # segurou: anda até soltar
        self._jog_segurar.timeout.connect(self._jog_continuo)
        side = QFormLayout()
        self.jog_passo = QComboBox()
        for t, val in (("0,1 mm", 0.1), ("1 mm", 1.0), ("10 mm", 10.0), ("50 mm", 50.0)):
            self.jog_passo.addItem(t, val)
        self.jog_passo.setCurrentIndex(2)
        side.addRow("Passo", self.jog_passo)
        self.jog_vel = QSpinBox()
        self.jog_vel.setRange(100, 6000)
        self.jog_vel.setValue(3000)
        self.jog_vel.setSuffix(" mm/min")
        side.addRow("Velocidade", self.jog_vel)
        row = QHBoxLayout()
        row.addLayout(jog)
        row.addLayout(side, 1)
        v.addLayout(row)

        btns = QGridLayout()
        self.btn_enquadrar = QPushButton(icon("frame"), "Enquadrar")
        self.btn_enquadrar.setToolTip("Contorna a área do trabalho com o laser DESLIGADO, para conferir a posição")
        self.btn_enquadrar.clicked.connect(lambda: self.enquadrar_trabalho())
        self.btn_origem = QPushButton(icon("origin"), "Definir origem")
        self.btn_origem.setToolTip("A posição atual do cabeçote passa a ser o 0,0 do trabalho")
        self.btn_origem.clicked.connect(lambda: self._comando_maquina(lambda c: c.definir_origem(0, 0),
                                                                     "Origem definida na posição atual."))
        self.btn_iniciar = QPushButton(icon("play"), "Iniciar")
        self.btn_iniciar.setToolTip("Envia o trabalho para a máquina (pede confirmação; o laser vai LIGAR)")
        self.btn_iniciar.clicked.connect(lambda: self.iniciar_trabalho())
        self.btn_pausar = QPushButton(icon("pause"), "Pausar")
        self.btn_pausar.clicked.connect(self._pausar_retomar)
        self.btn_parar = QPushButton(icon("stop"), "Parar")
        self.btn_parar.setToolTip("Para tudo na hora e apaga o laser (reset do controlador)")
        self.btn_parar.setStyleSheet("QPushButton{background:#7a1d22;border-color:#e0313b;font-weight:bold}")
        self.btn_parar.clicked.connect(self._parar_maquina)
        self.btn_zerar_origem = QPushButton("Zerar origem")
        self.btn_zerar_origem.setToolTip("Volta o 0,0 do trabalho para o 0,0 da máquina (onde o cabeçote estava ao "
                                         "ligar). Use se a posição na tela estiver fora da mesa")
        self.btn_zerar_origem.clicked.connect(lambda: self._comando_maquina(lambda c: c.zerar_origem(),
                                                                           "Origem zerada (0,0 = origem da máquina)."))
        self.btn_home = QPushButton(icon("home"), "Referenciar (home)")
        self.btn_home.setToolTip("Leva o cabeçote aos fins de curso (esquerda e frente) e usa esse ponto como 0,0")
        self.btn_home.clicked.connect(lambda: self.referenciar_maquina())
        self.btn_desbloquear = QPushButton("Desbloquear ($X)")
        self.btn_desbloquear.setToolTip("Tira a máquina do ALARME (confira antes o que causou o alarme)")
        self.btn_desbloquear.clicked.connect(lambda: self._comando_maquina(lambda c: c.desbloquear(),
                                                                          "Desbloqueio enviado."))
        self.btn_retomar = QPushButton("↻ Retomar interrompido…")
        self.btn_retomar.setToolTip("Continua o último trabalho que parou no meio (queda de luz, reset, Parar), "
                                    "algumas linhas antes do ponto onde estava")
        self.btn_retomar.clicked.connect(lambda: self.retomar_interrompido())
        self.btn_faixa = QPushButton("▶ Iniciar a partir de…")
        self.btn_faixa.setToolTip("Escolhe de onde até onde gravar (passar de novo num trecho que não cortou bem)")
        self.btn_faixa.clicked.connect(lambda: self.iniciar_trabalho(escolher_faixa=True))
        self.btn_mira = QPushButton("💡 Mira (luz fraca)")
        self.btn_mira.setCheckable(True)
        self.btn_mira.setToolTip("Acende o ponto do laser bem fraco e PARADO, e deixa aceso até desligar — para "
                                 "posicionar a peça (ou o cabeçote com a mão)")
        self.btn_mira.toggled.connect(self._mira)
        self.btn_motores = QPushButton("✋ Soltar motores")
        self.btn_motores.setCheckable(True)
        self.btn_motores.setToolTip("Solta os motores quando a máquina para ($1=25), para empurrar o cabeçote com a "
                                    "mão. Desmarque para travar de novo ($1=255)")
        self.btn_motores.toggled.connect(self._motores)
        self.btn_laser = QPushButton("🔥 Laser ligado")
        self.btn_laser.setCheckable(True)
        self.btn_laser.setToolTip("Acende o laser na potência ao lado (até 100 %) e deixa aceso até desligar. Com ele "
                                  "aceso, as setas do teclado movem o cabeçote (toque = 10 mm; Alt 0,1 · Ctrl 1 · "
                                  "Shift 50; segurar = anda até soltar) e o laser vai riscando. QUEIMA: use óculos")
        self.btn_laser.setStyleSheet("QPushButton:checked{background:#7a1d22;border-color:#e0313b;font-weight:bold}")
        self.btn_laser.toggled.connect(self._laser_ligado)
        self.btn_laser.installEventFilter(self)  # setas com o botão focado também movem
        self.pot_laser = QDoubleSpinBox()
        self.pot_laser.setRange(0.5, 100.0)
        self.pot_laser.setDecimals(1)
        self.pot_laser.setValue(self.settings.value("pot_laser_ligado", 100.0, type=float))
        self.pot_laser.setSuffix(" %")
        self.pot_laser.setAccessibleName("Potência do laser ligado")
        self.pot_laser.setToolTip("Potência do botão Laser ligado (vale na próxima vez que ligar)")
        self.pot_laser.valueChanged.connect(lambda x: self.settings.setValue("pot_laser_ligado", x))
        for k, b in enumerate((self.btn_home, self.btn_enquadrar, self.btn_origem, self.btn_zerar_origem,
                               self.btn_desbloquear, self.btn_mira, self.btn_motores, self.btn_retomar,
                               self.btn_faixa, self.btn_iniciar, self.btn_pausar, self.btn_parar)):
            btns.addWidget(b, k // 3, k % 3)
        v.addLayout(btns)
        linha_laser = QHBoxLayout()
        linha_laser.addWidget(self.btn_laser, 1)
        linha_laser.addWidget(QLabel("Potência"))
        linha_laser.addWidget(self.pot_laser)
        v.addLayout(linha_laser)
        self.btn_ar = QPushButton(icon("air"), "Air assist")
        self.btn_ar.setCheckable(True)
        self.btn_ar.setToolTip("Liga/desliga a bomba de ar (M8/M9). No trabalho, o ar liga sozinho nas camadas com "
                               "\"Ar\" marcado")
        self.btn_ar.toggled.connect(self._ar_assist)
        self.chk_laser_fraco = QCheckBox("Enquadrar com laser fraco")
        self.chk_laser_fraco.setToolTip("O cabeçote contorna a área com o laser bem fraco, para ver onde o feixe "
                                        "vai passar")
        self.chk_laser_fraco.toggled.connect(self._laser_fraco)
        self.pot_enquadrar = QDoubleSpinBox()
        self.pot_enquadrar.setRange(0.5, cx.POT_MAX_ENQUADRAR)
        self.pot_enquadrar.setDecimals(1)
        self.pot_enquadrar.setSingleStep(0.5)
        self.pot_enquadrar.setValue(1.0)
        self.pot_enquadrar.setSuffix(" %")
        self.pot_enquadrar.setToolTip(f"Potência do laser ao enquadrar (máximo {cx.POT_MAX_ENQUADRAR:g} %)")
        self.chk_home_auto = QCheckBox("Referenciar ao liberar o controle")
        self.chk_home_auto.setToolTip("Faz o homing (fins de curso) sozinho toda vez que você libera o controle")
        self.chk_home_auto.setChecked(self.settings.value("home_ao_liberar", False, type=bool))
        self.chk_home_auto.toggled.connect(lambda on: self.settings.setValue("home_ao_liberar", on))
        v.addWidget(self.chk_home_auto)
        self.chk_reref = QCheckBox(f"Referenciar de novo a cada {REREF_MIN} min no trabalho")
        self.chk_reref.setToolTip("Máquina com fim de curso: a cada tanto o envio para num deslocamento sem laser, faz o "
                                  "homing ($H) e continua da mesma linha. Corrige passo perdido antes de acumular.")
        self.chk_reref.setChecked(self.settings.value("referenciar_no_trabalho", False, type=bool))
        self.chk_reref.toggled.connect(lambda on: self.settings.setValue("referenciar_no_trabalho", on))
        v.addWidget(self.chk_reref)
        self.chk_sons = QCheckBox("Sons")
        self.chk_sons.setToolTip("Aviso sonoro ao iniciar, pausar, parar, terminar e em erro/alarme")
        self.chk_sons.setChecked(self.settings.value("sons_maquina", True, type=bool))
        self.chk_sons.toggled.connect(lambda on: self.settings.setValue("sons_maquina", on))
        self.chk_ar_todo = QCheckBox("Ar forte no trabalho todo")
        self.chk_ar_todo.setToolTip("Liga o air assist (M8) no começo do trabalho e só desliga no fim, em qualquer camada "
                                    "(sem isso, só nas camadas com \"Ar\" marcado)")
        self.chk_ar_todo.setChecked(self.settings.value("ar_trabalho_todo", True, type=bool))
        self.chk_ar_todo.toggled.connect(lambda on: self.settings.setValue("ar_trabalho_todo", on))
        v.addWidget(self.chk_ar_todo)
        fraco = QHBoxLayout()
        fraco.addWidget(self.chk_sons)
        fraco.addWidget(self.btn_ar)
        fraco.addWidget(self.chk_laser_fraco)
        fraco.addWidget(self.pot_enquadrar)
        v.addLayout(fraco)
        self.lbl_ar = QLabel("Ar na máquina: —")
        self.lbl_ar.setToolTip("O que a própria máquina informa do air assist (M8). Na S30, ar FRACO = M8 desligado "
                               "(a bomba fica no modo baixo); se estiver FORTE e ainda sair pouco ar, confira o "
                               "regulador da bomba e a mangueira")
        v.addWidget(self.lbl_ar)
        self.inicio_trabalho = QComboBox()
        self.inicio_trabalho.addItem("Origem do trabalho (0,0 definido)", "origem")
        self.inicio_trabalho.addItem("Posição atual (canto inferior esquerdo do trabalho)", "atual")
        self.inicio_trabalho.setToolTip("Origem: usa as coordenadas da mesa a partir do 0,0 (máquina sem homing: o 0,0 é "
                                        "onde o cabeçote estava ao ligar, ou o definido em \"Definir origem\").\n"
                                        "Posição atual: o canto inferior esquerdo do trabalho fica onde o cabeçote está.")
        f = QFormLayout()
        f.addRow("Começar de", self.inicio_trabalho)
        v.addLayout(f)
        self.progresso_trabalho = QProgressBar()
        self.progresso_trabalho.setRange(0, 1000)
        self.progresso_trabalho.setTextVisible(True)
        self.progresso_trabalho.setFormat("Nenhum trabalho")
        v.addWidget(self.progresso_trabalho)
        for b in (self.btn_controle, *self.jog_btns.values(), self.btn_enquadrar, self.btn_origem,
                  self.btn_desbloquear, self.btn_iniciar, self.btn_pausar, self.btn_parar, self.btn_ar,
                  self.btn_zerar_origem, self.btn_home, self.btn_retomar, self.btn_faixa, self.btn_mira,
                  self.btn_motores, self.btn_laser):
            b.setEnabled(False)  # tudo travado até conectar (e o controle até ser liberado)
        v.addWidget(QLabel("O botão Parar do aplicativo não substitui a parada de emergência física."))
        v.itemAt(v.count() - 1).widget().setWordWrap(True)
        v.addStretch(1)
        return w

    def _materials_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._demo_note(
            f"{mt.MAQUINA}: valores de REFERÊNCIA publicados por revendedor, NÃO validados (a máquina ainda não "
            "foi testada). Teste numa sobra do material antes de usar. Rolo rotativo: Laser → Configuração do rotativo."))
        self.mat_list = QListWidget()
        self.mat_list.setAccessibleName("Materiais")
        self.mat_list.currentRowChanged.connect(self._mostrar_material)
        v.addWidget(self.mat_list, 1)
        self.mat_info = QLabel()
        self.mat_info.setWordWrap(True)
        v.addWidget(self.mat_info)
        bt = QHBoxLayout()
        self.btn_mat_aplicar = QPushButton("Aplicar à camada")
        self.btn_mat_aplicar.setToolTip("Copia velocidade, potência, passadas, air assist e modo para a camada "
                                        "selecionada no painel Camadas (desfazível)")
        self.btn_mat_aplicar.clicked.connect(lambda: self.aplicar_material(self._material_atual(),
                                                                           self._current_layer_id()))
        self.btn_mat_salvar = QPushButton("Salvar camada como material…")
        self.btn_mat_salvar.setToolTip("Guarda os parâmetros da camada selecionada como seu material (testado)")
        self.btn_mat_salvar.clicked.connect(self._salvar_material_dialogo)
        self.btn_mat_editar = QPushButton("Editar…")
        self.btn_mat_editar.setToolTip("Muda velocidade, potência, passadas, air assist e espessura do material "
                                       "(um de referência vira uma cópia sua)")
        self.btn_mat_editar.clicked.connect(lambda: self.editar_material())
        self.btn_mat_excluir = QPushButton("Excluir")
        self.btn_mat_excluir.clicked.connect(self._excluir_material)
        for b in (self.btn_mat_aplicar, self.btn_mat_salvar, self.btn_mat_editar, self.btn_mat_excluir):
            bt.addWidget(b)
        v.addLayout(bt)
        self.btn_matriz = QPushButton("Matriz de testes…")
        self.btn_matriz.setToolTip("Grade de potências × velocidades em volta do material selecionado")
        self.btn_matriz.clicked.connect(self._matriz_dialogo)
        self.btn_resultado = QPushButton("Salvar do quadrado escolhido…")
        self.btn_resultado.setToolTip("Depois de gravar a matriz: clique no melhor quadrado e salve como material")
        self.btn_resultado.clicked.connect(self._resultado_matriz_dialogo)
        h2 = QHBoxLayout()
        h2.addWidget(self.btn_matriz)
        h2.addWidget(self.btn_resultado)
        v.addLayout(h2)
        self._montar_materiais()
        return w

    # ---------- materiais ----------
    def materiais(self) -> list:
        meus = mt.meus(self.settings)
        chaves = {(m.nome, m.espessura_mm, m.operacao) for m in meus}
        pre = [m for m in mt.PREDEFINIDOS_REDBLACK if (m.nome, m.espessura_mm, m.operacao) not in chaves]
        return meus + pre + list(mt.REFERENCIA_S30_PRO_MAX_20W)

    def _montar_materiais(self, selecionar=0):
        self._mats = self.materiais()
        self.mat_list.clear()
        for m in self._mats:
            QListWidgetItem(m.rotulo(), self.mat_list)
        self.mat_list.setCurrentRow(min(selecionar, len(self._mats) - 1))

    def _material_atual(self):
        i = self.mat_list.currentRow()
        return self._mats[i] if 0 <= i < len(self._mats) else None

    def _mostrar_material(self, *_):
        m = self._material_atual()
        self.btn_mat_excluir.setEnabled(bool(m and m.origem == "meu" and m not in mt.PREDEFINIDOS_REDBLACK))
        self.btn_mat_aplicar.setEnabled(m is not None)
        if m is None:
            self.mat_info.setText("")
            return
        txt = (f"{m.velocidade_mm_min:g} mm/min · potência {m.potencia_max:g} % · {m.passadas} passada(s) · "
               f"air assist {'ligado' if m.air else 'desligado'}")
        if m.operacao == "gravação":
            txt += f" · intervalo {m.intervalo_mm:g} mm"
        txt = txt.replace(".", ",") + (f"\n{m.nota}" if m.nota else "")
        txt += "\nCadastrado por você." if m.origem == "meu" else "\nFonte: " + mt.FONTE
        self.mat_info.setText(txt)

    def aplicar_material(self, m, layer_id) -> bool:
        if m is None or layer_id is None:
            self.statusBar().showMessage("Escolha um material e uma camada (painel Camadas).")
            return False
        c = self.layer(layer_id)
        if c is None:
            return False
        if c.modo == "imagem" and m.operacao == "corte":
            self.show_error("Material não aplicado", f"A camada {layer_id} tem imagens; só parâmetros de "
                            "gravação servem para ela.")
            return False
        ok = self.set_layer_fields(layer_id, m.campos_camada(c.modo), f"Material {m.nome} na camada {layer_id}")
        if ok:
            aviso = "" if m.origem == "meu" else " — referência NÃO validada: teste antes"
            self.statusBar().showMessage(f"{m.rotulo()} aplicado à camada {layer_id}{aviso}.")
        return ok

    def editar_material(self, m=None):
        """Edita a especificação de um material; o resultado é guardado como material seu."""
        m = m or self._material_atual()
        if m is None:
            return False
        campos = [("nome", "Nome", m.nome, None),
                  ("espessura_mm", "Espessura (0 = gravação)", m.espessura_mm, (0, 100, 1, " mm")),
                  ("operacao", "Operação", m.operacao, [("corte", "Corte"), ("gravação", "Gravação")]),
                  ("velocidade_mm_min", "Velocidade", m.velocidade_mm_min, (1, 20000, 0, " mm/min")),
                  ("potencia_max", "Potência", m.potencia_max, (0, 100, 1, " %")),
                  ("passadas", "Passadas", m.passadas, (1, 50, 0, "")),
                  ("air", "Air assist", m.air, None),
                  ("intervalo_mm", "Intervalo da gravação", m.intervalo_mm, (0.01, 5, 2, " mm")),
                  ("nota", "Observação", m.nota, None)]
        v = self.ask_valores(f"Editar material — {m.rotulo()}", campos,
                             "Fica guardado como material seu; aplique na camada com \"Aplicar à camada\".")
        if not v:
            return False
        try:
            novo = mt.Material(str(v["nome"]).strip()[:80], float(v["espessura_mm"]), v["operacao"],
                               float(v["velocidade_mm_min"]), float(v["potencia_max"]), int(v["passadas"]),
                               bool(v["air"]), float(v["intervalo_mm"]), str(v["nota"]), "meu")
            e = mt.erros(novo)
            if e:
                raise ValueError("; ".join(e))
        except (ValueError, TypeError) as e:
            self.show_error("Material não salvo", str(e))
            return False
        if m.origem == "meu" and (m.nome, m.espessura_mm, m.operacao) != (novo.nome, novo.espessura_mm,
                                                                           novo.operacao):
            mt.gravar_meus(self.settings, [x for x in mt.meus(self.settings) if x != m])  # renomeado: tira o antigo
        return self._guardar_material(novo)

    def ask_material_nome(self):
        """(nome, espessura mm) ou None. Substituível nos testes."""
        nome, ok = QInputDialog.getText(self, "Salvar material", "Nome do material (ex.: MDF cru):")
        if not ok or not nome.strip():
            return None
        esp, ok = QInputDialog.getDouble(self, "Salvar material", "Espessura em mm (0 = gravação):", 3, 0, 100, 1)
        return (nome, esp) if ok else None

    def salvar_material(self, layer_id, nome, espessura) -> bool:
        c = self.layer(layer_id)
        try:
            m = mt.do_camada(c, nome, espessura) if c else None
        except ValueError as e:
            self.show_error("Material não salvo", str(e))
            return False
        return self._guardar_material(m) if m else False

    def _guardar_material(self, m) -> bool:
        lista = [x for x in mt.meus(self.settings) if (x.nome, x.espessura_mm, x.operacao) !=
                 (m.nome, m.espessura_mm, m.operacao)] + [m]  # mesmo nome/espessura/operação: substitui
        mt.gravar_meus(self.settings, lista)
        self._montar_materiais(next((i for i, x in enumerate(self._mats) if x == m), 0))
        self.statusBar().showMessage(f"Material salvo: {m.rotulo()}.")
        return True

    def _salvar_material_dialogo(self):
        lid = self._current_layer_id()
        if lid is None:
            self.statusBar().showMessage("Selecione a camada no painel Camadas.")
            return
        r = self.ask_material_nome()
        if r:
            self.salvar_material(lid, *r)

    # ---------- matriz de testes ----------
    def ask_matriz(self, inicial, material):
        """Matriz escolhida ou None. Substituível nos testes."""
        dlg = MatrizDialog(self, inicial, material)
        if material is not None and inicial == mz.Matriz():
            dlg.usar_material()  # 1ª vez: faixa já em volta do material selecionado
        r = dlg.matriz() if dlg.exec() == MatrizDialog.Accepted else None
        self._acao_matriz = dlg.acao
        return r

    def _matriz_dialogo(self):
        self._acao_matriz = "gcode"
        m = self.ask_matriz(self._ultima_matriz or mz.Matriz(), self._material_atual())
        if m is None:
            return
        self._ultima_matriz = m
        self.settings.setValue("ultima_matriz", json.dumps(mz.para_dict(m)))
        if self._acao_matriz == "maquina":
            try:
                texto, perc = mz.gerar(m)
            except (gc.GcodeInvalido, pc.LimiteExcedido) as e:
                self.show_error("Matriz não gerada", str(e))
                return
            self.enviar_teste(texto, perc.tempo_s)
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar matriz de testes",
                                              os.path.join(self._last_dir(), "matriz_de_testes.gcode"),
                                              "G-code (*.gcode *.nc *.gc)")
        if path:
            if not os.path.splitext(path)[1]:
                path += ".gcode"
            self.exportar_matriz(m, path)

    def _ler_ultima_matriz(self):
        try:
            return mz.de_dict(json.loads(self.settings.value("ultima_matriz", "") or "null"))
        except (TypeError, ValueError):
            return None  # ausente ou corrompida

    def salvar_material_da_matriz(self, m, linha, coluna, nome, espessura, nota="") -> bool:
        try:
            mat = mz.material(m, linha, coluna, nome, espessura, nota)
        except ValueError as e:
            self.show_error("Material não salvo", str(e))
            return False
        return self._guardar_material(mat)

    def ask_resultado_matriz(self, m):
        """(linha, coluna, nome, espessura, observação) ou None. Substituível nos testes."""
        atual = self._material_atual()
        dlg = ResultadoMatrizDialog(self, m, atual.nome if atual and atual.origem == "meu" else "",
                                    atual.espessura_mm if atual else 0.0)
        return dlg.resultado() if dlg.exec() == ResultadoMatrizDialog.Accepted else None

    def _resultado_matriz_dialogo(self):
        m = self._ultima_matriz
        if m is None:
            self.show_info("Matriz de testes", "Nenhuma matriz exportada ainda. Gere uma em Laser → Matriz de testes "
                           "de materiais…; depois de gravar, volte aqui para escolher o quadrado.")
            return
        r = self.ask_resultado_matriz(m)
        if r:
            self.salvar_material_da_matriz(m, *r)

    def abrir_calibracao_xy(self):
        from .dialogo_calibracao_xy import DialogoCalibracaoXY
        d = DialogoCalibracaoXY(self)
        d.show()
        return d

    def _ligar_comp_x(self, on):
        from . import dialogo_calibracao_xy as cxy
        d = cxy.ler(self.settings)
        if d["ativo"] != on:
            d["ativo"] = on
            cxy.gravar(self.settings, d)
            self.calibracao_xy_estado(cxy.aplicar(self.settings))
            self.statusBar().showMessage("Compensação do eixo X " + ("LIGADA." if on else "desligada: G-code igual ao "
                                                                     "programado."), 5000)

    def calibracao_xy_estado(self, texto):
        """Mostra na barra de status quando a calibração X/Y está ligada (fica visível o tempo todo)."""
        if not hasattr(self, "cal_xy_label"):
            self.cal_xy_label = QLabel()
            self.cal_xy_label.setStyleSheet("background:#3a2a14;color:#ffd27a;padding:0 6px;border-radius:3px")
            self.statusBar().addPermanentWidget(self.cal_xy_label)
        self.cal_xy_label.setText(texto)
        self.cal_xy_label.setVisible(bool(texto))
        if hasattr(self, "act_comp_x"):
            self.act_comp_x.blockSignals(True)
            self.act_comp_x.setChecked(bool(texto))
            self.act_comp_x.blockSignals(False)
        self._agendar_tempo()

    def saida_de_teste(self, texto, nome_arquivo):
        """Teste gerado: envia à máquina (se conectada e liberada) ou salva o G-code."""
        c = self.conexao
        if c is not None and c.controle:
            return self.enviar_teste(texto)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar teste", os.path.join(self._last_dir(), nome_arquivo),
                                              "G-code (*.gcode *.nc *.gc)")
        if path:
            gc.salvar(path if os.path.splitext(path)[1] else path + ".gcode", texto)
            self.statusBar().showMessage(f"Teste salvo: {path}")
        return bool(path)

    def ask_precisao(self):
        v = self.ask_valores("Teste de precisão (escala e esquadro)", [
            ("lado", "Lado do quadrado", 100.0, (20, 300, 0, " mm")),
            ("potencia", "Potência (marcar, não cortar)", 15.0, (1, 100, 0, " %")),
            ("velocidade", "Velocidade", 1500.0, (100, 20000, 0, " mm/min")),
            ("acao", "Saída", "maquina", [("maquina", "Enviar para a máquina"), ("gcode", "Salvar G-code…")])],
            "Depois de gravar, meça com paquímetro: o quadrado deve ter o lado pedido nos dois eixos (escala) e as "
            "duas diagonais devem ser iguais (esquadro). O círculo deve ser redondo (sem folga de correia).")
        return v

    def teste_precisao(self):
        v = self.ask_precisao()
        if not v:
            return False
        try:
            texto, perc = mz.gerar_precisao(30.0, 30.0, float(v["lado"]), float(v["potencia"]), float(v["velocidade"]))
        except (gc.GcodeInvalido, pc.LimiteExcedido) as e:
            self.show_error("Teste não gerado", str(e))
            return False
        if v["acao"] == "maquina":
            return self.enviar_teste(texto, perc.tempo_s)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar teste de precisão",
                                              os.path.join(self._last_dir(), "teste_precisao.gcode"),
                                              "G-code (*.gcode *.nc *.gc)")
        if path:
            gc.salvar(path if os.path.splitext(path)[1] else path + ".gcode", texto)
        return bool(path)

    def enviar_teste(self, texto, tempo_s=0.0):
        """Envia um G-code de teste (matriz, precisão) à máquina, com a mesma confirmação, opção "Posição atual" e
        conferência de curso do Iniciar."""
        c = self.conexao
        if c is None or not c.controle:
            self.show_error("Máquina", "Conecte a máquina e clique em \"Liberar controle\" no painel Máquina.")
            return False
        import re as _re
        xs = [float(x) for x in _re.findall(r"X(-?[\d.]+)", texto)]
        ys = [float(y) for y in _re.findall(r"Y(-?[\d.]+)", texto)]
        if not xs:
            return False
        caixa = (min(xs), min(ys), max(xs), max(ys))
        info = {**gc.analisar(texto), "tempo_s": tempo_s}
        if not self.ask_confirmar_trabalho(info, caixa):
            return False
        if self._comecar_daqui():
            pos = c.posicao
            if pos is None:
                return False
            dx, dy = pos[0] - caixa[0], pos[1] - caixa[1]
            texto = gc.deslocar(texto, dx, dy)
            caixa = (caixa[0] + dx, caixa[1] + dy, caixa[2] + dx, caixa[3] + dy)
        if not self._dentro_do_curso(caixa):
            return False
        self._mapa_cabecote = None
        return self._comando_maquina(lambda c: c.iniciar_trabalho(texto), "Teste enviado à máquina.")

    def exportar_matriz(self, m, path) -> bool:
        """Grava o G-code da matriz. Não altera o projeto e não envia nada à máquina."""
        try:
            texto, perc = mz.gerar(m)
            info = gc.analisar(texto)
            if not (info["dentro_da_area"] and info["fim_desligado"]):
                raise gc.GcodeInvalido("Conferência do G-code falhou (área ou laser ao final).")
            gc.salvar(path, texto)
        except (gc.GcodeInvalido, pc.LimiteExcedido, OSError) as e:
            self.show_error("Matriz não gerada", str(e))
            return False
        self._remember_dir(path)
        self._ultima_matriz = m
        self.settings.setValue("ultima_matriz", json.dumps(mz.para_dict(m)))
        self.show_info("Matriz de testes gerada",
                       f"{os.path.basename(path)}: {m.colunas} potências ({m.pot_min:g}–{m.pot_max:g} %, colunas) × "
                       f"{m.linhas} valores de {m.linhas_param} ({m.valores_linhas()[0]:g}–{m.valores_linhas()[-1]:g} "
                       f"{m.unidade_linhas()}, linhas, de cima para baixo). "
                       f"Tempo mínimo estimado {pc.fmt_tempo(perc.tempo_s)}.\n\n"
                       "Depois de gravar: Materiais → \"Salvar do quadrado escolhido…\" e clique no melhor "
                       "quadrado.\n\n"
                       "Perfil da máquina NÃO confirmado; nada foi enviado à máquina.")
        return True

    def _excluir_material(self):
        m = self._material_atual()
        if m and m.origem == "meu":
            mt.gravar_meus(self.settings, [x for x in mt.meus(self.settings) if x != m])
            self._montar_materiais()

    # ---------- status ----------
    def _build_status(self):
        sb = self.statusBar()
        sb.showMessage("Pronto — protótipo (Etapa 13: conexão somente leitura).")
        self.coords = QLabel("X: —   Y: —")
        self.coords.setMinimumWidth(250)
        sb.addPermanentWidget(self.coords)
        self.scale_label = QLabel()
        self.scale_label.setToolTip("Pixels de tela por milímetro do documento")
        sb.addPermanentWidget(self.scale_label)
        self.mesa_label = QLabel(self._texto_mesa())
        sb.addPermanentWidget(self.mesa_label)
        self.rotativo_label = QLabel()
        self.rotativo_label.setStyleSheet("background:#e0313b;color:white;font-weight:bold")
        self.rotativo_label.setToolTip("Rotativo ativo: o G-code converte Y em giro da peça (Laser → Configuração do "
                                       "rotativo…)")
        sb.addPermanentWidget(self.rotativo_label)
        self.machine_status_label = QLabel("Máquina: desconectada")
        sb.addPermanentWidget(self.machine_status_label)
        badge = QLabel("MODO DEMONSTRATIVO")
        badge.setObjectName("demoBadge")
        sb.addPermanentWidget(badge)
        self.interruptores = {}
        for chave, texto, dica in (("mover", "Mover", "Permitir mover objetos arrastando"),
                                   ("tamanho", "Tamanho", "Permitir redimensionar pelas alças"),
                                   ("girar", "Girar", "Permitir girar pela alça redonda"),
                                   ("cisalhar", "Cisalhar", "Tirar do esquadro: as alças do MEIO dos lados inclinam "
                                                            "a peça (eixo X pelas de cima/baixo, Y pelas laterais)")):
            b = QToolButton()
            b.setText(texto)
            b.setCheckable(True)
            b.setToolTip(dica + " (liga/desliga)")
            b.setAccessibleName(f"{texto} ao arrastar")
            b.setStyleSheet("QToolButton{border:0;padding:0 6px;color:#9aa0aa}"
                            "QToolButton:checked{color:#e8e8e8}")
            ligado = self.settings.value(f"permitir_{chave}", chave != "cisalhar", type=bool)
            b.setChecked(ligado)
            self.canvas.view.permitir[chave] = ligado
            b.toggled.connect(lambda on, k=chave: self._interruptor(k, on))
            self._pinta_interruptor(b)
            sb.insertPermanentWidget(len(self.interruptores), b)  # permanente: mensagens não escondem
            self.interruptores[chave] = b
        v = self.canvas.view
        v.cursorMoved.connect(self._on_cursor)
        v.viewChanged.connect(self._on_view_changed)
        v.measured.connect(lambda text: sb.showMessage(text))
        self._on_view_changed()

    def _interruptor(self, chave, on):
        self.canvas.view.permitir[chave] = on
        self.settings.setValue(f"permitir_{chave}", on)
        self._pinta_interruptor(self.interruptores[chave])

    @staticmethod
    def _pinta_interruptor(b):
        b.setText(("● " if b.isChecked() else "○ ") + b.text().lstrip("●○ "))

    def _on_cursor(self, pos):
        if pos is None:
            self.coords.setText("X: —   Y: —")
            return
        x, y = pos
        out = "" if 0 <= x <= g.BED_W and 0 <= y <= g.BED_H else "  (fora da mesa)"
        self.coords.setText(f"X: {x:.2f}   Y: {y:.2f} mm{out}".replace(".", ","))

    def _on_view_changed(self):
        self.scale_label.setText(f"Escala: {self.canvas.view.scale_px_mm:.2f} px/mm".replace(".", ","))

    def _on_measure_toggled(self, on):
        self.canvas.view.set_measure_mode(on)
        if on:
            self.canvas.view.setFocus()
            self.statusBar().showMessage("Medir: arraste com o botão esquerdo. Esc encerra.")
        else:
            self.tools["select"].setChecked(True)
            self.statusBar().showMessage("Pronto.")

    # ---------- layout ----------
    # ---------- prévia do percurso ----------
    def _toggle_preview(self, on):
        self.preview_dock.setVisible(on)

    def _on_preview_visibility(self, visible):
        self.act_preview.blockSignals(True)
        self.act_preview.setChecked(visible)
        self.act_preview.blockSignals(False)
        if visible and self.preview_dock.height() > 340 and not self.preview_dock.isFloating():
            self.resizeDocks([self.preview_dock], [320], Qt.Vertical)  # não espremer a área de desenho
        self._refresh_preview()

    # ---------- G-code ----------
    def export_gcode(self):
        start = os.path.splitext(self.file_path)[0] + ".gcode" if self.file_path else \
            os.path.join(self._last_dir(), "trabalho.gcode")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar G-code", start, "G-code (*.gcode *.nc *.gc)")
        if path:
            if not os.path.splitext(path)[1]:
                path += ".gcode"
            self.export_gcode_to(path)

    def export_gcode_to(self, path) -> bool:
        """Gera e grava o G-code. Nada é enviado à máquina. Em erro (limites etc.) nenhum arquivo é escrito."""
        try:
            snaps = self.snaps_saida([s.snapshot() for s in self.canvas.view.shapes()], self.vars)
            if not snaps:
                raise gc.GcodeInvalido("Nada para gravar: nenhuma peça tem linha na planilha.")
            perc = pc.gerar(snaps, self.layers, **self.otimizacao())
            texto = gc.gerar(perc, self.layers, rotativo=self.rotativo)
            info = gc.analisar(texto)  # conferência independente do texto gerado
            if not ((info["dentro_da_area"] or self.rotativo.ativo) and info["fim_desligado"]):
                raise gc.GcodeInvalido("Conferência do G-code falhou (área ou laser ao final).")
            gc.salvar(path, texto)
        except (gc.GcodeInvalido, pc.LimiteExcedido) as e:
            self.show_error("G-code não gerado", str(e))
            return False
        except OSError as e:
            self.show_error("Não foi possível gravar o G-code", str(e))
            return False
        self._remember_dir(path)
        linhas = texto.count("\n")
        self.statusBar().showMessage(f"G-code salvo: {path} ({linhas} linhas)")
        self.show_info("G-code gerado",
                       f"{os.path.basename(path)}: {linhas} linhas, {info['comprimento_corte']:.1f} mm com laser.\n\n"
                       f"Perfil: {gc.PERFIL.nome}. {self._texto_mesa()}, {gc.PERFIL.comando}, S 0 a "
                       f"{gc.PERFIL.s_max}. Exige modo laser do GRBL ($32=1).\n"
                       "Nada foi enviado à máquina. Confira o arquivo antes de qualquer uso.")
        return True

    def _refresh_preview(self, *_):
        """Recalcula o percurso do documento atual (só com o painel aberto) e esmaece os objetos."""
        view = self.canvas.view
        active = self.preview_dock.isVisible()
        shapes = view.shapes()
        for s in shapes:
            s.setOpacity(0.3 if active else 1.0)
        ov = view.percurso_overlay
        if not active:
            ov.set_percurso(None)
            return
        msg = ""
        try:
            p = pc.gerar(self.snaps_saida([s.snapshot() for s in shapes], self.vars), self.layers, **self.otimizacao(),
                         rapido=self.preview_panel.rapido.value())
        except pc.LimiteExcedido as e:
            p, msg = None, str(e)
        ov.set_percurso(p)
        self.preview_panel.set_percurso(p, msg, {c.id: c.passadas for c in cm.expandir(self.layers)})

    def reset_layout(self):
        self.restoreState(self._default_state)
        for d in self.docks:
            d.setFloating(False)
            if d is self.preview_dock:
                continue  # a prévia só abre quando o usuário pede
            d.show()

    # ---------- máquina (Etapa 13: somente leitura) ----------
    def _procurar_portas(self):
        try:
            portas = tp.listar_portas()
        except Exception as e:  # driver/biblioteca ausente: informa e segue com o simulador
            self.statusBar().showMessage(f"Não foi possível listar portas: {e}")
            return
        atual = self.port_combo.currentData()
        while self.port_combo.count() > 1:
            self.port_combo.removeItem(1)
        for nome, desc in portas:
            self.port_combo.addItem(f"{nome} — {desc}", nome)
        idx = self.port_combo.findData(atual)
        self.port_combo.setCurrentIndex(max(idx, 0))
        self.statusBar().showMessage(f"{len(portas)} porta(s) serial(is) encontrada(s).")

    # ---------- controle da máquina ----------
    def ask_liberar_controle(self):
        r = QMessageBox.warning(
            self, "Liberar controle da máquina",
            "O RedBlack vai poder MOVER o cabeçote e LIGAR o laser (ao iniciar um trabalho).\n\n"
            "Antes de continuar:\n• use óculos de proteção para o comprimento de onda do laser;\n"
            "• área de trabalho livre, material preso e plano, foco ajustado;\n• assistência de ar ligada e "
            "ambiente ventilado;\n• NUNCA deixe a máquina gravando sozinha; tenha um extintor por perto.\n\n"
            "O botão Parar do programa não substitui a parada de emergência física.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def _liberar_controle(self, on):
        c = self.conexao
        if on:
            if c is None or c.estado != cx.CONECTADO:
                self.statusBar().showMessage("Conecte a máquina primeiro.")
                on = False
            elif not self.ask_liberar_controle():
                on = False
        if c is not None and c.estado == cx.CONECTADO:
            c.habilitar_controle(on)
            if on and self.chk_home_auto.isChecked() and not self.rotativo.ativo:  # rotativo: Y sem fim de curso
                self.referenciar_maquina()
        self.btn_controle.blockSignals(True)
        self.btn_controle.setChecked(on)
        self.btn_controle.setText("🔒 Bloquear controle" if on else "🔓 Liberar controle da máquina")
        self.btn_controle.blockSignals(False)
        self._atualizar_maquina()

    def ask_ativar_homing(self):
        r = QMessageBox.question(
            self, "Ativar referência (homing)",
            "O homing está DESLIGADO no controlador ($22=0).\n\nPosso gravar $22=1 na máquina? Ela já está configurada "
            "para procurar os fins de curso da ESQUERDA e da FRENTE ($23=7), velocidade de busca $25 e recuo $27.\n\n"
            "Depois de ativado, a máquina pode pedir a referência ao ligar (fica em alarme até referenciar). Dá para "
            "desligar de novo com $22=0.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def referenciar_maquina(self):
        """Homing pelos fins de curso; ao terminar, o ponto de referência vira o 0,0 do trabalho."""
        if self.rotativo.ativo:
            self.show_error("Referenciar", MSG_REFERENCIAR_ROTATIVO)
            return False
        c = self.conexao
        if c is None or not c.controle:
            self.statusBar().showMessage("Libere o controle da máquina primeiro.")
            return False
        if not c.tem_homing:
            if not self.ask_ativar_homing():
                return False
            if not self._comando_maquina(lambda c: c.ativar_homing(True), "Homing ativado ($22=1)."):
                return False
            c.info.config[22] = 1.0  # a fila envia $22=1 antes do $H
        return self._comando_maquina(lambda c: c.referenciar(),
                                     "Referenciando: o cabeçote vai até os fins de curso (esquerda e frente)…")

    def _comando_maquina(self, fn, msg=""):
        try:
            fn(self.conexao)
        except cx.ComandoProibido as e:
            self.statusBar().showMessage(str(e))
            return False
        if msg:
            self.statusBar().showMessage(msg)
        self._atualizar_maquina()
        return True

    def _comecar_daqui(self) -> bool:
        """Trabalho começa onde o cabeçote está? Com rotativo, SEMPRE (não existe 0,0 da mesa no eixo que gira)."""
        return self.rotativo.ativo or self.inicio_trabalho.currentData() == "atual"

    def _vel_movimento(self):
        """Velocidade dos movimentos manuais/enquadrar: com rotativo, no máximo a velocidade de giro (não patina)."""
        f = self.jog_vel.value()
        return min(f, self.rotativo.vel_giro_max) if self.rotativo.ativo else f

    def _mover_cabecote(self, direcao, passo=None):
        feed = self._vel_movimento()
        if direcao is None:
            return self._comando_maquina(lambda c: c.ir_para(0, 0, feed), "Indo para a origem (laser desligado).")
        passo = passo or self.jog_passo.currentData()
        return self._comando_maquina(lambda c: c.jog(direcao[0] * passo, direcao[1] * passo, feed))

    _SETAS = {Qt.Key_Up: (0, 1), Qt.Key_Down: (0, -1), Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0)}

    def eventFilter(self, obj, ev):
        """Setas com um botão de mover focado: toque = 10 mm (Alt 0,1 · Ctrl 1 · Shift 50); segurar = anda até soltar."""
        if obj in getattr(self, "jog_btns", {}).values() or obj is getattr(self, "btn_laser", None):
            t = ev.type()
            if t in (QEvent.KeyPress, QEvent.KeyRelease) and ev.key() in self._SETAS:
                if not ev.isAutoRepeat():
                    self._seta_jog(ev.key(), ev.modifiers(), t == QEvent.KeyPress)
                return True
            if t == QEvent.FocusOut and self._jog_seta:  # perdeu o foco segurando: nunca deixar andando
                self._seta_jog(None, None, False)
        return super().eventFilter(obj, ev)

    def _seta_jog(self, key, mods, apertou):
        if apertou:
            passo = (0.1 if mods & Qt.AltModifier else 1.0 if mods & Qt.ControlModifier
                     else 50.0 if mods & Qt.ShiftModifier else 10.0)
            self._jog_seta = (self._SETAS[key], passo)
            self._jog_segurar.start()
            return
        if self._jog_seta is None:
            return
        (d, passo), self._jog_seta = self._jog_seta, None
        if self._jog_segurar.isActive():  # soltou rápido: um passo
            self._jog_segurar.stop()
            self._mover_cabecote(d, passo)
        elif self.conexao:
            self.conexao.parar_jog()  # 0x85: o GRBL para na hora

    def _jog_continuo(self):
        """Seta segurada: um jog longo até o fim do curso (ou o tamanho da mesa); soltar a seta cancela."""
        if self._jog_seta is None:
            return
        d = self._jog_seta[0]
        eixo = 0 if d[0] else 1
        W, H = gc.area(gc.PERFIL)
        dist = (W, H)[eixo]
        c = self.conexao
        lim = c.info.valor(130 + eixo, None) if c else None
        pos = c.posicao_maquina if c else None
        if lim and pos and not self.rotativo.ativo:
            dist = (lim - pos[eixo] if d[eixo] > 0 else pos[eixo]) - 0.5
        if dist > 0.05:
            self._mover_cabecote(d, dist)
        else:
            self._jog_seta = None
            self.statusBar().showMessage("Fim do curso: o cabeçote não foi movido.")

    def laser_ate_ponto(self, p):
        """Duplo clique na mesa: leva o cabeçote até o ponto (laser desligado), se o controle estiver liberado."""
        c = self.conexao
        if c is None or c.estado != cx.CONECTADO:
            self.statusBar().showMessage("Duplo clique leva o laser até o ponto: conecte a máquina primeiro.", 6000)
            return False
        if not c.controle:
            self.statusBar().showMessage("Duplo clique leva o laser até o ponto: clique em \"Liberar controle da "
                                         "máquina\" no painel Máquina.", 6000)
            return False
        W, H = gc.area(gc.PERFIL)
        x, y = gc.doc_para_maquina(p.x(), p.y(), W, H)
        if not (0 <= x <= W and 0 <= y <= H) or not self._dentro_do_curso((x, y, x, y)):
            self.statusBar().showMessage("Ponto fora da mesa: o cabeçote não foi movido.")
            return False
        return self._comando_maquina(lambda c: c.ir_para(x, y, self._vel_movimento()),
                                     f"Indo para X {x:.1f} Y {y:.1f} mm (laser desligado).".replace(".", ","))

    def _avisos_sonoros(self, c):
        """Toca o aviso quando o trabalho muda de estado (ou entra em alarme)."""
        antes = getattr(self, "_som_estado", None)
        alarme = bool(c.status and c.status.em_alarme)
        agora = (c.trabalho, alarme, c.estado == cx.FALHA)
        self._som_estado = agora
        if antes is None or antes == agora or not self.chk_sons.isChecked():
            return None
        evento = None
        import time as _t
        logo_apos_parar = _t.monotonic() - getattr(self, "_parou_em", -99) < 3.0
        if (alarme and not antes[1]) or (agora[2] and not antes[2]):
            evento = None if logo_apos_parar else "erro"  # o reset do Parar costuma gerar ALARM:3: não é erro
        elif agora[0] != antes[0]:
            evento = {cx.TRABALHO_RODANDO: "inicio" if antes[0] != cx.TRABALHO_PAUSADO else None,
                      cx.TRABALHO_PAUSADO: "pausa", cx.TRABALHO_FIM: "fim",
                      cx.TRABALHO_ERRO: "erro" if not getattr(self, "_parado_pelo_usuario", False) else "parado"
                      }.get(agora[0])
            self._parado_pelo_usuario = False
        if evento:
            self._ultimo_som = evento
            sons.tocar(evento)
        return evento

    def _ar_assist(self, on):
        if not self._comando_maquina(lambda c: c.ar(on), "Air assist " + ("ligado (M8)." if on else "desligado (M9).")):
            self.btn_ar.blockSignals(True)
            self.btn_ar.setChecked(not on)
            self.btn_ar.blockSignals(False)

    def ask_laser_fraco(self):
        r = QMessageBox.warning(
            self, "Enquadrar com laser fraco",
            "O laser vai LIGAR (bem fraco) enquanto o cabeçote contorna a área.\n\nMesmo fraco ele pode marcar papel, "
            "madeira escura e plástico preto. Use óculos de proteção e não olhe para o ponto sem eles.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def _laser_fraco(self, on):
        if on and not self.ask_laser_fraco():
            self.chk_laser_fraco.blockSignals(True)
            self.chk_laser_fraco.setChecked(False)
            self.chk_laser_fraco.blockSignals(False)

    def _pausar_retomar(self):
        c = self.conexao
        if c is None:
            return
        if c.trabalho == cx.TRABALHO_PAUSADO:
            self._comando_maquina(lambda c: c.retomar(), "Retomado.")
        else:
            c.pausar()
            self.statusBar().showMessage("Pausado (o laser apaga na pausa com M4). Retomar continua daqui.")
        self._atualizar_maquina()

    def _parar_maquina(self):
        if self.conexao is not None:
            import time as _t
            self._parado_pelo_usuario = True
            self._parou_em = _t.monotonic()
            self.conexao.parar()
            self.statusBar().showMessage("PARADO: reset enviado (movimento parado e laser apagado).")
            self._atualizar_maquina()

    def gcode_do_trabalho(self):
        """(texto do G-code, caixa da gravação em mm da máquina (x0, y0, x1, y1), info) do documento atual."""
        snaps = self.snaps_saida([s.snapshot() for s in self.canvas.view.shapes()], self.vars)
        if not snaps:
            raise gc.GcodeInvalido("Nada para gravar.")
        perc = pc.gerar(snaps, self.layers, **self.otimizacao())
        texto = gc.gerar(perc, self.layers, rotativo=self.rotativo)
        if self.chk_ar_todo.isChecked():
            texto = gc.ar_no_trabalho_todo(texto)
        info = gc.analisar(texto)
        if not ((info["dentro_da_area"] or self.rotativo.ativo) and info["fim_desligado"]):
            raise gc.GcodeInvalido("Conferência do G-code falhou (área ou laser ao final).")
        W, H = gc.area(gc.PERFIL)
        pts = [gc.doc_para_maquina(x, y, W, H) for t in perc.trechos if t.tipo != "vazio" for x, y in t.pontos]
        if not pts:
            raise gc.GcodeInvalido("Nada com laser para gravar.")
        caixa = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        info["tempo_s"] = sum(t.tempo_s for t in perc.trechos)
        return texto, caixa, info

    def caixa_do_trabalho(self):
        """Retângulo (mm da máquina: x0, y0, x1, y1) do que vai gravar, só pela geometria das peças — instantâneo,
        sem gerar o percurso (que numa imagem grande leva dezenas de segundos). None se não houver nada."""
        saida = {c.id for c in self.layers if c.saida}
        caixa = QRectF()
        for snap in self.snaps_saida([s.snapshot() for s in self.canvas.view.shapes()], self.vars):
            for path, tf, layer, _ in pc.folhas(snap):
                if layer in saida or cm.base_id(layer) in saida:
                    r = tf.mapRect(path.boundingRect())
                    caixa = r if caixa.isNull() else caixa.united(r)
        if caixa.isNull():
            return None
        W, H = gc.area(gc.PERFIL)
        (ax, ay), (bx, by) = gc.doc_para_maquina(caixa.left(), caixa.top(), W, H),             gc.doc_para_maquina(caixa.right(), caixa.bottom(), W, H)
        return self._caixa_na_saida((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))

    def _caixa_na_saida(self, caixa):
        """Caixa do desenho (mm da máquina) -> caixa nas coordenadas do G-code: com rotativo, a volta é escalada a
        partir do começo (mesma conta do gc.gerar) e o motor no X troca os eixos."""
        x0, y0, x1, y1 = caixa
        r = self.rotativo
        if r.ativo:
            y1 = y0 + (y1 - y0) * r.fator
            if r.eixo == "X":
                x0, y0, x1, y1 = y0, x0, y1, x1
        return x0, y0, x1, y1

    def _mapa_saida_para_desenho(self, desenho, dx=0.0, dy=0.0):
        """Função posição da máquina (coordenadas do G-code enviado) -> posição no desenho (mm da máquina). Desfaz
        o deslocamento da "posição atual" e a escala/troca de eixos do rotativo."""
        r = self.rotativo
        _x0, ya, _x1, yb = desenho

        def mapa(pos):
            x, y = pos[0] - dx, pos[1] - dy
            if not r.ativo:
                return x, y
            volta, ao_longo = (x, y) if r.eixo == "X" else (y, x)
            d = (volta - ya) / r.fator
            return ao_longo, (yb - d if r.espelhar else ya + d)
        return mapa

    def enquadrar_trabalho(self):
        caixa = self.caixa_do_trabalho()
        if caixa is None:
            self.statusBar().showMessage("Enquadrar: nada para gravar (camadas com Saída ligada).")
            return False
        x0, y0, x1, y1 = caixa
        feed = self._vel_movimento()
        daqui = self._comecar_daqui()
        c = self.conexao
        if c is not None:  # mesma checagem de curso do Iniciar
            pos = c.posicao
            vai = ((pos[0], pos[1], pos[0] + x1 - x0, pos[1] + y1 - y0) if daqui and pos else (x0, y0, x1, y1))
            if not self._dentro_do_curso(vai):
                return False
        if self.chk_laser_fraco.isChecked():
            pct = self.pot_enquadrar.value()
            return self._comando_maquina(
                lambda c: c.enquadrar_com_laser(x0, y0, x1, y1, pct, feed, gc.PERFIL.s_max, relativo=daqui),
                f"Enquadrando com laser fraco ({pct:g} %).".replace(".", ","))
        if daqui:
            return self._comando_maquina(lambda c: c.enquadrar_daqui(x1 - x0, y1 - y0, feed),
                                         f"Enquadrando {x1 - x0:.1f} × {y1 - y0:.1f} mm a partir daqui "
                                         "(laser desligado).".replace(".", ","))
        return self._comando_maquina(lambda c: c.enquadrar(x0, y0, x1, y1, feed),
                                     "Enquadrando a área do trabalho (laser desligado).")

    def ask_confirmar_trabalho(self, info, caixa):
        x0, y0, x1, y1 = caixa
        r = QMessageBox.warning(
            self, "Iniciar trabalho — o laser vai LIGAR",
            f"Área: {x1 - x0:.1f} × {y1 - y0:.1f} mm · laser ligado em {info['comprimento_corte'] / 1000:.2f} m · "
            f"tempo estimado ≈ {pc.fmt_tempo(info['tempo_s'])}.\n\n"
            + (f"⚠ ROTATIVO LIGADO: o Y vai ser multiplicado por {self.rotativo.fator:.2f}. Se a peça é PLANA, "
               "cancele e desligue o rotativo!\n\n" if self.rotativo.ativo else "") +
            "Confira: óculos de proteção, material preso, foco ajustado, ar ligado, Enquadrar feito.\n"
            "Fique junto da máquina o tempo todo. Botão Parar (ou a emergência da máquina) para tudo.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def _reref_s(self):
        """Segundos entre referências no meio do trabalho, ou None (desmarcado, sem fim de curso ou com rotativo)."""
        c = self.conexao
        if not (getattr(self, "chk_reref", None) and self.chk_reref.isChecked()) or c is None:
            return None
        if self.rotativo.ativo or not c.tem_homing:
            self.statusBar().showMessage("Referenciar no trabalho ignorado: precisa de fim de curso e sem rotativo.")
            return None
        return REREF_MIN * 60.0

    def iniciar_trabalho(self, escolher_faixa=False):
        c = self.conexao
        if c is None or not c.controle:
            self.statusBar().showMessage("Libere o controle da máquina primeiro.")
            return False
        self.statusBar().showMessage("Gerando o trabalho… (imagens grandes podem levar alguns segundos)")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            texto, caixa, info = self.gcode_do_trabalho()
        except (gc.GcodeInvalido, pc.LimiteExcedido) as e:
            QApplication.restoreOverrideCursor()
            self.show_error("Trabalho não iniciado", str(e))
            return False
        QApplication.restoreOverrideCursor()
        if escolher_faixa:  # começar no meio / passar de novo só num trecho
            linhas = cx.Conexao.linhas_do_gcode(texto)
            faixa = self.ask_faixa(linhas)
            if faixa is None:
                return False
            texto = "\n".join(gc.retomar_de(linhas, *faixa)) + "\n"
        if not self.ask_confirmar_trabalho(info, caixa):
            return False
        desenho, caixa = caixa, self._caixa_na_saida(caixa)  # caixa nas coordenadas que o G-code usa
        dx = dy = 0.0
        if self._comecar_daqui():  # o canto do trabalho vai para onde o cabeçote está
            pos = c.posicao
            if pos is None:
                self.show_error("Trabalho não iniciado", "Posição do cabeçote ainda desconhecida; espere um instante.")
                return False
            dx, dy = pos[0] - caixa[0], pos[1] - caixa[1]
            texto = gc.deslocar(texto, dx, dy)  # sem mexer na origem guardada no controlador
            caixa = (caixa[0] + dx, caixa[1] + dy, caixa[2] + dx, caixa[3] + dy)
        if not self._dentro_do_curso(caixa):
            return False
        self._mapa_cabecote = self._mapa_saida_para_desenho(desenho, dx, dy)
        ok = self._comando_maquina(lambda c: c.iniciar_trabalho(texto, self._reref_s()), "Trabalho enviado à máquina.")
        if ok:
            self._aba_do_trabalho = (self.pagina_atual, self.nomes_paginas[self.pagina_atual], c._job)
            self._gravar_trabalho(c._job, 0)
            if ler_pref(self.settings, "tela_corte_auto"):
                self.act_tela_corte.setChecked(True)
        return ok

    def _modo_corte(self, on):
        """Troca entre a edição (igual a sempre) e a tela de corte. Os painéis e barras voltam como estavam."""
        if on == (self.pilha_central.currentIndex() == 1):
            return
        if on:
            self._estado_edicao = self.saveState()
            for d in self.docks:
                d.hide()
            for tb in self.toolbars:
                if tb is not self.barra_principal:
                    tb.hide()
            self.pilha_central.setCurrentIndex(1)
            self.tela_corte.vista.mostrar_mesa(QRectF(0, 0, g.BED_W, g.BED_H))
        else:
            self.pilha_central.setCurrentIndex(0)
            if getattr(self, "_estado_edicao", None) is not None:
                self.restoreState(self._estado_edicao)
        self.act_tela_corte.blockSignals(True)
        self.act_tela_corte.setChecked(on)
        self.act_tela_corte.blockSignals(False)

    def _trabalho_para_cena(self):
        """Coordenadas do trabalho (G-code / posição da máquina) -> mesa da tela (a mesma conta da mira)."""
        W, H = gc.area(gc.PERFIL)
        mapa = getattr(self, "_mapa_cabecote", None)

        def f(x, y):
            p = mapa((x, y)) if mapa is not None else (x, y)
            return QPointF(*gc.doc_para_maquina(p[0], p[1], W, H))
        return f

    def _tempo_do_trabalho(self, c):
        """Tempo decorrido, restante (corrigido pelo tempo real) e a camada de agora; atualiza a tela de corte."""
        import time
        job = c._job
        if job and job is not getattr(self, "_job_visto", None):  # trabalho novo (Iniciar, Retomar, faixa...)
            self._job_visto = job
            self._prev = tt.Previsao(tt.estimar(job, c.info.valor(110, 6000.0) or 6000.0))
            cam = tt.camadas(getattr(c, "texto_trabalho", "") or "")
            self._camadas_job = cam if len(cam) == len(job) else []
            self._t0, self._pausado, self._pausa_ini, self._fim = time.monotonic(), 0.0, None, None
            self._trechos, self._trilha_i = tt.trechos_com_laser(job), 0
            self.tela_corte.vista.limpar_trilha()
        self._marcar_aba_do_trabalho(c)
        prev = getattr(self, "_prev", None)
        rodando = c.trabalho in (cx.TRABALHO_RODANDO, cx.TRABALHO_PAUSADO)
        if prev is None or not (rodando or self._fim is not None or c.trabalho in (cx.TRABALHO_FIM, cx.TRABALHO_ERRO)):
            self.tela_corte.mostrar("Nenhum trabalho")
            return None
        agora = time.monotonic()
        if c.trabalho == cx.TRABALHO_PAUSADO and self._pausa_ini is None:
            self._pausa_ini = agora
        elif c.trabalho != cx.TRABALHO_PAUSADO and self._pausa_ini is not None:
            self._pausado += agora - self._pausa_ini
            self._pausa_ini = None
        if not rodando and self._fim is None:
            self._fim = agora - self._t0 - self._pausado  # congela o tempo no fim
        decorrido = self._fim if self._fim is not None else agora - self._t0 - self._pausado - (
            agora - self._pausa_ini if self._pausa_ini is not None else 0.0)
        feita = max(0, c.trabalho_ok - 15)  # "ok" = entrou no planejador do GRBL (~15 linhas à frente)
        if c.trabalho == cx.TRABALHO_FIM:
            feita = len(self._trechos)
        if feita > self._trilha_i:  # o que já foi feito com laser fica verde (do G-code: sem retas falsas)
            para_cena = self._trabalho_para_cena()
            self.tela_corte.vista.adicionar_trilha([(para_cena(*t[0]), para_cena(*t[1]))
                                                    for t in self._trechos[self._trilha_i:feita] if t])
            self._trilha_i = feita
        restante = prev.restante(feita, decorrido)[0] if rodando else 0.0
        # a camada de agora (o cabeçalho não tem: pega a próxima que aparece)
        cam = next((x for x in self._camadas_job[feita:feita + 500] if x), "") if rodando else ""
        nomes = {cx.TRABALHO_RODANDO: "Gravando / cortando…", cx.TRABALHO_PAUSADO: "PAUSADO",
                 cx.TRABALHO_FIM: "✔ Concluído", cx.TRABALHO_ERRO: "⏹ Parado / interrompido"}
        self.tela_corte.mostrar(nomes.get(c.trabalho, c.trabalho), decorrido, restante if rodando else None,
                                c.progresso if rodando else (1.0 if c.trabalho == cx.TRABALHO_FIM else 0.0),
                                f"Agora: {cam}" if cam else "",
                                f"{c.trabalho_ok} de {len(job)} linhas" if rodando else "")
        return restante if rodando else None

    # ---------- retomar depois de queda de luz / começar no meio ----------
    def _pasta_trabalho(self):
        from PySide6.QtCore import QStandardPaths
        base = (os.path.dirname(self.settings.fileName()) if self.settings.format() == QSettings.IniFormat
                else QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~"))
        pasta = os.path.join(base, "trabalho_em_andamento")
        os.makedirs(pasta, exist_ok=True)
        return pasta

    def _gravar_trabalho(self, linhas, base):
        """Guarda as linhas enviadas (uma vez) e o progresso (a cada segundo) para retomar depois."""
        pasta = self._pasta_trabalho()
        if base == 0:  # trabalho novo: grava as linhas
            with open(os.path.join(pasta, "trabalho.gcode"), "w", encoding="utf-8") as f:
                f.write("\n".join(linhas))
        c = self.conexao
        self._prog = {"total": len(linhas) if base == 0 else self._prog["total"], "base": base, "ok": max(base, 0),
                      "projeto": self.file_path or "", "homing": bool(c and c.tem_homing),
                      "inicio": self.inicio_trabalho.currentData(), "t": 0.0}
        self._escrever_progresso()

    def _escrever_progresso(self):
        import json as _json
        with open(os.path.join(self._pasta_trabalho(), "progresso.json"), "w", encoding="utf-8") as f:
            _json.dump(self._prog, f)

    def _salvar_progresso(self, c):
        import time
        p = getattr(self, "_prog", None)
        if p is None:
            return
        if c.trabalho in (cx.TRABALHO_RODANDO, cx.TRABALHO_PAUSADO):
            p["ok"] = max(p["ok"], p["base"] + c.trabalho_ok)
            if time.monotonic() - p["t"] >= 1.0:
                p["t"] = time.monotonic()
                self._escrever_progresso()
        elif c.trabalho == cx.TRABALHO_FIM:  # terminou: não há o que retomar
            self._prog = None
            for nome in ("progresso.json", "trabalho.gcode"):
                try:
                    os.remove(os.path.join(self._pasta_trabalho(), nome))
                except OSError:
                    pass
        elif c.trabalho == cx.TRABALHO_ERRO:  # parou no meio (reset, queda, Parar): grava o ponto e guarda
            p["ok"] = max(p["ok"], p["base"] + c.trabalho_ok)
            self._escrever_progresso()
            self._prog = None

    def trabalho_salvo(self):
        """(linhas, progresso) do último trabalho que não terminou, ou None."""
        import json as _json
        pasta = self._pasta_trabalho()
        try:
            with open(os.path.join(pasta, "progresso.json"), encoding="utf-8") as f:
                prog = _json.load(f)
            with open(os.path.join(pasta, "trabalho.gcode"), encoding="utf-8") as f:
                linhas = f.read().splitlines()
        except (OSError, ValueError):
            return None
        if not linhas or prog.get("ok", 0) >= len(linhas):
            return None
        return linhas, prog

    def ask_retomar(self, prog, total):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox
        d = QDialog(self)
        d.setWindowTitle("Retomar trabalho interrompido")
        f = QFormLayout(d)
        pct = prog["ok"] / max(total, 1) * 100
        info = QLabel(f"O último trabalho parou na linha {prog['ok']} de {total} ({pct:.0f} %)."
                      + (f"\nProjeto: {os.path.basename(prog['projeto'])}" if prog.get("projeto") else ""))
        info.setWordWrap(True)
        f.addRow(info)
        volta = QSpinBox()
        volta.setRange(0, max(0, prog["ok"]))
        volta.setValue(min(40, prog["ok"]))
        volta.setSuffix(" linhas antes")
        volta.setToolTip("A máquina guarda ~15 movimentos no buffer: os últimos \"ok\" podem não ter sido feitos. "
                         "Voltar um pouco repassa o trecho final com segurança.")
        f.addRow("Recomeçar:", volta)
        aviso = QLabel("⚠ A posição só bate se a máquina estiver no MESMO 0,0 de antes: faça \"Referenciar (home)\" "
                       "antes de retomar." + ("" if prog.get("homing") else
                                              "\nEste trabalho foi feito SEM homing: confira o ponto com a Mira "
                                              "antes (sem homing, o 0,0 é onde a máquina foi ligada)."))
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color:#ffd27a")
        f.addRow(aviso)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        f.addRow(bb)
        return volta.value() if d.exec() == QDialog.Accepted else None

    def retomar_interrompido(self):
        c = self.conexao
        salvo = self.trabalho_salvo()
        if c is None or not c.controle or salvo is None:
            self.statusBar().showMessage("Nada para retomar (ou controle da máquina não liberado).")
            return False
        linhas, prog = salvo
        voltar = self.ask_retomar(prog, len(linhas))
        if voltar is None:
            return False
        k = max(0, prog["ok"] - voltar)
        novo = gc.retomar_de(linhas, k)
        prefixo = len(novo) - (len(linhas) - k)
        self._mapa_cabecote = None  # coordenadas já são as da máquina
        ok = self._comando_maquina(lambda c: c.iniciar_trabalho("\n".join(novo), self._reref_s()),
                                   f"Retomando da linha {k} de {len(linhas)}…")
        if ok:
            if getattr(self, "_aba_do_trabalho", None) is not None:  # retomou a aba desta sessão: terminar marca ela
                self._aba_do_trabalho = (*self._aba_do_trabalho[:2], c._job)
            self._prog = {**prog, "base": k - prefixo, "ok": k, "t": 0.0}
            self._escrever_progresso()
        return ok

    def ask_faixa(self, linhas):
        """(início, fim) em linhas do G-code, escolhidos com prévia do trecho destacado no desenho; ou None."""
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QPainterPath as _P
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QSlider, QVBoxLayout as _V
        n = len(linhas)
        pos = []  # posição (x, y) em mm da máquina depois de cada linha
        x = y = 0.0
        import re as _re
        for ln in linhas:
            mx, my = _re.search(r"X(-?[\d.]+)", ln), _re.search(r"Y(-?[\d.]+)", ln)
            x, y = (float(mx.group(1)) if mx else x), (float(my.group(1)) if my else y)
            pos.append((x, y, ln.startswith("G1")))
        W, H = gc.area(gc.PERFIL)
        d = QDialog(self)
        d.setWindowTitle("Iniciar a partir de…")
        v = _V(d)
        v.addWidget(QLabel("Escolha o trecho do trabalho. O trecho aparece destacado em rosa no desenho; a máquina vai "
                           "até o começo dele com o laser APAGADO e grava só essa parte."))
        ini, fim = QSlider(_Qt.Horizontal), QSlider(_Qt.Horizontal)
        for s_ in (ini, fim):
            s_.setRange(0, n)
        fim.setValue(n)
        rot = QLabel()
        v.addWidget(QLabel("Começar em:"))
        v.addWidget(ini)
        v.addWidget(QLabel("Terminar em:"))
        v.addWidget(fim)
        v.addWidget(rot)

        def mostrar():
            a, b = ini.value(), max(ini.value(), fim.value())
            caminho = _P()
            ant = pos[a - 1][:2] if a > 0 else None
            for i in range(a, b):
                px, py, corte = pos[i]
                dx_, dy_ = gc.doc_para_maquina(px, py, W, H)
                if corte and ant is not None:
                    ax_, ay_ = gc.doc_para_maquina(ant[0], ant[1], W, H)
                    caminho.moveTo(ax_, ay_)
                    caminho.lineTo(dx_, dy_)
                ant = (px, py)
            if a < n:
                sx, sy = gc.doc_para_maquina(*(pos[a - 1][:2] if a > 0 else pos[0][:2]), W, H)
                caminho.addEllipse(QPointF(sx, sy), 2.5, 2.5)  # onde começa
            self.canvas.view.destacar(caminho)
            rot.setText(f"Linhas {a} até {b} de {n}  ({a / max(n, 1) * 100:.0f} % → {b / max(n, 1) * 100:.0f} %)")
        ini.valueChanged.connect(mostrar)
        fim.valueChanged.connect(mostrar)
        mostrar()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        r = d.exec() == QDialog.Accepted
        self.canvas.view.destacar(None)
        return (ini.value(), max(ini.value(), fim.value())) if r else None

    def _mira(self, on):
        c = self.conexao
        pot = min(self.pot_enquadrar.value(), cx.MIRA_POT_MAX)
        if on and self.btn_laser.isChecked():  # um só M3 por vez
            self.btn_laser.blockSignals(True)
            self.btn_laser.setChecked(False)
            self.btn_laser.blockSignals(False)
        if not self._comando_maquina(lambda c: c.mira(on, pot, gc.PERFIL.s_max),
                                     f"Mira {'LIGADA' if on else 'desligada'}" + (f" ({pot:g} %)" if on else "")):
            self.btn_mira.blockSignals(True)
            self.btn_mira.setChecked(False)
            self.btn_mira.blockSignals(False)
        _ = c

    def ask_laser_ligado(self, pot):
        return QMessageBox.warning(
            self, "Laser ligado", f"O laser vai ACENDER a {pot:g} % e ficar aceso até você desligar.\n\nEle QUEIMA e "
            "corta: confira o material embaixo e use óculos de proteção. As setas do teclado movem o cabeçote com o "
            "laser aceso.", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes

    def _laser_ligado(self, on):
        pot = self.pot_laser.value()
        ok = not on or self.ask_laser_ligado(pot)
        if on and ok and self.btn_mira.isChecked():  # um só M3 por vez
            self.btn_mira.blockSignals(True)
            self.btn_mira.setChecked(False)
            self.btn_mira.blockSignals(False)
        if not ok or not self._comando_maquina(lambda c: c.laser_ligado(on, pot, gc.PERFIL.s_max),
                                               f"Laser LIGADO a {pot:g} %: setas movem o cabeçote." if on
                                               else "Laser desligado."):
            self.btn_laser.blockSignals(True)
            self.btn_laser.setChecked(False if on else self.btn_laser.isChecked())
            self.btn_laser.blockSignals(False)
            return
        if on:
            self.btn_laser.setFocus()  # setas já funcionam

    def _motores(self, soltos):
        if not self._comando_maquina(lambda c: c.soltar_motores(soltos),
                                     "Motores SOLTOS ao parar: pode empurrar o cabeçote com a mão." if soltos
                                     else "Motores travados de novo."):
            self.btn_motores.blockSignals(True)
            self.btn_motores.setChecked(not soltos)
            self.btn_motores.blockSignals(False)

    def ask_fora_do_curso(self, avisos):
        r = QMessageBox.warning(
            self, "Fora da área da máquina",
            "O trabalho " + " e ".join(avisos) + ".\n\nSem homing, a máquina conta a área a partir de onde o cabeçote "
            "estava quando foi ligada. Se continuar, ela pode bater no fim do trilho.\n\nDicas: \"Zerar origem\", "
            "mova o desenho para dentro da mesa ou use \"Começar de: Posição atual\".\n\nContinuar mesmo assim?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Yes

    def _dentro_do_curso(self, caixa):
        if self.rotativo.ativo and self.conexao and self.conexao.info.valor(20, 0) == 1:
            # GRBL com limite por software confere o eixo do rotativo contra o curso da mesa e trava no meio do giro
            self.show_error("Rotativo × limite de curso ($20=1)",
                            "A placa está com o limite de curso por software LIGADO ($20=1). Com o rotativo, o eixo "
                            f"{self.rotativo.eixo} gira a peça e passa do tamanho da mesa: o GRBL entra em ALARME no "
                            "meio da gravação.\n\nPara usar o rotativo: Laser → Rotativo: liberar GRBL ($20=0). Quando "
                            "voltar para a mesa normal: Laser → Rotativo: religar limite de curso ($20=1). "
                            "Nada foi enviado.")
            return False
        if self.rotativo.ativo:  # o eixo que gira a peça não tem fim de curso: só o outro conta
            x0, y0, x1, y1 = caixa
            caixa = (x0, y0, x0, y1) if self.rotativo.eixo == "X" else (x0, y0, x1, y0)
        avisos = self.conexao.fora_do_curso(*caixa) if self.conexao else []
        return not avisos or self.ask_fora_do_curso(avisos)

    def _toggle_conexao(self):
        if self.conexao and self.conexao.estado not in (cx.DESCONECTADO, cx.FALHA):
            self.conexao.desconectar()
            self._atualizar_maquina()
            return
        porta = self.port_combo.currentData()
        if porta is None:
            sim = SimuladorGrbl()
            sim.conectado = False  # abrir a porta = placa reinicia (mostra boas-vindas)
            tr = tp.TransporteSimulado(sim)
        else:
            tr = tp.TransporteSerial(porta, int(self.baud_combo.currentText()))
        self.conexao = cx.Conexao(tr, intervalo_status_s=0.12)  # ~8 leituras/s: mira acompanha melhor
        if isinstance(tr, tp.TransporteSerial):
            # cada resposta do GRBL é tratada na thread da serial (como o LaserGRBL): o "ok" manda a próxima linha
            # na hora, mesmo com a tela ocupada redesenhando — antes a máquina parava e marcava a peça
            tr.ao_linha = self.conexao.chegou
        self._log_visto = 0
        self.machine_log.clear()
        self.conexao.conectar()
        self._conexao_timer.start()
        self._atualizar_maquina()

    def _tick_conexao(self):
        if self.conexao:
            self.conexao.tick(self._conexao_timer.interval() / 1000)
            texto = getattr(self, "_trabalho_pendente", None)
            c = self.conexao
            if texto and c.estado == cx.CONECTADO and not c._fila and c._atual is None:
                self._trabalho_pendente = None
                self._comando_maquina(lambda c: c.iniciar_trabalho(texto, self._reref_s()),
                                      "Trabalho enviado à máquina.")
            self._atualizar_maquina()

    def _atualizar_maquina(self):
        c = self.conexao
        if c is None:
            return
        ativo = c.estado not in (cx.DESCONECTADO, cx.FALHA)
        if not ativo:
            self._conexao_timer.stop()
        self.btn_connect.setText("Desconectar" if ativo else "Conectar")
        self._avisos_sonoros(c)
        pos = c.posicao if ativo else None
        if pos is not None:  # mostra o cabeçote na mesa (trabalho -> desenho; a conta é a mesma nos dois sentidos)
            W, H = gc.area(gc.PERFIL)
            mapa = getattr(self, "_mapa_cabecote", None)
            if mapa is not None and c.trabalho in (cx.TRABALHO_RODANDO, cx.TRABALHO_PAUSADO):
                pos = mapa(pos)  # durante o trabalho: a mira anda em cima do desenho (posição atual / rotativo)
            dx, dy = gc.doc_para_maquina(pos[0], pos[1], W, H)
            laser = bool(c.status and (c.status.spindle or 0) > 0 and c.status.estado.startswith("Run"))
            self.canvas.view.definir_cabecote(QPointF(dx, dy), laser)
            self.tela_corte.vista.definir(QPointF(dx, dy), laser)
        else:
            self.canvas.view.definir_cabecote(None)
        livre = ativo and c.estado == cx.CONECTADO and c.controle
        rodando = c.trabalho in (cx.TRABALHO_RODANDO, cx.TRABALHO_PAUSADO)
        for b in (*self.jog_btns.values(), self.btn_enquadrar, self.btn_origem, self.btn_desbloquear, self.btn_ar,
                  self.btn_zerar_origem, self.btn_home, self.btn_faixa, self.btn_mira, self.btn_motores,
                  self.btn_laser):
            b.setEnabled(livre and not rodando)
        ar = c.ar_maquina if ativo else None
        self.lbl_ar.setText("Ar na máquina: " + ("—" if ar is None else "FORTE (M8 ligado)" if ar
                                                 else "fraco (M8 desligado)"))
        self.btn_iniciar.setEnabled(livre and not rodando)
        self.btn_retomar.setEnabled(livre and not rodando and self.trabalho_salvo() is not None)
        if livre and self.btn_motores.isEnabled():
            soltos = (c.info.valor(1, 255) or 255) != 255
            if soltos != self.btn_motores.isChecked():
                self.btn_motores.blockSignals(True)
                self.btn_motores.setChecked(soltos)
                self.btn_motores.blockSignals(False)
        for b in (self.btn_mira, self.btn_laser):
            if (rodando or not livre) and b.isChecked():  # o trabalho começa com M5 / sem controle: apagou
                b.blockSignals(True)
                b.setChecked(False)
                b.blockSignals(False)
        self._salvar_progresso(c)
        self.btn_pausar.setEnabled(livre and rodando)
        self.btn_pausar.setText("Retomar" if c.trabalho == cx.TRABALHO_PAUSADO else "Pausar")
        self.btn_parar.setEnabled(ativo)
        self.btn_controle.setEnabled(ativo and c.estado == cx.CONECTADO)
        if not ativo and self.btn_controle.isChecked():
            self.btn_controle.blockSignals(True)
            self.btn_controle.setChecked(False)
            self.btn_controle.setText("🔓 Liberar controle da máquina")
            self.btn_controle.blockSignals(False)
        restante = self._tempo_do_trabalho(c)
        tc = self.tela_corte
        tc.btn_pausar.setEnabled(self.btn_pausar.isEnabled())
        tc.btn_pausar.setText("▶  RETOMAR" if c.trabalho == cx.TRABALHO_PAUSADO else "⏸  PAUSAR")
        tc.btn_parar.setEnabled(self.btn_parar.isEnabled())
        tc.btn_ar.setEnabled(self.btn_ar.isEnabled())
        if tc.btn_ar.isChecked() != self.btn_ar.isChecked():
            tc.btn_ar.setChecked(self.btn_ar.isChecked())
        if c._job or rodando:
            self.progresso_trabalho.setValue(int(c.progresso * 1000))
            self.progresso_trabalho.setFormat(f"{c.trabalho}: {c.trabalho_ok} de {len(c._job)} linhas (%p%)"
                                              + (f" — falta ≈ {tt.fmt(restante)}" if restante is not None else ""))
        elif c.trabalho != cx.TRABALHO_PARADO:
            self.progresso_trabalho.setValue(1000 if c.trabalho == cx.TRABALHO_FIM else 0)
            self.progresso_trabalho.setFormat(f"Trabalho: {c.trabalho}")
        self.port_combo.setEnabled(not ativo)
        self.baud_combo.setEnabled(not ativo)
        estado = f"Estado: {c.estado}"
        if c.status and c.status.em_alarme:
            estado += " — ⚠ MÁQUINA EM ALARME: clique em \"Desbloquear ($X)\""
        elif c.status:
            estado += f" — controlador: {c.status.estado}"
            if pos is not None:
                estado += f" — cabeçote X {pos[0]:.1f} Y {pos[1]:.1f} mm".replace(".", ",")
            if c.status.spindle is not None and (c.status.spindle > 0 or c.status.estado.startswith("Run")):
                pct = c.status.spindle / max(gc.PERFIL.s_max, 1) * 100
                estado += f" — laser S{c.status.spindle:.0f} ({pct:.0f} %)".replace(".", ",")
        if c.estado == cx.FALHA:
            estado += f" — {c.erro}"
        self.machine_state.setText(estado)
        alvo = "simulador" if isinstance(c.tr, tp.TransporteSimulado) else getattr(c.tr, "porta", "")
        self.machine_status_label.setText(f"Máquina: {c.estado.lower()} ({alvo}, somente leitura)" if ativo
                                          else "Máquina: desconectada")
        info = c.info
        linhas = []
        if info.firmware or info.versao:
            linhas.append(f"Firmware: Grbl {info.firmware or '?'} {info.versao and '(' + info.versao + ')'}")
        if c.status and c.status.mpos:
            x, y = c.status.mpos[:2]
            linhas.append(f"Posição de máquina: X {x:.3f}  Y {y:.3f} mm")
        if info.config:
            a = info.area
            linhas.append(f"Área ($130×$131): {a[0]:g} × {a[1]:g} mm" if a else "Área: não informada")
            def v(n):
                return "?" if n not in info.config else f"{info.config[n]:g}"
            linhas.append(f"$30 potência máx.: {v(30)} · $32 modo laser: {v(32)} · $22 homing: {v(22)} · "
                          f"$20 limites: {v(20)}")
            linhas.append(f"Velocidade máx. X/Y ($110/$111): {v(110)} / {v(111)} mm/min")
        self.machine_info.setText("\n".join(linhas) or ("Não conectado." if not ativo else "Aguardando resposta…"))
        avisos = info.avisos() if info.config else []
        if c.status and c.status.em_alarme:
            avisos.insert(0, "Controlador em ALARME. Esta versão não desbloqueia: verifique a máquina.")
        self.machine_warn.setText("\n".join("⚠ " + a for a in avisos))
        self.machine_warn.setVisible(bool(avisos))
        self.btn_report.setEnabled(bool(info.config))
        novos = c.n_log - self._log_visto  # o registro guarda só o fim: conta pelo total já registrado
        for sentido, texto in (c.log[-novos:] if novos > 0 else []):
            if not (sentido == "←" and texto.startswith("<")):  # status periódico não polui o registro
                self.machine_log.appendPlainText(f"{sentido} {texto}")
        self._log_visto = c.n_log

    def _salvar_relatorio_dialogo(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar relatório da máquina",
                                              os.path.join(self._last_dir(), "maquina.json"), "JSON (*.json)")
        if path:
            self.salvar_relatorio_maquina(path)

    def salvar_relatorio_maquina(self, path) -> bool:
        c = self.conexao
        if not c or not c.info.config:
            return False
        rel = {"lido_em": datetime.now().isoformat(timespec="seconds"), "porta": getattr(c.tr, "nome", ""),
               "estado": c.status.estado if c.status else None, "avisos": c.info.avisos(), **c.info.resumo()}
        try:
            gc.salvar(path, json.dumps(rel, ensure_ascii=False, indent=1) + "\n")
        except OSError as e:
            self.show_error("Não foi possível salvar o relatório", str(e))
            return False
        self.statusBar().showMessage(f"Relatório da máquina salvo: {path}")
        return True

    def closeEvent(self, e):
        if not self._maybe_save():
            e.ignore()
            return
        self._limpar_recuperacao()  # fechou certinho (salvou ou descartou): nada a recuperar
        if not self.file_path:
            self.settings.setValue("sessao/ultimo", "")  # projeto novo descartado: começa limpo
        if self.conexao and self.conexao.estado not in (cx.DESCONECTADO, cx.FALHA):
            self.conexao.desconectar()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.sync()
        super().closeEvent(e)

    def _about(self):
        QMessageBox.about(self, "Sobre o RedBlack Laser",
                          f"<b>RedBlack Laser</b> {__version__}<br>{DIREITOS}<br>{CREDITOS}<br><br>"
                          "Protótipo: gera G-code, mas ainda não envia nada à máquina (conexão somente leitura). "
                          "Valores da máquina e dos materiais NÃO validados: teste antes de usar.<br><br>"
                          "Feito com Qt for Python (PySide6), licença LGPL v3 — https://www.qt.io/")
