"""Compensação do eixo X (cortes): desconta uma quantidade fixa de mm/min da velocidade nos trechos em X.

Medido na SCULPFUN S30 Pro Max 20 W em MDF 3 mm: Y corta limpo a 800 mm/min e X precisa de 550 → desconto padrão
de 250 mm/min. Vale para qualquer velocidade de corte (800 → X 550; 1000 → X 750), com transição gradual nas
diagonais/curvas (cos² da direção) e um mínimo configurável (nunca zero/negativo). Só muda a VELOCIDADE dos
trechos de CORTE com laser ligado: potência, passadas, medidas, deslocamentos sem laser e GRBL ficam iguais.
LIGADA por padrão e salva nas configurações; desliga pelo menu Laser ou por esta janela.
"""
import json

from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from .. import gcode as gc

CHAVE = "compensacao_x"
PADRAO = {"ativo": True, "desconto": 250.0, "minimo": 150.0,
          "teste": {"velocidade": 800.0, "potencia": 85.0, "passadas": 2}}


def ler(settings) -> dict:
    try:
        d = json.loads(settings.value(CHAVE, "") or "null") or {}
    except (TypeError, ValueError):
        d = {}
    out = {**PADRAO, **{k: v for k, v in d.items() if k in PADRAO}}
    out["teste"] = {**PADRAO["teste"], **(d.get("teste") or {})}
    return out


def gravar(settings, d):
    settings.setValue(CHAVE, json.dumps(d, ensure_ascii=False))


def aplicar(settings) -> str:
    """Liga/desliga a compensação no gerador de G-code conforme o salvo. Devolve o texto da barra de status."""
    d = ler(settings)
    try:
        gc.definir_comp_x(float(d["desconto"]) if d["ativo"] else 0.0, float(d["minimo"]))
    except ValueError:
        gc.definir_comp_x(0.0, 150.0)
        return ""
    return (f"Compensação X: −{d['desconto']:g} mm/min (mín. {d['minimo']:g})"
            if d["ativo"] and d["desconto"] > 0 else "")


def gcode_teste(d, x0=30.0, y0=30.0) -> str:
    """Teste comparativo: à esquerda SEM compensação, à direita COM. Cada lado: quadrado 20×20 mm, linha horizontal e
    vertical de 30 mm, todos na velocidade/potência/passadas do teste; rótulos gravados fracos."""
    from dataclasses import replace

    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainterPath, QTransform

    from .. import camadas as cm
    from .. import matriz as mz
    from .. import percurso as pc
    W, H = gc.area(gc.PERFIL)
    if x0 + 125 > W or y0 + 70 > H:
        raise gc.GcodeInvalido("O teste (125 × 70 mm) não cabe na mesa nessa posição.")
    t = d["teste"]
    vel, desconto, minimo = float(t["velocidade"]), float(d["desconto"]), float(d["minimo"])
    rot = QPainterPath()
    rot.addPath(mz._texto("SEM", x0 + 10, y0 - 5))
    rot.addPath(mz._texto("COM", x0 + 80, y0 - 5))
    lay = cm.Camada("MROT", "rótulos", "linha", 3000, 15, 0.0, 1, 0.1)
    rotulos = gc.gerar(pc.gerar([(rot, QTransform(), "rot", "MROT", "#fff", None)], [lay]), [lay],
                       replace(gc.PERFIL, comp_x_desconto=0.0))
    linhas = rotulos.splitlines()
    while linhas and linhas[-1].split(";")[0].strip() in ("M5", "M9", "M2", ""):
        linhas.pop()
    s = round(float(t["potencia"]) / 100 * gc.PERFIL.s_max)
    vx = gc.velocidade_compensada(vel, 1.0, desconto, minimo)
    out = linhas + ["M5", "M3 S0 ; corte em potencia constante", "M8 ; air assist"]

    def maq(x, y):
        return gc.doc_para_maquina(x, y, W, H)
    for k, com in ((0, False), (1, True)):
        bx = x0 + k * 70
        q = QRectF(bx, y0, 20, 20)
        formas = [[(q.left(), q.top()), (q.right(), q.top()), (q.right(), q.bottom()), (q.left(), q.bottom()),
                   (q.left(), q.top())],
                  [(bx, y0 + 32), (bx + 30, y0 + 32)],          # horizontal (X)
                  [(bx + 40, y0), (bx + 40, y0 + 30)]]          # vertical (Y)
        out.append(f"; {'COM' if com else 'SEM'} compensacao: X {vx if com else vel:g} / Y {vel:g} mm/min, "
                   f"{t['potencia']:g} %, {int(t['passadas'])} passada(s)")
        for pts in formas:
            m = [maq(*a) for a in pts]
            for _ in range(int(t["passadas"])):
                out.append(f"G0 X{m[0][0]:.3f} Y{m[0][1]:.3f}")
                for (ax, ay), (cx, cy) in zip(m, m[1:]):
                    f = vx if (com and abs(cx - ax) > abs(cy - ay)) else vel
                    out.append(f"G1 X{cx:.3f} Y{cy:.3f} S{s} F{f:g}")
    out += ["M5 ; laser desligado", "M9 ; air assist desligado", "M2 ; fim do programa"]
    return "\n".join(out) + "\n"


