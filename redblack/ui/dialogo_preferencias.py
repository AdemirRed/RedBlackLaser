"""Configurações do programa (preferências), guardadas no QSettings do usuário."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFontComboBox, QFormLayout, QPushButton,
    QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

# chave: (padrão, tipo) — fonte única dos valores padrão
PADROES = {
    "auto_salvar_min": (2, int),
    "auto_salvar_arquivo": (True, bool),
    "abrir_ultimo": (True, bool),
    "zoom_invertido": (False, bool),
    "passo_seta_mm": (1.0, float),
    "passo_seta_shift_mm": (10.0, float),
    "encaixe_px": (12, int),
    "encaixe_grade": (False, bool),
    "voltar_selecionar": (True, bool),
    "texto_fonte": ("Arial", str),
    "texto_altura_mm": (10.0, float),
    "otim_internas_primeiro": (True, bool),
    "otim_vizinho": (False, bool),
    "otim_remover_sobrepostas": (False, bool),
    "importar_centralizar": (False, bool),
    "importar_agrupar": (False, bool),
    "tema_mesa": ("cinza", str),
    "espessura_linha": (2.5, float),
    "dicas_animadas": (True, bool),
}


def ler(settings, chave):
    padrao, tipo = PADROES[chave]
    v = settings.value(chave, padrao, type=tipo)
    return padrao if v is None else v


class PreferenciasDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.settings = settings
        v = QVBoxLayout(self)
        abas = QTabWidget()
        v.addWidget(abas)
        self.w = {}

        def aba(titulo, linhas):
            pg = QWidget()
            f = QFormLayout(pg)
            for chave, rotulo, widget in linhas:
                self.w[chave] = widget
                if isinstance(widget, QCheckBox):
                    widget.setText(rotulo)
                    f.addRow(widget)
                else:
                    f.addRow(rotulo, widget)
            abas.addTab(pg, titulo)

        def num(lo, hi, casas, suf):
            s = QSpinBox() if casas == 0 else QDoubleSpinBox()
            if casas:
                s.setDecimals(casas)
            s.setRange(lo, hi)
            s.setSuffix(suf)
            return s

        aba("Editor", [
            ("auto_salvar_min", "Salvamento automático a cada (0 = desligado)", num(0, 120, 0, " min")),
            ("auto_salvar_arquivo", "Salvar automaticamente no próprio arquivo do projeto (o Desfazer continua)",
             QCheckBox()),
            ("abrir_ultimo", "Ao abrir o programa, continuar o último projeto", QCheckBox()),
            ("zoom_invertido", "Inverter a direção do zoom com a roda do mouse", QCheckBox()),
            ("passo_seta_mm", "Mover com as setas", num(0.01, 100, 2, " mm")),
            ("passo_seta_shift_mm", "Mover com Shift + setas", num(0.01, 500, 2, " mm")),
            ("encaixe_px", "Distância de encaixe", num(2, 60, 0, " px")),
            ("encaixe_grade", "Encaixar na grade quando não houver canto/centro perto", QCheckBox()),
            ("voltar_selecionar", "Voltar para Selecionar depois de desenhar uma forma", QCheckBox())])
        aba("Texto", [
            ("texto_fonte", "Fonte padrão", QFontComboBox()),
            ("texto_altura_mm", "Altura padrão (X maiúsculo)", num(0.1, 1000, 2, " mm"))])
        aba("Otimização de corte", [
            ("otim_internas_primeiro", "Cortar primeiro as formas internas (furos antes do contorno)", QCheckBox()),
            ("otim_vizinho", "Reduzir deslocamentos: próximo contorno mais perto (ignora a ordem da lista) e "
                             "melhor ponto de partida", QCheckBox()),
            ("otim_remover_sobrepostas", "Remover linhas sobrepostas (lados iguais de peças encostadas são "
                                         "cortados uma vez só)", QCheckBox())])
        temas = QComboBox()
        from .canvas import TEMAS
        for k, (rot, *_cores) in TEMAS.items():
            temas.addItem(rot, k)
        aba("Visual", [
            ("tema_mesa", "Fundo da área de desenho", temas),
            ("espessura_linha", "Espessura das linhas dos desenhos na tela", num(1, 6, 1, " px")),
            ("dicas_animadas", "Dicas animadas nas ferramentas (passe o mouse num botão da barra lateral)",
             QCheckBox())])
        aba("Importar", [
            ("importar_centralizar", "Centralizar na mesa o que for importado", QCheckBox()),
            ("importar_agrupar", "Agrupar os objetos de cada arquivo importado (SVG/DXF)", QCheckBox())])
        self.carregar()
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        repor = QPushButton("Repor padrões")
        b.addButton(repor, QDialogButtonBox.ResetRole)
        repor.clicked.connect(lambda: self.carregar(padrao=True))
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def carregar(self, padrao=False):
        for k, w in self.w.items():
            val = PADROES[k][0] if padrao else ler(self.settings, k)
            if isinstance(w, QCheckBox):
                w.setChecked(val)
            elif isinstance(w, QFontComboBox):
                w.setCurrentFont(QFont(val))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(val)))
            else:
                w.setValue(val)

    def valores(self) -> dict:
        out = {}
        for k, w in self.w.items():
            out[k] = (w.isChecked() if isinstance(w, QCheckBox) else w.currentFont().family()
                      if isinstance(w, QFontComboBox) else w.currentData() if isinstance(w, QComboBox)
                      else w.value())
        return out
