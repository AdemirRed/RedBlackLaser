"""Gera capturas da interface para avaliação: python tools/capturar.py <pasta_saida>"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPoint, QPointF, QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack.ui import theme  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "."
app = QApplication(sys.argv[:1])
theme.apply(app)
tmp = tempfile.TemporaryDirectory()  # não altera o layout salvo do usuário
win = MainWindow(QSettings(os.path.join(tmp.name, "c.ini"), QSettings.IniFormat))
win.ask_save = lambda: "discard"  # capturas não salvam nada
view = win.canvas.view


def zoom_on(x_mm, y_mm, factor):
    # zoom ancorado no ponto da cena, como faria a roda do mouse sobre ele
    view.zoom_at(QPointF(view.mapFromScene(QPointF(x_mm, y_mm))), factor)


def measure():
    win.tools["measure"].setChecked(True)
    view._measure_start = QPointF(40, 40)
    view._set_measure(QPointF(100, 70))
    view._measure_start = None
    view.cursorMoved.emit((100.0, 330.0))


shots = [
    (lambda: win.resize(1600, 900), "interface_1600x900.png"),
    (lambda: win.resize(1024, 640), "interface_1024x640.png"),
    (lambda: (win.resize(1600, 900), view.fit(), zoom_on(70, 55, 4.0)), "zoom_4x_retangulo.png"),
    (lambda: zoom_on(40, 40, 12.0), "zoom_profundo_canto.png"),
    (lambda: (view.fit(), measure()), "medicao.png"),
    (lambda: (win.tools["select"].setChecked(True), select(0)), "selecao_retangulo.png"),
    (lambda: (win.select_all(), zoom_on(110, 80, 2.0)), "selecao_multipla.png"),
    (lambda: (view.fit(), select(1), win._rotate(30), win.objects_dock.raise_()), "elipse_girada_30.png"),
]


def select(i):
    view.scene().clearSelection()
    view.shapes()[i].setSelected(True)


def step():
    if not shots:
        win.close()
        app.quit()
        return
    action, name = shots.pop(0)
    action()
    QTimer.singleShot(600, lambda: (win.grab().save(os.path.join(out, name)), print(name), step()))


win.show()
step()
app.exec()
