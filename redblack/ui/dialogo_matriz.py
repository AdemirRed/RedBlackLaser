"""Diálogo da matriz de testes de materiais."""
from dataclasses import fields

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)

from .. import geometria as g
from .. import gcode as gc
from .. import matriz as mz
from .. import percurso as pc

MODOS = (("preenchimento", "Gravação (preenchimento)"), ("linha", "Corte / contorno (linha)"))
# Tipos prontos (como os geradores do LaserGRBL): (rótulo, modo, colunas, linhas)
TIPOS = (("Gravação: Potência × Velocidade", "preenchimento", "potencia", "velocidade"),
         ("Corte: Velocidade × Passadas (potência fixa)", "linha", "velocidade", "passadas"),
         ("Corte: Potência × Passadas", "linha", "potencia", "passadas"),
         ("Gravação: Potência × Intervalo de linhas", "preenchimento", "potencia", "intervalo"),
         ("Personalizado", None, None, None))


def _dsb(lo, hi, dec, suf, step=1.0):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSuffix(suf)
    s.setSingleStep(step)
    return s


def _isb(lo, hi):
    s = QSpinBox()
    s.setRange(lo, hi)
    return s


class MatrizDialog(QDialog):
    def __init__(self, parent, inicial: mz.Matriz, material=None):
        super().__init__(parent)
        self.setWindowTitle("Matriz de testes de materiais")
        self.material = material
        v = QVBoxLayout(self)
        aviso = QLabel("Grava uma grade de quadrados, cada um com parâmetros próprios. Exporte o G-code ou envie "
                       "direto para a máquina conectada. Use numa sobra do mesmo material.")
        aviso.setWordWrap(True)
        v.addWidget(aviso)
        c = self.campos = {}
        c["modo"] = QComboBox()
        for k, t in MODOS:
            c["modo"].addItem(t, k)
        c["pot_min"], c["pot_max"] = _dsb(0, 100, 1, " %"), _dsb(0, 100, 1, " %")
        c["colunas"], c["linhas"] = _isb(1, mz.MAX_LADO), _isb(1, mz.MAX_LADO)
        c["vel_min"], c["vel_max"] = _dsb(1, 60000, 0, " mm/min", 100), _dsb(1, 60000, 0, " mm/min", 100)
        c["celula_mm"], c["vao_mm"] = _dsb(2, 100, 1, " mm"), _dsb(0, 50, 1, " mm")
        c["x_mm"], c["y_mm"] = _dsb(0, 10000, 1, " mm"), _dsb(0, 10000, 1, " mm")
        c["passadas"] = _isb(1, 99)
        c["intervalo_mm"] = _dsb(0.01, 5, 2, " mm", 0.01)
        c["air"] = QCheckBox("Air assist")
        c["rotulos"] = QCheckBox("Gravar rótulos (valores das colunas em cima e das linhas à esquerda)")
        c["rotulo_pot"], c["rotulo_vel"] = _dsb(0, 100, 1, " %"), _dsb(1, 60000, 0, " mm/min", 100)
        c["linhas_param"] = QComboBox()
        for k, t in (("velocidade", "Velocidade"), ("intervalo", "Intervalo de linhas (teste de intervalo)"),
                     ("passadas", "Passadas")):
            c["linhas_param"].addItem(t, k)
        c["lin_min"], c["lin_max"] = _dsb(0.01, 99, 2, "", 0.05), _dsb(0.01, 99, 2, "", 0.05)
        c["colunas_param"] = QComboBox()
        for k, t in (("potencia", "Potência"), ("velocidade", "Velocidade (potência fixa)")):
            c["colunas_param"].addItem(t, k)
        c["pot_fixa"] = _dsb(0, 100, 1, " %")
        c["comando"] = QComboBox()
        for k, t in (("", "O do perfil da máquina"), ("M3", "M3 — potência constante"),
                     ("M4", "M4 — dinâmica (acompanha a velocidade)")):
            c["comando"].addItem(t, k)
        self.tipo = QComboBox()
        for t in TIPOS:
            self.tipo.addItem(t[0])
        self.tipo.currentIndexChanged.connect(self._aplicar_tipo)
        v.addWidget(QLabel("<b>Tipo de teste</b>"))
        v.addWidget(self.tipo)

        def grupo(titulo, linhas):
            grp = QGroupBox(titulo)
            f = QFormLayout(grp)
            for rot, w in linhas:
                f.addRow(rot, w) if rot else f.addRow(w)
            v.addWidget(grp)

        grupo("Teste", [("Operação", c["modo"]), ("Modo do laser", c["comando"]), ("Passadas", c["passadas"]),
                        ("Intervalo de linhas", c["intervalo_mm"]), (None, c["air"])])
        grupo("Colunas", [("As colunas variam", c["colunas_param"]), ("Potência de", c["pot_min"]),
                          ("Potência até", c["pot_max"]), ("Potência fixa", c["pot_fixa"]), ("Colunas", c["colunas"])])
        grupo("Linhas", [("As linhas variam", c["linhas_param"]), ("Velocidade de", c["vel_min"]),
                         ("Velocidade até", c["vel_max"]), ("Valor de", c["lin_min"]), ("Valor até", c["lin_max"]),
                         ("Linhas", c["linhas"])])
        grupo("Posição e tamanho", [("Lado do quadrado", c["celula_mm"]), ("Vão", c["vao_mm"]),
                                    ("X do canto superior esquerdo", c["x_mm"]),
                                    ("Y do canto superior esquerdo", c["y_mm"]), (None, c["rotulos"]),
                                    ("Potência dos rótulos", c["rotulo_pot"]),
                                    ("Velocidade dos rótulos", c["rotulo_vel"])])
        h = QHBoxLayout()
        self.btn_material = QPushButton("Faixa em volta do material selecionado")
        self.btn_material.setEnabled(material is not None)
        self.btn_material.setToolTip("Potência e velocidade em volta do preset escolhido no painel Materiais")
        self.btn_material.clicked.connect(self.usar_material)
        h.addWidget(self.btn_material)
        v.addLayout(h)
        self.resumo = QLabel()
        self.resumo.setWordWrap(True)
        v.addWidget(self.resumo)
        self.botoes = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.acao = "gcode"
        self.btn_ok = self.botoes.addButton("Exportar G-code…", QDialogButtonBox.AcceptRole)
        self.btn_enviar = self.botoes.addButton("Enviar para a máquina", QDialogButtonBox.AcceptRole)
        self.btn_enviar.setToolTip("Grava agora na máquina conectada (pede confirmação; respeita \"Começar de\" do "
                                   "painel Máquina — use Posição atual para gravar onde o cabeçote está)")
        self.btn_ok.clicked.connect(lambda: setattr(self, "acao", "gcode"))
        self.btn_enviar.clicked.connect(lambda: setattr(self, "acao", "maquina"))
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        v.addWidget(self.botoes)
        self._mostrar(inicial)
        for w in c.values():
            sig = getattr(w, "valueChanged", None) or getattr(w, "toggled", None) or w.currentIndexChanged
            sig.connect(self._atualizar)
        self._atualizar()

    # Y em coordenadas de exibição (origem inferior esquerda), como no resto do programa.
    def _mostrar(self, m):
        c = self.campos
        for f in fields(mz.Matriz):
            w, val = c[f.name], getattr(m, f.name)
            if isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(val)))
            elif isinstance(w, QCheckBox):
                w.setChecked(val)
            else:
                w.setValue(g.BED_H - val if f.name == "y_mm" else val)

    def matriz(self) -> mz.Matriz:
        c, d = self.campos, {}
        for f in fields(mz.Matriz):
            w = c[f.name]
            if isinstance(w, QComboBox):
                d[f.name] = w.currentData()
            elif isinstance(w, QCheckBox):
                d[f.name] = w.isChecked()
            else:
                d[f.name] = g.BED_H - w.value() if f.name == "y_mm" else w.value()
        return mz.Matriz(**d)

    def usar_material(self):
        m, c = self.material, self.campos
        c["modo"].setCurrentIndex(c["modo"].findData(m.modo))
        c["pot_min"].setValue(max(1.0, m.potencia_max - 20 if m.operacao == "corte" else m.potencia_max * 0.5))
        c["pot_max"].setValue(m.potencia_max if m.operacao == "corte" else min(100.0, m.potencia_max * 1.5))
        c["vel_min"].setValue(max(1.0, round(m.velocidade_mm_min * 0.5)))
        c["vel_max"].setValue(round(m.velocidade_mm_min * 1.5))
        c["passadas"].setValue(m.passadas)
        c["intervalo_mm"].setValue(m.intervalo_mm)
        c["air"].setChecked(m.air)

    def _aplicar_tipo(self, i):
        _t, modo, col, lin = TIPOS[i]
        if modo is None:
            return
        c = self.campos
        c["modo"].setCurrentIndex(c["modo"].findData(modo))
        c["colunas_param"].setCurrentIndex(c["colunas_param"].findData(col))
        c["linhas_param"].setCurrentIndex(c["linhas_param"].findData(lin))
        if lin == "passadas":
            c["lin_min"].setValue(1)
            c["lin_max"].setValue(4)
            c["linhas"].setValue(4)  # 1, 2, 3 e 4 passadas (sem repetir)
        if col == "velocidade" and c["vel_max"].value() > 3000:  # corte: velocidades baixas
            c["vel_min"].setValue(150)
            c["vel_max"].setValue(750)

    def _atualizar(self, *_):
        m = self.matriz()
        self.campos["intervalo_mm"].setEnabled(m.modo != "linha" and m.linhas_param != "intervalo")
        self.campos["passadas"].setEnabled(m.linhas_param != "passadas")
        var = m.linhas_param == "velocidade"
        col_vel = m.colunas_param == "velocidade"
        self.campos["vel_max"].setEnabled(var or col_vel)
        for k in ("pot_min", "pot_max"):
            self.campos[k].setEnabled(not col_vel)
        self.campos["pot_fixa"].setEnabled(col_vel)
        for k in ("lin_min", "lin_max"):
            self.campos[k].setEnabled(not var)
            self.campos[k].setSuffix(" mm" if m.linhas_param == "intervalo" else "")
        for k in ("rotulo_pot", "rotulo_vel"):
            self.campos[k].setEnabled(m.rotulos)
        e = mz.erros(m, g.BED_W, g.BED_H)
        x0, y0, x1, y1 = m.limites()
        txt = f"{m.colunas * m.linhas} quadrado(s); área {x1 - x0:.0f} × {y1 - y0:.0f} mm.".replace(".", ",")
        if not e:
            try:
                _, perc = mz.gerar(m)
                txt += f" Tempo mínimo estimado: {pc.fmt_tempo(perc.tempo_s)}."
            except (gc.GcodeInvalido, pc.LimiteExcedido) as ex:
                e = [str(ex)]
        if e:
            txt += "\n" + "; ".join(e)
        self.resumo.setText(txt)
        self.btn_ok.setEnabled(not e)
        self.btn_enviar.setEnabled(not e)
