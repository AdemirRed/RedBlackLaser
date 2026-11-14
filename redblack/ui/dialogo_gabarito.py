"""Diálogo do gabarito na mesa: grade de células, posição e gabaritos salvos para reutilizar."""
import json

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)

from .. import geometria as g
from .. import gabarito as gbm

CHAVE = "gabaritos"  # QSettings: {nome: campos}


def salvos(settings) -> dict:
    """Gabaritos salvos válidos (entradas corrompidas são ignoradas)."""
    try:
        bruto = json.loads(settings.value(CHAVE, "{}") or "{}")
    except (TypeError, ValueError):
        return {}
    out = {}
    for nome, d in (bruto.items() if isinstance(bruto, dict) else ()):
        try:
            out[str(nome)] = gbm.de_dict(d)
        except ValueError:
            pass
    return out


def gravar_salvos(settings, d: dict):
    settings.setValue(CHAVE, json.dumps({n: gbm.para_dict(g) for n, g in d.items()}, ensure_ascii=False))


class GabaritoDialog(QDialog):
    def __init__(self, parent, inicial: gbm.Gabarito, settings, tamanho_sel=None):
        super().__init__(parent)
        self.setWindowTitle("Gabarito na mesa")
        self.settings = settings
        self.tamanho_sel = tamanho_sel  # (largura, altura) da seleção, para "Célula do tamanho da seleção"
        v = QVBoxLayout(self)
        topo = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setAccessibleName("Gabaritos salvos")
        self.combo.activated.connect(self._carregar_salvo)
        topo.addWidget(QLabel("Salvos:"))
        topo.addWidget(self.combo, 1)
        self.btn_salvar = QPushButton("Salvar como…")
        self.btn_salvar.clicked.connect(self._salvar)
        self.btn_excluir = QPushButton("Excluir")
        self.btn_excluir.clicked.connect(self._excluir)
        topo.addWidget(self.btn_salvar)
        topo.addWidget(self.btn_excluir)
        v.addLayout(topo)

        form = QFormLayout()
        self.campos = {}
        for nome, rotulo, lo, hi in (("colunas", "Colunas", 1, gbm.MAX_CELULAS_LADO),
                                     ("linhas", "Linhas", 1, gbm.MAX_CELULAS_LADO)):
            sb = QSpinBox()
            sb.setRange(lo, hi)
            self.campos[nome] = sb
            form.addRow(rotulo, sb)
        for nome, rotulo in (("largura_mm", "Largura da célula"), ("altura_mm", "Altura da célula"),
                             ("espaco_x_mm", "Vão entre colunas"), ("espaco_y_mm", "Vão entre linhas"),
                             ("x", "X do canto superior esquerdo"), ("y", "Y do canto superior esquerdo")):
            sb = QDoubleSpinBox()
            sb.setDecimals(2)
            sb.setRange(0, 10000)
            sb.setSuffix(" mm")
            self.campos[nome] = sb
            form.addRow(rotulo, sb)
        self.giro = QDoubleSpinBox()
        self.giro.setDecimals(1)
        self.giro.setRange(-360, 360)
        self.giro.setSingleStep(90)
        self.giro.setSuffix(" °")
        self.giro.setToolTip("Gira cada peça dentro da sua célula (positivo = horário). Setas: passos de 90°")
        self.campos["giro"] = self.giro
        form.addRow("Girar peças na célula", self.giro)
        v.addLayout(form)
        acoes = QHBoxLayout()
        self.btn_sel = QPushButton("Célula do tamanho da seleção")
        self.btn_sel.setEnabled(tamanho_sel is not None)
        self.btn_sel.setToolTip("Usa a largura e a altura do desenho selecionado como célula")
        self.btn_sel.clicked.connect(self._do_tamanho_sel)
        self.btn_centro = QPushButton("Centralizar na mesa")
        self.btn_centro.clicked.connect(self._centralizar)
        acoes.addWidget(self.btn_sel)
        acoes.addWidget(self.btn_centro)
        v.addLayout(acoes)
        self.info = QLabel()
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        self.botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        v.addWidget(self.botoes)
        for sb in self.campos.values():
            sb.valueChanged.connect(self._atualizar)
        self._mostrar(inicial)
        self._montar_combo()

    # Campos X/Y em coordenadas de exibição (origem inferior esquerda), como no resto do programa.
    def _mostrar(self, gb):
        c = self.campos
        for nome in ("colunas", "linhas", "largura_mm", "altura_mm", "espaco_x_mm", "espaco_y_mm"):
            c[nome].setValue(getattr(gb, nome))
        c["x"].setValue(gb.x_mm)
        c["y"].setValue(g.BED_H - gb.y_mm)
        c["giro"].setValue(gb.giro_graus)
        self._atualizar()

    def gabarito(self) -> gbm.Gabarito:
        c = self.campos
        return gbm.Gabarito(c["colunas"].value(), c["linhas"].value(), c["largura_mm"].value(),
                            c["altura_mm"].value(), c["espaco_x_mm"].value(), c["espaco_y_mm"].value(),
                            c["x"].value(), g.BED_H - c["y"].value(), c["giro"].value())

    def _atualizar(self, *_):
        gb = self.gabarito()
        x0, y0, x1, y1 = gb.limites()
        e = gbm.erros(gb, g.BED_W, g.BED_H)
        txt = f"{gb.total} peça(s) por mesa; grade de {x1 - x0:.1f} × {y1 - y0:.1f} mm.".replace(".", ",")
        if self.tamanho_sel:
            w, h = gbm.caixa_girada(*self.tamanho_sel, gb.giro_graus)
            if w > gb.largura_mm + 1e-6 or h > gb.altura_mm + 1e-6:
                txt += f"\nAtenção: a seleção ({w:.1f} × {h:.1f} mm) não cabe na célula.".replace(".", ",")
        if e:
            txt += "\n" + "; ".join(e).capitalize() + "."
        self.info.setText(txt)
        self.botoes.button(QDialogButtonBox.Ok).setEnabled(not e)

    def _do_tamanho_sel(self):
        w, h = gbm.caixa_girada(*self.tamanho_sel, self.giro.value())
        self.campos["largura_mm"].setValue(w)
        self.campos["altura_mm"].setValue(h)

    def _centralizar(self):
        gb = self.gabarito()
        x0, y0, x1, y1 = gb.limites()
        self.campos["x"].setValue(max(0.0, (g.BED_W - (x1 - x0)) / 2))
        self.campos["y"].setValue(g.BED_H - max(0.0, (g.BED_H - (y1 - y0)) / 2))

    # ---------- salvos ----------
    def _montar_combo(self):
        self.combo.clear()
        nomes = sorted(salvos(self.settings), key=str.casefold)
        self.combo.addItems(nomes)
        self.combo.setEnabled(bool(nomes))
        self.btn_excluir.setEnabled(bool(nomes))

    def _carregar_salvo(self, _=None):
        gb = salvos(self.settings).get(self.combo.currentText())
        if gb:
            self._mostrar(gb)

    def pedir_nome(self) -> str:
        """Substituível nos testes."""
        nome, ok = QInputDialog.getText(self, "Salvar gabarito", "Nome do gabarito:")
        return nome.strip() if ok else ""

    def _salvar(self):
        nome = self.pedir_nome()
        if not nome:
            return
        d = salvos(self.settings)
        d[nome[:60]] = self.gabarito()
        gravar_salvos(self.settings, d)
        self._montar_combo()
        self.combo.setCurrentText(nome[:60])

    def _excluir(self):
        d = salvos(self.settings)
        d.pop(self.combo.currentText(), None)
        gravar_salvos(self.settings, d)
        self._montar_combo()
