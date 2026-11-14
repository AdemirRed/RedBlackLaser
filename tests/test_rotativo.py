"""Rotativo (rolo/mandril): conversão de Y no G-code."""
import math
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import rotativo as rt  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def ys_corte(texto):
    ys, laser = [], False
    for ln in texto.splitlines():
        if ln.startswith("G1") and "Y" in ln:
            ys.append(float(re.search(r"Y(-?[\d.]+)", ln).group(1)))
    return ys


class RotativoTest(unittest.TestCase):
    def test_fator(self):
        rolo = rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=100, diametro_rolo_mm=20, diametro_objeto_mm=80)
        self.assertAlmostEqual(rolo.fator, 100 / (math.pi * 20))             # rolo: diâmetro da peça não entra
        mand = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=100, diametro_objeto_mm=80)
        self.assertAlmostEqual(mand.fator, 100 / (math.pi * 80))
        self.assertTrue(rt.erros(rt.Rotativo(tipo="x")))
        self.assertEqual(rt.de_dict(rt.para_dict(rolo)), rolo)

    def test_gcode_escala_y_a_partir_do_comeco(self):
        snap = (fm.rect_path(QRectF(10, 300, 20, 50)), QTransform(), "x", "C01", "#fff", None)  # y máq. 50..100
        c = [cm.nova("C01")]
        p = pc.gerar([snap], c)
        normal = ys_corte(gc.gerar(p, c))
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / math.pi / 2)  # ×2
        texto = gc.gerar(p, c, rotativo=r)
        rot = ys_corte(texto)
        self.assertAlmostEqual(min(rot), min(normal), 3)                     # começo fica onde está
        self.assertAlmostEqual(max(rot) - min(rot), (max(normal) - min(normal)) * 2, 3)
        self.assertIn("ROTATIVO (mandril)", texto)
        self.assertNotIn("ROTATIVO", gc.gerar(p, c, rotativo=rt.Rotativo()))  # desligado: sem efeito

    def test_janela_lembra_e_exporta(self):
        tmp = tempfile.TemporaryDirectory()
        st = QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat)
        w = MainWindow(st)
        w.ask_save = lambda: "discard"
        w.show_info = lambda *a: None
        w.new_document()
        self.assertFalse(w.rotativo_label.isVisible() and w.rotativo_label.isVisibleTo(w))
        self.assertTrue(w.definir_rotativo(rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=200)))
        self.assertTrue(w.rotativo_label.isVisibleTo(w))
        w.create_shape(fm.rect_path(QRectF(10, 300, 20, 50)), "rect")
        saida = os.path.join(tmp.name, "r.gcode")
        self.assertTrue(w.export_gcode_to(saida))
        with open(saida, encoding="utf-8") as f:
            self.assertIn("ROTATIVO (rolo)", f.read())
        w.close()
        w2 = MainWindow(st)
        self.assertTrue(w2.rotativo.ativo)
        w2.ask_save = lambda: "discard"
        w2.close()
        tmp.cleanup()



class EixoXTest(unittest.TestCase):
    def test_motor_no_x_troca_os_eixos(self):
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / (2 * math.pi),
                         eixo="X")
        self.assertEqual(r.fator, 2.0)
        self.assertEqual(rt.de_dict(rt.para_dict(r)).eixo, "X")
        with self.assertRaises(ValueError):
            rt.de_dict({"eixo": "Z"})

class EnquadrarRotativoTest(unittest.TestCase):
    def test_caixa_do_enquadrar_igual_ao_gcode(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        from redblack.ui.main_window import MainWindow
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(20, 50, 30, 10)), "rect")
        plano = w.caixa_do_trabalho()
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / (2 * math.pi))
        w.definir_rotativo(r)
        caixa = w.caixa_do_trabalho()
        self.assertAlmostEqual(caixa[3] - caixa[1], (plano[3] - plano[1]) * 2, places=6)  # volta ×2
        self.assertAlmostEqual(caixa[2] - caixa[0], plano[2] - plano[0], places=6)
        w.definir_rotativo(rt.Rotativo(**{**rt.para_dict(r), "eixo": "X"}))
        x = w.caixa_do_trabalho()
        self.assertAlmostEqual(x[2] - x[0], (plano[3] - plano[1]) * 2, places=6)  # motor no X: a volta vai no X
        w.definir_rotativo(rt.Rotativo())
        w.close()


if __name__ == "__main__":
    unittest.main()
