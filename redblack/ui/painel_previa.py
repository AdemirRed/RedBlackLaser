"""Painel da prévia do percurso (Etapa 10): resumo, estimativa de tempo e simulação."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSlider, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import percurso as pc

DURACAO_ANIMACAO_S = 15.0  # a simulação completa dura isto, independente do tempo estimado do trabalho
PASSO_MS = 30
ESCALA = 1000


class PainelPrevia(QWidget):
    rapidoChanged = Signal(float)
    tempoChanged = Signal(float)       # instante da simulação em segundos
    mostrarVaziosChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.percurso = None
        self.cron = []
        v = QVBoxLayout(self)
        self.nota = QLabel("Estimativa MÍNIMA (comprimento ÷ velocidade): ignora aceleração e firmware; "
                           "o tempo real tende a ser maior.")
        self.nota.setObjectName("banner")
        self.nota.setWordWrap(True)
        v.addWidget(self.nota)

        top = QHBoxLayout()
        self.lbl_tempo = QLabel("—")
        self.lbl_tempo.setStyleSheet("font-weight:bold;font-size:12pt")
        self.lbl_tempo.setAccessibleName("Tempo estimado")
        top.addWidget(self.lbl_tempo)
        top.addStretch(1)
        top.addWidget(QLabel("Deslocamento sem laser"))
        self.rapido = QDoubleSpinBox()
        self.rapido.setRange(100, 60000)
        self.rapido.setDecimals(0)
        self.rapido.setSuffix(" mm/min")
        self.rapido.setValue(pc.DEFAULT_RAPIDO_MM_MIN)
        self.rapido.setKeyboardTracking(False)
        self.rapido.setToolTip("SUPOSIÇÃO: velocidade da máquina ainda não confirmada (docs/MAQUINA.md)")
        self.rapido.editingFinished.connect(lambda: self.rapidoChanged.emit(self.rapido.value()))
        top.addWidget(self.rapido)
        v.addLayout(top)

        self.lbl_resumo = QLabel("")
        self.lbl_resumo.setWordWrap(True)
        v.addWidget(self.lbl_resumo)
        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setObjectName("banner")
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.hide()
        v.addWidget(self.lbl_aviso)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Camada", "Passadas", "Com laser (mm)", "Tempo"])
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setAccessibleName("Resumo por camada")
        self.tabela.setMaximumHeight(96)
        v.addWidget(self.tabela)

        ctl = QHBoxLayout()
        self.btn_play = QPushButton("▶ Simular")
        self.btn_play.setCheckable(True)
        self.btn_play.toggled.connect(self._toggle_play)
        ctl.addWidget(self.btn_play)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, ESCALA)
        self.slider.setAccessibleName("Posição da simulação")
        self.slider.valueChanged.connect(self._on_slider)
        ctl.addWidget(self.slider, 1)
        self.chk_vazios = QCheckBox("Mostrar deslocamentos")
        self.chk_vazios.setChecked(True)
        self.chk_vazios.toggled.connect(self.mostrarVaziosChanged)
        ctl.addWidget(self.chk_vazios)
        v.addLayout(ctl)
        self.lbl_estado = QLabel("")
        v.addWidget(self.lbl_estado)
        legenda = QLabel("Colorido = laser ligado · tracejado cinza = deslocamento sem laser · "
                         "círculo cheio = emitindo, vazado = deslocando")
        legenda.setWordWrap(True)
        v.addWidget(legenda)
        v.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(PASSO_MS)
        self.timer.timeout.connect(self._tick)

    # ---------- dados ----------
    def set_percurso(self, p, mensagem="", passadas=None):
        """p = Percurso (ou None). `passadas`: {camada: n} para a tabela."""
        self.btn_play.setChecked(False)
        self.percurso, self.cron = p, (p.cronograma() if p else [])
        self.tabela.setRowCount(0)
        self.lbl_aviso.hide()
        if p is None or not p.trechos:
            self.lbl_tempo.setText("—")
            self.lbl_resumo.setText(mensagem or "Nada para executar: nenhum objeto em camada com Saída ligada.")
            self.lbl_estado.setText("")
            self.slider.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.slider.setValue(0)
            return
        self.slider.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.lbl_tempo.setText(f"Tempo estimado: ≈ {pc.fmt_tempo(p.tempo_s)} (mínimo)")
        vazio_s = sum(t.tempo_s for t in p.trechos if t.tipo == "vazio")
        self.lbl_resumo.setText(
            f"Com laser: {p.comprimento_corte:,.1f} mm · Sem laser: {p.comprimento_vazio:,.1f} mm "
            f"(≈ {pc.fmt_tempo(vazio_s)})".replace(",", " ").replace(".", ","))
        res = p.por_camada()
        self.tabela.setRowCount(len(res))
        for r, (lid, (comp, seg)) in enumerate(res.items()):
            vals = (lid, str((passadas or {}).get(lid, "")), f"{comp:,.1f}".replace(",", " ").replace(".", ","),
                    pc.fmt_tempo(seg))
            for c, val in enumerate(vals):
                self.tabela.setItem(r, c, QTableWidgetItem(val))
        self.tabela.resizeColumnsToContents()
        if p.fora_da_mesa():
            self.lbl_aviso.setText("Atenção: parte do percurso está fora da área da mesa (400 × 400 mm demonstrativos).")
            self.lbl_aviso.show()
        self._on_slider(self.slider.value())

    def tempo_atual(self) -> float:
        total = self.cron[-1] if self.cron else 0.0
        return total * self.slider.value() / ESCALA

    # ---------- simulação ----------
    def _on_slider(self, _=None):
        t = self.tempo_atual()
        self.tempoChanged.emit(t)
        p = self.percurso
        if p is None or not p.trechos:
            return
        n, _pts, _atual, emitindo = p.estado_em(t, self.cron)
        if t >= self.cron[-1] - 1e-9:
            quando = "fim do percurso (retornou à origem)"
        elif emitindo:
            quando = f"CORTANDO com laser ligado — camada {p.trechos[n].camada}"
        else:
            quando = "deslocamento sem laser"
        self.lbl_estado.setText(f"{pc.fmt_tempo(t)} de {pc.fmt_tempo(self.cron[-1])} — {quando}")

    def _toggle_play(self, on):
        self.btn_play.setText("⏸ Pausar" if on else "▶ Simular")
        if on:
            if self.slider.value() >= ESCALA:
                self.slider.setValue(0)
            self.timer.start()
        else:
            self.timer.stop()

    def _tick(self):
        passo = max(1, round(ESCALA * PASSO_MS / 1000 / DURACAO_ANIMACAO_S))
        v = min(ESCALA, self.slider.value() + passo)
        self.slider.setValue(v)
        if v >= ESCALA:
            self.btn_play.setChecked(False)
