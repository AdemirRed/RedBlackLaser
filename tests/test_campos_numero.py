"""Campos de número: setinhas visíveis no tema e roda do mouse só com o campo clicado (com foco)."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QVBoxLayout, QWidget  # noqa: E402

from redblack.ui import theme  # noqa: E402

app = QApplication.instance() or QApplication([])


class CamposNumeroTest(unittest.TestCase):
    def test_roda_so_com_foco_e_setinhas_no_tema(self):
        theme.instalar_roda(app)
        self.assertIn("up-arrow", theme._setas())
        self.assertIn("down-button", theme.STYLE)
        janela = QWidget()
        lay = QVBoxLayout(janela)
        campo, outro = QDoubleSpinBox(), QDoubleSpinBox()
        campo.setRange(0, 100)
        campo.setValue(10)
        lay.addWidget(campo)
        lay.addWidget(outro)
        janela.show()
        app.processEvents()

        def rolar():
            pos = QPointF(5, 5)
            ev = QWheelEvent(pos, QPointF(campo.mapToGlobal(QPoint(5, 5))), QPoint(), QPoint(0, 120), Qt.NoButton,
                             Qt.NoModifier, Qt.NoScrollPhase, False)
            app.sendEvent(campo, ev)
            app.processEvents()
        outro.setFocus()
        app.processEvents()
        rolar()
        self.assertEqual(campo.value(), 10)  # só passou o mouse: não muda
        self.assertFalse(campo.hasFocus())   # e não "pega" o foco
        campo.setFocus()
        app.processEvents()
        rolar()
        self.assertEqual(campo.value(), 11)  # clicado: a roda muda o valor
        janela.close()


if __name__ == "__main__":
    unittest.main()