class DialogoCalibracaoXY(QDialog):
    def __init__(self, janela):
        super().__init__(janela)
        self.jp = janela
        self.setWindowTitle("Compensação do eixo X")
        self.d = ler(janela.settings)
        v = QVBoxLayout(self)
        intro = QLabel("Nos CORTES, os trechos em X andam mais devagar que os em Y (o feixe da S30 corta melhor em Y). "
                       "Só a velocidade muda: potência, passadas, medidas e movimentos sem laser ficam iguais; nada é "
                       "gravado na máquina. Diagonais e curvas recebem a compensação aos poucos.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        self.ativo = QCheckBox("Compensação LIGADA (vale para todos os projetos)")
        self.ativo.setStyleSheet("font-weight:bold")
        v.addWidget(self.ativo)
        f = QFormLayout()
        self.desconto, self.minimo = QDoubleSpinBox(), QDoubleSpinBox()
        for s, lo in ((self.desconto, 0), (self.minimo, gc.COMP_X_MINIMO_ABS)):
            s.setRange(lo, 10000)
            s.setDecimals(0)
            s.setSuffix(" mm/min")
        f.addRow("Descontar no eixo X:", self.desconto)
        f.addRow("Velocidade mínima em X:", self.minimo)
        v.addLayout(f)
        self.exemplos = QLabel()
        self.exemplos.setWordWrap(True)
        v.addWidget(self.exemplos)
        g = QGroupBox("Teste SEM × COM (quadrado e linhas H/V lado a lado)")
        tf = QFormLayout(g)
        self.t_vel, self.t_pot, self.t_pas = QDoubleSpinBox(), QDoubleSpinBox(), QSpinBox()
        self.t_vel.setRange(10, 20000)
        self.t_vel.setDecimals(0)
        self.t_vel.setSuffix(" mm/min")
        self.t_pot.setRange(1, 100)
        self.t_pot.setSuffix(" %")
        self.t_pas.setRange(1, 20)
        tf.addRow("Velocidade programada:", self.t_vel)
        tf.addRow("Potência:", self.t_pot)
        tf.addRow("Passadas:", self.t_pas)
        v.addWidget(g)
        bts = QHBoxLayout()
        restaurar = QPushButton("Restaurar padrão (250 / mín. 150)")
        restaurar.clicked.connect(self.restaurar)
        teste = QPushButton("Gerar teste SEM × COM…")
        teste.clicked.connect(self.teste)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.close)
        for b in (restaurar, teste, fechar):
            bts.addWidget(b)
        v.addLayout(bts)
        self._mostrar()
        self.ativo.toggled.connect(self.salvar)
        for w in (self.desconto, self.minimo, self.t_vel, self.t_pot):
            w.valueChanged.connect(self.salvar)
        self.t_pas.valueChanged.connect(self.salvar)

    def _mostrar(self):
        d = self.d
        for w, val in ((self.ativo, d["ativo"]), (self.desconto, d["desconto"]), (self.minimo, d["minimo"]),
                       (self.t_vel, d["teste"]["velocidade"]), (self.t_pot, d["teste"]["potencia"]),
                       (self.t_pas, d["teste"]["passadas"])):
            w.blockSignals(True)
            w.setChecked(bool(val)) if isinstance(w, QCheckBox) else w.setValue(val)
            w.blockSignals(False)
        self._exemplos()

    def _exemplos(self):
        de, mi = self.desconto.value(), self.minimo.value()
        if not self.ativo.isChecked() or de <= 0:
            self.exemplos.setText("Desligada: o G-code sai igual ao programado, nos dois eixos.")
            return
        ex = []
        for vel in (300, 800, 1000, 1500):
            vx = gc.velocidade_compensada(vel, 1.0, de, mi)
            vd = gc.velocidade_compensada(vel, 0.5, de, mi)
            ex.append(f"{vel} → X {vx:g} · diagonal {vd:g} · Y {vel}")
        txt = "Exemplos (mm/min): " + " | ".join(ex)
        if de >= 0.5 * 800:
            txt += "\n⚠ Desconto grande: confira alinhamento do módulo/lente e correias antes — a compensação não deve " \
                   "esconder problema mecânico ou óptico."
        self.exemplos.setText(txt)

    def salvar(self, *_):
        self.d = {"ativo": self.ativo.isChecked(), "desconto": self.desconto.value(), "minimo": self.minimo.value(),
                  "teste": {"velocidade": self.t_vel.value(), "potencia": self.t_pot.value(),
                            "passadas": self.t_pas.value()}}
        gravar(self.jp.settings, self.d)
        self.jp.calibracao_xy_estado(aplicar(self.jp.settings))
        self._exemplos()

    def restaurar(self):
        self.d = json.loads(json.dumps(PADRAO))
        self._mostrar()
        self.salvar()

    # nomes antigos (testes/atalhos)
    def ativar(self):
        self.ativo.setChecked(True)

    def desativar(self):
        self.ativo.setChecked(False)

    def teste(self):
        try:
            texto = gcode_teste(self.d)
        except gc.GcodeInvalido as e:
            QMessageBox.warning(self, "Compensação do eixo X", str(e))
            return None
        return self.jp.saida_de_teste(texto, "teste_compensacao_x.gcode")
