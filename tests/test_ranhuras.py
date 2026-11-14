"""Redimensionar slots: só os slots da largura pedida mudam, centrados; o resto do contorno fica igual."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import ranhuras as rn  # noqa: E402

app = QApplication.instance() or QApplication([])


def caminho(pts, fechar=True):
    p = QPainterPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if fechar:
        p.lineTo(*pts[0])
    return p


def pontos(p):
    return [(round(p.elementAt(i).x, 6), round(p.elementAt(i).y, 6)) for i in range(p.elementCount())]


# placa 100 × 30 com 3 slots de 3 mm (profundidade 10) na borda de cima, centros em x = 20, 50, 80
PENTE = [(0, 0), (18.5, 0), (18.5, 10), (21.5, 10), (21.5, 0), (48.5, 0), (48.5, 10), (51.5, 10), (51.5, 0),
         (78.5, 0), (78.5, 10), (81.5, 10), (81.5, 0), (100, 0), (100, 30), (0, 30)]


class RanhurasTest(unittest.TestCase):
    def test_pente_3_para_4_mm_centrado(self):
        novo, n = rn.redimensionar(caminho(PENTE), 3.0, 4.0)
        self.assertEqual(n, 3)
        p = pontos(novo)
        for cx in (20, 50, 80):  # paredes em cx ± 2
            self.assertIn((cx - 2, 0), p)
            self.assertIn((cx - 2, 10), p)
            self.assertIn((cx + 2, 10), p)
            self.assertIn((cx + 2, 0), p)
        self.assertIn((100, 30), p)  # resto igual
        self.assertEqual(p[0], p[-1])  # continua fechado
        self.assertEqual(len(p), len(PENTE) + 1)

    def test_outra_largura_nao_muda(self):
        orig = caminho(PENTE)
        novo, n = rn.redimensionar(orig, 5.0, 6.0)
        self.assertEqual(n, 0)
        self.assertEqual(pontos(novo), pontos(orig))

    def test_estreitar_e_tolerancia(self):
        quase = [(x + (0.03 if x == 21.5 else 0), y) for x, y in PENTE]  # slot medido 3,03
        novo, n = rn.redimensionar(caminho(quase), 3.0, 2.5, tol=0.05)
        self.assertEqual(n, 3)
        self.assertIn((18.75, 10), pontos(novo))
        self.assertEqual(rn.redimensionar(caminho(quase), 3.0, 2.5, tol=0.01)[1], 2)

    def test_slot_vertical(self):
        # slot na borda direita, abrindo para a direita
        pts = [(0, 0), (30, 0), (30, 10), (20, 10), (20, 13), (30, 13), (30, 30), (0, 30)]
        novo, n = rn.redimensionar(caminho(pts), 3.0, 5.0)
        self.assertEqual(n, 1)
        p = pontos(novo)
        self.assertIn((20, 9), p)
        self.assertIn((20, 14), p)

    def test_furo_retangular_e_curvas(self):
        q = QPainterPath()
        q.addRect(0, 0, 3, 20)  # furo de encaixe (mortise) de 3 × 20: a largura 3 vira 4, a altura fica
        q.moveTo(50, 50)
        q.cubicTo(60, 40, 70, 60, 80, 50)
        novo, n = rn.redimensionar(q, 3.0, 4.0)
        self.assertEqual(n, 1)
        self.assertEqual(pontos(novo)[:5], [(-0.5, 0), (3.5, 0), (3.5, 20), (-0.5, 20), (-0.5, 0)])
        self.assertEqual(novo.elementCount(), q.elementCount())
        self.assertEqual(pontos(novo)[-4:], pontos(q)[-4:])  # a curva não muda

    def test_invalidos(self):
        with self.assertRaises(ValueError):
            rn.redimensionar(caminho(PENTE), 3, 0)


class RanhurasJanelaTest(unittest.TestCase):
    def test_comando_troca_e_desfaz(self):
        import tempfile
        from PySide6.QtCore import QSettings
        from redblack import objetos as ob
        from redblack.ui.main_window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            pente = ob.Shape(caminho(PENTE), "pente", "C01", "#fff")
            w.canvas.scene.addItem(pente)
            w.canvas.scene.clearSelection()
            pente.setSelected(True)
            self.assertTrue(w.redimensionar_slots({"largura": 3.0, "nova": 4.0, "tol": 0.05}))
            novo = w._sel()[0]
            self.assertIn((18, 10), pontos(novo.sceneTransform().map(novo.path())))
            w.undo_stack.undo()
            volta = next(s for s in w.canvas.view.shapes() if s.name == "pente")
            self.assertIn((18.5, 10), pontos(volta.sceneTransform().map(volta.path())))  # desfazer volta a 3 mm
            w.canvas.scene.clearSelection()
            volta.setSelected(True)
            self.assertFalse(w.redimensionar_slots({"largura": 9.0, "nova": 4.0, "tol": 0.05}))  # nada achado
            w.close()


if __name__ == "__main__":
    unittest.main()
