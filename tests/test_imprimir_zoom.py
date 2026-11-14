"""Imprimir em escala 1:1 (para PDF no teste) e ajustar o zoom à seleção."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtPrintSupport import QPrinter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class ImprimirZoomTest(unittest.TestCase):
    def test_pdf_e_zoom(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.resize(1200, 800)
        w.show()
        app.processEvents()
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(10, 10, 50, 30)), "rect")
        pdf = os.path.join(tmp.name, "a.pdf")
        pr = QPrinter(QPrinter.HighResolution)
        pr.setOutputFormat(QPrinter.PdfFormat)
        pr.setOutputFileName(pdf)
        self.assertTrue(w.imprimir(pr))
        self.assertGreater(os.path.getsize(pdf), 500)
        w.ask_impressao = lambda printer: None                              # cancelado: nada acontece
        self.assertFalse(w.imprimir())
        v = w.canvas.view
        antes = v.scale_px_mm
        w.actions_by_key["zoom_sel"].trigger()
        self.assertGreater(v.scale_px_mm, antes)                              # aproximou na peça
        self.assertTrue(v.mapToScene(v.viewport().rect()).boundingRect().contains(QRectF(10, 10, 50, 30)))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
