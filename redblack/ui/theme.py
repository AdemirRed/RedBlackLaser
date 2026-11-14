"""Tema escuro RedBlack: paleta Qt + folha de estilo com foco visível."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractSpinBox, QApplication

ACCENT = "#e0313b"
BG = "#1e2025"
PANEL = "#26292f"
FIELD = "#16181c"
TEXT = "#e4e6eb"
MUTED = "#9aa0aa"

STYLE = f"""
QWidget {{ font-size: 10pt; }}
QMainWindow::separator {{ background: #33363d; width: 5px; height: 5px; }}
QMainWindow::separator:hover {{ background: {ACCENT}; }}
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: #2e3138; padding: 5px 8px; border-left: 3px solid {ACCENT}; }}
QToolBar {{ background: {PANEL}; border: 0; spacing: 2px; padding: 2px; }}
QToolButton {{ padding: 3px; border: 1px solid transparent; border-radius: 3px; }}
QToolButton:hover {{ background: #353943; }}
QToolButton:checked {{ background: #4a2226; border-color: {ACCENT}; }}
QPushButton {{ background: #31353d; border: 1px solid #454a54; border-radius: 3px; padding: 4px 10px; }}
QPushButton:hover {{ background: #3a3f48; }}
QPushButton:disabled, QToolButton:disabled {{ color: {MUTED}; }}
QPushButton:disabled {{ background: #2a2d33; border-color: #363a42; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {FIELD}; border: 1px solid #3c4049; border-radius: 3px; padding: 2px 4px; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 18px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 16px;
    background: #2c3038; border-left: 1px solid #3c4049; border-bottom: 1px solid #3c4049; border-top-right-radius: 3px; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right;
    width: 16px; background: #2c3038; border-left: 1px solid #3c4049; border-bottom-right-radius: 3px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: #3a3f48; }}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{ background: {ACCENT}; }}
{{SETAS}}QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {MUTED}; background: #1b1d21; }}
*:focus {{ outline: none; }}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTableWidget:focus, QTreeWidget:focus, QListWidget:focus, QGraphicsView:focus,
QCheckBox:focus, QTabBar::tab:focus {{ border: 2px solid {ACCENT}; }}
QHeaderView::section {{ background: #2e3138; border: 0; border-right: 1px solid #3c4049; padding: 3px 6px; }}
QTableWidget, QTreeWidget, QListWidget {{ background: {FIELD}; gridline-color: #2f3239; border: 1px solid #33363d; }}
QTabBar::tab {{ background: #2a2d33; padding: 5px 10px; border: 1px solid #33363d; }}
QTabBar::tab:selected {{ background: #353943; border-bottom: 2px solid {ACCENT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QStatusBar {{ background: {PANEL}; }}
QLabel#demoBadge {{ background: #5a4a12; color: #ffe08a; padding: 1px 8px; border-radius: 3px; font-weight: bold; }}
QLabel#banner {{ background: #3a2a14; color: #ffd27a; padding: 6px; border-radius: 3px; }}
QLabel#machineState {{ color: {MUTED}; font-weight: bold; }}
"""


class RodaSoComFoco(QObject):
    """Roda do mouse em campo de número só muda o valor se o campo foi clicado (está com o cursor); passando por
    cima, a roda rola o painel/janela como se o campo não estivesse ali (nada muda sem querer)."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Wheel and isinstance(obj, QAbstractSpinBox):
            if obj.focusPolicy() != Qt.StrongFocus:
                obj.setFocusPolicy(Qt.StrongFocus)  # a roda não "pega" o foco sozinha
            if not obj.hasFocus():
                ev.ignore()
                pai = obj.parentWidget()
                if pai is not None:
                    QApplication.sendEvent(pai, ev)  # deixa rolar o painel de trás
                return True
        return False


_FILTRO = None


def instalar_roda(app: QApplication) -> None:
    global _FILTRO
    if _FILTRO is None:
        _FILTRO = RodaSoComFoco(app)
        app.installEventFilter(_FILTRO)


SETAS_QSS = """
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({cima}); width: 9px; height: 6px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({baixo}); width: 9px; height: 6px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
QDoubleSpinBox::up-arrow:off {{ image: url({cima_off}); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
QDoubleSpinBox::down-arrow:off {{ image: url({baixo_off}); }}
"""


def _setas() -> str:
    """Desenha as setinhas ▲▼ dos campos de número (PNG numa pasta temporária) e devolve o trecho de estilo."""
    import os
    import tempfile
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage, QPainter, QPolygonF
    pasta = os.path.join(tempfile.gettempdir(), "redblack_tema")
    os.makedirs(pasta, exist_ok=True)
    caminhos = {}
    for nome, para_cima, cor in (("cima", True, TEXT), ("baixo", False, TEXT), ("cima_off", True, "#555b66"),
                                 ("baixo_off", False, "#555b66")):
        img = QImage(36, 24, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(cor))
        pts = [(2, 22), (34, 22), (18, 2)] if para_cima else [(2, 2), (34, 2), (18, 22)]
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        p.end()
        arq = os.path.join(pasta, f"seta_{nome}.png")
        img.save(arq, "PNG")
        caminhos[nome] = arq.replace("\\", "/")
    return SETAS_QSS.format(**caminhos)


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in (
        (QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, FIELD),
        (QPalette.AlternateBase, PANEL), (QPalette.Text, TEXT), (QPalette.Button, "#31353d"),
        (QPalette.ButtonText, TEXT), (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#ffffff"),
        (QPalette.ToolTipBase, "#2e3138"), (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, MUTED),
    ):
        pal.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(MUTED))
    app.setPalette(pal)
    try:
        setas = _setas()
    except OSError:  # sem pasta temporária: fica sem as setinhas desenhadas (os botões continuam)
        setas = ""
    app.setStyleSheet(STYLE.replace("{SETAS}", setas))
    instalar_roda(app)
