"""Traçar imagem (vetorizar)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import importar_imagem as im  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import tracar as tr  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def desenho():
    img = QImage(200, 100, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("black"))
    p.drawRect(10, 10, 80, 80)
    p.setBrush(QColor("white"))
    p.drawRect(30, 30, 40, 40)                                           # furo
    p.setBrush(QColor("black"))
    p.drawEllipse(110, 10, 80, 80)
    p.drawRect(195, 95, 1, 1)                                            # mancha de 1 px (ruído)
    p.end()
    return img


def caixas(path):
    return sorted(tuple(round(v, 1) for v in (b.left(), b.top(), b.width(), b.height()))
                  for b in (q.boundingRect() for q in path.toSubpathPolygons()))


class TracarTest(unittest.TestCase):
    def test_contornos_furo_e_ruido(self):
        c = caixas(tr.tracar(desenho(), 40, 20))
        self.assertEqual(len(c), 3)                                          # quadrado, furo, círculo (sem a mancha)
        self.assertIn((2.0, 2.0, 16.0, 16.0), c)
        self.assertIn((6.0, 6.0, 8.0, 8.0), c)
        self.assertEqual(tr.tracar(desenho(), 40, 20).fillRule(), Qt.OddEvenFill)
        self.assertEqual(len(caixas(tr.tracar(desenho(), 40, 20, suavizar_px=0.1, minimo_px=0))), 4)  # com a mancha

    def test_negativo_e_vazio(self):
        branco = QImage(50, 50, QImage.Format_RGB32)
        branco.fill(QColor("white"))
        self.assertTrue(tr.tracar(branco, 10, 10).isEmpty())
        self.assertFalse(tr.tracar(branco, 10, 10, negativo=True).isEmpty())

    def test_na_janela_acompanha_a_imagem(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        ba = QByteArray()
        b = QBuffer(ba)
        b.open(QIODevice.WriteOnly)
        desenho().save(b, "PNG")
        r = im.from_bytes(bytes(ba), "d.png")
        s = ob.ImageShape(r.imagem, 40, 20, "logo")
        ob.move_by([s], 100, 100)
        w.canvas.scene.addItem(s)
        s.setSelected(True)
        self.assertTrue(w.tracar_imagem({"limiar": 50.0, "suavizar": 1.0, "minimo": 4.0, "negativo": False}))
        tracado = next(x for x in w.canvas.view.shapes() if x.name == "Traçado de logo")
        b = ob.geom_rect(tracado)
        self.assertAlmostEqual(b.left(), 102, 1)                             # 100 + 2 mm
        self.assertEqual(len(w.canvas.view.shapes()), 2)                    # a imagem continua
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
