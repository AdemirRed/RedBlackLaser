"""Operações de nós por teclas (D I M L C B)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import nos  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
Q = fm.rect_path(QRectF(0, 0, 10, 10))


def pontos(p):
    return [(round(p.elementAt(i).x, 6), round(p.elementAt(i).y, 6)) for i in range(p.elementCount())]


class NosTest(unittest.TestCase):
    def test_localizar(self):
        self.assertEqual(nos.localizar(Q, (10.1, 0), 0.5), ("no", 0, 1))
        alvo = nos.localizar(Q, (5, 0.2), 0.5)
        self.assertEqual(alvo[:3], ("seg", 0, 0))
        self.assertAlmostEqual(alvo[3], 0.5, 1)
        self.assertIsNone(nos.localizar(Q, (5, 5), 0.5))

    def test_excluir_inserir_meio(self):
        tri = nos.excluir_no(Q, 0, 1)                                         # some o canto (10, 0)
        self.assertEqual(pontos(tri), [(0, 0), (10, 10), (0, 10), (0, 0)])
        m = nos.inserir_no(Q, 0, 0, 0.5)
        self.assertEqual(pontos(m)[:3], [(0, 0), (5, 0), (10, 0)])
        self.assertTrue(nos.excluir_no(fm.polyline_path([QPointF(0, 0), QPointF(5, 0)]), 0, 0).isEmpty())

    def test_excluir_trecho_abre_e_divide(self):
        aberto = nos.excluir_seg(Q, 0, 0)                                     # tira o lado de cima
        self.assertEqual(pontos(aberto), [(10, 0), (10, 10), (0, 10), (0, 0)])
        linha = fm.polyline_path([QPointF(0, 0), QPointF(5, 0), QPointF(5, 5), QPointF(10, 5)])
        self.assertEqual(len(fm.subcaminhos(nos.excluir_seg(linha, 0, 1))), 2)

    def test_curva_reta_canto_e_quebrar(self):
        c = fm.ellipse_path(QRectF(0, 0, 10, 10))
        self.assertEqual(nos.em_reta(c, 0, 0).elementAt(1).type, QPainterPath.LineToElement)
        canto = nos.estrutura(nos.em_canto(c, 0, 1))[0]["segs"]
        self.assertEqual(canto[0][2], canto[0][3])                          # alça de entrada no próprio nó
        self.assertEqual(canto[1][1], canto[0][3])                          # alça de saída também
        linha = fm.polyline_path([QPointF(0, 0), QPointF(5, 0), QPointF(10, 0)])
        self.assertEqual(len(fm.subcaminhos(nos.quebrar(linha, 0, 1))), 2)
        meia = nos.inserir_no(c, 0, 0, 0.5)
        self.assertEqual(meia.elementCount(), c.elementCount() + 3)       # curva dividida em duas

    def test_pela_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(100, 100, 40, 40)), "rect")
        w.tools["node"].setChecked(True)
        self.assertTrue(w.operacao_no("M", QPointF(120, 100)))
        s = w.canvas.view.shapes()[0]
        self.assertEqual(len(fm.nodes(s.path())), 5)
        self.assertTrue(w.operacao_no("D", QPointF(120, 100)))
        self.assertEqual(len(fm.nodes(s.path())), 4)
        self.assertFalse(w.operacao_no("D", QPointF(300, 300)))             # nada sob o cursor
        w.undo_stack.undo()
        self.assertEqual(len(fm.nodes(w.canvas.view.shapes()[0].path())), 5)
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        ev = QKeyEvent(QKeyEvent.Type.ShortcutOverride, Qt.Key_M, Qt.NoModifier, "m")
        self.assertTrue(w.canvas.view.event(ev) and ev.isAccepted())       # M não abre o Medir em Editar nós
        w.close()
        tmp.cleanup()



class SuavizarTest(unittest.TestCase):
    def test_canto_vira_suave_com_alcas_alinhadas(self):
        p = QPainterPath()
        p.moveTo(0, 0)
        p.lineTo(10, 0)
        p.lineTo(10, 10)
        novo = nos.suavizar(p, 0, 1)
        e = nos.estrutura(novo)[0]["segs"]
        self.assertEqual([s[0] for s in e], ["C", "C"])
        no = e[0][3]
        a, b = e[0][2], e[1][1]                                   # alças dos dois lados do nó
        self.assertAlmostEqual((a[0] - no[0]) * (b[1] - no[1]) - (a[1] - no[1]) * (b[0] - no[0]), 0, 9)
        self.assertEqual(e[1][3], (10.0, 10.0))
        self.assertIs(nos.suavizar(p, 0, 0), p)                   # ponta de linha aberta não muda


if __name__ == "__main__":
    unittest.main()
