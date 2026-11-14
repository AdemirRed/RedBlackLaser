"""Compensação automática de kerf por camada."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap(path, layer="C01"):
    return (path, QTransform(), "x", layer, "#ffffff", None)


def caixas(perc):
    """Retângulo envolvente de cada trecho de corte."""
    out = []
    for t in perc.trechos:
        if t.tipo == "corte":
            xs, ys = [p[0] for p in t.pontos], [p[1] for p in t.pontos]
            out.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
    return out


class KerfTest(unittest.TestCase):
    def camada(self, k, modo="linha"):
        return [cm.Camada("C01", "c", modo, kerf_mm=k)]

    def test_peca_cresce_meio_kerf(self):
        for path, w in ((fm.rect_path(QRectF(10, 10, 20, 20)), 20), (fm.ellipse_path(QRectF(10, 10, 99.6, 99.6)), 99.6)):
            (x, y, bw, bh), = caixas(pc.gerar([snap(path)], self.camada(0.2)))
            self.assertAlmostEqual(bw, w + 0.2, 3)
            self.assertAlmostEqual(bh, w + 0.2, 3)
            self.assertAlmostEqual(x, 10 - 0.1, 3)

    def test_furo_diminui_meio_kerf(self):
        p = QPainterPath()
        p.setFillRule(Qt.OddEvenFill)
        p.addRect(QRectF(0, 0, 50, 50))
        p.addEllipse(QRectF(15, 15, 20, 20))                     # furo Ø20
        cx = sorted(caixas(pc.gerar([snap(p)], self.camada(0.2))), key=lambda c: c[2])
        self.assertAlmostEqual(cx[0][2], 19.8, 3)                # furo: Ø19,8 no percurso
        self.assertAlmostEqual(cx[1][2], 50.2, 3)                # borda: 50,2

    def test_sem_kerf_e_preenchimento_inalterados(self):
        r = fm.rect_path(QRectF(10, 10, 20, 20))
        self.assertAlmostEqual(caixas(pc.gerar([snap(r)], self.camada(0)))[0][2], 20)
        fill = pc.gerar([snap(r)], self.camada(0.5, "preenchimento"))
        self.assertAlmostEqual(max(c[0] + c[2] for c in caixas(fill)), 30, 6)  # preenchimento ignora kerf

    def test_linha_aberta_nao_muda(self):
        p = fm.polyline_path([QPointF(0, 0), QPointF(30, 0), QPointF(30, 10)])
        (x, y, w, h), = caixas(pc.gerar([snap(p)], self.camada(0.4)))
        self.assertEqual((x, y, w, h), (0, 0, 30, 10))

    def test_limites_e_projeto_antigo(self):
        with self.assertRaises(ValueError):
            cm.alterar(cm.nova("C01"), kerf_mm=3)
        d = pj.to_dict([], [cm.Camada("C01", "c", kerf_mm=0.15)])
        self.assertEqual(pj.layers_from_dict(d)[0].kerf_mm, 0.15)
        del d["camadas"][0]["kerf_mm"]                             # projeto v7
        self.assertEqual(pj.layers_from_dict(d)[0].kerf_mm, 0.0)
        d["camadas"][0]["kerf_mm"] = "0.2"
        with self.assertRaises(pj.ProjetoInvalido):
            pj.layers_from_dict(d)


class PainelTest(unittest.TestCase):
    def test_campo_no_painel_e_desfazer(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(10, 10, 20, 20)), "rect")
        w.layer_table.selectRow(0)
        f = w.layer_form["kerf_mm"]
        self.assertTrue(f.isEnabled())
        f.setValue(0.2)
        f.editingFinished.emit()
        self.assertEqual(w.layer("C01").kerf_mm, 0.2)
        w.undo_stack.undo()
        self.assertEqual(w.layer("C01").kerf_mm, 0.0)
        w.set_layer_field("C01", "modo", "preenchimento")
        self.assertFalse(f.isEnabled())
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
