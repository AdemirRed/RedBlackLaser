"""Verificações da Etapa 1. Executar: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton  # noqa: E402

from redblack.ui import theme  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
theme.apply(app)


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        w = MainWindow(self.settings)
        w.ask_save = lambda: "discard"  # sem diálogo modal nos testes
        w.resize(1280, 800)
        w.show()
        app.processEvents()
        return w

    def test_paineis_existem(self):
        w = self.make()
        self.assertEqual([d.windowTitle() for d in w.docks],
                         ["Camadas", "Máquina", "Objetos", "Materiais", "Texto variável", "Prévia do percurso",
                          "Notas", "Histórico"])
        self.assertFalse(w.preview_dock.isVisible())  # a prévia só abre quando pedida
        w.close()

    def test_nada_de_maquina_habilitado(self):
        w = self.make()
        machine = w.docks[1].widget().widget()  # dock -> QScrollArea -> painel
        # Etapa 13 libera só conexão somente leitura; movimento, laser e execução seguem desabilitados.
        # (Desligar rotativo só muda uma configuração do programa, não mexe na máquina)
        leitura = {"Conectar", "Procurar portas", "Salvar relatório da máquina…", "Desligar rotativo"}
        for b in machine.findChildren(QPushButton) + machine.findChildren(QToolButton):
            if b.text() not in leitura:
                self.assertFalse(b.isEnabled(), b.text() or b.accessibleName())
        # Prévia, gerar G-code, matriz de testes e configuração do rotativo só calculam/gravam arquivo.
        acts = [a for a in w.laser_menu.actions()
                if not a.isSeparator() and a not in (w.act_preview, w.act_gcode, w.act_matriz, w.act_precisao, w.act_cal_xy, w.act_comp_x,
                                                       w.act_resultado,
                                                       w.act_rotativo, w.act_maquina)]
        self.assertTrue(acts and all(not a.isEnabled() for a in acts), [a.text() for a in acts if a.isEnabled()])
        self.assertNotIn("PySide6.QtSerialPort", sys.modules)
        w.close()

    def test_layout_persistido(self):
        w = self.make()
        # toggleViewAction reflete "painel aberto", independente de qual aba está à frente.
        opened = lambda win, i: win.docks[i].toggleViewAction().isChecked()  # noqa: E731
        self.assertTrue(opened(w, 3))
        w.docks[3].close()  # Materiais
        w.close()
        w2 = self.make()
        self.assertFalse(opened(w2, 3))
        self.assertTrue(opened(w2, 0))
        w2.reset_layout()
        self.assertTrue(opened(w2, 3))
        w2.close()

    def test_area_de_desenho_ajustada(self):
        from PySide6.QtCore import QPointF
        w = self.make()
        v = w.canvas.view
        self.assertIsNotNone(v.scene())
        vp = v.viewport().rect()
        a, b = v.mapFromScene(QPointF(0, 0)), v.mapFromScene(QPointF(400, 400))
        self.assertTrue(vp.contains(a) and vp.contains(b))
        # centralizada no eixo maior (tolerância de 3 px)
        self.assertLess(abs((a.x() + b.x()) / 2 - vp.center().x()), 3)
        self.assertLess(abs((a.y() + b.y()) / 2 - vp.center().y()), 3)
        w.close()

    def test_redimensionar(self):
        w = self.make()
        for size in ((1024, 640), (1920, 1080), (1280, 800)):
            w.resize(*size)
            app.processEvents()
            self.assertEqual((w.width(), w.height()), size)  # mínimo da janela não estoura
            c = w.centralWidget().geometry()
            self.assertGreater(c.width(), 200, size)
            self.assertGreater(c.height(), 200, size)
            for d in w.docks:
                if d.isVisible() and not d.isFloating():
                    self.assertFalse(c.intersects(d.geometry()), (size, d.windowTitle()))
        w.close()


if __name__ == "__main__":
    unittest.main()
